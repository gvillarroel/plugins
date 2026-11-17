"""Offline API contract and conflict tests; these do not contact Google Cloud."""

import copy
import json

import pytest

from knowledge_catalog.gcp import (
    API_ROOT,
    ASPECT_TYPE_ID,
    ENTRY_TYPE_ID,
    CatalogClient,
    CatalogError,
    PlanConflict,
    canonical_hash,
    metadata_template,
)


class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status_code = status

    def json(self):
        return copy.deepcopy(self.data)


class MemorySession:
    def __init__(self):
        self.resources = {}
        self.calls = []
        self.pages = {}

    def request(self, method, url, **kwargs):
        assert url.startswith(API_ROOT)
        assert kwargs["allow_redirects"] is False
        assert kwargs["timeout"] == 30
        path = url[len(API_ROOT) :]
        self.calls.append((method, path, copy.deepcopy(kwargs)))
        if method == "GET":
            page = self.pages.get((path, kwargs["params"].get("pageToken", "")))
            if page is not None:
                return Response(page)
            return (
                Response(self.resources[path])
                if path in self.resources
                else Response({"error": {"message": "Not found"}}, 404)
            )
        if path.endswith(":searchEntries"):
            return Response({"results": [], "totalSize": 0})
        if method == "POST":
            key = next(key for key in kwargs["params"] if key.endswith("Id"))
            target = path + "/" + kwargs["params"][key]
            if target in self.resources:
                return Response({"error": {"message": "Already exists"}}, 409)
            resource = dict(copy.deepcopy(kwargs["json"]), name=target, updateTime="2026-10-24T12:00:00Z")
            self.resources[target] = resource
            if key != "entryId":
                return Response(
                    {
                        "name": "projects/synthetic-demo/locations/global/operations/bootstrap",
                        "done": True,
                        "response": resource,
                    }
                )
            return Response(resource)
        if method == "PATCH":
            assert kwargs["params"]["updateMask"] == "aspects"
            assert kwargs["params"]["deleteMissingAspects"] == "false"
            assert kwargs["params"]["allowMissing"] == "false"
            resource = self.resources[path]
            resource.setdefault("aspects", {}).update(copy.deepcopy(kwargs["json"]["aspects"]))
            resource["updateTime"] = "2026-10-24T13:00:00Z"
            return Response(resource)
        raise AssertionError(method)

    @property
    def writes(self):
        return [
            call
            for call in self.calls
            if call[0] in ("POST", "PATCH") and not call[1].endswith(":searchEntries")
        ]


@pytest.fixture
def metadata():
    return {
        "title": "Synthetic customer orders",
        "name": "orders",
        "description": "A synthetic retail work domain with customer and order metadata.",
        "domain": "retail",
        "owner": "Data platform",
        "license": "CC0",
        "synthetic": True,
        "row_count": 20,
        "source": {"system": "kaggle", "url": "https://www.kaggle.com/datasets/example/orders", "version": 1},
        "columns": [
            {
                "name": "order_id",
                "dtype": "int64",
                "description": "Order identifier",
                "semantic_type": "retail:OrderIdentifier",
                "nullable": False,
                "distinct": 20,
                "sensitivity": "internal",
            }
        ],
        "quality": {"score": 85, "warnings": ["License evidence requires review"]},
        "ontology": {"conforms": True, "terms": ["retail:Order"]},
        "provenance": {"analyzer": "local", "sha256": "abcdef"},
        "custom_field": {"anything": "must survive"},
    }


@pytest.fixture
def client():
    return CatalogClient("synthetic-demo", session=MemorySession())


def bootstrap_resources(client):
    for operation in client._dependencies("curated"):
        client.session.resources[operation["target"]] = dict(
            copy.deepcopy(operation["body"]),
            name=operation["target"],
            etag="original",
            updateTime="2026-10-24T10:00:00Z",
        )


def test_offline_preview_is_lossless_and_never_authenticates(metadata):
    client = CatalogClient("synthetic-demo")
    plan = client.build_plan(metadata)
    assert client._session is None
    assert plan["snapshot"]["mode"] == "unverified"
    assert plan["snapshot"]["exists"] is None
    assert len(plan["bootstrap"]) == 3
    assert plan["metadata_hash"] == canonical_hash(metadata)
    body = plan["operations"][0]["body"]
    aspect = body["aspects"][plan["managed_aspect_key"]]["data"]
    assert json.loads(aspect["metadata_json"]) == metadata
    assert json.loads(aspect["columns"][0]["details_json"])["distinct"] == 20
    assert aspect["columns"][0]["semantic_type"] == "retail:OrderIdentifier"
    assert aspect["row_count"] == 20
    assert aspect["synthetic"] is True
    assert "aspectType" not in body["aspects"][plan["managed_aspect_key"]]
    with pytest.raises(ValueError, match="offline preview"):
        client.apply_plan(plan)


