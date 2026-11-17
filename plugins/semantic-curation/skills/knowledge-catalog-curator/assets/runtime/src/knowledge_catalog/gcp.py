"""Knowledge Catalog REST adapter; planning never writes and publishing is explicit.

The public product name is Knowledge Catalog. Its current REST service remains
``dataplex.googleapis.com/v1``. Authentication is lazy so the local demo works
without credentials.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from typing import Any
from urllib.parse import quote

API_ROOT = "https://dataplex.googleapis.com/v1/"
MANAGER = "knowledge-catalog-claude"
ASPECT_TYPE_ID = "claude-dataset-metadata-v1"
ENTRY_TYPE_ID = "claude-dataset-v1"
_PROJECT = re.compile(r"(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[0-9]{6,30})\Z")
_LOCATION = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
_CUSTOM_ID = re.compile(r"[a-z][a-z0-9-]{0,61}[a-z0-9]\Z")
# Aspect.data is a protobuf Struct whose numeric values use IEEE754 doubles.
_MAX_EXACT_COUNT = 2**53 - 1


class CatalogError(RuntimeError):
    """A catalog request or local API contract failed."""


class PlanConflict(CatalogError):
    """The reviewed remote state has changed; prepare and approve a fresh plan."""


def canonical_hash(value: Any) -> str:
    """Return a deterministic SHA-256 digest, rejecting non-JSON NaN values."""
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _source_reference(source: dict) -> str:
    for key in ("uri", "url", "source_url", "dataset_url", "path"):
        if isinstance(source.get(key), str) and source[key]:
            return source[key]
    return ""


def _record(name: str, fields: list[tuple[str, str]]) -> dict:
    return {
        "name": name,
        "type": "record",
        "recordFields": [
            {"name": key, "type": kind, "index": index} for index, (key, kind) in enumerate(fields, 1)
        ],
    }


def metadata_template() -> dict:
    """Stable, indexed v1 schema; retain full approved metadata in JSON fields."""
    result = _record(
        "dataset_metadata",
        [
            ("title", "string"),
            ("description", "string"),
            ("domain", "string"),
            ("owner", "string"),
            ("license", "string"),
            ("synthetic", "bool"),
            ("source_uri", "string"),
            ("source_system", "string"),
            ("column_count", "int"),
            ("row_count", "int"),
            ("metadata_sha256", "string"),
            ("source_json", "string"),
            ("quality_json", "string"),
            ("ontology_json", "string"),
            ("provenance_json", "string"),
            ("metadata_json", "string"),
        ],
    )
    columns = _record(
        "item",
        [
            ("name", "string"),
            ("data_type", "string"),
            ("description", "string"),
            ("semantic_type", "string"),
            ("sensitivity", "string"),
            ("details_json", "string"),
        ],
    )
    result["recordFields"].append(
        {
            "name": "columns",
            "type": "array",
            "index": 17,
            "arrayItems": columns,
        }
    )
    result["recordFields"].extend(
        [
            {"name": "row_count_known", "type": "bool", "index": 18},
            {"name": "sampled", "type": "bool", "index": 19},
            {"name": "sampled_rows", "type": "int", "index": 20},
            {"name": "profile_json", "type": "string", "index": 21},
            {
                "name": "semantic_terms",
                "type": "array",
                "index": 22,
                "arrayItems": {"name": "item", "type": "string"},
            },
        ]
    )
    return result


def _aspect_data(metadata: dict) -> dict:
    source = metadata.get("source", {})
    if not isinstance(source, dict):
        source = {"uri": _text(source)}
    columns = metadata.get(
        "columns",
        metadata.get("schema", {}).get("columns", []) if isinstance(metadata.get("schema"), dict) else [],
    )
    if not isinstance(columns, list) or any(not isinstance(column, dict) for column in columns):
        raise ValueError("metadata.columns must be a list of objects")
    profile = metadata.get("profile", {})
    if not isinstance(profile, dict):
        profile = {}
    row_count = metadata.get("row_count", profile.get("row_count", metadata.get("rows")))
    if row_count is not None and (
        not isinstance(row_count, int)
        or isinstance(row_count, bool)
        or not 0 <= row_count <= _MAX_EXACT_COUNT
    ):
        raise ValueError(f"row_count must be a nonnegative integer at most {_MAX_EXACT_COUNT}, or null")
    row_count_known = row_count is not None
    synthetic = metadata.get("synthetic", source.get("synthetic"))
    concepts = metadata.get("concepts", [])
    terms = (
        [
            item["concept"]
            for item in concepts
            if isinstance(item, dict) and isinstance(item.get("concept"), str)
        ]
        if isinstance(concepts, list)
        else []
    )
    data = {
        "title": _text(metadata.get("title", metadata.get("name", "Dataset"))),
        "description": _text(metadata.get("description", "")),
        "domain": _text(metadata.get("domain", "")),
        "owner": _text(metadata.get("owner", source.get("owner", ""))),
        "license": _text(metadata.get("license", source.get("license", ""))),
        "source_uri": _source_reference(source) or _text(source.get("filename", "")),
        "source_system": _text(
            source.get("system", source.get("provider", source.get("source", "external")))
        ),
        "column_count": len(columns),
        "row_count_known": row_count_known,
        "sampled": profile.get("sampled") is True,
        "sampled_rows": profile.get("sampled_rows", 0),
        "profile_json": _json(profile),
        "semantic_terms": terms,
        "metadata_sha256": canonical_hash(metadata),
        "source_json": _json(source),
        "quality_json": _json(metadata.get("quality", {"findings": metadata.get("quality_findings", [])})),
        "ontology_json": _json(
            metadata.get(
                "ontology", {"concepts": concepts, "semantic_method": metadata.get("semantic_method", {})}
            )
        ),
        "provenance_json": _json(metadata.get("provenance", source)),
        "metadata_json": _json(metadata),
        "columns": [
            {
                "name": _text(column.get("name", "")),
                "data_type": _text(column.get("data_type", column.get("dtype", column.get("type", "")))),
                "description": _text(column.get("description", "")),
                "semantic_type": _text(column.get("semantic_type", column.get("ontology_term", ""))),
                "sensitivity": _text(
                    column.get("sensitivity", ", ".join(map(str, column.get("pii_flags", []))))
                ),
                "details_json": _json(column),
            }
            for column in columns
        ],
    }
    if row_count_known:
        data["row_count"] = row_count
    if isinstance(synthetic, bool):
        data["synthetic"] = synthetic
    if (
        not isinstance(data["sampled_rows"], int)
        or isinstance(data["sampled_rows"], bool)
        or not 0 <= data["sampled_rows"] <= _MAX_EXACT_COUNT
    ):
        raise ValueError(f"profile.sampled_rows must be a nonnegative integer at most {_MAX_EXACT_COUNT}")
    # API maximum is 120 KB UTF-8. Never silently truncate an approved record.
    if len(_json(data).encode("utf-8")) > 120_000:
        raise ValueError("Approved metadata exceeds the 120 KB aspect limit; split the dataset metadata")
    return data


class CatalogClient:
    """Read a single configured project; apply only verified, reviewed plans.

    ``session`` accepts a requests-compatible transport for contract tests. The
    approval service must enforce its write flag, project allowlist and human
    approval before calling ``apply_plan``. This class independently validates
    plan shape, limits every write to its own project/location and resource
    types, and checks remote state before it issues any write.
    """

    def __init__(self, project: str, location: str = "global", session: Any = None):
        if not isinstance(project, str) or not _PROJECT.fullmatch(project):
            raise ValueError("project must be a Google Cloud project ID or project number")
        if not isinstance(location, str) or not _LOCATION.fullmatch(location):
            raise ValueError("location must be a region ID or global")
        self.project = project
        self.location = location
        self.parent = f"projects/{project}/locations/{location}"
        self._session = session

    @property
    def session(self):
        if self._session is None:
            try:
                import google.auth
                from google.auth.transport.requests import AuthorizedSession
            except ImportError as exc:
                raise CatalogError("Install project dependencies to use Google Cloud authentication") from exc
            try:
                credentials, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                self._session = AuthorizedSession(credentials)
            except google.auth.exceptions.DefaultCredentialsError as exc:
                raise CatalogError(
                    "Application Default Credentials are required for live catalog access"
                ) from exc
        return self._session

    def _request(
        self, method: str, path: str, *, params=None, body=None, missing_ok=False, timeout: float = 30
    ) -> dict | None:
        from requests.exceptions import RequestException, Timeout

        if not path.startswith(f"projects/{self.project}/locations/") or ".." in path.split("/"):
            raise ValueError("Catalog path is outside the configured project")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
            raise ValueError("Request timeout must be positive and at most 30 seconds")
        query = {
            key: (str(value).lower() if isinstance(value, bool) else value)
            for key, value in (params or {}).items()
        }
        kwargs = {"params": query, "timeout": timeout, "allow_redirects": False}
        if body is not None:
            kwargs["json"] = body
        try:
            response = self.session.request(method, API_ROOT + quote(path, safe="/:@"), **kwargs)
        except RequestException as exc:
            category = "transport timeout" if isinstance(exc, Timeout) else "transport failure"
            uncertain = (
                "; inspect remote state before retrying this write"
                if method in {"POST", "PATCH"} and not path.endswith(":searchEntries")
                else ""
            )
            raise CatalogError(f"Knowledge Catalog {category}{uncertain}") from None
        if response.status_code == 404 and missing_ok:
            return None
        if not 200 <= response.status_code < 300:
            # Service messages can echo rejected metadata or signed URLs. Keep
            # only the status code; detailed diagnostics need deliberate review.
            raise CatalogError(f"Knowledge Catalog HTTP {response.status_code}: request failed")
        try:
            result = response.json()
        except ValueError:
            raise CatalogError("Knowledge Catalog returned invalid JSON") from None
        if not isinstance(result, dict):
            raise CatalogError("Knowledge Catalog returned an invalid JSON object")
        return result

    def search(self, query: str, page_token: str = "", page_size: int = 100) -> dict:
        if not isinstance(query, str) or not query.strip() or len(query) > 20_000:
            raise ValueError("Provide a nonempty catalog search query under 20,000 characters")
        self._page_size(page_size)
        # Current REST reference uses query parameters with an EMPTY POST body.
        return self._request(
            "POST",
            f"projects/{self.project}/locations/global:searchEntries",
            params={
                "query": query,
                "pageSize": page_size,
                "pageToken": page_token,
                "scope": f"projects/{self.project}",
            },
        )

    @staticmethod
    def _page_size(value: int, maximum: int = 1000):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ValueError(f"page_size must be between 1 and {maximum}")

    def _list(self, path: str, page_token: str = "", page_size: int = 100) -> dict:
        collection = path.rsplit("/", 1)[1]
        self._page_size(page_size, 100 if collection == "entries" else 1000)
        if not isinstance(page_token, str):
            raise ValueError("page_token must be a string")
        result = self._request("GET", path, params={"pageSize": page_size, "pageToken": page_token})
        items = result.get(collection, [])
        unreachable = result.get("unreachableLocations", [])
        if (
            not isinstance(items, list)
            or any(not isinstance(item, dict) for item in items)
            or not isinstance(result.get("nextPageToken", ""), str)
            or not isinstance(unreachable, list)
            or any(not isinstance(location, str) for location in unreachable)
        ):
            raise CatalogError("Knowledge Catalog returned a malformed list page")
        return result

    def list_entry_groups(self, page_token: str = "", page_size: int = 100) -> dict:
        return self._list(f"{self.parent}/entryGroups", page_token, page_size)

    def list_entry_types(self, page_token: str = "", page_size: int = 100) -> dict:
        return self._list(f"{self.parent}/entryTypes", page_token, page_size)

    def list_aspect_types(self, page_token: str = "", page_size: int = 100) -> dict:
        return self._list(f"{self.parent}/aspectTypes", page_token, page_size)

    def list_entries(self, entry_group: str, page_token: str = "", page_size: int = 100) -> dict:
        if not isinstance(entry_group, str):
            raise ValueError("Entry group must be an ID or resource name string")
        if "/" not in entry_group:
            if not re.fullmatch(r"@?[A-Za-z0-9_-]{1,128}", entry_group):
                raise ValueError("Invalid entry group ID")
            entry_group = f"{self.parent}/entryGroups/{entry_group}"
        if not re.fullmatch(re.escape(self.parent) + r"/entryGroups/@?[A-Za-z0-9_-]{1,128}", entry_group):
            alias = re.fullmatch(
                r"projects/([0-9]{6,30})/locations/"
                + re.escape(self.location)
                + r"/entryGroups/(@?[A-Za-z0-9_-]{1,128})",
                entry_group,
            )
            if alias is None or self.project.isdigit():
                raise ValueError("Entry group must belong to the configured project/location")
            scoped_group = f"{self.parent}/entryGroups/{alias[2]}"
            group = self._request("GET", scoped_group)
            if group.get("name") != entry_group:
                raise ValueError("Numeric project alias does not match the configured project's group")
            entry_group = scoped_group
        return self._list(f"{entry_group}/entries", page_token, page_size)

    def _validate_entry_name(self, name: str):
        if not isinstance(name, str):
            raise ValueError("Entry name must be a resource name string")
        match = re.fullmatch(
            r"projects/([^/]+)/locations/"
            + re.escape(self.location)
            + r"/entryGroups/@?[A-Za-z0-9_-]{1,128}/entries/.{1,4000}",
            name,
        )
        if not match or not _PROJECT.fullmatch(match[1]):
            raise ValueError("Entry name must belong to the configured project/location")
        named_project = match[1]
        if named_project != self.project and (not named_project.isdigit() or self.project.isdigit()):
            raise ValueError("Entry name must belong to the configured project/location")
        tail = name.split("/entries/", 1)[1]
        if (
            any(part in ("", ".", "..") for part in tail.split("/"))
            or any(char in tail for char in "?#%\\")
            or any(ord(char) < 32 for char in tail)
        ):
            raise ValueError("Entry name contains an unsafe path")
        # Always query our configured project. A numeric alias is verified only
        # from this scoped response, never trusted as an arbitrary project.
        return "projects/" + self.project + name[len("projects/" + named_project) :]

    def get_entry(self, name: str) -> dict:
        scoped_name = self._validate_entry_name(name)
        resource = self._request("GET", scoped_name, params={"view": "ALL"})
        if scoped_name != name and resource.get("name") != name:
            raise ValueError("Numeric project alias does not match the configured project's entry")
        return resource

    def inventory(self, max_pages: int = 100) -> dict:
        """Paginated inventory scoped to this location; explicitly signal limits."""
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 1000:
            raise ValueError("max_pages must be between 1 and 1000")
        result = {
            "project": self.project,
            "location": self.location,
            "entryGroups": [],
            "entryTypes": [],
            "aspectTypes": [],
            "entries": [],
            "truncated": [],
            "unreachableLocations": [],
            "scope": "configured location",
        }

        def collect(method, field, *args):
            token = ""
            seen = set()
            for _ in range(max_pages):
                page = method(*args, page_token=token)
                result[field].extend(page.get(field, []))
                for location in page.get("unreachableLocations", []):
                    if location not in result["unreachableLocations"]:
                        result["unreachableLocations"].append(location)
                token = page.get("nextPageToken", "")
                if not token:
                    return
                if token in seen:
                    raise CatalogError("Catalog pagination returned a repeated page token")
                seen.add(token)
            result["truncated"].append(
                {"collection": field, "parent": args[0] if args else self.parent, "nextPageToken": token}
            )

        collect(self.list_entry_groups, "entryGroups")
        collect(self.list_entry_types, "entryTypes")
        collect(self.list_aspect_types, "aspectTypes")
        for group in result["entryGroups"]:
            # Google may return the canonical numeric project in resource names.
            group_id = group["name"].rsplit("/", 1)[1]
            collect(self.list_entries, "entries", group_id)
        return result

    def _snapshot(self, path: str, verified: bool, entry=False) -> dict:
        if not verified:
            return {
                "mode": "unverified",
                "exists": None,
                "updateTime": None,
                "etag": None,
                "content_hash": None,
                "resource": None,
            }
        resource = self._request("GET", path, params={"view": "ALL"} if entry else {}, missing_ok=True)
        snapshot = {
            "mode": "verified",
            "exists": resource is not None,
            "updateTime": resource.get("updateTime") if resource else None,
            "etag": resource.get("etag") if resource else None,
            "content_hash": canonical_hash(resource) if resource is not None else None,
            "resource": resource,
        }
        self._check_snapshot_integrity(snapshot, path)
        return snapshot

    def _dependencies(self, entry_group_id: str) -> list[dict]:
        aspect_name = f"{self.parent}/aspectTypes/{ASPECT_TYPE_ID}"
        return [
            {
                "kind": "entryGroup",
                "method": "POST",
                "path": f"{self.parent}/entryGroups",
                "target": f"{self.parent}/entryGroups/{entry_group_id}",
                "params": {"entryGroupId": entry_group_id},
                "body": {
                    "displayName": "Claude curated datasets",
                    "description": "Datasets published after explicit metadata review.",
                    "labels": {"managed-by": MANAGER},
                },
            },
            {
                "kind": "aspectType",
                "method": "POST",
                "path": f"{self.parent}/aspectTypes",
                "target": aspect_name,
                "params": {"aspectTypeId": ASPECT_TYPE_ID},
                "body": {
                    "displayName": "Reviewed dataset metadata v1",
                    "description": "Versioned dataset provenance, schema, ontology and quality metadata.",
                    "labels": {"managed-by": MANAGER},
                    "metadataTemplate": metadata_template(),
                },
            },
            {
                "kind": "entryType",
                "method": "POST",
                "path": f"{self.parent}/entryTypes",
                "target": f"{self.parent}/entryTypes/{ENTRY_TYPE_ID}",
                "params": {"entryTypeId": ENTRY_TYPE_ID},
                "body": {
                    "displayName": "Reviewed external dataset v1",
                    "description": "External datasets curated through Claude.",
                    "labels": {"managed-by": MANAGER},
                    "typeAliases": ["DATASET"],
                    "requiredAspects": [{"type": aspect_name}],
                },
            },
        ]

    def _entry_body(self, metadata: dict, name: str) -> dict:
        data = _aspect_data(metadata)
        return {
            "name": name,
            "entryType": f"{self.parent}/entryTypes/{ENTRY_TYPE_ID}",
            "fullyQualifiedName": f"claude-curated:{self.project}.{self.location}.{name.split('/entries/', 1)[1]}",
            "entrySource": {
                "resource": data["source_uri"][:4000],
                "system": data["source_system"][:64],
                "platform": "external",
                "displayName": data["title"][:500],
                "description": data["description"][:2000],
            },
            "aspects": {f"{self.project}.{self.location}.{ASPECT_TYPE_ID}": {"data": data}},
        }

    def build_plan(
        self,
        metadata: dict,
        entry_group_id: str = "curated",
        entry_id: str | None = None,
        *,
        remote_snapshot: bool = False,
    ) -> dict:
        if not isinstance(metadata, dict) or not metadata:
            raise ValueError("metadata must be a nonempty object")
        if not isinstance(entry_group_id, str) or not _CUSTOM_ID.fullmatch(entry_group_id):
            raise ValueError("Use a custom entry group ID with 2-63 lowercase letters, digits or hyphens")
        metadata = copy.deepcopy(metadata)
        # A Kaggle dataset can contain several files sharing one landing URL.
        # Use file identity too; local files without a URI use their content hash.
        source = metadata.get("source", {})
        if isinstance(source, dict):
            reference = _source_reference(source)
            identity = (
                {"reference": reference, "filename": source.get("filename", "")}
                if reference
                else source.get("sha256", source.get("filename", ""))
            )
        else:
            identity = source
        identity = identity or metadata.get("name", metadata.get("title", canonical_hash(metadata)))
        entry_id = entry_id or f"dataset-{canonical_hash(identity)[:24]}"
        if not isinstance(entry_id, str) or not _CUSTOM_ID.fullmatch(entry_id):
            raise ValueError("Use a custom entry ID with 2-63 lowercase letters, digits or hyphens")
        target = f"{self.parent}/entryGroups/{entry_group_id}/entries/{entry_id}"
        body = self._entry_body(metadata, target)
        snapshot = self._snapshot(target, remote_snapshot, entry=True)
        bootstrap = self._dependencies(entry_group_id)
        for operation in bootstrap:
            operation["snapshot"] = self._snapshot(operation["target"], remote_snapshot)
            operation["needed"] = None if not remote_snapshot else not operation["snapshot"]["exists"]
        entry_operation = self._entry_operation(body, entry_group_id, entry_id, snapshot)
        return {
            "schema_version": 1,
            "project": self.project,
            "location": self.location,
            "target": target,
            "entry_group_id": entry_group_id,
            "entry_id": entry_id,
            "snapshot": snapshot,
            "bootstrap": bootstrap,
            "operations": [entry_operation],
            "metadata_hash": canonical_hash(metadata),
            "metadata": metadata,
            "managed_aspect_key": next(iter(body["aspects"])),
            "warnings": (
                [
                    "Offline preview: remote existence and conflicts are unknown. Create a verified live plan before approval/publication."
                ]
                if not remote_snapshot
                else []
            )
            + [
                "Entry updates have no server-side etag precondition; concurrent changes after the final read remain possible."
            ],
        }

    def _entry_operation(self, body, entry_group_id, entry_id, snapshot):
        exists = snapshot["exists"] is True
        if exists:
            # Source updates may require a new source updateTime. Preserve that
            # provenance and keep revised descriptions in our own aspect.
            body = {"name": body["name"], "aspects": body["aspects"]}
        return {
            "kind": "entry",
            "method": "PATCH" if exists else "POST",
            "path": body["name"] if exists else f"{self.parent}/entryGroups/{entry_group_id}/entries",
            "target": body["name"],
            "params": (
                {
                    "updateMask": "aspects",
                    "aspectKeys": list(body["aspects"]),
                    "deleteMissingAspects": False,
                    "allowMissing": False,
                }
                if exists
                else {"entryId": entry_id}
            ),
            "body": body,
        }

    def _validate_plan(self, plan: dict):
        if (
            plan.get("schema_version") != 1
            or plan.get("project") != self.project
            or plan.get("location") != self.location
        ):
            raise ValueError("Plan is for a different project/location or unsupported schema")
        if plan.get("snapshot", {}).get("mode") != "verified":
            raise ValueError("An offline preview cannot be published; build a verified live plan first")
        # Reconstruct all writable paths and bodies without trusting supplied HTTP.
        expected = self.build_plan(plan["metadata"], plan["entry_group_id"], plan["entry_id"])
        if (
            plan.get("metadata_hash") != expected["metadata_hash"]
            or plan.get("target") != expected["target"]
            or plan.get("managed_aspect_key") != expected["managed_aspect_key"]
        ):
            raise ValueError("Plan metadata/target hash is invalid")
        dependencies = self._dependencies(plan["entry_group_id"])
        if len(plan.get("bootstrap", [])) != len(dependencies):
            raise ValueError("Plan bootstrap operations were modified")
        for actual, desired in zip(plan["bootstrap"], dependencies):
            if actual.get("snapshot", {}).get("mode") != "verified":
                raise ValueError("Plan dependency snapshot is unverified")
            if (
                set(actual) != set(desired) | {"snapshot", "needed"}
                or {key: actual.get(key) for key in desired} != desired
            ):
                raise ValueError("Plan bootstrap operations were modified")
            self._check_snapshot_integrity(actual["snapshot"], desired["target"])
            if actual["needed"] is not (not actual["snapshot"]["exists"]):
                raise ValueError("Plan bootstrap state is inconsistent")
        self._check_snapshot_integrity(plan["snapshot"], plan["target"])
        body = self._entry_body(plan["metadata"], plan["target"])
        if plan.get("operations") != [
            self._entry_operation(body, plan["entry_group_id"], plan["entry_id"], plan["snapshot"])
        ]:
            raise ValueError("Plan entry operations were modified")

    def _check_snapshot_integrity(self, snapshot, expected_name):
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "mode",
            "exists",
            "resource",
            "content_hash",
            "etag",
            "updateTime",
        }:
            raise ValueError("Plan snapshot is malformed")
        resource = snapshot.get("resource")
        if (
            snapshot["mode"] != "verified"
            or not isinstance(snapshot["exists"], bool)
            or (resource is not None) != snapshot["exists"]
            or (resource is not None and not isinstance(resource, dict))
            or any(
                snapshot[key] is not None and not isinstance(snapshot[key], str)
                for key in ("etag", "updateTime")
            )
        ):
            raise ValueError("Plan snapshot is malformed")
        if resource is None and any(snapshot[key] is not None for key in ("etag", "updateTime")):
            raise ValueError("Absent resource snapshot cannot contain a version")
        if resource is not None and not self._resource_name_matches(resource.get("name"), expected_name):
            raise ValueError("Snapshot resource does not match the expected target")
        if snapshot.get("content_hash") != (canonical_hash(resource) if resource is not None else None):
            raise ValueError("Plan snapshot hash is invalid")
        if resource is not None and (
            snapshot.get("etag") != resource.get("etag")
            or snapshot.get("updateTime") != resource.get("updateTime")
        ):
            raise ValueError("Plan snapshot version is invalid")

    def _dependency_compatible(self, operation, resource, dependencies):
        desired = operation["body"]
        if resource.get("labels", {}).get("managed-by") != MANAGER:
            return False
        if operation["kind"] == "aspectType":
            return resource.get("metadataTemplate") == desired["metadataTemplate"]
        if operation["kind"] == "entryType":
            expected_aspects = {item["type"] for item in desired["requiredAspects"]}
            for dependency in dependencies:
                if dependency["kind"] == "aspectType":
                    canonical = dependency["snapshot"].get("resource")
                    if canonical and self._resource_name_matches(canonical.get("name"), dependency["target"]):
                        expected_aspects.add(canonical["name"])
            required = resource.get("requiredAspects", [])
            return (
                isinstance(required, list)
                and len(required) == 1
                and isinstance(required[0], dict)
                and required[0].get("type") in expected_aspects
            )
        return True

    def _entry_matches(self, resource, desired, dependencies):
        if resource is None:
            return False
        type_names = {desired["entryType"]}
        for operation in dependencies:
            if operation["kind"] == "entryType" and operation["snapshot"].get("resource"):
                type_names.add(operation["snapshot"]["resource"].get("name"))
        if resource.get("entryType") not in type_names:
            return False
        desired_data = next(iter(desired["aspects"].values()))["data"]
        # The service may normalize the project ID to its numeric project.
        keys = {next(iter(desired["aspects"]))}
        for operation in dependencies:
            if operation["kind"] == "aspectType" and operation["snapshot"].get("resource"):
                parts = operation["snapshot"]["resource"].get("name", "").split("/")
                if len(parts) == 6:
                    keys.add(f"{parts[1]}.{parts[3]}.{parts[5]}")
        match = any(resource.get("aspects", {}).get(key, {}).get("data") == desired_data for key in keys)
        return match

    def _resource_name_matches(self, actual: str, expected: str) -> bool:
        if actual == expected:
            return True
        if not isinstance(actual, str) or self.project.isdigit():
            return False
        return bool(re.fullmatch(r"projects/[0-9]{6,30}/" + re.escape(expected.split("/", 2)[2]), actual))

    def _wait_operation(self, operation: dict, expected_resource: str | None = None) -> dict:
        deadline = time.monotonic() + 60
        while True:
            if not isinstance(operation, dict) or not isinstance(operation.get("done", False), bool):
                raise CatalogError("Catalog returned a malformed long-running operation")
            name = operation.get("name", "")
            if not isinstance(name, str) or not re.fullmatch(
                r"projects/(?:"
                + re.escape(self.project)
                + r"|[0-9]{6,30})/locations/"
                + re.escape(self.location)
                + r"/operations/[A-Za-z0-9_-]+",
                name,
            ):
                raise CatalogError("Catalog returned an unexpected long-running operation name")
            result_keys = {"error", "response"}.intersection(operation)
            if operation.get("done", False):
                if len(result_keys) != 1:
                    raise CatalogError("Catalog returned a malformed completed operation")
                if "error" in result_keys:
                    raise CatalogError("Catalog operation failed; inspect its status in GCP")
                response = operation["response"]
                if not isinstance(response, dict) or (
                    expected_resource is not None
                    and not self._resource_name_matches(response.get("name"), expected_resource)
                ):
                    raise CatalogError("Catalog operation did not confirm the expected resource")
                return response
            if result_keys:
                raise CatalogError("Catalog returned a result for an unfinished operation")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CatalogError(
                    f"Catalog operation is still pending: {name}. Inspect it before retrying publication"
                )
            time.sleep(min(0.5, remaining))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CatalogError(
                    "Catalog operation is still pending; inspect it before retrying publication"
                )
            parts = name.split("/")
            parts[1] = self.project
            operation = self._request("GET", "/".join(parts), timeout=min(30, remaining))

    def apply_plan(self, plan: dict) -> dict:
        """Apply a verified plan after the caller's durable approval gate.

        Every snapshot is checked before the first mutation. Creates use POST,
        so an existing entry is never implicitly overwritten. A changed entry
        requires a fresh plan. Identical already-applied metadata is a no-op.
        """
        self._validate_plan(plan)
        desired = self._entry_body(plan["metadata"], plan["target"])
        current_dependencies = copy.deepcopy(plan["bootstrap"])
        for operation in current_dependencies:
            current = self._snapshot(operation["target"], True)
            previous = operation["snapshot"]
            if current["exists"] and not self._dependency_compatible(
                operation, current["resource"], current_dependencies
            ):
                raise PlanConflict(
                    f"Existing {operation['kind']} is not a compatible plugin-managed resource"
                )
            if previous["exists"] and current["content_hash"] != previous["content_hash"]:
                raise PlanConflict(f"{operation['kind']} changed after review; prepare a new plan")
            operation["snapshot"] = current
        current = self._snapshot(plan["target"], True, entry=True)
        if self._entry_matches(current["resource"], desired, current_dependencies):
            return {
                "status": "unchanged",
                "target": plan["target"],
                "entry": current["resource"],
                "operations_applied": [],
            }
        if (
            current["content_hash"] != plan["snapshot"]["content_hash"]
            or current["exists"] != plan["snapshot"]["exists"]
        ):
            raise PlanConflict("Entry changed after review; prepare and approve a new plan")
        if current["exists"]:
            type_names = {desired["entryType"]}
            type_resource = current_dependencies[2]["snapshot"].get("resource")
            if type_resource:
                type_names.add(type_resource.get("name"))
            if current["resource"].get("entryType") not in type_names:
                raise PlanConflict("Refusing to modify an entry with a different entry type")
        applied = []
        for operation in current_dependencies:
            if operation["snapshot"]["exists"]:
                continue
            response = self._request(
                operation["method"], operation["path"], params=operation["params"], body=operation["body"]
            )
            created = self._wait_operation(response, operation["target"])
            operation["snapshot"].update(
                exists=True,
                resource=created,
                content_hash=canonical_hash(created),
                etag=created.get("etag"),
                updateTime=created.get("updateTime"),
            )
            applied.append(operation["target"])
        # Final read narrows (but cannot eliminate) the documented race window.
        final = self._snapshot(plan["target"], True, entry=True)
        if final["content_hash"] != current["content_hash"] or final["exists"] != current["exists"]:
            raise PlanConflict("Entry changed during bootstrap; prepare a new plan")
        operation = plan["operations"][0]
        entry = self._request(
            operation["method"], operation["path"], params=operation["params"], body=operation["body"]
        )
        if not self._resource_name_matches(entry.get("name"), plan["target"]) or not self._entry_matches(
            entry, desired, current_dependencies
        ):
            raise CatalogError(
                "Catalog write did not confirm the expected entry metadata; inspect remote state"
            )
        applied.append(plan["target"])
        return {
            "status": "published",
            "target": plan["target"],
            "entry": entry,
            "operations_applied": applied,
        }
