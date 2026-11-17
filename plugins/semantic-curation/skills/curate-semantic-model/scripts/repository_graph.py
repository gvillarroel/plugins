#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Canonical local snapshots and evidence-linked changes between repository models.

The graph digest identifies a declared JSON projection, not logical equivalence,
natural-language truth, or reproducible model inference. No network/model calls.
"""
import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import semantic_model as core

VERSION = "1.0.3"


def canonical_bytes(value):
    """Stable UTF-8 JSON bytes, including one LF; arbitrary arrays stay ordered."""
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, OverflowError, UnicodeError) as exc:
        raise core.EngineError("INVALID_JSON_VALUE", str(exc)) from exc


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def canonical_json_equal(left, right):
    """Compare JSON by the exact serialization used in canonical model hashes."""
    return canonical_bytes(left) == canonical_bytes(right)


def sorted_strings(value):
    # Keep duplicates: normalizing order must never repair invalid provenance.
    return sorted(value) if core.string_list(value) else copy.deepcopy(value)


def canonical_model(model):
    """Normalize declared set-valued fields, preserving record identity and data."""
    core.require(isinstance(model, dict), "Model must be an object", code="MODEL_PARSE_ERROR")
    result = copy.deepcopy(model)
    for collection in ("sources", "nodes", "relations"):
        rows = result.get(collection)
        core.require(isinstance(rows, list), "Model collections must be arrays",
                     "/" + collection, "AMBIGUOUS_IDENTITY")
        core.require(all(isinstance(row, dict) and core.nonempty(row.get("id")) for row in rows),
                     "Every record needs a nonempty string ID", "/" + collection,
                     "AMBIGUOUS_IDENTITY")
        ids = [row["id"] for row in rows]
        core.require(len(ids) == len(set(ids)), "Duplicate IDs prevent an unambiguous comparison",
                     "/" + collection, "AMBIGUOUS_IDENTITY")
        result[collection] = sorted(rows, key=lambda row: row["id"])
        if collection in ("nodes", "relations"):
            for row in result[collection]:
                if "source_ids" in row:
                    row["source_ids"] = sorted_strings(row["source_ids"])
                if collection == "nodes" and "aliases" in row:
                    row["aliases"] = sorted_strings(row["aliases"])
    if isinstance(result.get("bindings"), dict):
        result["bindings"] = {key: sorted_strings(value)
                              for key, value in sorted(result["bindings"].items())}
    # history, attributes and extra source metadata can contain meaningful arrays.
    return json.loads(canonical_bytes(result))


def canonical_contract(contract):
    """Normalize only the contract language's explicit unordered ID lists."""
    core.check_contract(contract)
    result = copy.deepcopy(contract)
    for profile in result["types"].values():
        if "required_attributes" in profile:
            profile["required_attributes"] = sorted_strings(profile["required_attributes"])
        for spec in profile.get("attributes", {}).values():
            if "node_reference_types" in spec:
                spec["node_reference_types"] = sorted_strings(spec["node_reference_types"])
    for rule in result["relations"].values():
        for field in ("from_types", "to_types", "exclusive_with"):
            if field in rule:
                rule[field] = sorted_strings(rule[field])
    if "checks" in result:
        result["checks"] = sorted(result["checks"], key=lambda row: row["id"])
        for check in result["checks"]:
            check["expect"] = sorted_strings(check["expect"])
    # Sorting mappings also makes validation traversal stable for direct API callers.
    return json.loads(canonical_bytes(result))


def graph_projection(model):
    """Content graph: IDs, labels, definitions, types and attributes, sans evidence."""
    return {
        "nodes": [{key: value for key, value in row.items() if key != "source_ids"}
                  for row in model["nodes"]],
        "relations": [{key: value for key, value in row.items()
                       if key not in ("source_ids", "review")}
                      for row in model["relations"]],
    }


def build_snapshot(model, contract):
    normalized, policy = canonical_model(model), canonical_contract(contract)
    validation = core.validate(normalized, policy)
    return {
        "schema_version": "1", "tool": "repository-graph", "tool_version": VERSION,
        "engine_status": "completed", "semantic_status": "not_run",
        "model_sha256": digest(normalized), "contract_sha256": digest(policy),
        "graph_sha256": digest(graph_projection(normalized)),
        "hash_scope": "Declared JSON graph including IDs, labels, definitions and attributes; excludes source_ids, relation review, sources, bindings, metadata and history. Not logical equivalence.",
        "model": normalized, "contract": policy, "validation": validation,
    }


