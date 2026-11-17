"""OpenLineage and Data Lineage contracts; every transport is offline."""

import copy
import json
import uuid
from urllib.parse import parse_qs, urlsplit

import pytest

from knowledge_catalog.gcp import CatalogClient, CatalogError, canonical_hash
from knowledge_catalog.lineage_gcp import (
    API_ROOT,
    EVENT_SCHEMA,
    LineageClient,
    build_lineage_plan,
    catalog_metadata,
    export_openlineage,
)


@pytest.fixture
def graph():
    return {
        "id": "retail-demo",
        "title": "Retail lineage",
        "domain": "retail",
        "synthetic": True,
        "clock_kind": "simulated",
        "generated_at": "2025-02-01T09:00:00Z",
        "datasets": [
            {
                "id": "orders",
                "name": "Raw orders",
                "columns": [{"name": "quantity", "data_type": "integer", "description": "Ordered units"}],
            },
            {"id": "prices", "name": "Product prices", "columns": [{"name": "price", "data_type": "number"}]},
            {
                "id": "sales",
                "name": "Enriched sales",
                "columns": [{"name": "revenue", "data_type": "number"}],
            },
        ],
        "processes": [
            {
                "id": "enrich",
                "name": "Calculate revenue",
                "inputs": ["orders", "prices"],
                "outputs": ["sales"],
                "transformation": "quantity * price",
            }
        ],
        "edges": [
            {"source": "orders", "target": "sales", "process_id": "enrich"},
            {"source": "prices", "target": "sales", "process_id": "enrich"},
        ],
        "column_lineage": [
            {
                "source_dataset": "orders",
                "source_column": "quantity",
                "target_dataset": "sales",
                "target_column": "revenue",
                "process_id": "enrich",
                "transformation": "quantity * price",
            },
            {
                "source_dataset": "prices",
                "source_column": "price",
                "target_dataset": "sales",
                "target_column": "revenue",
                "process_id": "enrich",
                "transformation": "quantity * price",
            },
        ],
        "runs": [
            {
                "id": "5bcae46a-d871-5363-bad7-91ca7140a733",
                "process_id": "enrich",
                "status": "COMPLETED",
                "started_at": "2025-02-01T09:00:00Z",
                "ended_at": "2025-02-01T09:01:00Z",
                "clock_kind": "simulated",
                "execution": "executed_locally",
            }
        ],
    }


class Response:
    def __init__(self, value, status=200):
        self.value, self.status_code = value, status

    def json(self):
        return copy.deepcopy(self.value)


class Session:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, **kwargs):
        assert url.startswith(API_ROOT)
        assert kwargs["timeout"] == 30 and kwargs["allow_redirects"] is False
        path = url[len(API_ROOT) :]
        token = kwargs.get("json", kwargs.get("params", {})).get("pageToken", "")
        self.calls.append((method, path, copy.deepcopy(kwargs)))
        return self.routes[(method, path, token)]


def test_export_preserves_column_schema_transformations_and_simulated_time(graph):
    original = copy.deepcopy(graph)
    bundle = export_openlineage(graph, "test-project", "us-central1")
    event = bundle["events"][0]
    assert event["eventType"] == "COMPLETE"
    assert event["eventTime"] == "2025-02-01T09:01:00Z"
    assert event["schemaURL"] == EVENT_SCHEMA
    assert event["run"]["runId"] == graph["runs"][0]["id"]
    assert event["run"]["facets"]["nominalTime"]["nominalStartTime"] == "2025-02-01T09:00:00Z"
    assert all(dataset["namespace"] == "custom" for dataset in event["inputs"] + event["outputs"])
    output = event["outputs"][0]
    assert output["facets"]["schema"]["fields"] == [{"name": "revenue", "type": "number"}]
    fields = output["facets"]["columnLineage"]["fields"]["revenue"]["inputFields"]
    assert {field["field"] for field in fields} == {"quantity", "price"}
    assert all(field["transformations"][0]["description"] == "quantity * price" for field in fields)
    assert bundle["graph_snapshot"] == original == graph
    assert bundle["graph_hash"] == canonical_hash(graph)
    assert any("not rendered" in warning for warning in bundle["warnings"])
    assert any("simulated clock" in warning for warning in bundle["warnings"])


