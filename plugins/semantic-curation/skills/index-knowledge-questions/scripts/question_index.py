#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build and query a reviewed, non-authoritative question-oriented sidecar."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import unicodedata


class ContractError(ValueError):
    """An input does not satisfy the closed sidecar contract."""


ROOT_FIELDS = {"schema_version", "passages", "concepts", "predicates", "annotations", "relations", "families"}
STOP = frozenset("a an and are as at be by can do does for from how i in is it of on or that the their this to was what when where which who why with would".split())


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold())


def words(text: str) -> list[str]:
    return [word for word in tokens(text) if word not in STOP]


def phrase_in(phrase: str, query: str) -> bool:
    needle, haystack = tokens(phrase), tokens(query)
    return bool(needle) and any(haystack[i:i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def shape(value: object, fields: set[str], where: str) -> dict:
    require(isinstance(value, dict), f"{where} must be an object.")
    require(set(value) == fields, f"{where} fields must be exactly {sorted(fields)}.")
    return value


def text_value(value: object, where: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{where} must be a nonempty string.")
    return value


def strings(value: object, where: str) -> list[str]:
    require(isinstance(value, list), f"{where} must be an array.")
    for item in value:
        text_value(item, where)
    require(len(value) == len(set(value)), f"{where} must not contain duplicates.")
    return value


def checked_rows(data: dict, name: str, fields: set[str], identity: str = "id") -> dict[str, dict]:
    require(isinstance(data[name], list), f"{name} must be an array.")
    result = {}
    for row in data[name]:
        shape(row, fields, name)
        key = text_value(row[identity], f"{name}.{identity}")
        require(key not in result, f"Duplicate {name} identity: {key}.")
        result[key] = row
    return result


def validate_input(data: object) -> dict:
    data = shape(data, ROOT_FIELDS, "Input")
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "Input schema_version must be 1.")
    passages = checked_rows(data, "passages", {"id", "text", "source", "locator"})
    require(bool(passages), "At least one passage is required.")
    for row in passages.values():
        for key in ("text", "source", "locator"):
            text_value(row[key], f"passages.{key}")
    concepts = checked_rows(data, "concepts", {"id", "label", "aliases", "parents"})
    predicates = checked_rows(data, "predicates", {"id", "label", "aliases"})
    for name, values in (("concepts", concepts), ("predicates", predicates)):
        for row in values.values():
            text_value(row["label"], f"{name}.label")
            strings(row["aliases"], f"{name}.aliases")
    for row in concepts.values():
        parents = strings(row["parents"], "concepts.parents")
        require(all(parent in concepts for parent in parents), f"Unknown parent for concept {row['id']}.")
    visited, active = set(), set()

    def visit(key: str) -> None:
        require(key not in active, f"Taxonomy cycle at {key}.")
        if key in visited:
            return
        active.add(key)
        for parent in concepts[key]["parents"]:
            visit(parent)
        active.remove(key)
        visited.add(key)

    for key in concepts:
        visit(key)
    annotations = checked_rows(data, "annotations", {"passage_id", "concept_ids"}, "passage_id")
    for row in annotations.values():
        require(row["passage_id"] in passages, "Annotation references an unknown passage.")
        ids = strings(row["concept_ids"], "annotations.concept_ids")
        require(all(key in concepts for key in ids), "Annotation references an unknown concept.")
    relations = checked_rows(data, "relations", {"id", "subject", "predicate", "object", "evidence"})
    for row in relations.values():
        require(isinstance(row["subject"], str) and row["subject"] in concepts, "Relation subject must reference a concept.")
        require(isinstance(row["object"], str) and row["object"] in concepts, "Relation object must reference a concept.")
        require(isinstance(row["predicate"], str) and row["predicate"] in predicates, "Relation predicate must reference a predicate.")
        evidence = strings(row["evidence"], "relations.evidence")
        require(bool(evidence) and all(key in passages for key in evidence), "Relation evidence must reference one or more existing passages.")
    families = checked_rows(data, "families", {"id", "kind", "cues", "examples"})
    for row in families.values():
        require(row["kind"] in ("lookup", "taxonomy", "relation"), "Family kind must be lookup, taxonomy, or relation.")
        strings(row["cues"], "families.cues")
        strings(row["examples"], "families.examples")
    return data


def canonical(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data: object) -> str:
    return hashlib.sha256(canonical(data)).hexdigest()


def build(data: dict) -> dict:
    validate_input(data)
    return {"schema_version": 1, "input": data, "input_sha256": digest(data)}


def validate_index(index: object) -> dict:
    index = shape(index, {"schema_version", "input", "input_sha256"}, "Index")
    require(type(index["schema_version"]) is int and index["schema_version"] == 1, "Index schema_version must be 1.")
    data = validate_input(index["input"])
    require(isinstance(index["input_sha256"], str) and index["input_sha256"] == digest(data), "Index input_sha256 does not match the input.")
    return data


def bm25(texts: dict[str, str], query: str) -> dict[str, float]:
    counts = {key: Counter(words(value)) for key, value in texts.items()}
    lengths = {key: sum(count.values()) for key, count in counts.items()}
    average = sum(lengths.values()) / len(counts) or 1.0
    frequencies = Counter(word for count in counts.values() for word in count)
    result = {}
    for key, count in counts.items():
        score = 0.0
        for word in sorted(set(words(query))):
            frequency = count[word]
            if not frequency:
                continue
            idf = math.log(1 + (len(counts) - frequencies[word] + 0.5) / (frequencies[word] + 0.5))
            score += idf * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * lengths[key] / average))
        if score:
            result[key] = score
    return result