def identified(prefix, payload):
    fingerprint = digest(payload)
    return {"id": prefix + ":" + fingerprint[:24], "fingerprint": fingerprint, **payload}


def change(kind, collection, entity_id, before, after, field=None, *,
           base_present=None, head_present=None,
           base_present_fields=None, head_present_fields=None):
    payload = {"kind": kind, "collection": collection, "entity_id": entity_id,
               "before": copy.deepcopy(before), "after": copy.deepcopy(after)}
    if field is not None:
        payload["field"] = field
    if (base_present is not None and head_present is not None
            and base_present != head_present):
        payload["base_present"] = base_present
        payload["head_present"] = head_present
    if (base_present_fields is not None and head_present_fields is not None
            and base_present_fields != head_present_fields):
        payload["base_present_fields"] = sorted(base_present_fields)
        payload["head_present_fields"] = sorted(head_present_fields)
    return identified("change", payload)


def record_changes(base, head):
    changes = []
    node_kinds = {"label": "node_renamed", "definition": "definition_changed",
                  "type": "type_changed", "attributes": "attributes_changed",
                  "aliases": "aliases_changed", "source_ids": "node_evidence_changed"}
    for collection, noun in (("nodes", "node"), ("relations", "relation"), ("sources", "source")):
        old = {row["id"]: row for row in base[collection]}
        new = {row["id"]: row for row in head[collection]}
        for entity_id in sorted(set(old) | set(new)):
            if entity_id not in old:
                changes.append(change(noun + "_added", collection, entity_id, None, new[entity_id]))
            elif entity_id not in new:
                changes.append(change(noun + "_removed", collection, entity_id, old[entity_id], None))
            elif not canonical_json_equal(old[entity_id], new[entity_id]):
                if collection == "nodes":
                    left, right = old[entity_id], new[entity_id]
                    for field in sorted((set(left) | set(right)) - {"id"}):
                        if field not in left or field not in right or not canonical_json_equal(left[field], right[field]):
                            changes.append(change(node_kinds.get(field, "node_changed"), collection,
                                                  entity_id, left, right, field,
                                                  base_present=field in left,
                                                  head_present=field in right))
                else:
                    left, right = old[entity_id], new[entity_id]
                    changes.append(change(noun + "_changed", collection, entity_id, left, right,
                                          base_present_fields=set(left), head_present_fields=set(right)))
    left, right = base.get("bindings", {}), head.get("bindings", {})
    if (("bindings" in base) != ("bindings" in head)
            or not canonical_json_equal(left, right)):
        changes.append(change("bindings_changed", "bindings", "bindings", left, right,
                              base_present="bindings" in base, head_present="bindings" in head))
    for field in ("metadata", "history"):
        if (field in base) != (field in head) or not canonical_json_equal(base.get(field), head.get(field)):
            changes.append(change(field + "_changed", field, field, base.get(field), head.get(field),
                                  base_present=field in base, head_present=field in head))
    handled = {"sources", "nodes", "relations", "bindings", "metadata", "history"}
    for field in sorted((set(base) | set(head)) - handled):
        if (field in base) != (field in head) or not canonical_json_equal(base.get(field), head.get(field)):
            changes.append(change("model_field_changed", "model", field, base.get(field), head.get(field), field,
                                  base_present=field in base, head_present=field in head))
    return changes


def evidence_for(model, entity_id, side, diagnostic=None):
    source_map = {row["id"]: row for row in model["sources"]}
    node_map = {row["id"]: row for row in model["nodes"]}
    relation_map = {row["id"]: row for row in model["relations"]}
    path = (diagnostic or {}).get("path", "")
    # IDs are unique within each collection; equal IDs across collections are valid.
    records = relation_map if path.startswith("/relations/") else node_map
    source_ids = set()
    if entity_id in source_map and (path.startswith(("/sources/", "/bindings/")) or entity_id not in records):
        source_ids.add(entity_id)
    record = records.get(entity_id, {})
    if core.string_list(record.get("source_ids", [])):
        source_ids.update(record.get("source_ids", []))
    # Cycles and global competency diagnostics may name several affected nodes.
    actual = (diagnostic or {}).get("actual")
    if isinstance(actual, list):
        for value in actual:
            if isinstance(value, str) and value in node_map and core.string_list(node_map[value].get("source_ids", [])):
                source_ids.update(node_map[value].get("source_ids", []))
    return [{"source_id": sid, "side": side, "locator": source_map[sid].get("locator"),
             "text": source_map[sid].get("text"), "source_fingerprint": digest(source_map[sid])}
            for sid in sorted(source_ids) if sid in source_map]