def test_search_uses_empty_post_body_and_project_scope(client):
    client.search("type=dataset", "next-token", page_size=50)
    method, path, kwargs = client.session.calls[-1]
    assert method == "POST"
    assert path == "projects/synthetic-demo/locations/global:searchEntries"
    assert "json" not in kwargs
    assert kwargs["params"] == {
        "query": "type=dataset",
        "pageToken": "next-token",
        "pageSize": 50,
        "scope": "projects/synthetic-demo",
    }
    assert client.session.writes == []


def test_list_inventory_paginates_and_marks_location_scope(client):
    parent = client.parent
    client.session.pages = {
        (f"{parent}/entryGroups", ""): {
            "entryGroups": [{"name": f"{parent}/entryGroups/curated"}],
            "nextPageToken": "next",
        },
        (f"{parent}/entryGroups", "next"): {"entryGroups": []},
        (f"{parent}/entryTypes", ""): {"entryTypes": [{"name": "a type"}]},
        (f"{parent}/aspectTypes", ""): {"aspectTypes": [{"name": "an aspect"}]},
        (f"{parent}/entryGroups/curated/entries", ""): {"entries": [{"name": "an entry"}]},
    }
    result = client.inventory()
    assert len(result["entries"]) == 1
    assert len(result["entryTypes"]) == 1
    assert result["truncated"] == []
    assert result["scope"] == "configured location"
    assert client.session.writes == []


def test_inventory_reports_truncation(client):
    for collection in ("entryGroups", "entryTypes", "aspectTypes"):
        client.session.pages[(f"{client.parent}/{collection}", "")] = {
            collection: [],
            "nextPageToken": "next",
        }
    result = client.inventory(max_pages=1)
    assert len(result["truncated"]) == 3


def test_live_plan_reads_snapshot_and_publishes_dependencies_before_entry(client, metadata):
    plan = client.build_plan(metadata, remote_snapshot=True)
    assert plan["snapshot"]["exists"] is False
    assert client.session.writes == []
    result = client.apply_plan(plan)
    assert result["status"] == "published"
    assert len(result["operations_applied"]) == 4
    assert [call[1].rsplit("/", 1)[-1] for call in client.session.writes] == [
        "entryGroups",
        "aspectTypes",
        "entryTypes",
        "entries",
    ]
    assert client.session.writes[-1][2]["params"] == {"entryId": plan["entry_id"]}
    # A repeated approved plan is harmless after success.
    count = len(client.session.writes)
    assert client.apply_plan(plan)["status"] == "unchanged"
    assert len(client.session.writes) == count


def test_patch_updates_only_managed_aspect_and_preserves_source(client, metadata):
    bootstrap_resources(client)
    preview = client.build_plan(metadata)
    original = preview["operations"][0]["body"]
    original["aspects"]["other.global.aspect"] = {"data": {"owner": "another team"}}
    original["entrySource"]["updateTime"] = "2026-10-24T09:00:00Z"
    original["updateTime"] = "2026-10-24T10:00:00Z"
    client.session.resources[preview["target"]] = original
    updated_metadata = dict(metadata, description="Revised reviewed description")
    plan = client.build_plan(updated_metadata, remote_snapshot=True)
    operation = plan["operations"][0]
    assert operation["method"] == "PATCH"
    assert operation["params"]["aspectKeys"] == [f"synthetic-demo.global.{ASPECT_TYPE_ID}"]
    assert set(operation["body"]) == {"name", "aspects"}
    result = client.apply_plan(plan)
    assert len(client.session.writes) == 1
    assert result["entry"]["aspects"]["other.global.aspect"] == {"data": {"owner": "another team"}}
    assert result["entry"]["entrySource"]["updateTime"] == "2026-10-24T09:00:00Z"
    assert client.apply_plan(plan)["status"] == "unchanged"


def test_remote_entry_change_conflicts_before_any_write(client, metadata):
    plan = client.build_plan(metadata, remote_snapshot=True)
    client.session.resources[plan["target"]] = {
        "name": plan["target"],
        "updateTime": "2026-10-24T11:00:00Z",
        "entryType": "someone-elses-type",
    }
    with pytest.raises(PlanConflict, match="changed after review"):
        client.apply_plan(plan)
    assert not client.session.writes


def test_bootstrap_collision_is_never_overwritten(client, metadata):
    plan = client.build_plan(metadata, remote_snapshot=True)
    dependency = plan["bootstrap"][1]
    client.session.resources[dependency["target"]] = {
        "name": dependency["target"],
        "metadataTemplate": metadata_template(),
        "labels": {},
    }
    with pytest.raises(PlanConflict, match="compatible"):
        client.apply_plan(plan)
    assert not client.session.writes