def ranked(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda key: (-scores[key], key))


def search(index: dict, query: str, mode: str = "guided", top_k: int = 5, family: str | None = None) -> dict:
    data = validate_index(index)
    text_value(query, "Query")
    require(mode in ("lexical", "guided"), "Mode must be lexical or guided.")
    require(type(top_k) is int and 1 <= top_k <= 1000, "top_k must be an integer from 1 to 1000.")
    passages = {row["id"]: row for row in data["passages"]}
    concepts = {row["id"]: row for row in data["concepts"]}
    predicates = {row["id"]: row for row in data["predicates"]}
    annotations = {row["passage_id"]: set(row["concept_ids"]) for row in data["annotations"]}
    families = {row["id"]: row for row in data["families"]}
    if family is not None:
        require(family in families, f"Unknown family: {family}.")
    else:
        routing = [(sum(len(tokens(cue)) for cue in row["cues"] if phrase_in(cue, query)), key) for key, row in families.items()]
        routing.sort(key=lambda pair: (-pair[0], pair[1]))
        family = routing[0][1] if routing and routing[0][0] > 0 else None
    kind = families[family]["kind"] if family else "lookup"
    matched = {key for key, row in concepts.items() if any(phrase_in(term, query) for term in [row["label"], *row["aliases"]])}
    matched_predicates = {key for key, row in predicates.items() if any(phrase_in(term, query) for term in [row["label"], *row["aliases"]])}
    ancestor_cache = {}

    def ancestors(key: str) -> set[str]:
        if key not in ancestor_cache:
            ancestor_cache[key] = {parent for direct in concepts[key]["parents"] for parent in ({direct} | ancestors(direct))}
        return ancestor_cache[key]

    raw = {key: row["text"] for key, row in passages.items()}
    lexical = bm25(raw, query)
    scores = dict(lexical)
    eligible_relations = []
    warnings = ["Ranked passages and declared evidence bundles are retrieval candidates; ranking and bundle completeness do not establish factual support.", "Source and locator fields are supplied metadata; raw source bytes and contextual entailment have not been verified."]
    if mode == "guided":
        enriched = {}
        for key, text in raw.items():
            bound = annotations.get(key, set())
            expanded = bound | {ancestor for concept in bound for ancestor in ancestors(concept)}
            terms = [term for concept in sorted(expanded) for term in [concepts[concept]["label"], *concepts[concept]["aliases"]]]
            enriched[key] = text + " " + " ".join(terms)
        scores = {}
        for lane in (lexical, bm25(enriched, query)):
            for rank, key in enumerate(ranked(lane), 1):
                scores[key] = scores.get(key, 0) + 1 / (60 + rank)
        for key, bound in annotations.items():
            direct = bound & matched
            broader = {ancestor for concept in bound for ancestor in ancestors(concept)} & matched
            if direct or (kind == "taxonomy" and broader):
                scores[key] = scores.get(key, 0) + 0.04 * len(direct) + (0.04 * len(broader) if kind == "taxonomy" else 0)
        if kind == "relation":
            eligible_relations = [row for row in data["relations"] if row["predicate"] in matched_predicates and matched & {row["subject"], row["object"]}]
            eligible_relations.sort(key=lambda row: (-len(matched & {row["subject"], row["object"]}), -sum(scores.get(key, 0) for key in row["evidence"]), row["id"]))
            if not eligible_relations:
                warnings.append("No reviewed relation matched both a declared predicate and a mentioned endpoint; lexical candidates remain available.")
    chosen = []
    for row in eligible_relations:
        remaining = [key for key in row["evidence"] if key not in chosen]
        if len(chosen) + len(remaining) <= top_k:
            chosen.extend(remaining)
        else:
            warnings.append(f"Relation {row['id']} cannot fit as a complete evidence bundle within the remaining passage budget.")
    for key in ranked(scores):
        if len(chosen) == top_k:
            break
        if key not in chosen:
            chosen.append(key)
    if not chosen:
        warnings.append("No indexed lexical or reviewed vocabulary match; no evidence candidates returned.")
    bundles = [{"relation_id": row["id"], "subject": row["subject"], "predicate": row["predicate"], "object": row["object"], "evidence": row["evidence"], "returned_evidence": [key for key in row["evidence"] if key in chosen], "complete": all(key in chosen for key in row["evidence"])} for row in eligible_relations]
    return {"schema_version": 1, "query": query, "mode": mode, "family": family or "default-lookup", "family_kind": kind, "hits": [{"passage_id": key, "rank": rank, "score": scores.get(key, 0), "text": passages[key]["text"], "source": passages[key]["source"], "locator": passages[key]["locator"], "matched_concepts": sorted(annotations.get(key, set()) & matched)} for rank, key in enumerate(chosen, 1)], "bundles": bundles, "warnings": warnings, "authority": "retrieval-candidates-only", "input_sha256": index["input_sha256"]}