def test_plan_is_deterministic_body_is_event_and_request_id_is_query(graph, monkeypatch):
    def no_adc(_):
        raise AssertionError("Offline export must not authenticate")

    monkeypatch.setattr(CatalogClient, "session", property(no_adc))
    first = build_lineage_plan(graph, "test-project", "us-central1")
    assert first == build_lineage_plan(graph, "test-project", "us-central1")
    assert first["mode"] == "export_only" and first["writes_executed"] is False
    operation = first["operations"][0]
    assert operation["method"] == "POST"
    parsed = urlsplit(operation["url"])
    assert parsed.netloc == "datalineage.googleapis.com"
    assert parsed.path == "/v1/projects/test-project/locations/us-central1:processOpenLineageRunEvent"
    assert parse_qs(parsed.query) == {"requestId": [operation["request_id"]]}
    assert str(uuid.UUID(operation["request_id"])) == operation["request_id"]
    assert "openLineage" not in operation["body"] and operation["body"]["eventType"] == "COMPLETE"


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "missing-dataset",
        "unknown-column",
        "missing-edge",
        "extra-edge",
        "failed-run",
        "no-runs",
        "no-time",
        "negative-duration",
        "nonfinite",
    ],
)
def test_invalid_graph_is_not_silently_repaired_or_exported(graph, mutation):
    if mutation == "duplicate":
        graph["datasets"].append(copy.deepcopy(graph["datasets"][0]))
    elif mutation == "missing-dataset":
        graph["processes"][0]["inputs"].append("missing")
    elif mutation == "unknown-column":
        graph["column_lineage"][0]["source_column"] = "secret_unknown"
    elif mutation == "missing-edge":
        graph["edges"].pop()
    elif mutation == "extra-edge":
        graph["edges"].append({"source": "prices", "target": "orders", "process_id": "enrich"})
    elif mutation == "failed-run":
        graph["runs"][0]["status"] = "FAILED"
    elif mutation == "no-runs":
        graph["runs"] = []
    elif mutation == "no-time":
        del graph["runs"][0]["ended_at"]
    elif mutation == "negative-duration":
        graph["runs"][0]["started_at"] = "2026-02-01T00:00:00Z"
    elif mutation == "nonfinite":
        graph["score"] = float("nan")
    with pytest.raises(ValueError):
        export_openlineage(graph, "test-project", "us-central1")


def test_non_uuid_source_run_id_is_mapped_stably_without_losing_original(graph):
    graph["runs"][0]["id"] = "local-run-42"
    first = export_openlineage(graph, "test-project", "us-central1")
    assert uuid.UUID(first["runs"][0]["run_id"]).version == 5
    assert first["runs"][0]["source_run_id"] == "local-run-42"
    assert first == export_openlineage(graph, "test-project", "us-central1")


def test_subsecond_negative_duration_cannot_pass_lexical_timestamp_comparison(graph):
    graph["runs"][0]["started_at"] = "2025-02-01T09:01:00.500Z"
    with pytest.raises(ValueError, match="end precedes"):
        export_openlineage(graph, "test-project", "us-central1")


def test_custom_facets_are_preserved_locally_without_claiming_gcp_retains_them(graph):
    facet = {
        "_producer": "urn:local:producer",
        "_schemaURL": "urn:local:schema:1",
        "evidence": "source assertion",
    }
    graph["runs"][0]["facets"] = {"myCompanyReview": facet}
    bundle = export_openlineage(graph, "test-project", "us-central1")
    assert bundle["events"][0]["run"]["facets"]["myCompanyReview"] == facet
    assert any("does not preserve every facet" in warning for warning in bundle["warnings"])
    graph["datasets"][0]["facets"] = {"schema": facet}
    with pytest.raises(ValueError, match="overriding"):
        export_openlineage(graph, "test-project", "us-central1")


def test_catalog_metadata_retains_one_graph_and_does_not_invent_owner_or_license(graph):
    metadata = catalog_metadata(graph)
    assert metadata["relationships"][0]["graph"] == graph
    assert metadata["relationships"][0]["graph_sha256"] == canonical_hash(graph)
    assert metadata["source"]["sha256"] == canonical_hash(graph)
    assert "owner" not in metadata and "license" not in metadata
    assert metadata["synthetic"] is True
    plan = CatalogClient("test-project", "us-central1").build_plan(metadata)
    data = plan["operations"][0]["body"]["aspects"][plan["managed_aspect_key"]]["data"]
    assert "row_count" not in data
    assert json.loads(data["metadata_json"])["relationships"][0]["graph"] == graph