def test_existing_dependency_change_conflicts_before_any_write(client, metadata):
    bootstrap_resources(client)
    plan = client.build_plan(metadata, remote_snapshot=True)
    client.session.resources[plan["bootstrap"][0]["target"]]["etag"] = "changed"
    with pytest.raises(PlanConflict, match="changed after review"):
        client.apply_plan(plan)
    assert not client.session.writes


def test_entry_type_mismatch_requires_new_entry(client, metadata):
    bootstrap_resources(client)
    preview = client.build_plan(metadata)
    client.session.resources[preview["target"]] = {
        "name": preview["target"],
        "entryType": f"{client.parent}/entryTypes/other",
    }
    plan = client.build_plan(metadata, remote_snapshot=True)
    with pytest.raises(PlanConflict, match="different entry type"):
        client.apply_plan(plan)
    assert not client.session.writes


@pytest.mark.parametrize("mutation", ["metadata", "target", "operation", "bootstrap", "snapshot", "project"])
def test_tampered_plan_is_rejected_before_any_write(client, metadata, mutation):
    plan = client.build_plan(metadata, remote_snapshot=True)
    if mutation == "metadata":
        plan["metadata"]["description"] = "tampered"
    elif mutation == "target":
        plan["target"] += "-other"
    elif mutation == "operation":
        plan["operations"][0]["method"] = "DELETE"
    elif mutation == "bootstrap":
        plan["bootstrap"][0]["path"] = "projects/other-project/locations/global/entryGroups"
    elif mutation == "snapshot":
        plan["snapshot"]["exists"] = True
    elif mutation == "project":
        plan["project"] = "other-project"
    with pytest.raises(ValueError):
        client.apply_plan(plan)
    assert not client.session.writes


def test_metadata_limit_refuses_lossy_export(client, metadata):
    metadata["description"] = "á" * 70_000
    with pytest.raises(ValueError, match="120 KB"):
        client.build_plan(metadata)
    assert not client.session.calls


def test_entry_id_stable_for_same_source(client, metadata):
    original = client.build_plan(metadata)
    updated = client.build_plan(dict(metadata, description="Changed semantics"))
    assert original["target"] == updated["target"]
    assert original["metadata_hash"] != updated["metadata_hash"]


def test_several_kaggle_files_have_distinct_targets(client, metadata):
    metadata["source"]["filename"] = "orders.csv"
    first = client.build_plan(metadata)
    metadata["source"]["filename"] = "customers.csv"
    second = client.build_plan(metadata)
    assert first["target"] != second["target"]


def test_actual_analyzer_schema_preserves_sampling_unknowns_and_terms(client):
    metadata = {
        "title": "Orders",
        "description": "A sampled dataset",
        "domain": "retail",
        "source": {
            "filename": "orders.csv",
            "sha256": "abc",
            "source_url": "https://www.kaggle.com/datasets/a/b",
            "source": "kaggle",
        },
        "profile": {"row_count": None, "sampled_rows": 5000, "sampled": True},
        "columns": [
            {
                "name": "customer_id",
                "data_type": "string",
                "semantic_type": "identifier",
                "pii_flags": ["identifier"],
                "statistics": {"null_count": 0},
            }
        ],
        "concepts": [{"concept": "https://example.org/retail/Customer", "confidence": 0.4}],
        "quality_findings": [{"code": "SAMPLED_SOURCE", "severity": "warning"}],
    }
    plan = client.build_plan(metadata)
    data = next(iter(plan["operations"][0]["body"]["aspects"].values()))["data"]
    assert data["source_system"] == "kaggle"
    assert data["source_uri"] == metadata["source"]["source_url"]
    assert "row_count" not in data
    assert data["row_count_known"] is False
    assert data["sampled_rows"] == 5000
    assert data["sampled"] is True
    assert "synthetic" not in data  # Unknown is not an assertion of non-synthetic.
    assert data["semantic_terms"] == ["https://example.org/retail/Customer"]
    assert data["columns"][0]["sensitivity"] == "identifier"
    assert json.loads(data["quality_json"])["findings"][0]["code"] == "SAMPLED_SOURCE"


@pytest.mark.parametrize("project", ["", "../bad", "https://bad.example", "x", "-project", "a" * 31])
def test_bad_project_rejected(project):
    with pytest.raises(ValueError):
        CatalogClient(project)