def diagnostic_key(item):
    return digest({key: value for key, value in item.items() if key != "severity"})


def validation_findings(base, head):
    findings = []
    old = {diagnostic_key(row): row for row in base["validation"]["errors"]}
    new = {diagnostic_key(row): row for row in head["validation"]["errors"]}
    for fingerprint in sorted(set(old) | set(new)):
        status = "historical" if fingerprint in old and fingerprint in new else "new" if fingerprint in new else "resolved"
        diagnostic = new.get(fingerprint, old.get(fingerprint))
        entity_id = diagnostic.get("entity") or diagnostic.get("path")
        evidence = []
        if fingerprint in old:
            evidence.extend(evidence_for(base["model"], entity_id, "base", diagnostic))
        if fingerprint in new:
            evidence.extend(evidence_for(head["model"], entity_id, "head", diagnostic))
        findings.append(identified("finding", {
            "code": diagnostic["code"], "severity": "info" if status == "resolved" else diagnostic["severity"],
            "classification": status, "historical": fingerprint in old,
            "entity_id": entity_id, "message": diagnostic["message"],
            "diagnostic": diagnostic, "evidence": evidence,
            "options": ["inspect_evidence", "revise_candidate", "revise_contract", "defer"],
        }))
    return findings


def competency_deltas(base, head):
    checks = []
    outcomes = [{row["id"]: row for row in state["validation"]["competency_checks"]}
                for state in (base, head)]
    for test in base["contract"].get("checks", []):
        before, after = (rows.get(test["id"]) for rows in outcomes)
        complete = before is not None and after is not None
        entry = {"id": test["id"], "status": "completed" if complete else "not_run",
                 "before": before["actual"] if before else None,
                 "after": after["actual"] if after else None,
                 "changed": not core.exact_json_equal(before["actual"], after["actual"]) if complete else None,
                 "expected": sorted(set(test["expect"])),
                 "base_passed": before["passed"] if before else None,
                 "head_passed": after["passed"] if after else None,
                 "base_status": "completed" if before else "not_run",
                 "head_status": "completed" if after else "not_run"}
        if not complete:
            entry["reason"] = "Structural validation prevented competency execution for at least one state."
        checks.append(entry)
    return checks


