"""Persistent, versioned proposals. Approval is exposed only in the human UI/CLI."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

VALIDATION_POLICY_VERSION = 1


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class Workflow:
    def __init__(self, home: str | Path):
        self.home = Path(home).resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.config_path = self.home / "config.json"
        self.db = self.home / "catalog.sqlite3"
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            con.execute(
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at REAL, proposal TEXT, action TEXT, detail TEXT)"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS revisions (proposal TEXT, revision INTEGER, digest TEXT, "
                "body TEXT NOT NULL, at REAL, action TEXT, detail TEXT, PRIMARY KEY(proposal,revision))"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS configuration_generation (id INTEGER PRIMARY KEY, generation INTEGER NOT NULL)"
            )
            con.execute("INSERT OR IGNORE INTO configuration_generation VALUES (1,0)")
            # Migration preserves the earliest state still available locally;
            # overwritten historical revisions cannot be reconstructed.
            for proposal_id, body in con.execute("SELECT id,body FROM proposals"):
                current = json.loads(body)
                con.execute(
                    "INSERT OR IGNORE INTO revisions VALUES (?,?,?,?,?,?,?)",
                    (
                        proposal_id,
                        current["revision"],
                        current["digest"],
                        body,
                        time.time(),
                        "history_migrated",
                        "Earlier revisions were not retained by this installation",
                    ),
                )

    def connect(self):
        return sqlite3.connect(self.db, timeout=30)

    def config(self) -> dict:
        defaults = {
            "project": "",
            "location": "us-central1",
            "writes_enabled": False,
            "allowed_projects": [],
            "allowed_roots": [str(self.home.parent)],
            "approval_ttl_seconds": 86400,
        }
        if self.config_path.exists():
            if self.config_path.stat().st_size > 65536:
                raise ValueError("Configuration exceeds 64 KiB")
            stored = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(stored, dict) or set(stored) - set(defaults):
                raise ValueError("Configuration must be an object with supported settings")
            defaults.update(stored)
        self._validate_config(defaults)
        return defaults

    @staticmethod
    def _validate_config(config: dict) -> None:
        project_pattern = r"(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[0-9]{6,30})"
        project = config["project"]
        if not isinstance(project, str) or (project and not re.fullmatch(project_pattern, project)):
            raise ValueError("project must be a Google Cloud project ID or number")
        if not isinstance(config["location"], str) or not re.fullmatch(
            r"[a-z][a-z0-9-]{0,62}", config["location"]
        ):
            raise ValueError("location must be a Google Cloud location identifier")
        if type(config["writes_enabled"]) is not bool:
            raise ValueError("writes_enabled must be a boolean")
        projects = config["allowed_projects"]
        if (
            not isinstance(projects, list)
            or len(projects) > 100
            or any(
                not isinstance(value, str) or not re.fullmatch(project_pattern, value) for value in projects
            )
            or len(set(projects)) != len(projects)
        ):
            raise ValueError("allowed_projects must contain distinct valid project IDs or numbers")
        roots = config["allowed_roots"]
        if (
            not isinstance(roots, list)
            or not 1 <= len(roots) <= 100
            or any(
                not isinstance(value, str) or not value.strip() or not Path(value).is_absolute()
                for value in roots
            )
        ):
            raise ValueError("allowed_roots must contain 1–100 absolute directory paths")
        ttl = config["approval_ttl_seconds"]
        if type(ttl) is not int or not 1 <= ttl <= 604800:
            raise ValueError("approval_ttl_seconds must be an integer between 1 and 604800")
        if config["writes_enabled"] and (not project or project not in projects):
            raise ValueError("Add the exact project to allowed_projects before enabling writes")

    def configure(self, **updates) -> dict:
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            config = self.config()
            original = copy.deepcopy(config)
            unknown = set(updates) - set(config)
            if unknown:
                raise ValueError(f"Unknown settings: {sorted(unknown)}")
            config.update(updates)
            self._validate_config(config)
            changed = config != original
            if changed and any(
                json.loads(row[0]).get("status") == "publishing"
                for row in con.execute("SELECT body FROM proposals")
            ):
                raise ValueError(
                    "Publication in progress; finish or recover it before changing configuration"
                )
            descriptor, temporary = tempfile.mkstemp(prefix=".config-", suffix=".json", dir=self.home)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(config, stream, indent=2, allow_nan=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.config_path)
                if changed:
                    con.execute("UPDATE configuration_generation SET generation=generation+1 WHERE id=1")
            finally:
                Path(temporary).unlink(missing_ok=True)
        return config

    def allowed_path(self, path: str | Path) -> Path:
        path = Path(path).resolve(strict=True)
        if not any(path.is_relative_to(Path(root).resolve()) for root in self.config()["allowed_roots"]):
            raise ValueError("File is outside configured allowed_roots")
        if not path.is_file():
            raise ValueError("Expected a regular file")
        return path

    def _save(self, con, proposal: dict, action: str, detail: str = ""):
        existing = con.execute(
            "SELECT digest FROM revisions WHERE proposal=? AND revision=?",
            (proposal["id"], proposal["revision"]),
        ).fetchone()
        if existing and existing[0] != proposal["digest"]:
            raise ValueError("Existing review revision cannot be rewritten; create a new revision")
        con.execute(
            "INSERT OR IGNORE INTO revisions VALUES (?,?,?,?,?,?,?)",
            (
                proposal["id"],
                proposal["revision"],
                proposal["digest"],
                json.dumps(proposal),
                time.time(),
                action,
                detail,
            ),
        )
        con.execute("INSERT OR REPLACE INTO proposals VALUES (?,?)", (proposal["id"], json.dumps(proposal)))
        con.execute(
            "INSERT INTO events(at,proposal,action,detail) VALUES (?,?,?,?)",
            (time.time(), proposal["id"], action, detail),
        )

    def _get(self, con, proposal_id: str) -> dict:
        row = con.execute("SELECT body FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        if not row:
            raise ValueError("Proposal not found")
        return json.loads(row[0])

    def get(self, proposal_id: str) -> dict:
        with self.connect() as con:
            return self._get(con, proposal_id)

    def list(self) -> list[dict]:
        with self.connect() as con:
            return [
                json.loads(row[0]) for row in con.execute("SELECT body FROM proposals ORDER BY rowid DESC")
            ]

    def list_page(self, *, offset: int = 0, limit: int = 20) -> dict:
        self._page_limit(limit)
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        with self.connect() as con:
            total = con.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
            rows = con.execute(
                "SELECT body FROM proposals ORDER BY json_extract(body,'$.created_at') DESC,id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        proposals = [json.loads(row[0]) for row in rows]
        return {
            "proposals": proposals,
            "total": total,
            "offset": offset,
            "next_offset": offset + len(proposals) if offset + len(proposals) < total else None,
        }

    def events(self) -> list[dict]:
        with self.connect() as con:
            con.row_factory = sqlite3.Row
            return [dict(row) for row in con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 200")]

    @staticmethod
    def _page_limit(limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")

    def history(self, proposal_id: str, *, before_revision: int | None = None, limit: int = 20) -> dict:
        self._page_limit(limit)
        if before_revision is not None and (type(before_revision) is not int or before_revision < 1):
            raise ValueError("before_revision must be a positive revision number")
        with self.connect() as con:
            self._get(con, proposal_id)
            rows = con.execute(
                "SELECT revision,digest,at,action,detail FROM revisions WHERE proposal=? "
                "AND (? IS NULL OR revision<?) ORDER BY revision DESC LIMIT ?",
                (proposal_id, before_revision, before_revision, limit + 1),
            ).fetchall()
        keys = ("revision", "digest", "at", "action", "detail")
        records = [dict(zip(keys, row)) for row in rows[:limit]]
        return {
            "proposal_id": proposal_id,
            "revisions": records,
            "next_before_revision": records[-1]["revision"] if len(rows) > limit else None,
        }

    def get_revision(self, proposal_id: str, revision: int) -> dict:
        if type(revision) is not int or revision < 1:
            raise ValueError("revision must be a positive integer")
        with self.connect() as con:
            row = con.execute(
                "SELECT body FROM revisions WHERE proposal=? AND revision=?", (proposal_id, revision)
            ).fetchone()
        if row is None:
            raise ValueError("Historical revision not found; earlier versions may predate durable history")
        return json.loads(row[0])

    def diff(
        self, proposal_id: str, from_revision: int, to_revision: int | None = None, *, limit: int = 100
    ) -> dict:
        self._page_limit(limit)
        before = self.get_revision(proposal_id, from_revision)
        after = (
            self.get_revision(proposal_id, to_revision) if to_revision is not None else self.get(proposal_id)
        )
        changes = []

        def compare(old, new, path):
            if len(changes) > limit or old == new:
                return
            if isinstance(old, dict) and isinstance(new, dict):
                for key in sorted(set(old) | set(new)):
                    child = path + "/" + key.replace("~", "~0").replace("/", "~1")
                    if key not in old or key not in new:
                        changes.append({"path": child, "before": old.get(key), "after": new.get(key)})
                    else:
                        compare(old[key], new[key], child)
                    if len(changes) > limit:
                        break
            elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
                for index, (left, right) in enumerate(zip(old, new)):
                    compare(left, right, path + f"/{index}")
                    if len(changes) > limit:
                        break
            else:
                changes.append({"path": path, "before": old, "after": new})

        for section in ("metadata", "plan", "quality"):
            compare(before[section], after[section], "/" + section)
        return {
            "proposal_id": proposal_id,
            "from_revision": before["revision"],
            "to_revision": after["revision"],
            "changes": changes[:limit],
            "truncated": len(changes) > limit,
        }

    def taxonomy_suggestions(
        self,
        proposal_id: str,
        *,
        column_name: str | None = None,
        query: str = "",
        expected_digest: str | None = None,
        provider: str = "local",
    ) -> dict:
        """Compare vocabulary candidates without changing a saved revision."""
        from .taxonomy import suggest_concepts

        proposal = self.get(proposal_id)
        self._integrity(proposal)
        self._expected(proposal, expected_digest)
        if provider == "open-ontologies":
            from .open_ontologies import compare_concepts

            comparison = compare_concepts(proposal["metadata"], column_name=column_name, query=query)
        elif provider == "local":
            comparison = suggest_concepts(proposal["metadata"], column_name=column_name, query=query)
            comparison["provider"] = {
                "id": "local",
                "label": "Local comparison",
                "version": comparison["method"]["policy_version"],
                "invoked": False,
            }
        else:
            raise ValueError("provider must be local or open-ontologies")
        return {
            **comparison,
            "proposal_id": proposal["id"],
            "revision": proposal["revision"],
            "digest": proposal["digest"],
            "column_name": column_name,
        }

    def client(self):
        from .gcp import CatalogClient

        config = self.config()
        return CatalogClient(config["project"] or "synthetic-demo", config["location"])

    def _prepare(self, proposal: dict, *, live: bool = False) -> dict:
        from .ontology import validate_metadata

        proposal["quality"] = validate_metadata(proposal["metadata"])
        proposal["metadata"]["quality"] = copy.deepcopy(proposal["quality"])
        proposal["plan"] = self.client().build_plan(
            proposal["metadata"], entry_id=proposal.get("entry_id"), remote_snapshot=live
        )
        proposal["entry_id"] = proposal["plan"]["entry_id"]
        proposal["revision"] += 1
        proposal["status"] = "draft"
        proposal["approval"] = None
        proposal["digest"] = self._content_digest(proposal)
        return proposal

    def propose(self, path: str, domain: str = "retail", provenance: dict | None = None) -> dict:
        from .analysis import analyze_file

        source_path = self.allowed_path(path)
        if provenance is not None and not isinstance(provenance, dict):
            raise ValueError("provenance must be an object containing source evidence")
        actual = self._file_hash(source_path)
        # An explicit empty/custom provenance object must not bypass an adjacent
        # download manifest. Its recorded hashes and license gates remain binding.
        adjacent = None
        for parent in list(source_path.parents)[:10]:
            evidence_path = parent / "provenance.json"
            try:
                relative = source_path.relative_to(parent / "files").as_posix()
            except ValueError:
                continue
            if not evidence_path.is_file():
                continue
            self.allowed_path(evidence_path)
            if evidence_path.stat().st_size > 1_000_000:
                raise ValueError("Provenance file exceeds 1 MB")
            adjacent = json.loads(evidence_path.read_text(encoding="utf-8"))
            self._verify_provenance(adjacent, relative, actual)
            break
        if adjacent is not None:
            if provenance is not None:
                self._check_source_override(adjacent, provenance)
            provenance = {**(provenance or {}), **adjacent}
        elif provenance is not None:
            self._verify_provenance(provenance, source_path.name, actual, require_files=False)
        metadata = analyze_file(source_path, domain=domain, provenance=provenance)
        if metadata["source"]["sha256"] != actual or self._file_hash(source_path) != actual:
            raise ValueError("Source changed during analysis; retry with a stable local file")
        proposal = self._prepare(
            {
                "id": uuid.uuid4().hex[:12],
                "metadata": metadata,
                "revision": 0,
                "created_at": time.time(),
                "observed_evidence": self._observed(metadata),
            }
        )
        with self.connect() as con:
            self._save(con, proposal, "proposed")
        return proposal

    @staticmethod
    def _file_hash(path: Path) -> str:
        result = hashlib.sha256()
        total = 0
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                total += len(block)
                if total > 25 * 1024 * 1024:
                    raise ValueError("File exceeds the 25 MiB analysis limit")
                result.update(block)
        return result.hexdigest()

    @staticmethod
    def _verify_provenance(provenance: dict, relative: str, actual: str, *, require_files: bool = True):
        if not isinstance(provenance, dict):
            raise ValueError("Provenance must be an object")
        records = provenance.get("files")
        if records is not None or require_files:
            if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
                raise ValueError("Provenance files must be a list of file records")
            matches = [item for item in records if item.get("path") == relative]
            if len(matches) != 1:
                raise ValueError("File is not uniquely listed in the adjacent download provenance")
            if matches[0].get("sha256") != actual:
                raise ValueError("Downloaded file changed since provenance was recorded")
        declared = provenance.get("sha256")
        if declared is not None and declared != actual:
            raise ValueError("Explicit source hash does not match the analyzed file")

    @staticmethod
    def _check_source_override(adjacent: dict, supplied: dict):
        def license_value(value):
            return value.get("spdx_id") or value.get("name") if isinstance(value, dict) else value

        def synthetic_value(value):
            return value.get("publisher_claim") if isinstance(value, dict) else value

        checks = {
            "license": license_value,
            "synthetic": synthetic_value,
            "publication_allowed": lambda value: value,
            "dataset_version": lambda value: value,
            "handle": lambda value: value,
        }
        for key, normalise in checks.items():
            if key in supplied and key in adjacent and normalise(supplied[key]) != normalise(adjacent[key]):
                raise ValueError(f"Explicit provenance conflicts with adjacent source evidence: {key}")
        expected_url = adjacent.get("source_url", adjacent.get("url"))
        if expected_url and any(
            supplied.get(key, expected_url) != expected_url for key in ("url", "source_url")
        ):
            raise ValueError("Explicit provenance conflicts with adjacent source URL")

    @staticmethod
    def _expected(proposal: dict, expected_digest: str | None) -> None:
        if expected_digest is not None and (
            not isinstance(expected_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_digest)
        ):
            raise ValueError("expected_digest must be the 64-character SHA-256 of the reviewed revision")
        if expected_digest is not None and proposal["digest"] != expected_digest:
            raise ValueError("Proposal changed; reload and review its current revision")

    @staticmethod
    def _content_digest(proposal: dict) -> str:
        value = {key: proposal[key] for key in ("metadata", "plan", "quality", "revision")}
        if "observed_evidence" in proposal:
            value["observed_evidence"] = proposal["observed_evidence"]
        return digest(value)

    @staticmethod
    def _observed(metadata: dict) -> dict:
        return copy.deepcopy(
            {
                "source": metadata.get("source", {}),
                "profile": metadata.get("profile", {}),
                "pii_flags": metadata.get("pii_flags", []),
                "quality_findings": metadata.get("quality_findings", []),
                "columns": [
                    {
                        key: column[key]
                        for key in ("name", "data_type", "statistics", "pii_flags")
                        if key in column
                    }
                    for column in metadata.get("columns", [])
                ],
            }
        )

    @staticmethod
    def _check_columns(columns: list, baseline: list) -> None:
        if not isinstance(columns, list) or any(not isinstance(column, dict) for column in columns):
            raise ValueError("columns must be a list of observed column objects")
        names = [column.get("name") for column in columns]
        if (
            any(not isinstance(name, str) for name in names)
            or len(set(names)) != len(names)
            or set(names) != {column["name"] for column in baseline}
        ):
            raise ValueError(
                "Observed schema identity cannot be removed, renamed or duplicated; re-analyze a changed source"
            )
        observed = {column["name"]: column for column in baseline}
        for column in columns:
            if any(column.get(key) != value for key, value in observed[column["name"]].items()):
                raise ValueError(
                    "Observed column types, statistics and pii_flags cannot be edited; revise semantic descriptions instead"
                )

    @classmethod
    def _integrity(cls, proposal: dict) -> None:
        try:
            valid = (
                type(proposal["revision"]) is int
                and proposal["revision"] > 0
                and all(isinstance(proposal[key], dict) for key in ("metadata", "plan", "quality"))
                and isinstance(proposal["digest"], str)
                and cls._content_digest(proposal) == proposal["digest"]
            )
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError(
                "Proposal integrity failed; reload and prepare a new revision for human approval"
            )

    @staticmethod
    def _human_text(value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{label} is required and must be a string under {maximum + 1} characters")
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError(f"{label} contains control characters")
        return value.strip()

    @staticmethod
    def _validation_fingerprint(quality: dict) -> str:
        """Bind reviewable validation semantics, excluding volatile report text.

        Finding order is presentation detail; messages, evidence, severity,
        coverage, score and rubric remain material to the human decision.
        """
        if not isinstance(quality, dict) or not isinstance(quality.get("findings"), list):
            raise ValueError("Invalid validation result; rebuild the plan before human approval")
        normalized = {key: quality.get(key) for key in ("score", "conforms", "coverage", "rubric")}
        normalized["findings"] = sorted(quality["findings"], key=digest)
        return digest(normalized)

    @classmethod
    def _check_current_validation(cls, proposal: dict) -> str:
        from .ontology import validate_metadata

        current = validate_metadata(proposal["metadata"])
        if proposal["quality"].get("conforms") is not True or current.get("conforms") is not True:
            raise ValueError(
                "Resolve blocking quality findings under current validation; rebuild the plan before human approval"
            )
        fingerprint = cls._validation_fingerprint(current)
        if cls._validation_fingerprint(proposal["quality"]) != fingerprint:
            raise ValueError(
                "Validation policy/result changed; rebuild the plan and obtain new human approval"
            )
        return fingerprint

    def revise(
        self, proposal_id: str, updates: dict, *, live: bool = False, expected_digest: str | None = None
    ) -> dict:
        if not isinstance(updates, dict):
            raise ValueError("updates must be an object of editable metadata fields")
        if len(json.dumps(updates, allow_nan=False).encode("utf-8")) > 1_000_000:
            raise ValueError("Metadata edits exceed 1 MB")
        allowed = {
            "title",
            "description",
            "domain",
            "owner",
            "license",
            "columns",
            "keywords",
            "synthetic",
            "synthetic_evidence",
            "business_context",
            "limitations",
            "relationships",
            "privacy_reviewed",
            "data_quality_reviewed",
            "concepts",
        }
        if set(updates) - allowed:
            raise ValueError("Unsupported edit; source evidence and hashes cannot be edited")
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            proposal = self._get(con, proposal_id)
            self._expected(proposal, expected_digest)
            if proposal["status"] == "publishing":
                raise ValueError("Publication in progress")
            baseline = proposal.get("observed_evidence") or self._observed(proposal["metadata"])
            if "columns" in updates:
                self._check_columns(updates["columns"], baseline["columns"])
            for flag in ("privacy_reviewed", "data_quality_reviewed"):
                if flag in updates and type(updates[flag]) is not bool:
                    raise ValueError(f"{flag} must be a boolean human review assertion")
            substantive = any(
                value != proposal["metadata"].get(key)
                for key, value in updates.items()
                if key not in {"privacy_reviewed", "data_quality_reviewed"}
            )
            proposal["metadata"].update(copy.deepcopy(updates))
            if substantive:
                proposal["metadata"].update(privacy_reviewed=False, data_quality_reviewed=False)
            proposal["observed_evidence"] = baseline
            self._prepare(proposal, live=live)
            self._save(con, proposal, "revised", f"revision={proposal['revision']}")
        return proposal

    def replan(self, proposal_id: str, *, live: bool = False, expected_digest: str | None = None) -> dict:
        return self.revise(proposal_id, {}, live=live, expected_digest=expected_digest)

    def approve(self, proposal_id: str, expected_digest: str, reviewer: str) -> dict:
        reviewer = self._human_text(reviewer, "Reviewer name", 200)
        if expected_digest is None:
            raise ValueError("expected_digest is required for human approval")
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            proposal = self._get(con, proposal_id)
            self._expected(proposal, expected_digest)
            self._integrity(proposal)
            if proposal["status"] not in {"draft", "rejected", "failed"}:
                raise ValueError("Proposal is not awaiting approval")
            validation_digest = self._check_current_validation(proposal)
            proposal["status"] = "approved"
            proposal["approval"] = {
                "digest": expected_digest,
                "reviewer": reviewer,
                "at": time.time(),
                "validation_policy": VALIDATION_POLICY_VERSION,
                "validation_digest": validation_digest,
                "configuration_generation": con.execute(
                    "SELECT generation FROM configuration_generation WHERE id=1"
                ).fetchone()[0],
            }
            self._save(con, proposal, "approved", reviewer)
        return proposal

    def reject(self, proposal_id: str, reason: str, *, expected_digest: str | None = None) -> dict:
        reason = self._human_text(reason, "A rejection reason", 2000)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            proposal = self._get(con, proposal_id)
            self._expected(proposal, expected_digest)
            if proposal["status"] == "publishing":
                raise ValueError("Publication in progress")
            proposal.update(status="rejected", approval=None)
            self._save(con, proposal, "rejected", reason)
        return proposal

    @contextmanager
    def _publication_lock(self, proposal_id: str):
        if not isinstance(proposal_id, str) or not proposal_id or len(proposal_id) > 128:
            raise ValueError("Invalid proposal ID")
        folder = self.home / "publication-locks"
        folder.mkdir(exist_ok=True)
        lock_path = folder / (hashlib.sha256(proposal_id.encode()).hexdigest() + ".lock")
        with lock_path.open("a+b") as stream:
            stream.seek(0)
            locked = False
            try:
                try:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    if os.fstat(stream.fileno()).st_size == 0:
                        stream.write(b"0")
                        stream.flush()
                except OSError:
                    raise ValueError(
                        "Publication in progress; inspect its state before any new human approval"
                    ) from None
                yield
            finally:
                if locked:
                    stream.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def recover_publication(self, proposal_id: str, expected_digest: str, reason: str) -> dict:
        """Human-only recovery after a stopped process; never retries cloud work.

        Kernel locks prevent recovery while an actual publisher still runs. A
        released lock does not prove a remote request had no effect: the new
        revision requires remote inspection, a live plan and fresh approval.
        """
        reason = self._human_text(reason, "Recovery reason", 2000)
        if expected_digest is None:
            raise ValueError("expected_digest is required for publication recovery")
        with self._publication_lock(proposal_id), self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            proposal = self._get(con, proposal_id)
            self._expected(proposal, expected_digest)
            self._integrity(proposal)
            if proposal["status"] != "publishing":
                raise ValueError("Only an interrupted publishing proposal can be recovered")
            publication = copy.deepcopy(proposal.get("publication", {}))
            self._prepare(proposal, live=False)
            proposal.update(status="failed", approval=None)
            proposal["publication"] = {
                **publication,
                "recovered_at": time.time(),
                "recovery_reason": reason,
                "outcome": "unknown; inspect remote state and prepare a new live plan",
            }
            self._save(con, proposal, "publication_recovered", reason)
        return proposal

    def publish(self, proposal_id: str, *, expected_digest: str | None = None) -> dict:
        with self._publication_lock(proposal_id):
            return self._publish(proposal_id, expected_digest=expected_digest)

    def _publish(self, proposal_id: str, *, expected_digest: str | None = None) -> dict:
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            config = self.config()
            if not config["writes_enabled"] or config["project"] not in config["allowed_projects"]:
                raise ValueError("Cloud writes are disabled. Configure an explicitly allowed project first")
            proposal = self._get(con, proposal_id)
            self._expected(proposal, expected_digest)
            self._integrity(proposal)
            approval = proposal.get("approval") or {}
            actual_digest = self._content_digest(proposal)
            if (
                proposal["status"] != "approved"
                or not isinstance(approval, dict)
                or approval.get("digest") != actual_digest
            ):
                raise ValueError("The current metadata and plan need human approval")
            approved_at = approval.get("at")
            if (
                type(approved_at) not in (int, float)
                or not math.isfinite(approved_at)
                or approved_at < 0
                or approved_at > time.time() + 60
                or not isinstance(approval.get("reviewer"), str)
                or not approval["reviewer"].strip()
            ):
                raise ValueError("Invalid human approval record; review and approve again")
            if time.time() - approval["at"] > config["approval_ttl_seconds"]:
                raise ValueError("Approval expired; review and approve again")
            validation_digest = self._check_current_validation(proposal)
            if (
                approval.get("validation_policy") != VALIDATION_POLICY_VERSION
                or approval.get("validation_digest") != validation_digest
            ):
                raise ValueError(
                    "Approval lacks the current validation policy binding; rebuild the plan and obtain new human approval"
                )
            plan = proposal["plan"]
            if plan["project"] != config["project"] or plan["location"] != config["location"]:
                raise ValueError("Target changed; rebuild and approve the plan")
            generation = con.execute("SELECT generation FROM configuration_generation WHERE id=1").fetchone()[
                0
            ]
            if approval.get("configuration_generation") != generation:
                raise ValueError("Configuration changed since human approval; rebuild and approve the plan")
            if plan["snapshot"]["mode"] != "verified":
                raise ValueError("Offline preview cannot be published; build a live plan and approve it")
            client = self.client()
            if self.config() != config:
                raise ValueError("Configuration changed while preparing publication; review the target again")
            proposal["status"] = "publishing"
            attempt = uuid.uuid4().hex
            proposal["publication"] = {"attempt": attempt, "started_at": time.time()}
            self._save(con, proposal, "publishing")
        try:
            if self.config() != config:
                raise ValueError("Configuration changed before the cloud request; publication stopped")
            result = client.apply_plan(plan)
            if (
                not isinstance(result, dict)
                or result.get("status") not in {"published", "unchanged"}
                or result.get("target") != plan["target"]
            ):
                raise ValueError("Catalog transport did not confirm publication of the approved target")
        except Exception as exc:
            with self.connect() as con:
                con.execute("BEGIN IMMEDIATE")
                current = self._get(con, proposal_id)
                if (
                    current.get("status") == "publishing"
                    and current.get("publication", {}).get("attempt") == attempt
                ):
                    current.update(status="failed", approval=None)
                    current["publication"]["finished_at"] = time.time()
                    self._save(con, current, "publication_failed", type(exc).__name__)
            raise
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            current = self._get(con, proposal_id)
            if (
                current.get("status") != "publishing"
                or current.get("publication", {}).get("attempt") != attempt
            ):
                raise ValueError(
                    "Publication state changed; inspect the remote result before recovering locally"
                )
            current.update(status="published", result=result, approval=None)
            current["publication"]["finished_at"] = time.time()
            self._save(con, current, "published")
        return current