@pytest.mark.parametrize(
    "name",
    [
        "projects/other-project/locations/global/entryGroups/curated/entries/demo",
        "projects/synthetic-demo/locations/global/entryGroups/curated/entries/../demo",
        "projects/synthetic-demo/locations/global/entryGroups/curated/entries/a?secret",
        "projects/synthetic-demo/locations/global/entryGroups/curated/entries/a%2f",
    ],
)
def test_get_rejects_out_of_scope_or_unsafe_names(client, name):
    with pytest.raises(ValueError):
        client.get_entry(name)
    assert not client.session.calls


def test_get_canonical_numeric_alias_is_verified_through_configured_project(client):
    suffix = "/locations/global/entryGroups/curated/entries/orders"
    canonical = "projects/1234567890" + suffix
    client.session.resources["projects/synthetic-demo" + suffix] = {"name": canonical}
    assert client.get_entry(canonical)["name"] == canonical
    assert client.session.calls[-1][1] == "projects/synthetic-demo" + suffix


def test_get_wrong_numeric_alias_never_queries_another_project(client):
    suffix = "/locations/global/entryGroups/curated/entries/orders"
    client.session.resources["projects/synthetic-demo" + suffix] = {"name": "projects/1234567890" + suffix}
    with pytest.raises(ValueError, match="alias does not match"):
        client.get_entry("projects/9999999999" + suffix)
    assert client.session.calls[-1][1] == "projects/synthetic-demo" + suffix


def test_http_errors_do_not_turn_into_empty_inventory(client):
    class Denied:
        def request(self, *args, **kwargs):
            return Response({"error": {"message": "Permission denied"}}, 403)

    client._session = Denied()
    with pytest.raises(CatalogError, match="HTTP 403"):
        client.inventory()


def test_schema_has_unique_stable_indexes_and_no_output_only_fields(client, metadata):
    template = metadata_template()
    fields = template["recordFields"]
    assert len({field["index"] for field in fields}) == len(fields)
    plan = client.build_plan(metadata)
    body = plan["operations"][0]["body"]
    assert "createTime" not in body and "updateTime" not in body
    assert body["entryType"].endswith(f"/entryTypes/{ENTRY_TYPE_ID}")


def test_non_finite_metadata_rejected(client, metadata):
    metadata["quality"]["score"] = float("nan")
    with pytest.raises(ValueError):
        client.build_plan(metadata)


def test_long_running_operation_polls_canonical_numeric_project(client, monkeypatch):
    monkeypatch.setattr("knowledge_catalog.gcp.time.sleep", lambda _: None)
    name = f"{client.parent}/operations/create-type"
    client.session.resources[name] = {"name": name, "done": True, "response": {"name": "created"}}
    result = client._wait_operation({"name": "projects/1234567890/locations/global/operations/create-type"})
    assert result == {"name": "created"}
    assert client.session.calls[-1][1] == name


def test_long_running_operation_error_is_not_reported_as_success(client):
    with pytest.raises(CatalogError, match="operation failed"):
        client._wait_operation(
            {
                "name": f"{client.parent}/operations/failed",
                "done": True,
                "error": {"message": "Permission denied"},
            }
        )


def test_long_running_operation_outside_target_is_rejected(client):
    with pytest.raises(CatalogError, match="unexpected"):
        client._wait_operation({"name": "projects/other-project/locations/global/operations/wrong"})
    assert not client.session.calls


def test_entry_change_during_bootstrap_prevents_entry_write(client, metadata):
    class RacingSession(MemorySession):
        def request(self, method, url, **kwargs):
            # A concurrent publisher creates the target after our dependency
            # creates. The final read must detect it and never overwrite it.
            if method == "GET" and "/entries/" in url and len(self.writes) == 3:
                path = url[len(API_ROOT) :]
                self.resources[path] = {"name": path, "entryType": "concurrent-type", "updateTime": "new"}
            return super().request(method, url, **kwargs)

    client._session = RacingSession()
    plan = client.build_plan(metadata, remote_snapshot=True)
    with pytest.raises(PlanConflict, match="during bootstrap"):
        client.apply_plan(plan)
    assert len(client.session.writes) == 3
    assert all(not call[1].endswith("/entries") for call in client.session.writes)


def test_repeated_pagination_token_fails_explicitly(client):
    path = f"{client.parent}/entryGroups"
    client.session.pages[(path, "")] = {"nextPageToken": "repeat"}
    client.session.pages[(path, "repeat")] = {"nextPageToken": "repeat"}
    with pytest.raises(CatalogError, match="repeated page token"):
        client.inventory()


@pytest.mark.parametrize("query,size", [("", 100), ("ok", 0), ("ok", 1001), ("ok", True)])
def test_search_input_validation_avoids_remote_requests(client, query, size):
    with pytest.raises(ValueError):
        client.search(query, page_size=size)
    assert not client.session.calls
