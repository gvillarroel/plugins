"""Additional sequential GCP review regressions, R14 through R23; no cloud calls."""

import copy
import json

import pytest
from test_gcp import MemorySession, Response, bootstrap_resources

from knowledge_catalog.gcp import CatalogClient, CatalogError, PlanConflict, canonical_hash


@pytest.fixture
def client():
    return CatalogClient("synthetic-demo", session=MemorySession())


@pytest.fixture
def metadata():
    return {
        "title": "Reviewed orders",
        "description": "Retail order quantities and prices.",
        "domain": "retail",
        "owner": "Demo stewardship",
        "license": "MIT",
        "source": {"uri": "https://example.org/orders.csv", "sha256": "a" * 64},
        "profile": {"kind": "tabular", "row_count": 2, "sampled_rows": 2, "sampled": False},
        "columns": [{"name": "quantity", "data_type": "integer", "description": "Ordered units"}],
    }


def test_r14_inventory_preserves_unreachable_regions_and_endpoint_page_limits(client):
    for collection in ("entryGroups", "entryTypes", "aspectTypes"):
        client.session.pages[(f"{client.parent}/{collection}", "")] = {
            collection: [],
            "unreachableLocations": ["europe-west1"],
        }
    inventory = client.inventory()
    assert inventory["unreachableLocations"] == ["europe-west1"]
    assert inventory["truncated"] == []
    calls = len(client.session.calls)
    with pytest.raises(ValueError, match="between 1 and 100"):
        client.list_entries("curated", page_size=101)
    with pytest.raises(ValueError, match="max_pages"):
        client.inventory(max_pages=True)
    with pytest.raises(ValueError, match="page_token"):
        client.list_entry_groups(page_token={"not": "a token"})
    assert len(client.session.calls) == calls
    client.session.pages[(f"{client.parent}/entryGroups", "")] = {"nextPageToken": []}
    with pytest.raises(CatalogError, match="malformed list page"):
        client.list_entry_groups()


def test_r15_source_versions_and_column_aspects_survive_metadata_revisions(client, metadata):
    bootstrap_resources(client)
    original_plan = client.build_plan(metadata)
    original = copy.deepcopy(original_plan["operations"][0]["body"])
    original["entrySource"].update(
        {
            "createTime": "2030-01-01T00:00:00Z",
            "updateTime": "2030-10-24T00:00:00Z",
            "ancestors": [{"name": "upstream-orders", "type": "database"}],
        }
    )
    foreign_key = "other.global.annotations@Schema.quantity"
    original["aspects"][foreign_key] = {"data": {"unit": "items", "steward": "Upstream"}}
    client.session.resources[original_plan["target"]] = original
    reviewed = copy.deepcopy(metadata)
    reviewed["source"]["source_last_updated"] = "2026-10-24T12:00:00Z"
    reviewed["columns"][0]["description"] = "The number of units purchased in an order."
    updated = client.build_plan(reviewed, remote_snapshot=True)
    assert updated["entry_id"] == original_plan["entry_id"]
    assert set(updated["operations"][0]["body"]) == {"name", "aspects"}
    result = client.apply_plan(updated)
    assert result["entry"]["entrySource"] == original["entrySource"]
    assert result["entry"]["aspects"][foreign_key] == original["aspects"][foreign_key]
    data = result["entry"]["aspects"][updated["managed_aspect_key"]]["data"]
    assert "2026-10-24T12:00:00Z" in data["source_json"]
    assert data["columns"][0]["description"] == reviewed["columns"][0]["description"]


def test_r16_errors_do_not_echo_metadata_tokens_or_transport_details(client):
    from requests import Timeout

    secret = "PRIVATE-SOURCE-VALUE-and-signed-token"

    class FailingSession:
        def __init__(self, response=None):
            self.response = response
            self.calls = 0

        def request(self, *args, **kwargs):
            self.calls += 1
            if self.response:
                return self.response
            raise Timeout(secret)

    client._session = FailingSession(Response({"error": {"message": secret}}, 400))
    with pytest.raises(CatalogError, match="HTTP 400") as captured:
        client.list_entry_groups()
    assert secret not in str(captured.value)
    client._session = FailingSession()
    with pytest.raises(CatalogError, match="inspect remote state") as captured:
        client._request("POST", f"{client.parent}/entryGroups", body={"description": secret})
    assert secret not in str(captured.value)
    assert captured.value.__suppress_context__ is True
    assert client.session.calls == 1  # An uncertain mutation is not retried.

    class InvalidJSON(Response):
        def json(self):
            raise ValueError(secret)

    client._session = FailingSession(InvalidJSON({}))
    with pytest.raises(CatalogError, match="invalid JSON") as captured:
        client.list_entry_groups()
    assert secret not in str(captured.value)
    with pytest.raises(CatalogError, match="operation failed") as captured:
        client._wait_operation(
            {"name": f"{client.parent}/operations/failed", "done": True, "error": {"message": secret}}
        )
    assert secret not in str(captured.value)


