#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Project explicit UTF-8 JSON files into a bounded typed value graph.

This is a deterministic structural projection, not ontology inference or a
claim about domain truth. See ../references/native-json-values.md.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

import semantic_model as core
import repository_graph as graph
import repository_sources as sources

VERSION = "0.2.0"
POLICY_ID = "json-values-exact-decimal-v2"
MAX_DOCUMENT_BYTES = 2_000_000
MAX_TOTAL_BYTES = 10_000_000
MAX_DOCUMENTS = 100
MAX_VALUES_PER_DOCUMENT = 20_000
MAX_TOTAL_VALUES = 100_000
MAX_DEPTH = 100
MAX_EXPONENT_DIGITS = 8
MAX_EVIDENCE_LINKS = 250_000
MAX_MODEL_BYTES = 32_000_000
MAX_ORIGIN_BYTES = 1_000_000
NUMBER = re.compile(r"(-?)(0|[1-9][0-9]*)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?\Z")
OUTPUT_KEYS = ("model", "contract", "report")


class ProjectionError(core.EngineError):
    """An unsupported or malformed JSON projection input."""


@dataclass(frozen=True)
class NumberToken:
    lexical: str


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_number(token: str) -> str:
    """Return the exact base-ten value as signed coefficient and power of ten."""
    match = NUMBER.fullmatch(token)
    if not match:
        raise ProjectionError("INVALID_JSON_NUMBER", "Invalid JSON number token", actual=token)
    sign, integer, fraction, exponent = match.groups()
    exponent_digits = (exponent or "0").lstrip("+-").lstrip("0") or "0"
    exponent_sign = -1 if (exponent or "").startswith("-") else 1
    if len(exponent_digits) > MAX_EXPONENT_DIGITS:
        raise ProjectionError("JSON_EXPONENT_LIMIT", "Exponent exceeds the declared projection bound",
                              actual=token)
    # Convert the bounded significant digits, not a potentially huge lexical
    # run of leading zeroes that Python's int string limit would reject.
    exponent_value = exponent_sign * int(exponent_digits)
    power = exponent_value - len(fraction or "")
    digits = (integer + (fraction or "")).lstrip("0")
    if not digits:
        return "0"
    coefficient = digits.rstrip("0")
    power += len(digits) - len(coefficient)
    return (sign or "") + coefficient + "e" + str(power)


