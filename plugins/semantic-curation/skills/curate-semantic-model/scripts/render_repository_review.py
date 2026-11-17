#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Render a repository-graph comparison as an offline, inspectable HTML review.

This view records draft choices only. It does not accept changes, certify source
meaning, run a reasoner, or modify the compared models.
"""
import argparse
import json
from pathlib import Path
import re

from semantic_model import EngineError, read_json


TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "templates" / "repository-review.html"


def require(condition, message):
    if not condition:
        raise EngineError("INVALID_REVIEW_REPORT", message)


def validate_report(report):
    """Validate the display envelope without hiding invalid candidate fields."""
    require(isinstance(report, dict), "The review report must be an object.")
    require(report.get("schema_version") == "1", "Expected review schema_version 1.")
    require(report.get("tool") == "repository-graph", "Expected a repository-graph report.")
    require(report.get("engine_status") == "completed", "Only completed comparisons can be rendered.")
    require(isinstance(report.get("review_revision"), str) and bool(report["review_revision"]),
            "A comparison review_revision is required.")
    for side in ("base", "head"):
        snapshot = report.get(side)
        require(isinstance(snapshot, dict), f"The {side} snapshot is required.")
        model = snapshot.get("model")
        require(isinstance(model, dict), f"The {side} model is required.")
        for collection in ("sources", "nodes", "relations"):
            records = model.get(collection)
            require(isinstance(records, list), f"{side}.{collection} must be an array.")
            seen = set()
            for record in records:
                require(isinstance(record, dict) and isinstance(record.get("id"), str) and bool(record["id"]),
                        f"Every {side}.{collection} record needs an ID.")
                require(record["id"] not in seen, f"Duplicate ID in {side}.{collection}: {record['id']}")
                seen.add(record["id"])
        # Bindings are included as evidence data but are not read by the view.
        # Let missing or malformed bindings remain inspectable with the
        # validator's existing findings instead of blocking report rendering.
    for collection in ("changes", "findings"):
        entries = report.get(collection)
        require(isinstance(entries, list), f"{collection} must be an array.")
        seen = set()
        for entry in entries:
            require(isinstance(entry, dict) and isinstance(entry.get("id"), str) and bool(entry["id"]),
                    f"Every {collection} entry needs a fingerprint ID.")
            require(entry["id"] not in seen, f"Duplicate {collection} fingerprint.")
            seen.add(entry["id"])
    return report


def number_lexemes(value):
    """Map RFC 6901 paths to the exact numeric tokens emitted in review JSON."""
    result = {}

    def pointer(path, token):
        escaped = str(token).replace("~", "~0").replace("/", "~1")
        return path + "/" + escaped

    def visit(item, path=""):
        # bool is an int subclass in Python, but JSON booleans are not numbers.
        if isinstance(item, bool) or item is None or isinstance(item, str):
            return
        if isinstance(item, int):
            result[path] = str(item)
            return
        if isinstance(item, float):
            # Use the same standard-library representation as the report JSON,
            # preserving values such as -0.0 without converting them to strings.
            result[path] = json.dumps(item, allow_nan=False, ensure_ascii=False)
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, pointer(path, index))
            return
        if isinstance(item, dict):
            for key, child in item.items():
                require(isinstance(key, str), "Review JSON object keys must be strings.")
                visit(child, pointer(path, key))
            return
        raise EngineError("INVALID_JSON_VALUE", f"Unsupported review value at {path or '/'}.")

    visit(value)
    return result


def script_json(value):
    """Serialize inert JSON for an HTML script data element."""
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    for character, escaped in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                               ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        payload = payload.replace(character, escaped)
    return payload


def render_report(report):
    validate_report(report)
    # Keep the authoritative review JSON intact. The companion path map lets
    # the local view restore exact number tokens after JavaScript's lossy parse.
    payload = script_json(report)
    lexemes = script_json(number_lexemes(report))
    template = TEMPLATE.read_text(encoding="utf-8")
    require(template.count("__REVIEW_JSON__") == 1, "The review template must contain one data placeholder.")
    require(template.count("__REVIEW_NUMBER_LEXEMES__") == 1,
            "The review template must contain one numeric lexeme placeholder.")
    replacements = {"__REVIEW_JSON__": payload, "__REVIEW_NUMBER_LEXEMES__": lexemes}
    return re.sub(r"__REVIEW_JSON__|__REVIEW_NUMBER_LEXEMES__",
                  lambda match: replacements[match.group(0)], template)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        source, target = Path(args.report).resolve(), Path(args.output).resolve()
        if target in (source, TEMPLATE.resolve(), Path(__file__).resolve()):
            raise EngineError("OUTPUT_ALIAS", "Output must not alias an input or skill resource.")
        if target.exists():
            raise EngineError("OUTPUT_EXISTS", "Output already exists; choose a new review path.")
        html = render_report(read_json(source))
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(html)
        print(json.dumps({"engine_status": "completed", "output": str(target),
                          "semantic_status": "not_run", "decisions_status": "draft_only"}))
        return 0
    except (EngineError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"engine_status": "error", "semantic_status": "not_run",
                          "errors": [{"code": exc.code if isinstance(exc, EngineError) else "RENDER_ERROR",
                                      "message": str(exc)}]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