def test_r17_malformed_bootstrap_success_cannot_advance_to_entry_publication(client, metadata):
    class MalformedBootstrap(MemorySession):
        def request(self, method, url, **kwargs):
            result = super().request(method, url, **kwargs)
            if method == "POST":
                return Response({})
            return result

    client._session = MalformedBootstrap()
    plan = client.build_plan(metadata, remote_snapshot=True)
    with pytest.raises(CatalogError, match="operation"):
        client.apply_plan(plan)
    assert len(client.session.writes) == 1
    assert not client.session.writes[0][1].endswith("/entries")
    name = f"{client.parent}/operations/contract"
    for malformed in (
        {"name": name, "done": "false"},
        {"name": name, "done": True},
        {"name": name, "done": False, "response": {}},
        {"name": name, "done": True, "response": {}, "error": {}},
    ):
        with pytest.raises(CatalogError):
            client._wait_operation(malformed)
    with pytest.raises(CatalogError, match="expected resource"):
        client._wait_operation({"name": name, "done": True, "response": {}}, plan["bootstrap"][0]["target"])


def test_r18_poll_timeout_uses_remaining_deadline_instead_of_another_full_request(client, monkeypatch):
    clock = [0.0]
    timeouts = []
    name = f"{client.parent}/operations/slow"
    monkeypatch.setattr("knowledge_catalog.gcp.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(
        "knowledge_catalog.gcp.time.sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    )

    class SlowOperation:
        def request(self, method, url, **kwargs):
            assert method == "GET"
            timeouts.append(kwargs["timeout"])
            clock[0] += kwargs["timeout"]
            return Response({"name": name, "done": False})

    client._session = SlowOperation()
    with pytest.raises(CatalogError, match="still pending"):
        client._wait_operation({"name": name})
    assert timeouts == [30, 29]
    assert clock[0] == 60


def test_r19_foreign_or_ill_typed_snapshots_fail_before_remote_requests(client, metadata):
    bootstrap_resources(client)
    preview = client.build_plan(metadata)
    client.session.resources[preview["target"]] = copy.deepcopy(preview["operations"][0]["body"])
    valid = client.build_plan(metadata, remote_snapshot=True)
    foreign = copy.deepcopy(valid)
    foreign["snapshot"]["resource"]["name"] = foreign["target"].replace("synthetic-demo", "other-project")
    foreign["snapshot"]["content_hash"] = canonical_hash(foreign["snapshot"]["resource"])
    boolean = copy.deepcopy(valid)
    boolean["snapshot"]["exists"] = 1
    version = copy.deepcopy(valid)
    version["snapshot"]["updateTime"] = 123
    version["snapshot"]["resource"]["updateTime"] = 123
    version["snapshot"]["content_hash"] = canonical_hash(version["snapshot"]["resource"])
    missing_state = copy.deepcopy(valid)
    del missing_state["bootstrap"][0]["needed"]
    for malformed in (foreign, boolean, version, missing_state):
        client.session.calls.clear()
        with pytest.raises(ValueError):
            client.apply_plan(malformed)
        assert client.session.calls == []
    absent = {
        "mode": "verified",
        "exists": False,
        "resource": None,
        "content_hash": None,
        "etag": None,
        "updateTime": "a version on a missing resource",
    }
    with pytest.raises(ValueError, match="Absent resource"):
        client._check_snapshot_integrity(absent, valid["target"])


def test_r20_required_aspect_project_must_match_its_verified_dependency(client, metadata):
    bootstrap_resources(client)
    dependencies = client._dependencies("curated")
    aspect = client.session.resources[dependencies[1]["target"]]
    entry_type = client.session.resources[dependencies[2]["target"]]
    entry_type["requiredAspects"] = [
        {"type": dependencies[1]["target"].replace("synthetic-demo", "foreign-project")}
    ]
    plan = client.build_plan(metadata, remote_snapshot=True)
    with pytest.raises(PlanConflict, match="compatible plugin-managed"):
        client.apply_plan(plan)
    assert client.session.writes == []
    # A numeric project is accepted only as the canonical name of the aspect
    # just read through our configured project's endpoint.
    aspect["name"] = dependencies[1]["target"].replace("synthetic-demo", "1234567890")
    entry_type["name"] = dependencies[2]["target"].replace("synthetic-demo", "1234567890")
    entry_type["requiredAspects"] = [{"type": aspect["name"]}]
    valid = client.build_plan(metadata, remote_snapshot=True)
    assert client.apply_plan(valid)["status"] == "published"
    assert len(client.session.writes) == 1
    assert all(
        "foreign-project" not in path and "1234567890" not in path for _, path, _ in client.session.calls
    )


def test_r21_uncertain_created_dependency_is_not_retried_and_is_reused_after_inspection(client, metadata):
    from requests import Timeout

    class CommitThenTimeout(MemorySession):
        timed_out = False

        def request(self, method, url, **kwargs):
            response = super().request(method, url, **kwargs)
            if method == "POST" and not self.timed_out:
                self.timed_out = True
                raise Timeout("response lost after creation")
            return response

    client._session = CommitThenTimeout()
    plan = client.build_plan(metadata, remote_snapshot=True)
    with pytest.raises(CatalogError, match="inspect remote state"):
        client.apply_plan(plan)
    assert len(client.session.writes) == 1
    assert plan["bootstrap"][0]["target"] in client.session.resources
    assert plan["target"] not in client.session.resources
    # The caller must reauthorize its retry. Internally the same exact plan can
    # reconcile the managed group found by its new preflight instead of POSTing
    # again and creating unrelated state.
    result = client.apply_plan(plan)
    assert result["status"] == "published"
    assert len(result["operations_applied"]) == 3
    assert len(client.session.writes) == 4
    group_posts = [call for call in client.session.writes if call[1].endswith("/entryGroups")]
    assert len(group_posts) == 1
    count = len(client.session.writes)
    assert client.apply_plan(plan)["status"] == "unchanged"
    assert len(client.session.writes) == count


def test_r22_full_group_numeric_alias_is_verified_before_scoped_listing(client):
    scoped_group = f"{client.parent}/entryGroups/curated"
    canonical = scoped_group.replace("synthetic-demo", "1234567890")
    client.session.resources[scoped_group] = {"name": canonical}
    client.session.pages[(scoped_group + "/entries", "next")] = {"entries": [{"name": "entry"}]}
    assert client.list_entries(canonical, page_token="next")["entries"] == [{"name": "entry"}]
    assert [call[1] for call in client.session.calls] == [scoped_group, scoped_group + "/entries"]
    assert client.session.calls[-1][2]["params"]["pageToken"] == "next"
    client.session.calls.clear()
    wrong = canonical.replace("1234567890", "9999999999")
    with pytest.raises(ValueError, match="alias does not match"):
        client.list_entries(wrong)
    assert [call[1] for call in client.session.calls] == [scoped_group]
    assert client.session.writes == []


def test_r23_unknown_document_count_and_utf8_boundary_never_fabricate_or_truncate(client, metadata):
    document = copy.deepcopy(metadata)
    document["profile"] = {"kind": "document", "sampled_characters": 120, "sampled": False}
    document["columns"] = []
    plan = client.build_plan(document)
    data = plan["operations"][0]["body"]["aspects"][plan["managed_aspect_key"]]["data"]
    assert "row_count" not in data
    assert data["row_count_known"] is False
    for invalid_count in (-1, True, 2**53):
        with pytest.raises(ValueError, match="row_count must"):
            client.build_plan(dict(document, row_count=invalid_count))

    # Find adjacent accepted/rejected lengths using multibyte Unicode. The
    # content itself must survive; EntrySource display truncation is irrelevant.
    low, high = 0, 40_000
    while high - low > 1:
        length = (low + high) // 2
        candidate = dict(document, description="é" * length)
        try:
            client.build_plan(candidate)
        except ValueError as error:
            assert "120 KB" in str(error)
            high = length
        else:
            low = length
    accepted = client.build_plan(dict(document, description="é" * low))
    payload = accepted["operations"][0]["body"]["aspects"][accepted["managed_aspect_key"]]["data"]
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(encoded) <= 120_000
    assert json.loads(payload["metadata_json"])["description"] == "é" * low
    with pytest.raises(ValueError, match="120 KB"):
        client.build_plan(dict(document, description="é" * high))
    assert client.session.calls == []


def test_r17_terminal_entry_confirmation_and_numeric_names_from_fresh_bootstrap(client, metadata):
    class EmptyEntryResponse(MemorySession):
        def request(self, method, url, **kwargs):
            result = super().request(method, url, **kwargs)
            return Response({}) if method == "POST" and url.endswith("/entries") else result

    client._session = EmptyEntryResponse()
    plan = client.build_plan(metadata, remote_snapshot=True)
    with pytest.raises(CatalogError, match="did not confirm the expected entry"):
        client.apply_plan(plan)
    assert len(client.session.writes) == 4
    assert plan["target"] in client.session.resources  # Applied, but unconfirmed.

    class CanonicalCreation(MemorySession):
        def request(self, method, url, **kwargs):
            result = super().request(method, url, **kwargs)
            if method != "POST":
                return result
            target_id = next(key for key in kwargs["params"] if key.endswith("Id"))
            path = url.split("/v1/", 1)[1] + "/" + kwargs["params"][target_id]
            resource = self.resources[path]
            resource["name"] = resource["name"].replace("synthetic-demo", "1234567890")
            if target_id == "entryId":
                resource["entryType"] = resource["entryType"].replace("synthetic-demo", "1234567890")
                resource["aspects"] = {
                    key.replace("synthetic-demo", "1234567890"): value
                    for key, value in resource["aspects"].items()
                }
                return Response(resource)
            if target_id == "entryTypeId":
                resource["requiredAspects"][0]["type"] = resource["requiredAspects"][0]["type"].replace(
                    "synthetic-demo", "1234567890"
                )
            return Response(
                {
                    "name": "projects/1234567890/locations/global/operations/created",
                    "done": True,
                    "response": resource,
                }
            )

    client._session = CanonicalCreation()
    canonical_plan = client.build_plan(metadata, remote_snapshot=True)
    assert client.apply_plan(canonical_plan)["status"] == "published"
    assert client.apply_plan(canonical_plan)["status"] == "unchanged"