def compare_models(base_model, head_model, contract, head_contract=None):
    """Validate both states against historical policy, then report full state changes."""
    base, head = build_snapshot(base_model, contract), build_snapshot(head_model, contract)
    changes = record_changes(base["model"], head["model"])
    findings = validation_findings(base, head)
    if head_contract is not None:
        proposed = build_snapshot(head_model, head_contract)
        head["proposed_contract"] = proposed["contract"]
        head["proposed_contract_sha256"] = proposed["contract_sha256"]
        head["proposed_validation"] = proposed["validation"]
        for diagnostic in proposed["validation"]["errors"]:
            entity_id = diagnostic.get("entity") or diagnostic.get("path")
            findings.append(identified("finding", {
                "code": diagnostic["code"], "severity": diagnostic["severity"],
                "classification": "new", "historical": False, "policy_scope": "proposed",
                "entity_id": entity_id, "message": diagnostic["message"],
                "diagnostic": diagnostic,
                "evidence": evidence_for(head["model"], entity_id, "head", diagnostic),
                "options": ["inspect_evidence", "revise_candidate", "revise_contract", "defer"],
            }))
        if proposed["contract_sha256"] != base["contract_sha256"]:
            changes.append(change("contract_changed", "contract", contract["id"], base["contract"], proposed["contract"]))
            findings.append(identified("finding", {
                "code": "POLICY_CHANGE", "severity": "warning", "classification": "new",
                "historical": False, "entity_id": contract["id"],
                "message": "The proposed contract differs. Historical validation remains authoritative in this comparison; inspect both policy versions.",
                "evidence": [], "options": ["inspect_evidence", "revise_contract", "defer"],
            }))
    removed = {row["entity_id"] for row in changes if row["kind"] == "node_removed"}
    for node_id in sorted(removed):
        incidents = sorted(row["id"] for row in base["model"]["relations"]
                           if row.get("from") == node_id or row.get("to") == node_id)
        if incidents:
            findings.append(identified("finding", {
                "code": "REMOVED_NODE_IMPACT", "severity": "warning", "classification": "new",
                "historical": False, "entity_id": node_id,
                "message": "A removed node participated in historical relations; inspect the affected assertions and competency results.",
                "affected_relation_ids": incidents, "evidence": evidence_for(base["model"], node_id, "base"),
                "options": ["inspect_evidence", "revise_candidate", "defer"],
            }))
    changes.sort(key=lambda row: (row["collection"], row["entity_id"], row["kind"], row.get("field", ""), row["id"]))
    findings.sort(key=lambda row: (row["code"], row["entity_id"], row["classification"], row["id"]))
    checks = competency_deltas(base, head)
    report = {
        "schema_version": "1", "tool": "repository-graph", "tool_version": VERSION,
        "engine_status": "completed", "semantic_status": "not_run",
        "base": base, "head": head, "changes": changes, "findings": findings,
        "competency_deltas": checks,
        "summary": {"changes": len(changes), "by_kind": dict(sorted(Counter(row["kind"] for row in changes).items())),
                    "findings": len(findings), "base_valid": base["validation"]["contract_status"] == "valid",
                    "head_valid": head["validation"]["contract_status"] == "valid",
                    "proposed_head_valid": head["proposed_validation"]["contract_status"] == "valid" if "proposed_validation" in head else None,
                    "new_errors": sum(row["classification"] == "new" and row["severity"] == "error" for row in findings),
                    "historical_errors": sum(row["classification"] == "historical" for row in findings),
                    "graph_changed": base["graph_sha256"] != head["graph_sha256"],
                    "model_changed": base["model_sha256"] != head["model_sha256"],
                    "policy_changed": any(row["code"] == "POLICY_CHANGE" for row in findings)},
    }
    report["review_revision"] = digest(report)
    return report


def write_output(path, value, inputs):
    target = Path(path).resolve()
    core.require(not core.aliases_input(target, inputs), "Output cannot overwrite an input",
                 str(target), "INPUT_OVERWRITE_FORBIDDEN")
    data = canonical_bytes(value)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    except OSError as exc:
        raise core.EngineError("OUTPUT_ERROR", str(exc), str(target)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--model", required=True)
    snapshot.add_argument("--contract", required=True)
    snapshot.add_argument("--output", required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--base", required=True)
    compare.add_argument("--head", required=True)
    compare.add_argument("--contract", required=True)
    compare.add_argument("--head-contract")
    compare.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    inputs = {Path(value).resolve() for key, value in vars(args).items()
              if key in ("model", "base", "head", "contract", "head_contract") and value}
    try:
        # Check collisions before any expensive work; existing output remains intact.
        core.require(not core.aliases_input(args.output, inputs), "Output cannot overwrite an input",
                     args.output, "INPUT_OVERWRITE_FORBIDDEN")
        contract = core.read_json(args.contract)
        if args.command == "snapshot":
            report = build_snapshot(core.read_json(args.model), contract)
            exit_code = 0 if report["validation"]["contract_status"] == "valid" else 1
        else:
            report = compare_models(core.read_json(args.base), core.read_json(args.head), contract,
                                    core.read_json(args.head_contract) if args.head_contract else None)
            exit_code = 0 if (report["summary"]["base_valid"] and report["summary"]["head_valid"]
                              and report["summary"]["proposed_head_valid"] is not False) else 1
        write_output(args.output, report, inputs)
        print(json.dumps({"engine_status": "completed", "semantic_status": "not_run", "exit_code": exit_code,
                          "output": str(Path(args.output).resolve()), "output_sha256": digest(report)}, sort_keys=True))
        return exit_code
    except (core.EngineError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"schema_version": "1", "tool": "repository-graph", "engine_status": "error",
                          "semantic_status": "not_run", "errors": [{"code": exc.code if isinstance(exc, core.EngineError) else "INPUT_ERROR",
                          "path": exc.path if isinstance(exc, core.EngineError) else "/", "message": str(exc)}]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
