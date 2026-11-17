#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Import bounded human/model semantic review proposals as draft findings.

This local helper checks proposal structure and exact source quotations. It does
not determine truth, resolve disagreement, call a model, or change either graph.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

sys.dont_write_bytecode = True

import semantic_model as core
import repository_graph as graph
import render_repository_review as renderer

VERSION = "1.0.1"
MAX_REPORT_BYTES = 32_000_000
MAX_PROPOSALS_BYTES = 8_000_000
MAX_LOCATOR_BYTES = 4096
MAX_TOTAL_EVIDENCE_BYTES = 16_000_000
MAX_FINDINGS = 5000
MAX_SOURCES_PER_FINDING = 20
MAX_TOTAL_CITATIONS = 20_000
MAX_QUOTE_CHARS = 20_000
MAX_TOTAL_QUOTE_CHARS = 2_000_000
MAX_FIELD_VALUE_BYTES = 65_536
MAX_POINTER_DEPTH = 64
MAX_TOTAL_FIELD_VALUE_BYTES = 2_000_000
MAX_OUTPUT_BYTES = 96_000_000
MAX_TEXT_CHARS = 4000
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TOP_KEYS = {"schema_version", "parent_review_revision", "reviewer", "findings"}
REVIEWER_KEYS = {"kind", "id", "artifact_sha256"}
FINDING_KEYS = {"proposal_id", "side", "collection", "entity_id", "field_pointer",
                "category", "summary", "uncertainty", "sources"}
SOURCE_KEYS = {"source_id", "quote"}
CATEGORIES = {"source_support", "scope", "identity", "modality", "representation", "other"}


