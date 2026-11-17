#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate book evidence, then render an inline fragment and portable HTML."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


BUNDLE = Path(__file__).resolve().parents[1]
TEMPLATES = BUNDLE / "assets" / "templates"
MAX_FRAGMENT_BYTES = 1_000_000


def safe_json(value: object) -> str:
    """Keep JSON inside a script data element even when source text is hostile."""
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    for character, replacement in [("<", r"\u003c"), (">", r"\u003e"), ("&", r"\u0026"), ("\u2028", r"\u2028"), ("\u2029", r"\u2029")]:
        encoded = encoded.replace(character, replacement)
    return encoded


def validate(corpus_path: Path, analysis_path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("book_corpus.py")), "check", "--corpus", str(corpus_path), "--analysis", str(analysis_path), "--fail-on-findings"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    try:
        report = json.loads(result.stdout)
    except (ValueError, TypeError) as error:
        raise ValueError("The evidence checker did not return valid JSON; no explorer was written.") from error
    if result.returncode != 0 or report.get("passed") is not True:
        raise ValueError("Evidence validation failed; no explorer was written. " + json.dumps(report.get("findings", []), ensure_ascii=False))
    return report


def check_outputs(corpus_path: Path, analysis_path: Path, fragment_path: Path, standalone_path: Path) -> None:
    inputs = {corpus_path.resolve(), analysis_path.resolve()}
    outputs = [fragment_path.resolve(), standalone_path.resolve()]
    if outputs[0] == outputs[1] or outputs[0] in outputs[1].parents or outputs[1] in outputs[0].parents:
        raise ValueError("Fragment and standalone outputs must be distinct files with independent parent paths.")
    for target in outputs:
        if target in inputs:
            raise ValueError("An output cannot replace the corpus or analysis input.")
        if target == BUNDLE or BUNDLE in target.parents:
            raise ValueError("Write generated explorers outside the read-only skill bundle.")
        if target.exists() and not target.is_file():
            raise ValueError("Every output path must name a file, not a directory.")
        if any(parent.exists() and not parent.is_dir() for parent in target.parents):
            raise ValueError("An output parent is an existing file.")


def inline_payload(corpus: dict, analysis: dict) -> dict:
    cited = {
        evidence["passageId"]
        for item in analysis["claims"] + analysis.get("relations", [])
        for evidence in item.get("evidence", [])
    }
    reduced = {
        "schemaVersion": corpus["schemaVersion"],
        "book": corpus["book"],
        "chapters": corpus["chapters"],
        "passages": [passage for passage in corpus["passages"] if passage["id"] in cited],
    }
    return {"corpus": reduced, "analysis": analysis}


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, prefix=".semantic-explorer-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def render(corpus_path: Path, analysis_path: Path, fragment_path: Path, standalone_path: Path) -> dict:
    check_outputs(corpus_path, analysis_path, fragment_path, standalone_path)
    corpus_bytes = corpus_path.read_bytes()
    analysis_bytes = analysis_path.read_bytes()
    report = validate(corpus_path, analysis_path)
    if corpus_path.read_bytes() != corpus_bytes or analysis_path.read_bytes() != analysis_bytes:
        raise ValueError("Input changed during validation; retry with stable corpus and analysis files. No explorer was written.")
    corpus = json.loads(corpus_bytes.decode("utf-8-sig"))
    analysis = json.loads(analysis_bytes.decode("utf-8-sig"))
    payload = inline_payload(corpus, analysis)
    template = (TEMPLATES / "semantic-explorer.html").read_text(encoding="utf-8")
    shell = (TEMPLATES / "standalone-shell.html").read_text(encoding="utf-8")
    if template.count("__BOOK_DATA__") != 1 or shell.count("<!--__EXPLORER_FRAGMENT__-->") != 1 or shell.count("__BOOK_TITLE__") != 1:
        raise ValueError("The bundled templates have missing or repeated insertion markers.")
    fragment = template.replace("__BOOK_DATA__", safe_json(payload))
    fragment_bytes = len(fragment.encode("utf-8"))
    if fragment_bytes > MAX_FRAGMENT_BYTES:
        raise ValueError(f"Inline fragment is {fragment_bytes} bytes; limit is {MAX_FRAGMENT_BYTES}. Reduce the analysis or use a smaller, explicitly scoped excerpt.")
    standalone = shell.replace("__BOOK_TITLE__", escape(corpus["book"]["title"], quote=True)).replace("<!--__EXPLORER_FRAGMENT__-->", fragment)
    write_atomic(fragment_path, fragment)
    write_atomic(standalone_path, standalone)
    return {
        "passed": True,
        "evidenceCheckPassed": report["passed"],
        "semanticQuality": "not-assessed",
        "fragment": str(fragment_path.resolve()),
        "standalone": str(standalone_path.resolve()),
        "fragmentBytes": fragment_bytes,
        "embeddedPassages": len(payload["corpus"]["passages"]),
        "corpusPassages": len(corpus["passages"]),
        "chapters": len(corpus["chapters"]),
        "corpusInputSha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "analysisInputSha256": hashlib.sha256(analysis_bytes).hexdigest(),
        "limitations": ["Rendered evidence structure and exact quotations do not establish interpretive quality or native assistant integration."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--fragment", type=Path, required=True)
    parser.add_argument("--standalone", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = render(args.corpus, args.analysis, args.fragment, args.standalone)
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"passed": False, "error": str(error), "semanticQuality": "not-assessed"}, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