def parse_document(data: bytes, path: str = "<bytes>") -> tuple[object, dict]:
    """Parse one bounded UTF-8 JSON document without float conversion."""
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ProjectionError("JSON_BYTE_LIMIT", "JSON document exceeds the byte limit", path,
                              {"bytes": len(data), "limit": MAX_DOCUMENT_BYTES})
    if data.startswith(b"\xef\xbb\xbf"):
        raise ProjectionError("JSON_BOM_UNSUPPORTED", "UTF-8 BOM is not accepted for JSON inputs", path)
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ProjectionError("JSON_ENCODING", "JSON input must be strict UTF-8", path,
                              {"start": exc.start, "end": exc.end}) from exc

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProjectionError("JSON_DUPLICATE_KEY", "Duplicate decoded JSON object key", path,
                                      {"key": key})
            result[key] = value
        return result

    def invalid_constant(value):
        raise ProjectionError("JSON_NONFINITE", "NaN and Infinity are not JSON values", path,
                              {"token": value})

    def number_token(value):
        canonical_number(value)
        return NumberToken(value)

    try:
        value = json.loads(text, object_pairs_hook=unique_pairs, parse_int=number_token,
                           parse_float=number_token, parse_constant=invalid_constant)
    except ProjectionError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError, OverflowError) as exc:
        raise ProjectionError("JSON_PARSE", "Malformed or unsupported JSON document", path,
                              {"error": str(exc)}) from exc

    count = 0
    maximum_depth = 0
    by_kind = Counter()

    def visit(item, depth):
        nonlocal count, maximum_depth
        count += 1
        maximum_depth = max(maximum_depth, depth)
        if count > MAX_VALUES_PER_DOCUMENT:
            raise ProjectionError("JSON_VALUE_LIMIT", "JSON document exceeds the value-count limit", path,
                                  {"values": count, "limit": MAX_VALUES_PER_DOCUMENT})
        if depth > MAX_DEPTH:
            raise ProjectionError("JSON_DEPTH_LIMIT", "JSON document exceeds the nesting-depth limit", path,
                                  {"depth": depth, "limit": MAX_DEPTH})
        kind, _ = literal(item)
        by_kind[kind] += 1
        if isinstance(item, dict):
            for key, child in item.items():
                key.encode("utf-8", errors="strict")
                visit(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                visit(child, depth + 1)
        elif isinstance(item, str):
            item.encode("utf-8", errors="strict")

    try:
        visit(value, 0)
    except UnicodeEncodeError as exc:
        raise ProjectionError("JSON_SURROGATE", "JSON strings must contain Unicode scalar values", path,
                              {"start": exc.start}) from exc
    stats = {"value_count": count, "maximum_depth": maximum_depth,
             "values_by_kind": dict(sorted(by_kind.items()))}
    return value, stats


def literal(value) -> tuple[str, dict]:
    if isinstance(value, NumberToken):
        return "number", {"datatype": "JSON:number/exact-base-ten",
                           "canonical": canonical_number(value.lexical)}
    if value is None:
        return "null", {"datatype": "JSON:null", "value": None}
    if type(value) is bool:
        return "boolean", {"datatype": "JSON:boolean", "value": value}
    if isinstance(value, str):
        return "string", {"datatype": "JSON:string", "value": value}
    if isinstance(value, dict):
        return "object", {"datatype": "JSON:object", "members": sorted(value)}
    if isinstance(value, list):
        return "array", {"datatype": "JSON:array", "length": len(value)}
    raise ProjectionError("JSON_VALUE_TYPE", "Unsupported value produced by JSON parser")


def json_pointer_child(parent: str, segment: str) -> str:
    return parent + "/" + segment.replace("~", "~0").replace("/", "~1")


def _tree_id(path: str, pointer: str) -> str:
    payload = graph.canonical_bytes([path, pointer])
    return "json-value:" + sha256(payload)


def contract_document() -> dict:
    return {
        "schema_version": "1",
        "id": POLICY_ID,
        "version": "1",
        "require_source_bindings": True,
        "types": {
            "Artifact": {"attributes": {"path": {"type": "string"}}, "closed_attributes": True},
            "Claim": {"attributes": {
                "pointer": {"type": "string"},
                "kind": {"type": "string"},
                "literal": {"type": "object"},
                "parent_pointer": {"type": "string"},
                "segment": {"type": "string"},
            }, "closed_attributes": True},
        },
        "relations": {
            "about": {"from_types": ["Claim"], "to_types": ["Artifact"]},
        },
        "checks": [],
    }


def _ensure_regular_input_paths(root: Path, files: list[str]) -> dict[str, Path]:
    """Reject symlink/reparse components and resolve explicit regular files."""
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir():
        raise ProjectionError("INPUT_ROOT", "Input root must be a directory", str(root))
    resolved = {}
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for name in files:
        safe = sources.safe_path(name)
        current = resolved_root
        for index, part in enumerate(safe.parts):
            current = current / part
            try:
                info = current.lstat()
            except OSError as exc:
                raise ProjectionError("INPUT_FILE", "Could not inspect selected input file", name,
                                      {"error": str(exc)}) from exc
            attributes = getattr(info, "st_file_attributes", 0)
            if stat.S_ISLNK(info.st_mode) or attributes & reparse_flag:
                raise ProjectionError("INPUT_ALIAS", "Input path components may not be symlinks or reparse points",
                                      name, {"component": part})
            last = index == len(safe.parts) - 1
            if last and not stat.S_ISREG(info.st_mode):
                raise ProjectionError("INPUT_NOT_REGULAR", "Selected input must be a regular file", name)
            if not last and not stat.S_ISDIR(info.st_mode):
                raise ProjectionError("INPUT_NOT_DIRECTORY", "Input parent component must be a directory",
                                      name, {"component": part})
        resolved[name] = current
    selected = list(resolved.items())
    for index, (name, path) in enumerate(selected):
        for other_name, other_path in selected[:index]:
            try:
                aliases = os.path.samefile(path, other_path)
            except OSError:
                aliases = path.resolve() == other_path.resolve()
            if aliases:
                raise ProjectionError("INPUT_ALIAS", "Selected input paths identify the same physical file",
                                      name, {"other_path": other_name})
    return resolved


def _add_model_budget(current: int, amount: int, path: str, phase: str) -> int:
    # This is a lower-bound running estimate: fixed separators and final
    # provenance metadata are checked by the exact serialization below.
    proposed = current + amount
    if proposed > MAX_MODEL_BYTES:
        raise ProjectionError("JSON_MODEL_BYTE_LIMIT", "Projected model exceeds the serialized model-byte limit",
                              path, {"estimated_bytes": proposed, "limit": MAX_MODEL_BYTES, "phase": phase})
    return proposed


def _preflight_outputs(output_paths: dict[str, Path], input_paths: set[Path]) -> dict[str, Path]:
    if set(output_paths) != set(OUTPUT_KEYS):
        raise ProjectionError("OUTPUT_CONFIGURATION", "Exactly model, contract and report outputs are required")
    canonical = {}
    for key, raw in output_paths.items():
        target = raw.resolve(strict=False)
        if os.path.lexists(raw) or target.exists():
            raise ProjectionError("OUTPUT_EXISTS", "Refusing to overwrite an existing output", str(raw))
        if core.aliases_input(target, input_paths):
            raise ProjectionError("OUTPUT_ALIASES_INPUT", "Output must not alias an input", str(raw))
        canonical[key] = target
    values = list(canonical.values())
    if len(set(values)) != len(values):
        raise ProjectionError("OUTPUT_PATH_COLLISION", "Output paths must be distinct")
    return canonical


def _ensure_regular_origin(path: Path) -> Path:
    """Resolve an optional origin file while rejecting symlink/reparse components."""
    absolute = path.absolute()
    current = Path(absolute.anchor)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for index, part in enumerate(absolute.parts[1:]):
        current = current / part
        try:
            info = current.lstat()
        except OSError as exc:
            raise ProjectionError("ORIGIN_FILE", "Could not inspect origin path", str(path),
                                  {"error": str(exc)}) from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & reparse_flag:
            raise ProjectionError("ORIGIN_ALIAS", "Origin path components may not be symlinks or reparse points",
                                  str(path), {"component": part})
        if index < len(absolute.parts[1:]) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ProjectionError("ORIGIN_FILE", "Origin parent component must be a directory", str(path))
        if index == len(absolute.parts[1:]) - 1 and not stat.S_ISREG(info.st_mode):
            raise ProjectionError("ORIGIN_FILE", "Origin must be a regular JSON file", str(path))
    return current


def project_values(root: Path, files: list[str], origin: dict | None = None) -> tuple[dict, dict, dict]:
    """Build model, contract, and deterministic audit report from selected JSON files."""
    if not files or len(files) > MAX_DOCUMENTS:
        raise ProjectionError("JSON_DOCUMENT_LIMIT", "Select between 1 and 100 JSON files",
                              actual={"files": len(files), "limit": MAX_DOCUMENTS})
    try:
        normalized_names = [str(sources.safe_path(name)) for name in files]
    except core.EngineError as exc:
        raise ProjectionError(exc.code, str(exc), exc.path, exc.actual) from exc
    if len(set(normalized_names)) != len(normalized_names):
        raise ProjectionError("DUPLICATE_INPUT_PATH", "Input file paths must be unique")

    paths = _ensure_regular_input_paths(root, normalized_names)
    total_bytes = sum(path.stat().st_size for path in paths.values())
    if total_bytes > MAX_TOTAL_BYTES:
        raise ProjectionError("JSON_TOTAL_BYTE_LIMIT", "Selected documents exceed the combined byte limit",
                              actual={"bytes": total_bytes, "limit": MAX_TOTAL_BYTES})

    inventory = sources.inventory(root, normalized_names, max_chars=MAX_DOCUMENT_BYTES)
    doc_info = {doc["path"]: doc for doc in inventory["documents"]}
    parsed, stats = {}, {}
    for name in normalized_names:
        data = paths[name].read_bytes()
        if sha256(data) != doc_info[name]["blob_sha256"]:
            raise ProjectionError("INPUT_CHANGED_DURING_READ", "Input bytes differ from the inventory snapshot", name)
        parsed[name], stats[name] = parse_document(data, name)

    total_values = sum(item["value_count"] for item in stats.values())
    if total_values > MAX_TOTAL_VALUES:
        raise ProjectionError("JSON_TOTAL_VALUE_LIMIT", "Selected documents exceed the combined value limit",
                              actual={"values": total_values, "limit": MAX_TOTAL_VALUES})

    passages_by_document = Counter(source["path"] for source in inventory["sources"])
    evidence_links = sum(passages_by_document[name] * (3 * stats[name]["value_count"] + 2)
                         for name in normalized_names)
    if evidence_links > MAX_EVIDENCE_LINKS:
        raise ProjectionError("JSON_EVIDENCE_LINK_LIMIT", "Projection exceeds the bounded evidence-link limit",
                              actual={"evidence_link_occurrences": evidence_links,
                                      "limit": MAX_EVIDENCE_LINKS,
                                      "accounting": "node.source_ids + relation.source_ids + bindings targets"})

    contract = contract_document()
    core.check_contract(contract)
    nodes, relations, bindings = [], [], {}
    model_skeleton = {"schema_version": "1", "contract_id": POLICY_ID, "contract_version": "1",
                      "sources": [], "nodes": [], "relations": [], "bindings": {}}
    model_budget = len(graph.canonical_bytes(model_skeleton))
    source_bytes = sum(len(graph.canonical_bytes(source)) for source in inventory["sources"])
    model_budget = _add_model_budget(model_budget, source_bytes, "/sources", "source_inventory")
    for name in sorted(normalized_names):
        document_sources = sorted(source["id"] for source in inventory["sources"] if source["path"] == name)
        if not document_sources:
            raise ProjectionError("SOURCE_COVERAGE", "No evidence passages were inventoried for a selected file", name)
        binding_keys_bytes = sum(len(graph.canonical_bytes(source_id)) + 3 for source_id in document_sources)
        model_budget = _add_model_budget(model_budget, binding_keys_bytes, name, "binding_keys")
        artifact_id = "json-document:" + sha256(graph.canonical_bytes(name))
        artifact_node = {"id": artifact_id, "type": "Artifact", "label": name,
                         "definition": "An explicitly selected UTF-8 JSON document.",
                         "attributes": {"path": name}, "source_ids": document_sources}
        node_budget = len(graph.canonical_bytes(artifact_node))
        binding_target_budget = sum(len(graph.canonical_bytes(artifact_id)) for _ in document_sources)
        model_budget = _add_model_budget(model_budget, node_budget + binding_target_budget, name, "artifact_node")
        nodes.append(artifact_node)
        covered_nodes = [artifact_id]

        def visit(value, pointer: str, parent_pointer: str | None = None, segment: str | None = None):
            nonlocal model_budget
            kind, payload = literal(value)
            node_id = _tree_id(name, pointer)
            attributes = {"pointer": pointer, "kind": kind, "literal": payload}
            if parent_pointer is not None:
                attributes["parent_pointer"] = parent_pointer
                attributes["segment"] = segment
            node = {"id": node_id, "type": "Claim", "label": pointer or "(root)",
                    "definition": f"The JSON value at pointer {json.dumps(pointer, ensure_ascii=True)} has kind {kind}.",
                    "attributes": attributes, "source_ids": document_sources}
            relation = {"id": "about:" + node_id, "type": "about", "from": node_id,
                        "to": artifact_id, "source_ids": document_sources}
            append_bytes = (len(graph.canonical_bytes(node)) + len(graph.canonical_bytes(relation)) +
                            sum(len(graph.canonical_bytes(node_id)) for _ in document_sources))
            model_budget = _add_model_budget(model_budget, append_bytes, name, "value_node_and_relation")
            nodes.append(node)
            relations.append(relation)
            covered_nodes.append(node_id)
            if isinstance(value, dict):
                for key in sorted(value):
                    visit(value[key], json_pointer_child(pointer, key), pointer, key)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, json_pointer_child(pointer, str(index)), pointer, str(index))

        visit(parsed[name], "")
        for source_id in document_sources:
            bindings[source_id] = sorted(covered_nodes)

    model = {"schema_version": "1", "contract_id": POLICY_ID, "contract_version": "1",
             "sources": inventory["sources"], "nodes": nodes, "relations": relations,
             "bindings": {key: bindings[key] for key in sorted(bindings)}}
    model = sources.bind_provenance(inventory, model, origin)
    model_bytes = graph.canonical_bytes(model)
    if len(model_bytes) > MAX_MODEL_BYTES:
        raise ProjectionError("JSON_MODEL_BYTE_LIMIT", "Serialized model exceeds the exact model-byte limit",
                              actual={"serialized_bytes": len(model_bytes), "limit": MAX_MODEL_BYTES,
                                      "phase": "final_exact_check"})
    source_check = sources.check_sources(inventory, model)
    snapshot = graph.build_snapshot(model, contract)
    self_comparison = graph.compare_models(model, model, contract)
    replay = graph.compare_models(model, model, contract)
    deterministic = graph.canonical_bytes(self_comparison) == graph.canonical_bytes(replay)
    if not deterministic:
        raise ProjectionError("NONDETERMINISTIC_COMPARISON", "Self-comparison replay was not byte-stable")

    report = {
        "schema_version": "1",
        "tool": "native-json-values",
        "version": VERSION,
        "policy": {"id": POLICY_ID, "version": "1",
                   "number_equality": "exact base-ten value; exponent and trailing-zero spelling normalized",
                   "signed_zero": "negative and positive zero are equal",
                   "object_member_order": "ignored",
                   "array_order": "preserved by positional JSON Pointer indices",
                   "absence": "no node at an absent pointer; distinct from null and empty values"},
        "limits": {"document_bytes": MAX_DOCUMENT_BYTES, "total_bytes": MAX_TOTAL_BYTES,
                   "document_count": MAX_DOCUMENTS, "values_per_document": MAX_VALUES_PER_DOCUMENT,
                   "total_values": MAX_TOTAL_VALUES, "depth": MAX_DEPTH,
                   "significant_exponent_digits": MAX_EXPONENT_DIGITS,
                   "evidence_link_occurrences": MAX_EVIDENCE_LINKS,
                   "serialized_model_bytes": MAX_MODEL_BYTES,
                   "origin_file_bytes": MAX_ORIGIN_BYTES},
        "helper_versions": {"semantic_model": core.VERSION, "repository_sources": sources.VERSION,
                            "repository_graph": graph.VERSION},
        "projection_sha256": sha256(Path(__file__).read_bytes()),
        "inventory_sha256": inventory["inventory_sha256"],
        "documents": [{"path": doc["path"], "blob_sha256": doc["blob_sha256"],
                       "content_sha256": doc["content_sha256"], **stats[doc["path"]]}
                      for doc in inventory["documents"]],
        "coverage": {"inventory_passages": len(inventory["sources"]),
                     "represented_passages": source_check["represented_passages"],
                     "unrepresented_passage_ids": source_check["unrepresented_passage_ids"],
                     "source_status": source_check["source_status"]},
        "validation": {"contract_status": snapshot["validation"]["contract_status"],
                       "errors": snapshot["validation"]["errors"],
                       "warnings": snapshot["validation"]["warnings"],
                       "semantic_status": "not_run"},
        "source_check": source_check,
        "model_sha256": snapshot["model_sha256"],
        "contract_sha256": snapshot["contract_sha256"],
        "graph_sha256": snapshot["graph_sha256"],
        "counts": {"documents": len(inventory["documents"]), "values": total_values,
                   "nodes": len(model["nodes"]), "relations": len(model["relations"]),
                   "sources": len(model["sources"]), "evidence_link_occurrences": evidence_links,
                   "serialized_model_bytes": len(model_bytes)},
        "deterministic_self_comparison": {"replay_equal": deterministic,
                                          "review_revision": self_comparison["review_revision"],
                                          "graph_changed": self_comparison["summary"]["graph_changed"],
                                          "changes": self_comparison["summary"]["changes"]},
        "engine_status": "completed",
        "semantic_status": "not_run",
        "domain_semantics_status": "unassessed",
        "note": "A typed structural JSON projection only; not an ontology, JSON-LD interpretation, truth assessment, or formal equivalence result.",
    }
    return model, contract, report