class ImportErrorDetail(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ImportErrorDetail(code, message)


def _keys(obj: Any, expected: set[str], code: str, label: str) -> None:
    _require(isinstance(obj, dict), code, f"{label} must be a JSON object")
    missing = expected - set(obj)
    extra = set(obj) - expected
    _require(not missing and not extra, code,
             f"{label} keys mismatch; missing={sorted(missing)}, unknown={sorted(extra)}")


def _nonempty_string(value: Any, label: str, maximum: int = MAX_TEXT_CHARS) -> str:
    _require(isinstance(value, str) and bool(value.strip()), "INVALID_PROPOSAL",
             f"{label} must be a nonempty string")
    _require(len(value) <= maximum, "INPUT_LIMIT", f"{label} exceeds {maximum} characters")
    return value


def _decode_pointer(pointer: str) -> list[str]:
    _require(isinstance(pointer, str), "INVALID_FIELD_POINTER", "field_pointer must be a string")
    _require(pointer == "" or pointer.startswith("/"), "INVALID_FIELD_POINTER",
             "field_pointer must be empty for the whole record or begin with '/'")
    parts = [] if pointer == "" else pointer[1:].split("/")
    _require(len(parts) <= MAX_POINTER_DEPTH, "INVALID_FIELD_POINTER",
             f"field_pointer exceeds {MAX_POINTER_DEPTH} path segments")
    decoded = []
    for part in parts:
        i = 0
        out = ""
        while i < len(part):
            if part[i] != "~":
                out += part[i]
                i += 1
                continue
            _require(i + 1 < len(part) and part[i + 1] in "01", "INVALID_FIELD_POINTER",
                     "field_pointer contains an invalid RFC 6901 escape")
            out += "~" if part[i + 1] == "0" else "/"
            i += 2
        decoded.append(out)
    return decoded


def _pointer_value(record: Any, pointer: str) -> Any:
    value = record
    for part in _decode_pointer(pointer):
        if isinstance(value, dict):
            _require(part in value, "INVALID_FIELD_POINTER", f"field_pointer does not identify an existing field: {pointer}")
            value = value[part]
        elif isinstance(value, list):
            _require(bool(part) and all(char in "0123456789" for char in part) and len(part) <= 10 and str(int(part)) == part and int(part) < len(value),
                     "INVALID_FIELD_POINTER", f"field_pointer does not identify an existing array item: {pointer}")
            value = value[int(part)]
        else:
            raise ImportErrorDetail("INVALID_FIELD_POINTER", f"field_pointer traverses a scalar value: {pointer}")
    return value


def _validate_proposals(parent: dict[str, Any], proposals: Any, graph_module: Any) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    _keys(proposals, TOP_KEYS, "INVALID_PROPOSALS", "Proposal document")
    _require(proposals.get("schema_version") == "1", "INVALID_PROPOSALS", "Unsupported proposal schema_version")
    _require(proposals.get("parent_review_revision") == parent["review_revision"],
             "STALE_PARENT", "Proposal parent_review_revision does not match this parent report")
    reviewer = proposals.get("reviewer")
    _keys(reviewer, REVIEWER_KEYS, "INVALID_REVIEWER", "reviewer")
    _require(reviewer.get("kind") in ("human", "model"), "INVALID_REVIEWER", "reviewer.kind must be human or model")
    _nonempty_string(reviewer.get("id"), "reviewer.id", 200)
    _require(isinstance(reviewer.get("artifact_sha256"), str) and SHA256.fullmatch(reviewer["artifact_sha256"]) is not None,
             "INVALID_REVIEWER", "reviewer.artifact_sha256 must be lowercase SHA-256 hex")
    rows = proposals.get("findings")
    _require(isinstance(rows, list) and 1 <= len(rows) <= MAX_FINDINGS, "INVALID_PROPOSALS",
             f"findings must contain 1 to {MAX_FINDINGS} items")
    side_indexes: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for side in ("base", "head"):
        side_model = parent[side]["model"]
        side_indexes[side] = {}
        for collection in ("nodes", "relations", "sources"):
            side_indexes[side][collection] = {record["id"]: record for record in side_model[collection]}
    proposal_ids: set[str] = set()
    normalized = []
    total_citations = 0
    total_quote_chars = 0
    total_field_value_bytes = 0
    source_fingerprints: dict[tuple[str, str], tuple[str, str]] = {}
    source_locator_cache: dict[tuple[str, str], str] = {}
    field_value_sizes: dict[tuple[str, str, str, str], int] = {}
    total_evidence_bytes = 0
    for row in rows:
        _keys(row, FINDING_KEYS, "INVALID_PROPOSAL", "finding")
        proposal_id = _nonempty_string(row.get("proposal_id"), "proposal_id", 200)
        _require(proposal_id not in proposal_ids, "DUPLICATE_PROPOSAL_ID", f"Duplicate proposal_id: {proposal_id}")
        proposal_ids.add(proposal_id)
        side, collection = row.get("side"), row.get("collection")
        _require(side in ("base", "head"), "INVALID_PROPOSAL", "side must be base or head")
        _require(collection in ("nodes", "relations"), "INVALID_PROPOSAL", "collection must be nodes or relations")
        entity_id = _nonempty_string(row.get("entity_id"), "entity_id", 500)
        record = side_indexes[side][collection].get(entity_id)
        _require(record is not None, "UNKNOWN_ENTITY", f"Unknown {side}.{collection} entity: {entity_id}")
        pointer = row.get("field_pointer")
        _require(isinstance(pointer, str) and len(pointer) <= 2048, "INVALID_FIELD_POINTER",
                 "field_pointer must be a string of at most 2048 characters")
        current_value = _pointer_value(record, pointer)
        field_key = (side, collection, entity_id, pointer)
        if field_key not in field_value_sizes:
            field_value_sizes[field_key] = len(graph_module.canonical_bytes(current_value))
        current_value_size = field_value_sizes[field_key]
        _require(current_value_size <= MAX_FIELD_VALUE_BYTES, "FIELD_VALUE_LIMIT",
                 f"Current field value exceeds {MAX_FIELD_VALUE_BYTES} serialized bytes")
        total_field_value_bytes += current_value_size
        _require(total_field_value_bytes <= MAX_TOTAL_FIELD_VALUE_BYTES, "INPUT_LIMIT",
                 f"Imported field values exceed {MAX_TOTAL_FIELD_VALUE_BYTES} total serialized bytes")
        current_value = copy.deepcopy(current_value)
        category = row.get("category")
        _require(isinstance(category, str) and category in CATEGORIES,
                 "INVALID_PROPOSAL", "Unknown semantic review category")
        summary = _nonempty_string(row.get("summary"), "summary")
        uncertainty = _nonempty_string(row.get("uncertainty"), "uncertainty")
        citations = row.get("sources")
        _require(isinstance(citations, list) and 1 <= len(citations) <= MAX_SOURCES_PER_FINDING,
                 "INVALID_EVIDENCE", f"sources must contain 1 to {MAX_SOURCES_PER_FINDING} exact citations")
        evidence = []
        seen_citations = set()
        total_citations += len(citations)
        _require(total_citations <= MAX_TOTAL_CITATIONS, "INPUT_LIMIT",
                 f"Proposal citations exceed the {MAX_TOTAL_CITATIONS} item limit")
        for citation in citations:
            _keys(citation, SOURCE_KEYS, "INVALID_EVIDENCE", "source citation")
            source_id = _nonempty_string(citation.get("source_id"), "source_id", 500)
            quote = _nonempty_string(citation.get("quote"), "quote", MAX_QUOTE_CHARS)
            key = (source_id, quote)
            _require(key not in seen_citations, "DUPLICATE_EVIDENCE", "Duplicate source citation")
            seen_citations.add(key)
            source = side_indexes[side]["sources"].get(source_id)
            if source is None:
                other_side = "head" if side == "base" else "base"
                if source_id in side_indexes[other_side]["sources"]:
                    raise ImportErrorDetail("CROSS_SIDE_EVIDENCE", f"Citation {source_id} exists only on {other_side}, not {side}")
                raise ImportErrorDetail("UNKNOWN_SOURCE", f"Unknown {side} source_id: {source_id}")
            text = source.get("text")
            _require(isinstance(text, str) and quote in text, "QUOTE_NOT_IN_SOURCE",
                     f"Quote for {source_id} is not an exact substring of the {side} source text")
            total_quote_chars += len(quote)
            _require(total_quote_chars <= MAX_TOTAL_QUOTE_CHARS, "INPUT_LIMIT",
                     f"Exact quoted evidence exceeds {MAX_TOTAL_QUOTE_CHARS} total characters")
            cache_key = (side, source_id)
            if cache_key not in source_fingerprints:
                source_fingerprints[cache_key] = (graph_module.digest(source), sha256(text.encode("utf-8")))
                locator = source.get("locator")
                _require(isinstance(locator, str), "INVALID_SOURCE", "Source locator must be a string")
                locator_bytes = len(locator.encode("utf-8"))
                _require(locator_bytes <= MAX_LOCATOR_BYTES, "EVIDENCE_LOCATOR_LIMIT",
                         f"Source locator exceeds {MAX_LOCATOR_BYTES} UTF-8 bytes")
                source_locator_cache[cache_key] = locator
            source_fingerprint, source_text_sha = source_fingerprints[cache_key]
            locator = source_locator_cache[cache_key]
            evidence_item = {"side": side, "source_id": source_id, "locator": locator,
                             "quote": quote, "source_fingerprint": source_fingerprint,
                             "source_text_sha256": source_text_sha}
            evidence_bytes = len(graph_module.canonical_bytes(evidence_item))
            total_evidence_bytes += evidence_bytes
            _require(total_evidence_bytes <= MAX_TOTAL_EVIDENCE_BYTES, "EVIDENCE_TOTAL_LIMIT",
                     f"Serialized proposal evidence exceeds {MAX_TOTAL_EVIDENCE_BYTES} bytes")
            evidence.append(evidence_item)
        normalized.append({"proposal_id": proposal_id, "side": side, "collection": collection,
                           "entity_id": entity_id, "field_pointer": pointer, "category": category,
                           "summary": summary, "uncertainty": uncertainty,
                           "sources": sorted(evidence, key=lambda item: (item["source_id"], item["quote"])) ,
                           "current_value": current_value})
    normalized.sort(key=lambda item: item["proposal_id"])
    normalized_payload = {"schema_version": "1", "parent_review_revision": proposals["parent_review_revision"],
                          "reviewer": copy.deepcopy(reviewer), "findings": normalized}
    return normalized, copy.deepcopy(reviewer), graph_module.digest(normalized_payload)


def import_proposals(parent: dict[str, Any], proposals: dict[str, Any], proposal_file_sha256: str,
                     *, core_module: Any = core, graph_module: Any = graph,
                     renderer_module: Any = renderer) -> dict[str, Any]:
    _require(isinstance(parent, dict), "INVALID_PARENT", "Parent report must be an object")
    renderer_module.validate_report(parent)
    parent_revision = parent.get("review_revision")
    parent_payload = {key: value for key, value in parent.items() if key != "review_revision"}
    _require(graph_module.digest(parent_payload) == parent_revision, "STALE_PARENT",
             "Parent review_revision failed recomputation")
    _require("semantic_review_overlay" not in parent, "ALREADY_OVERLAID",
             "Refusing to append proposals to a report that already has a semantic overlay")
    _require(isinstance(proposal_file_sha256, str) and SHA256.fullmatch(proposal_file_sha256) is not None,
             "INVALID_PROPOSALS", "proposal_file_sha256 must be lowercase SHA-256 hex")
    normalized, reviewer, normalized_digest = _validate_proposals(parent, proposals, graph_module)
    report = copy.deepcopy(parent)
    previous_findings = len(report["findings"])
    overlay_findings = []
    for item in normalized:
        payload = {
            "code": "SEMANTIC_REVIEW_PROPOSAL", "severity": "warning", "classification": "proposed",
            "historical": False, "policy_scope": "unvalidated_semantic_review",
            "message": item["summary"],
            "proposal_id": item["proposal_id"], "reviewer": reviewer,
            "parent_review_revision": parent_revision,
            "normalized_proposals_sha256": normalized_digest,
            "target": {"side": item["side"], "collection": item["collection"],
                       "entity_id": item["entity_id"], "field_pointer": item["field_pointer"],
                       "field_value": item["current_value"]},
            "category": item["category"], "uncertainty": item["uncertainty"],
            "diagnostic": {"side": item["side"], "collection": item["collection"],
                           "entity_id": item["entity_id"], "field_pointer": item["field_pointer"],
                           "current_value": item["current_value"], "category": item["category"],
                           "uncertainty": item["uncertainty"]},
            "evidence": item["sources"],
            "options": ["inspect_evidence", "revise_candidate", "request_evidence", "defer"],
        }
        # The current renderer's Inspect button resolves IDs node-first. When
        # an ID exists in both record namespaces, keep the exact typed anchor
        # in target/diagnostic and omit the ambiguous button target.
        other_collection = "relations" if item["collection"] == "nodes" else "nodes"
        collides = any(any(row.get("id") == item["entity_id"] for row in parent[side]["model"][other_collection])
                       for side in ("base", "head"))
        if not collides:
            payload["entity_id"] = item["entity_id"]
        finding = graph_module.identified("finding", payload)
        collision = any(old.get("id") == finding["id"] for old in report["findings"] + overlay_findings)
        _require(not collision, "FINGERPRINT_COLLISION", "Imported proposal fingerprint collides with an existing finding")
        overlay_findings.append(finding)
    report["findings"].extend(overlay_findings)
    report["semantic_status"] = "proposals_imported_unvalidated"
    report["semantic_review_overlay"] = {
        "schema_version": "1", "status": "unvalidated_proposals_only",
        "importer_version": VERSION, "parent_review_revision": parent_revision,
        "proposal_file_sha256": proposal_file_sha256,
        "normalized_proposals_sha256": normalized_digest,
        "reviewer": reviewer,
        "proposal_ids": [item["proposal_id"] for item in normalized],
        "ordering_policy": "Findings are normalized and emitted in proposal_id order; exact proposal-file SHA remains provenance, so reordered source files yield a different imported report revision.",
    }
    summary = report.get("summary")
    _require(isinstance(summary, dict), "INVALID_PARENT", "Parent summary must be an object")
    summary["preexisting_findings"] = previous_findings
    summary["findings"] = len(report["findings"])
    summary["semantic_proposals"] = len(overlay_findings)
    # Structural validation counts remain exactly as generated by the parent.
    report.pop("review_revision", None)
    report["review_revision"] = graph_module.digest(report)
    renderer_module.validate_report(report)
    return report


def load_json(path: Path, max_bytes: int, core_module: Any = core) -> tuple[Any, bytes]:
    try:
        size = path.stat().st_size
        _require(size <= max_bytes, "INPUT_LIMIT", f"Input exceeds {max_bytes} bytes: {path}")
        with path.open("rb") as stream:
            raw = stream.read(max_bytes + 1)
        _require(len(raw) <= max_bytes, "INPUT_LIMIT", f"Input exceeds {max_bytes} bytes: {path}")
        text = raw.decode("utf-8-sig")
        value = core_module._parse_json_text(text, path)
    except Exception as exc:
        if isinstance(exc, ImportErrorDetail):
            raise
        raise ImportErrorDetail(getattr(exc, "code", "INVALID_JSON"), f"Could not read strict JSON {path}: {exc}") from exc
    return value, raw


def _resolved_output(path: Path, inputs: list[Path], skill_root: Path) -> Path:
    # Inspect the requested leaf before resolving it: resolve() follows a
    # dangling or live symlink and would otherwise turn it into a new target.
    is_junction = getattr(path, "is_junction", lambda: False)()
    try:
        leaf_stat = path.lstat()
    except OSError:
        leaf_stat = None
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    is_windows_reparse = (os.name == "nt" and leaf_stat is not None and
                          bool(getattr(leaf_stat, "st_file_attributes", 0) & reparse_flag))
    _require(not path.is_symlink() and not is_junction and not is_windows_reparse, "OUTPUT_SYMLINK",
             f"Output path must not be a symlink or junction: {path}")
    target = path.resolve()
    _require(target.parent.is_dir(), "OUTPUT_PARENT", f"Output parent directory must already exist: {target.parent}")
    _require(not target.exists(), "OUTPUT_EXISTS", f"Output must be a new path: {target}")
    _require(not target.is_relative_to(skill_root.resolve()), "OUTPUT_IN_BUNDLE",
             "Outputs must remain outside the installed skill bundle")
    for source in inputs:
        source = source.resolve()
        try:
            same = os.path.samefile(target, source)
        except OSError:
            same = False
        _require(not same and os.path.normcase(str(target)) != os.path.normcase(str(source)),
                 "OUTPUT_ALIASES_INPUT", f"Output aliases an input: {source}")
    return target


def _write_new(path: Path, data: bytes) -> None:
    created = False
    try:
        with path.open("xb") as stream:
            created = True
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        if created:
            try:
                path.unlink()
            except OSError:
                pass
        raise ImportErrorDetail("OUTPUT_ERROR", f"Could not create {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="Parent repository-graph review JSON")
    parser.add_argument("--proposals", type=Path, required=True, help="Strict schema_version 1 proposal JSON")
    parser.add_argument("--output", type=Path, required=True, help="New imported review JSON path")
    parser.add_argument("--html", type=Path, help="Optional new offline review HTML path")
    args = parser.parse_args(argv)
    outputs: list[Path] = []
    try:
        report_path, proposal_path = args.report.resolve(), args.proposals.resolve()
        report, report_raw = load_json(report_path, MAX_REPORT_BYTES)
        proposals, proposal_raw = load_json(proposal_path, MAX_PROPOSALS_BYTES)
        skill_root = Path(__file__).resolve().parents[1]
        output_json = _resolved_output(args.output, [report_path, proposal_path], skill_root)
        outputs.append(output_json)
        output_html = _resolved_output(args.html, [report_path, proposal_path, output_json], skill_root) if args.html else None
        if output_html:
            outputs.append(output_html)
        imported = import_proposals(report, proposals, sha256(proposal_raw))
        json_bytes_out = graph.canonical_bytes(imported)
        html_bytes = renderer.render_report(imported).encode("utf-8") if output_html else None
        output_size = len(json_bytes_out) + (len(html_bytes) if html_bytes is not None else 0)
        _require(output_size <= MAX_OUTPUT_BYTES, "OUTPUT_LIMIT",
                 f"Imported JSON and HTML exceed {MAX_OUTPUT_BYTES} combined bytes")
        written = []
        try:
            _write_new(output_json, json_bytes_out)
            written.append(output_json)
            if output_html is not None and html_bytes is not None:
                _write_new(output_html, html_bytes)
                written.append(output_html)
        except Exception:
            for path in written:
                try:
                    path.unlink()
                except OSError:
                    pass
            raise
        print(json.dumps({"engine_status": "completed", "semantic_status": imported["semantic_status"],
                          "proposals": imported["summary"]["semantic_proposals"],
                          "review_revision": imported["review_revision"],
                          "outputs": [str(path) for path in outputs]}, ensure_ascii=True))
        return 0
    except Exception as exc:
        print(json.dumps({"engine_status": "error", "errors": [{
            "code": getattr(exc, "code", "IMPORT_ERROR"), "message": str(exc)}]}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
