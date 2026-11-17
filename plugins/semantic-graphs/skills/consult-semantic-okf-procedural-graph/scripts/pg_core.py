"""Deterministic Procedural Graph kernel and evaluator-free knowledge tools.

This module never calls a model or reads a task verifier. It can be copied with
the skill; Python 3.10+ and the standard library are its only dependencies.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

NODE_TYPES = {"tool", "skill", "reasoning", "status"}
RELATIONS = {"LEADS_TO", "PROVIDES_INPUT_FOR"}
EDGE_FIELDS = {"source", "target", "relation", "condition", "guidance", "pitfalls"}
EVIDENCE_FIELDS = ("source_id", "record_id", "concept_path", "source_path", "record_sha256", "locator", "text_sha256")


class GraphError(ValueError):
    """A graph or edit contract failed a deterministic pre-evaluation gate."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_graph(graph: dict[str, Any], *, allow_cycles: bool = False) -> dict[str, Any]:
    """Validate B.6, repairing cycle-closing edges on a copy when cycles are off.

    Terminal means zero outdegree, not a hard-coded End node. The deterministic
    DFS order is the stored node/edge order; removed cycle edges are returned.
    """
    candidate = copy.deepcopy(graph)
    if set(candidate) != {"schema_version", "enabled", "nodes", "edges"}:
        raise GraphError("graph requires exactly schema_version, enabled, nodes, edges")
    if candidate["schema_version"] != 1 or not isinstance(candidate["enabled"], bool):
        raise GraphError("unsupported graph version or enabled flag")
    if not isinstance(candidate["nodes"], list) or not candidate["nodes"]:
        raise GraphError("nodes must be a non-empty array")
    if not isinstance(candidate["edges"], list):
        raise GraphError("edges must be an array")
    nodes: dict[str, dict[str, Any]] = {}
    for node in candidate["nodes"]:
        if not isinstance(node, dict) or set(node) != {"id", "type", "description"}:
            raise GraphError("each node requires exactly id, type, description")
        if not _text(node["id"]) or node["id"] in nodes:
            raise GraphError("node IDs must be non-empty and unique")
        if node["type"] not in NODE_TYPES or not _text(node["description"]):
            raise GraphError("invalid node type or description")
        nodes[node["id"]] = node
    if "Start" not in nodes:
        raise GraphError("Start is required for initial localization")
    seen = set()
    for edge in candidate["edges"]:
        if not isinstance(edge, dict) or set(edge) != EDGE_FIELDS:
            raise GraphError("edge fields do not match the attributed transition schema")
        if edge["source"] not in nodes or edge["target"] not in nodes:
            raise GraphError("edge references a missing endpoint")
        if edge["relation"] not in RELATIONS:
            raise GraphError("invalid relation type")
        if not all(isinstance(edge[k], str) for k in ("condition", "guidance", "pitfalls")):
            raise GraphError("edge attributes must be strings")
        identity = (edge["source"], edge["relation"], edge["target"])
        if identity in seen:
            raise GraphError("duplicate transition identity")
        seen.add(identity)
    adjacency: dict[str, list[tuple[int, str]]] = {node: [] for node in nodes}
    for index, edge in enumerate(candidate["edges"]):
        adjacency[edge["source"]].append((index, edge["target"]))
    removed: list[int] = []
    if not allow_cycles:
        state = {node: 0 for node in nodes}

        def visit(node: str) -> None:
            state[node] = 1
            for index, target in adjacency[node]:
                if state[target] == 1:
                    removed.append(index)
                elif state[target] == 0:
                    visit(target)
            state[node] = 2

        for node in nodes:
            if state[node] == 0:
                visit(node)
        removed_set = set(removed)
        candidate["edges"] = [e for i, e in enumerate(candidate["edges"]) if i not in removed_set]
        adjacency = {node: [] for node in nodes}
        for index, edge in enumerate(candidate["edges"]):
            adjacency[edge["source"]].append((index, edge["target"]))
    terminals = {node for node, outgoing in adjacency.items() if not outgoing}
    reachable = set(terminals)
    while True:
        previous = len(reachable)
        reachable.update(node for node, outgoing in adjacency.items() if any(t in reachable for _, t in outgoing))
        if len(reachable) == previous:
            break
    stranded = sorted(set(nodes) - reachable)
    if stranded:
        raise GraphError("no directed path to a terminal: " + ", ".join(stranded))
    return {"graph": candidate, "removed_cycle_edges": [graph["edges"][i] for i in removed],
            "terminals": sorted(terminals), "sha256": digest(candidate)}