def test_client_get_lists_and_post_search_are_read_only_and_do_not_echo_errors():
    parent = "projects/test-project/locations/us-central1"
    session = Session(
        {
            ("GET", parent + "/processes", "p2"): Response({"processes": []}),
            ("POST", parent + ":searchLinks", ""): Response({"links": []}),
        }
    )
    client = LineageClient("test-project", "us-central1", session)
    assert client.list_processes("p2")["processes"] == []
    assert "json" not in session.calls[0][2]
    result = client.search_links("custom:kc_synthetic.demo.orders")
    assert result["project_restricted"] is False
    assert session.calls[-1][2]["json"]["target"] == {"fullyQualifiedName": "custom:kc_synthetic.demo.orders"}
    client.search_links("custom:demo", direction="downstream")
    assert "source" in session.calls[-1][2]["json"] and "target" not in session.calls[-1][2]["json"]
    with pytest.raises(ValueError, match="reads only"):
        client._request("POST", parent + "/processes", body={})
    session.routes[("GET", parent + "/processes", "")] = Response(
        {"error": {"message": "PRIVATE-VALUES"}}, 403
    )
    with pytest.raises(CatalogError, match="HTTP 403") as captured:
        client.list_processes()
    assert "PRIVATE-VALUES" not in str(captured.value)


def test_inventory_page_size_stays_constant_and_global_limits_are_explicit():
    parent = "projects/test-project/locations/us-central1"
    processes = [{"name": parent + "/processes/first"}, {"name": parent + "/processes/second"}]
    session = Session(
        {
            ("GET", parent + "/processes", ""): Response({"processes": processes[:1], "nextPageToken": "p2"}),
            ("GET", parent + "/processes", "p2"): Response({"processes": processes[1:]}),
            ("GET", parent + "/processes/first/runs", ""): Response({"runs": []}),
            ("GET", parent + "/processes/second/runs", ""): Response({"runs": []}),
        }
    )
    client = LineageClient("test-project", "us-central1", session)
    result = client.inventory(max_processes=2)
    assert len(result["processes"]) == 2 and result["truncated"] == []
    assert [call[2]["params"]["pageSize"] for call in session.calls[:2]] == [2, 2]
    result = client.inventory(max_pages=1)
    assert result["truncated"][0]["nextPageToken"] == "p2"


def test_process_numeric_alias_is_verified_through_configured_project():
    parent = "projects/test-project/locations/us-central1"
    canonical = "projects/1234567890/locations/us-central1/processes/job"
    session = Session(
        {
            ("GET", parent + "/processes/job", ""): Response({"name": canonical}),
            ("GET", parent + "/processes/job/runs", ""): Response({"runs": []}),
        }
    )
    client = LineageClient("test-project", "us-central1", session)
    assert client.list_runs(canonical)["runs"] == []
    assert all(path.startswith(parent) for _, path, _ in session.calls)
    with pytest.raises(ValueError, match="alias"):
        client.list_runs(canonical.replace("1234567890", "9999999999"))


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "projects/other-project/locations/us-central1/processes/job",
        "projects/test-project/locations/europe-west1/processes/job",
    ],
)
def test_process_scope_and_paths_are_checked_before_network(name):
    session = Session({})
    client = LineageClient("test-project", "us-central1", session)
    with pytest.raises(ValueError):
        client.list_runs(name)
    assert session.calls == []


def test_inventory_detects_repeated_page_tokens():
    parent = "projects/test-project/locations/us-central1"
    session = Session(
        {
            ("GET", parent + "/processes", ""): Response({"nextPageToken": "repeat"}),
            ("GET", parent + "/processes", "repeat"): Response({"nextPageToken": "repeat"}),
        }
    )
    with pytest.raises(CatalogError, match="repeated page token"):
        LineageClient("test-project", "us-central1", session).inventory()


def test_real_demo_requires_correction_and_exports_all_four_executed_processes(tmp_path):
    from knowledge_catalog.lineage import generate_demo

    graph = generate_demo(tmp_path / "demo", seed=42)
    with pytest.raises(ValueError, match="contradicts"):
        export_openlineage(graph, "test-project", "us-central1")
    graph["edges"] = copy.deepcopy(graph["observed_dependencies"])
    bundle = export_openlineage(graph, "test-project", "us-central1")
    assert len(bundle["events"]) == 4
    assert len(bundle["datasets"]) == 8
    assert {run["process_id"] for run in bundle["runs"]} == {process["id"] for process in graph["processes"]}
    assert all(event["eventType"] == "COMPLETE" for event in bundle["events"])
    assert (
        CatalogClient("test-project", "us-central1").build_plan(catalog_metadata(graph))["snapshot"]["mode"]
        == "unverified"
    )


def test_private_transport_cannot_escape_scope_or_invoke_a_write_action():
    session = Session({})
    client = LineageClient("test-project", "us-central1", session)
    for path in (client.parent + "/processes/../../other", client.parent + "/processes?other=project"):
        with pytest.raises(ValueError):
            client._request("GET", path)
    with pytest.raises(ValueError):
        client._request("POST", client.parent + ":processOpenLineageRunEvent", body={})
    assert session.calls == []