def _write_outputs(output_paths: dict[str, Path], values: dict[str, dict]) -> None:
    """Create three new files; a later I/O failure can leave earlier outputs present."""
    serialized = {key: graph.canonical_bytes(values[key]) for key in OUTPUT_KEYS}
    for key in OUTPUT_KEYS:
        target = output_paths[key]
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as stream:
                stream.write(serialized[key])
        except OSError as exc:
            raise ProjectionError("OUTPUT_ERROR", str(exc), str(target)) from exc


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ProjectionError("ARGUMENT_ERROR", message)


def main(argv=None) -> int:
    parser = _Parser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    project = subcommands.add_parser("project", help="Project explicit JSON files into a typed value graph")
    project.add_argument("--root", required=True, type=Path)
    project.add_argument("--files", required=True, nargs="+")
    project.add_argument("--model-output", required=True, type=Path)
    project.add_argument("--contract-output", required=True, type=Path)
    project.add_argument("--report-output", required=True, type=Path)
    project.add_argument("--origin", type=Path)
    try:
        args = parser.parse_args(argv)
        inputs = _ensure_regular_input_paths(args.root, [str(sources.safe_path(name)) for name in args.files])
        if args.origin is not None:
            origin_path = _ensure_regular_origin(args.origin)
            origin_bytes = origin_path.stat().st_size
            if origin_bytes > MAX_ORIGIN_BYTES:
                raise ProjectionError("ORIGIN_BYTE_LIMIT", "Origin JSON exceeds the origin-file byte limit",
                                      str(origin_path), {"bytes": origin_bytes, "limit": MAX_ORIGIN_BYTES})
            inputs["<origin>"] = origin_path
        else:
            origin_path = None
        input_paths = {path.resolve(strict=True) for path in inputs.values()}
        output_paths = _preflight_outputs({"model": args.model_output, "contract": args.contract_output,
                                           "report": args.report_output}, input_paths)
        origin = core.read_json(origin_path) if origin_path else None
        if origin is not None and not isinstance(origin, dict):
            raise ProjectionError("INVALID_ORIGIN", "Origin JSON must be an object", str(origin_path))
        model, contract, report = project_values(args.root, args.files, origin)
        _write_outputs(output_paths, {"model": model, "contract": contract, "report": report})
        exit_code = 0
        if report["validation"]["contract_status"] != "valid" or report["coverage"]["source_status"] != "valid":
            exit_code = 1
        print(json.dumps({"engine_status": "completed", "semantic_status": "not_run",
                          "exit_code": exit_code, "outputs": {key: str(path) for key, path in output_paths.items()},
                          "model_sha256": report["model_sha256"], "graph_sha256": report["graph_sha256"]},
                         ensure_ascii=True, sort_keys=True))
        return exit_code
    except (ProjectionError, core.EngineError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        if isinstance(exc, core.EngineError):
            code, path, actual = exc.code, exc.path, exc.actual
        else:
            code, path, actual = "INPUT_OUTPUT_ERROR", "/", None
        print(json.dumps({"engine_status": "error", "semantic_status": "not_run",
                          "errors": [{"code": code, "path": path, "message": str(exc),
                                      **({"actual": actual} if actual is not None else {})}]},
                         ensure_ascii=True, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
