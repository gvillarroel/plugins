"""Faithful local OpenLineage exports and a read-only GCP Data Lineage client.

Exporting a plan never authenticates or sends its operations. Custom events sent
to GCP materialize table links, not a custom column-lineage console graph.
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

from .gcp import CatalogClient, CatalogError, canonical_hash

API_ROOT = "https://datalineage.googleapis.com/v1/"
PRODUCER = "urn:knowledge-catalog-curator:lineage-export:v1"
EVENT_SCHEMA = "https://openlineage.io/spec/1-0-5/OpenLineage.json#/$defs/RunEvent"
FACETS = "https://openlineage.io/spec/facets/"
MAX_EVENT_BYTES = 5_000_000
WARNINGS = [
    "GCP custom OpenLineage events materialize table-level links only; custom column lineage is not rendered in the Google Cloud console.",
    "GCP does not preserve every facet. Keep this local bundle and graph snapshot for schemas, column transformations, custom facets and execution evidence.",
    "These are terminal COMPLETE snapshots, not reconstructed START histories. GCP may map both run timestamps to eventTime and ignore nominalTime.",
    "GCP retains lineage for 30 days. Review simulated or historical event times before considering any external submission.",
    "Column mappings preserve declared field dependencies; filters, predicates and implicit dependencies are not exhaustively modeled or independently verified.",
]


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _text(value, label, maximum=4000):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError(f"{label} must be a nonempty string of at most {maximum} characters")
    return value


def _timestamp(value, label):
    _text(value, label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{label} must be an RFC3339 timestamp with a timezone") from None
    if parsed.tzinfo is None or "T" not in value:
        raise ValueError(f"{label} must include time and timezone")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _segment(value):
    return value if re.fullmatch(r"[A-Za-z0-9_-]+", value) else "`" + value.replace("`", "``") + "`"


def _facet(name, values):
    return {"_producer": PRODUCER, "_schemaURL": FACETS + name, **values}


def _extra_facets(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("facets must be an object")
    for facet in value.values():
        if not isinstance(facet, dict):
            raise ValueError("Each facet must be an object")
        for key in ("_producer", "_schemaURL"):
            uri = _text(facet.get(key), key)
            if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", uri) or any(c.isspace() for c in uri):
                raise ValueError(f"{key} must be an absolute URI")
    return copy.deepcopy(value)


def _index(records, label):
    if not isinstance(records, list) or len(records) > 1000:
        raise ValueError(f"{label} must be a list of at most 1000 objects")
    indexed = {}
    for item in records:
        if not isinstance(item, dict):
            raise ValueError(f"Each {label} item must be an object")
        identifier = _text(item.get("id"), f"{label}.id")
        if identifier in indexed:
            raise ValueError(f"Duplicate {label} ID")
        indexed[identifier] = item
    return indexed


def _model(graph):
    if not isinstance(graph, dict):
        raise ValueError("graph must be an object")
    if len(_json(graph).encode("utf-8")) > MAX_EVENT_BYTES:
        raise ValueError("Graph exceeds the 5 MB local export limit")
    graph = copy.deepcopy(graph)
    if "synthetic" in graph and not isinstance(graph["synthetic"], bool):
        raise ValueError("graph.synthetic must be a boolean")
    datasets = _index(graph.get("datasets"), "datasets")
    processes = _index(graph.get("processes"), "processes")
    if not datasets or not processes:
        raise ValueError("Export requires datasets and processes")
    columns = {}
    for identifier, dataset in datasets.items():
        _text(dataset.get("name", identifier), "dataset.name")
        fields = dataset.get("columns", [])
        if not isinstance(fields, list) or any(not isinstance(c, dict) for c in fields):
            raise ValueError("dataset.columns must be a list of field objects")
        names = [_text(field.get("name"), "column.name") for field in fields]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate column name")
        columns[identifier] = set(names)
    pairs = {}
    for identifier, process in processes.items():
        for side in ("inputs", "outputs"):
            refs = process.get(side)
            if not isinstance(refs, list) or any(
                not isinstance(ref, str) or ref not in datasets for ref in refs
            ):
                raise ValueError(f"process.{side} must reference existing dataset IDs")
            if len(refs) != len(set(refs)):
                raise ValueError("Duplicate process dataset reference")
        if not process["outputs"]:
            raise ValueError("A process must declare an output")
        pairs[identifier] = {
            (source, target) for source in process["inputs"] for target in process["outputs"]
        }
        if len(pairs[identifier]) > 1000:
            raise ValueError("A run would exceed GCP's 1000 table-link limit")
    if "edges" in graph:
        if not isinstance(graph["edges"], list):
            raise ValueError("graph.edges must be a list")
        declared = {key: set() for key in processes}
        for edge in graph["edges"]:
            if not isinstance(edge, dict) or edge.get("process_id") not in processes:
                raise ValueError("Every edge must reference an existing process_id")
            pair = (edge.get("source"), edge.get("target"))
            process_id = edge["process_id"]
            if pair not in pairs[process_id]:
                raise ValueError("An edge contradicts its process inputs/outputs")
            if pair in declared[process_id]:
                raise ValueError("Duplicate dataset edge")
            declared[process_id].add(pair)
        if declared != pairs:
            raise ValueError(
                "Edges must match process inputs × outputs; correct missing links or split a non-cartesian process before export"
            )
    mappings = graph.get("column_lineage", [])
    if not isinstance(mappings, list):
        raise ValueError("column_lineage must be a list")
    for mapping in mappings:
        if not isinstance(mapping, dict) or mapping.get("process_id") not in processes:
            raise ValueError("Column lineage must reference an existing process_id")
        source, target = mapping.get("source_dataset"), mapping.get("target_dataset")
        if (source, target) not in pairs[mapping["process_id"]]:
            raise ValueError("Column lineage contradicts its process inputs/outputs")
        if (
            mapping.get("source_column") not in columns[source]
            or mapping.get("target_column") not in columns[target]
        ):
            raise ValueError("Column lineage references an unknown column")
        if "transformation" in mapping and not isinstance(mapping["transformation"], str):
            raise ValueError("Column transformation must be text")
    return graph, datasets, processes, mappings


def _dataset_identity(dataset, graph_key, synthetic):
    # Custom namespace is explicitly documented by GCP's OpenLineage mapping.
    # Never imply a synthetic CSV is an existing BigQuery table.
    namespace = "custom"
    name = ".".join(
        (
            _segment("kc_synthetic" if synthetic else "kc_external"),
            _segment(graph_key),
            _segment(dataset["id"]),
        )
    )
    _text(namespace + ":" + name, "dataset FQN")
    return {"namespace": namespace, "name": name}


def _dataset_event(dataset, identity):
    facets = _extra_facets(dataset.get("facets"))
    if "schema" in facets:
        raise ValueError("Provide columns instead of overriding the generated schema facet")
    fields = []
    for column in dataset.get("columns", []):
        field = {"name": column["name"]}
        for source, target in (("data_type", "type"), ("description", "description")):
            if source in column:
                field[target] = _text(column[source], f"column.{source}")
        fields.append(field)
    facets["schema"] = _facet("1-0-0/SchemaDatasetFacet.json#/$defs/SchemaDatasetFacet", {"fields": fields})
    return {**identity, "facets": facets}


def export_openlineage(graph: dict, project: str, location: str) -> dict:
    """Return completed run snapshots, full local graph and explicit GCP losses.

    No clock, credentials, network, storage or live execution is introduced.
    Unsupported/inconsistent graphs fail before creating a misleading export.
    """
    client = CatalogClient(project, location)  # Identifier validation only; ADC is lazy.
    graph, datasets, processes, mappings = _model(graph)
    graph_hash = canonical_hash(graph)
    graph_key = _text(graph.get("id", f"graph-{graph_hash[:20]}"), "graph.id")
    synthetic = graph.get("synthetic") is True
    identities = {key: _dataset_identity(value, graph_key, synthetic) for key, value in datasets.items()}
    runs = graph.get("runs", [])
    if not isinstance(runs, list) or len(runs) > 1000:
        raise ValueError("runs must be a list of at most 1000 completed executions")
    if not runs:
        raise ValueError(
            "Completed runs with explicit ended_at/eventTime are required; exports never invent execution"
        )
    events, run_manifest, seen = [], [], set()
    covered = set()
    for run in runs:
        if not isinstance(run, dict) or run.get("process_id") not in processes:
            raise ValueError("Every run must reference an existing process_id")
        process = processes[run["process_id"]]
        status = run.get("status", run.get("state", ""))
        if status not in {"COMPLETE", "COMPLETED", "SUCCEEDED"}:
            raise ValueError("Only explicitly completed runs can become COMPLETE events")
        ended = _timestamp(run.get("ended_at", run.get("endTime", run.get("eventTime"))), "run.ended_at")
        started = run.get("started_at", run.get("startTime"))
        if started is not None:
            started = _timestamp(started, "run.started_at")
            if datetime.fromisoformat(started.replace("Z", "+00:00")) > datetime.fromisoformat(
                ended.replace("Z", "+00:00")
            ):
                raise ValueError("Run end precedes its start")
        source_id = _text(run.get("run_id", run.get("id")), "run.id")
        try:
            run_id = str(uuid.UUID(source_id))
        except ValueError:
            run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{graph_key}/{process['id']}/{source_id}"))
        if run_id in seen:
            raise ValueError("Run IDs must be globally unique within the bundle")
        seen.add(run_id)
        covered.add(process["id"])
        run_facets = _extra_facets(run.get("facets"))
        if started is not None:
            if "nominalTime" in run_facets:
                raise ValueError("Run facets cannot override declared execution timestamps")
            run_facets["nominalTime"] = _facet(
                "1-0-0/NominalTimeRunFacet.json#/$defs/NominalTimeRunFacet",
                {"nominalStartTime": started, "nominalEndTime": ended},
            )
        job_facets = _extra_facets(process.get("facets"))
        inputs = [_dataset_event(datasets[key], identities[key]) for key in process["inputs"]]
        outputs = [_dataset_event(datasets[key], identities[key]) for key in process["outputs"]]
        for output in outputs:
            output_id = next(key for key in process["outputs"] if identities[key]["name"] == output["name"])
            fields = {}
            for mapping in mappings:
                if mapping["process_id"] != process["id"] or mapping["target_dataset"] != output_id:
                    continue
                item = {**identities[mapping["source_dataset"]], "field": mapping["source_column"]}
                description = mapping.get("transformation", process.get("transformation", ""))
                if description:
                    item["transformations"] = [{"type": "DIRECT", "description": description}]
                field = fields.setdefault(mapping["target_column"], {"inputFields": []})
                if item not in field["inputFields"]:
                    field["inputFields"].append(item)
            if fields:
                if "columnLineage" in output["facets"]:
                    raise ValueError("Provide column_lineage instead of overriding its generated facet")
                output["facets"]["columnLineage"] = _facet(
                    "1-2-0/ColumnLineageDatasetFacet.json#/$defs/ColumnLineageDatasetFacet",
                    {"fields": fields},
                )
        event = {
            "eventType": "COMPLETE",
            "eventTime": ended,
            "run": {"runId": run_id, "facets": run_facets},
            "job": {
                "namespace": f"kc-{'synthetic' if synthetic else 'external'}://{project}/{location}",
                "name": f"{graph_key}/{process['id']}",
                "facets": job_facets,
            },
            "inputs": inputs,
            "outputs": outputs,
            "producer": PRODUCER,
            "schemaURL": EVENT_SCHEMA,
        }
        if len(_json(event).encode("utf-8")) > MAX_EVENT_BYTES:
            raise ValueError("An OpenLineage event exceeds GCP's 5 MB message limit")
        events.append(event)
        run_manifest.append(
            {
                "process_id": process["id"],
                "source_run_id": source_id,
                "run_id": run_id,
                "event_time": ended,
                "clock_kind": run.get("clock_kind", graph.get("clock_kind", "unspecified")),
            }
        )
    if covered != set(processes):
        raise ValueError("Every process needs an explicitly completed run before export")
    warnings = list(WARNINGS)
    if synthetic:
        warnings.append(
            "Synthetic local datasets use custom:kc_synthetic names. Neither this export nor its COMPLETE snapshots assert that any BigQuery table exists."
        )
    if graph.get("clock_kind") == "simulated" or any(
        run["clock_kind"] == "simulated" for run in run_manifest
    ):
        warnings.append(
            "Execution timestamps use a simulated clock and must not be represented as observed production wall-clock times."
        )
    return {
        "schema_version": 1,
        "format": "openlineage-complete-bundle",
        "target": client.parent,
        "project": project,
        "location": location,
        "graph_hash": graph_hash,
        "events": events,
        "runs": run_manifest,
        "datasets": [
            {"id": key, **identity, "fully_qualified_name": f"{identity['namespace']}:{identity['name']}"}
            for key, identity in identities.items()
        ],
        "graph_snapshot": graph,
        "warnings": warnings,
    }


def build_lineage_plan(graph: dict, project: str, location: str) -> dict:
    """Build immutable-content HTTP previews; this module has no write executor."""
    bundle = export_openlineage(graph, project, location)
    operations = []
    for event in bundle["events"]:
        request_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, canonical_hash({"target": bundle["target"], "event": event}))
        )
        operations.append(
            {
                "method": "POST",
                "url": f"{API_ROOT}{bundle['target']}:processOpenLineageRunEvent?requestId={request_id}",
                "body": copy.deepcopy(event),
                "request_id": request_id,
            }
        )
    return {
        "schema_version": 1,
        "mode": "export_only",
        "target": bundle["target"],
        "graph_hash": bundle["graph_hash"],
        "export_hash": canonical_hash(bundle),
        "operations": operations,
        "approval_required": True,
        "writes_executed": False,
        "warnings": bundle["warnings"],
    }


def catalog_metadata(graph: dict) -> dict:
    """Describe the model as one reviewable catalog record; retain its graph once."""
    graph, datasets, processes, mappings = _model(graph)
    checksum = canonical_hash(graph)
    metadata = {
        "schema_version": "1.0",
        "title": graph.get("name", graph.get("title", "Data lineage model")),
        "description": f"Lineage model with {len(datasets)} datasets, {len(processes)} processes and {len(mappings)} column dependencies. The complete graph and its evidence are retained in relationships.",
        "domain": graph.get("domain", "retail"),
        "source": {
            "filename": "lineage-graph.json",
            "format": "json",
            "system": "local-lineage-model",
            "sha256": checksum,
        },
        "profile": {"kind": "lineage_graph", "dataset_count": len(datasets), "process_count": len(processes)},
        "columns": [],
        "relationships": [{"type": "data_lineage", "graph_sha256": checksum, "graph": graph}],
        "limitations": list(WARNINGS),
        "keywords": ["data lineage", "OpenLineage", "metadata"],
    }
    for key in ("owner", "license"):
        if key in graph:
            metadata[key] = copy.deepcopy(graph[key])
    if "synthetic" in graph:
        metadata["synthetic"] = graph["synthetic"]
        metadata["source"]["synthetic"] = graph["synthetic"]
        if graph["synthetic"]:
            metadata["synthetic_evidence"] = (
                "The model declares synthetic=true; its clock and execution are documented in the attached graph. This declaration does not certify anonymization."
            )
    return metadata


class LineageClient:
    """Read-only Data Lineage REST client. POST is allowed only for searchLinks."""

    def __init__(self, project: str, location: str, session=None):
        self._auth = CatalogClient(project, location, session=session)
        self.project, self.location, self.parent = project, location, self._auth.parent

    def _request(self, method, path, *, params=None, body=None):
        from requests.exceptions import RequestException

        if (
            not isinstance(path, str)
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or any(c in path for c in "?#\\")
        ):
            raise ValueError("Unsafe lineage resource path")
        if not path.startswith(self.parent + "/") and path != self.parent + ":searchLinks":
            raise ValueError("Lineage path is outside the configured project/location")
        if method != "GET" and not (method == "POST" and path == self.parent + ":searchLinks"):
            raise ValueError("This lineage client permits reads only")
        kwargs = {"params": params or {}, "timeout": 30, "allow_redirects": False}
        if body is not None:
            kwargs["json"] = body
        try:
            response = self._auth.session.request(method, API_ROOT + quote(path, safe="/:"), **kwargs)
        except RequestException:
            raise CatalogError("Data Lineage read transport failed") from None
        if not 200 <= response.status_code < 300:
            raise CatalogError(f"Data Lineage HTTP {response.status_code}: read failed")
        try:
            result = response.json()
        except ValueError:
            raise CatalogError("Data Lineage returned invalid JSON") from None
        if not isinstance(result, dict):
            raise CatalogError("Data Lineage returned an invalid object")
        return result

    @staticmethod
    def _page(page_token, page_size):
        if not isinstance(page_token, str):
            raise ValueError("page_token must be a string")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        return {"pageToken": page_token, "pageSize": page_size}

    def _list(self, path, field, page_token, page_size):
        result = self._request("GET", path, params=self._page(page_token, page_size))
        self._validate_page(result, field)
        return result

    @staticmethod
    def _validate_page(result, field):
        if (
            not isinstance(result.get(field, []), list)
            or any(not isinstance(item, dict) for item in result.get(field, []))
            or not isinstance(result.get("nextPageToken", ""), str)
        ):
            raise CatalogError("Data Lineage returned a malformed page")

    def _process(self, process):
        _text(process, "process")
        if "/" not in process:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", process):
                raise ValueError("Invalid process ID")
            return f"{self.parent}/processes/{process}"
        match = re.fullmatch(
            r"projects/([^/]+)/locations/" + re.escape(self.location) + r"/processes/([A-Za-z0-9_-]{1,255})",
            process,
        )
        if not match or (match[1] != self.project and (not match[1].isdigit() or self.project.isdigit())):
            raise ValueError("Process must belong to the configured project/location")
        scoped = f"{self.parent}/processes/{match[2]}"
        if match[1] != self.project and self._request("GET", scoped).get("name") != process:
            raise ValueError("Numeric project alias does not match the configured process")
        return scoped

    def list_processes(self, page_token="", page_size=100):
        return self._list(f"{self.parent}/processes", "processes", page_token, page_size)

    def list_runs(self, process, page_token="", page_size=100):
        return self._list(self._process(process) + "/runs", "runs", page_token, page_size)

    def list_events(self, process, run_id, page_token="", page_size=100):
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", run_id):
            raise ValueError("Invalid run ID")
        return self._list(
            self._process(process) + f"/runs/{run_id}/lineageEvents", "lineageEvents", page_token, page_size
        )

    def search_links(self, fully_qualified_name, direction="upstream", page_token="", page_size=100):
        _text(fully_qualified_name, "fully_qualified_name")
        if direction not in {"upstream", "downstream"}:
            raise ValueError("direction must be upstream or downstream")
        body = self._page(page_token, page_size)
        body["target" if direction == "upstream" else "source"] = {"fullyQualifiedName": fully_qualified_name}
        result = self._request("POST", self.parent + ":searchLinks", body=body)
        self._validate_page(result, "links")
        return {
            **result,
            "scope": "Links in every project readable by the identity; the URL project attributes billing/quota.",
            "project_restricted": False,
        }

    def inventory(self, max_pages=5, max_processes=100, max_runs=100, max_events=500):
        limits = {"processes": max_processes, "runs": max_runs, "lineageEvents": max_events}
        if any(
            isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 1000
            for n in [max_pages, *limits.values()]
        ):
            raise ValueError("Inventory limits must be integers between 1 and 1000")
        result = {
            "project": self.project,
            "location": self.location,
            "scope": "configured project/location",
            "processes": [],
            "runs": [],
            "lineageEvents": [],
            "truncated": [],
        }

        def collect(method, field, *args):
            token, seen = "", set()
            page_size = min(100, limits[field])
            for _ in range(max_pages):
                remaining = limits[field] - len(result[field])
                if remaining <= 0:
                    result["truncated"].append(
                        {
                            "collection": field,
                            "parent": list(args),
                            "nextPageToken": token,
                            "reason": "global item limit",
                        }
                    )
                    return []
                page = method(*args, page_token=token, page_size=page_size)
                items = page.get(field, [])
                result[field].extend(items[:remaining])
                if len(items) > remaining:
                    result["truncated"].append(
                        {
                            "collection": field,
                            "parent": list(args),
                            "nextPageToken": token,
                            "offset": remaining,
                            "reason": "global item limit within page",
                        }
                    )
                    return []
                token = page.get("nextPageToken", "")
                if not token:
                    return items
                if token in seen:
                    raise CatalogError("Data Lineage returned a repeated page token")
                seen.add(token)
            result["truncated"].append(
                {"collection": field, "parent": list(args), "nextPageToken": token, "reason": "page limit"}
            )
            return []

        collect(self.list_processes, "processes")
        for process in result["processes"]:
            process_id = process.get("name", "").rsplit("/", 1)[-1]
            previous = len(result["runs"])
            collect(self.list_runs, "runs", process_id)
            for run in result["runs"][previous:]:
                run_id = run.get("name", "").rsplit("/", 1)[-1]
                collect(self.list_events, "lineageEvents", process_id, run_id)
        return result