def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON member: {key}.")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    def reject_constant(value: str) -> None:
        raise ContractError(f"Nonfinite JSON constant: {value}.")
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves existing inputs, indexes, and search outputs.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    builder = sub.add_parser("build", help="Validate input and create a new immutable sidecar.")
    builder.add_argument("input", type=Path)
    builder.add_argument("output", type=Path)
    validator = sub.add_parser("validate", help="Check the closed schema and canonical input digest.")
    validator.add_argument("index", type=Path)
    query = sub.add_parser("search", help="Return evidence candidates without asserting an answer.")
    query.add_argument("index", type=Path)
    query.add_argument("--query", required=True)
    query.add_argument("--mode", choices=("lexical", "guided"), default="guided")
    query.add_argument("--top-k", type=int, default=5)
    query.add_argument("--family")
    query.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build(read_json(args.input))
            write_json(args.output, result)
            result = {"valid": True, "output": str(args.output), "input_sha256": result["input_sha256"]}
        elif args.command == "validate":
            index = read_json(args.index)
            data = validate_index(index)
            result = {"valid": True, "passages": len(data["passages"]), "input_sha256": index["input_sha256"], "source_bytes_verified": False}
        else:
            result = search(read_json(args.index), args.query, args.mode, args.top_k, args.family)
            if args.output:
                write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except (ContractError, OSError, ValueError, TypeError, RecursionError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