def neighborhood(graph: dict[str, Any], action: str | None, hops: int = 2) -> dict[str, Any]:
    """Exact last-action localization and directed h-hop induced subgraph."""
    if isinstance(hops, bool) or not isinstance(hops, int) or hops < 0:
        raise GraphError("hops must be a non-negative integer")
    active = "Start" if action is None else action
    node_ids = {node["id"] for node in graph["nodes"]}
    if active not in node_ids:
        return {"active": active, "fallback": True, "hops": hops, "nodes": graph["nodes"], "edges": graph["edges"]}
    distance = {active: 0}
    queue = deque([active])
    while queue:
        node = queue.popleft()
        if distance[node] >= hops:
            continue
        for edge in graph["edges"]:
            if edge["source"] == node and edge["target"] not in distance:
                distance[edge["target"]] = distance[node] + 1
                queue.append(edge["target"])
    return {"active": active, "fallback": False, "hops": hops,
            "nodes": [dict(node, hop=distance[node["id"]]) for node in graph["nodes"] if node["id"] in distance],
            "edges": [edge for edge in graph["edges"] if edge["source"] in distance and edge["target"] in distance]}


def apply_edits(parent: dict[str, Any], edits: dict[str, Any], *, allow_cycles: bool = False) -> dict[str, Any]:
    """Apply the paper's ordered edits; delete all relations for an endpoint pair."""
    required = {"delete_edges", "delete_nodes", "add_nodes", "add_edges"}
    if not isinstance(edits, dict) or set(edits) != required or not all(isinstance(edits[k], list) for k in required):
        raise GraphError("edits require four arrays: delete_edges, delete_nodes, add_nodes, add_edges")
    candidate = copy.deepcopy(parent)
    pairs = set()
    for edge in edits["delete_edges"]:
        if not isinstance(edge, dict) or set(edge) != {"source", "target"}:
            raise GraphError("delete_edges accepts endpoint pairs only")
        pairs.add((edge["source"], edge["target"]))
    candidate["edges"] = [e for e in candidate["edges"] if (e["source"], e["target"]) not in pairs]
    if any(not _text(node) for node in edits["delete_nodes"]):
        raise GraphError("delete_nodes must contain IDs")
    deleted = set(edits["delete_nodes"])
    candidate["nodes"] = [n for n in candidate["nodes"] if n["id"] not in deleted]
    # Dangling edges are rejected rather than silently deleted (B.6).
    candidate["nodes"].extend(edits["add_nodes"])
    candidate["edges"].extend(edits["add_edges"])
    result = validate_graph(candidate, allow_cycles=allow_cycles)
    result["parent_sha256"] = digest(parent)
    result["edits_sha256"] = digest(edits)
    return result


def acceptance(retained_score: float, scores: list[float]) -> dict[str, Any]:
    if not isinstance(scores, list) or not scores or any(isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s) or not 0 <= s <= 1 for s in scores):
        raise GraphError("screen requires a complete non-empty finite [0,1] reward vector")
    if not math.isfinite(retained_score) or not 0 <= retained_score <= 1:
        raise GraphError("invalid retained screen score")
    score = sum(scores) / len(scores)
    return {"accepted": score >= retained_score, "candidate_score": score,
            "retained_score": score if score >= retained_score else retained_score, "ties_accepted": True}


def load_ledger(bundle: Path) -> list[dict[str, Any]]:
    root = bundle.resolve(strict=True)
    path = (root / "semantic" / "records.jsonl").resolve(strict=True)
    if not path.is_relative_to(root):
        raise GraphError("ledger escapes the mounted bundle")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    identities = [(r["source_id"], r["record_id"]) for r in rows]
    if len(identities) != len(set(identities)):
        raise GraphError("duplicate source-scoped record identity")
    return rows


def search(rows: list[dict[str, Any]], query: str, limit: int = 8, source_id: str | None = None) -> dict[str, Any]:
    if not _text(query) or not 1 <= limit <= 30:
        raise GraphError("search needs a non-empty query and limit in [1,30]")
    terms = list(dict.fromkeys(re.findall(r"[\w]+", query.casefold())))
    ranked = []
    for row in rows:
        if source_id is not None and row["source_id"] != source_id:
            continue
        title = str(row.get("title", "")).casefold()
        body = row["body"].casefold()
        score = sum((2 if term in title else 0) + (1 if term in body else 0) for term in terms)
        if score:
            ranked.append((score, row))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["source_id"], pair[1]["record_id"]))
    return {"total_hits": len(ranked), "hits": [{"source_id": r["source_id"], "record_id": r["record_id"],
             "title": r.get("title", ""), "score": s, "preview": r["body"][:480]} for s, r in ranked[:limit]]}


def read_record(rows: list[dict[str, Any]], source_id: str, record_id: str,
                start: int | None = None, end: int | None = None) -> dict[str, Any]:
    matches = [r for r in rows if r["source_id"] == source_id and r["record_id"] == record_id]
    if len(matches) != 1:
        raise GraphError("record not found uniquely")
    row = matches[0]
    body = row["body"]
    locator: dict[str, Any] = {"kind": "record"}
    if start is not None or end is not None:
        if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(body):
            raise GraphError("invalid Unicode code-point range")
        locator = {"kind": "character-range", "start": start, "end": end}
        body = body[start:end]
    evidence = {k: row[k] for k in EVIDENCE_FIELDS if k not in {"locator", "text_sha256"}}
    evidence["locator"] = locator
    evidence["text_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    evidence = {k: evidence[k] for k in EVIDENCE_FIELDS}
    return {"body": body, "body_length": len(row["body"]), "evidence": evidence}


def check_answer(rows: list[dict[str, Any]], answer: dict[str, Any]) -> dict[str, Any]:
    """Check exact evidence and envelope, without hidden semantic answers/rubrics."""
    errors = []
    if not isinstance(answer, dict) or set(answer) != {"question_id", "answer", "evidence"}:
        return {"valid": False, "errors": ["top-level keys must be question_id, answer, evidence"]}
    if not _text(answer["question_id"]) or not isinstance(answer["evidence"], list):
        return {"valid": False, "errors": ["invalid question_id or evidence array"]}
    response = answer["answer"]
    if response is None:
        return {"valid": answer["evidence"] == [], "errors": [] if answer["evidence"] == [] else ["null answer requires empty evidence"]}
    if not isinstance(response, dict) or set(response) not in ({"summary", "claims"}, {"summary", "facts", "claims"}):
        return {"valid": False, "errors": ["answer requires summary, claims and optional task-declared facts"]}
    if not _text(response["summary"]) or len(response["summary"].split()) > 450:
        errors.append("summary must contain 1-450 words")
    if "facts" in response and not isinstance(response["facts"], dict):
        errors.append("facts must be an object")
    if not isinstance(response["claims"], list) or not response["claims"]:
        return {"valid": False, "errors": errors + ["non-null answer requires claims"]}
    used = set()
    for claim in response["claims"]:
        if not isinstance(claim, dict) or set(claim) != {"statement", "evidence_indices"} or not _text(claim.get("statement")):
            errors.append("invalid claim shape")
            continue
        indices = claim["evidence_indices"]
        if not isinstance(indices, list) or not indices:
            errors.append("claim requires evidence indices")
            continue
        for index in indices:
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(answer["evidence"]):
                errors.append("out-of-range evidence index")
            else:
                used.add(index)
    if used != set(range(len(answer["evidence"]))):
        errors.append("every evidence row must support a claim")
    for item in answer["evidence"]:
        try:
            if not isinstance(item, dict) or set(item) != set(EVIDENCE_FIELDS):
                raise GraphError("evidence field mismatch")
            locator = item["locator"]
            if not isinstance(locator, dict) or locator.get("kind") not in {"record", "character-range"}:
                raise GraphError("unsupported locator")
            if set(locator) - {"kind", "target", "fragment", "start", "end"}:
                raise GraphError("unexpected locator field")
            if locator["kind"] == "record" and ("start" in locator or "end" in locator):
                raise GraphError("record locator must not include a range")
            if locator["kind"] == "character-range" and not {"start", "end"}.issubset(locator):
                raise GraphError("character-range requires start and end")
            expected = read_record(rows, item["source_id"], item["record_id"],
                                   locator.get("start"), locator.get("end"))["evidence"]
            for field in EVIDENCE_FIELDS:
                if field != "locator" and item[field] != expected[field]:
                    raise GraphError("evidence does not match the mounted source: " + field)
        except (GraphError, KeyError, TypeError) as exc:
            errors.append(str(exc))
    return {"valid": not errors, "errors": errors,
            "scope": "envelope and exact source provenance; no semantic oracle"}


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("validate", "neighborhood", "apply", "search", "read", "check"))
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--bundle", type=Path, default=Path("/knowledge"))
    args = parser.parse_args(argv)
    request = json.load(sys.stdin)
    try:
        if args.operation in {"validate", "neighborhood", "apply"}:
            if args.graph is None:
                raise GraphError("--graph is required")
            graph = json.loads(args.graph.read_text(encoding="utf-8"))
            if args.operation == "validate":
                result = validate_graph(graph, allow_cycles=request.get("allow_cycles", False))
            elif args.operation == "neighborhood":
                result = neighborhood(graph, request.get("action"), request.get("hops", 2))
            else:
                result = apply_edits(graph, request["edits"], allow_cycles=request.get("allow_cycles", False))
        else:
            rows = load_ledger(args.bundle)
            if args.operation == "search":
                result = search(rows, request["query"], request.get("limit", 8), request.get("source_id"))
            elif args.operation == "read":
                result = read_record(rows, request["source_id"], request["record_id"], request.get("start"), request.get("end"))
            else:
                result = check_answer(rows, request["answer"])
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (GraphError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
