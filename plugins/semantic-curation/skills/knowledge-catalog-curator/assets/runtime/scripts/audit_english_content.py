"""Read-only audit of project-owned text and active demo display payloads."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

# This is a regression check for the previously generated Spanish copy, not a
# general language classifier. Literal publisher evidence and multilingual input
# recognition aliases are outside the generated presentation-language contract.
SPANISH_COPY = re.compile(
    r"\b(?:catálogo|sintético|sintéticos|revisión|revisiones|propuesta|propuestas|"
    r"metadatos|columnas|devoluciones|calidad|guardar|descartar|aprobar|"
    r"hipótesis|grafo|generador|evidencia|interfaz|SIMULADO|descripción|"
    r"ejecuciones|hallazgos|procedencia|peticiones|cuarenta|cantidad|moneda)\b",
    re.IGNORECASE,
)


def generated_strings(value, path="", *, preserve_source=False):
    if isinstance(value, dict):
        for key, child in value.items():
            if preserve_source and key == "source":
                continue
            yield from generated_strings(child, path + "/" + str(key), preserve_source=preserve_source)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from generated_strings(child, path + f"/{index}", preserve_source=preserve_source)
    elif isinstance(value, str):
        yield path, value


def inspect_text(text):
    return sorted(set(match.group(0) for match in SPANISH_COPY.finditer(text)))


def audit(root):
    root = Path(root).resolve()
    findings, files, payloads = [], 0, 0
    paths = [root / name for name in ("README.md", "SECURITY.md", "CHANGELOG.md")]
    for folder in ("docs", "examples", "plugin", "desktop", "ontology", "artifacts", "output/lineage"):
        paths.extend(
            path for path in (root / folder).rglob("*") if path.suffix in {".md", ".json", ".ttl", ".html"}
        )
    paths.extend(root / "src/knowledge_catalog" / name for name in ("review.html", "lineage.html"))
    paths.extend(root / "web" / name for name in ("host-bridge.js", "qa-host.js", "qa-server.mjs"))
    for path in sorted(set(paths)):
        if not path.is_file():
            continue
        files += 1
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if inspect_text(line):
                findings.append(
                    {
                        "file": path.relative_to(root).as_posix(),
                        "line": number,
                        "category": "generated Spanish presentation text",
                    }
                )
    for database, table, section in (
        ("catalog.sqlite3", "revisions", "metadata"),
        ("lineage.sqlite3", "lineage_revisions", "graph"),
    ):
        path = root / ".kc" / database
        if not path.is_file():
            continue
        with closing(sqlite3.connect(path)) as connection:
            for (body,) in connection.execute(f"SELECT body FROM {table}"):
                record = json.loads(body)
                payloads += 1
                for pointer, text in generated_strings(record[section], preserve_source=True):
                    if inspect_text(text):
                        findings.append(
                            {
                                "database": database,
                                "record": record["id"],
                                "revision": record["revision"],
                                "pointer": pointer,
                                "category": "generated Spanish display payload",
                            }
                        )
    return {
        "language": "en",
        "checked_at": datetime.now(UTC).isoformat(),
        "files_checked": files,
        "active_revision_payloads_checked": payloads,
        "findings": findings,
        "conforms": not findings,
        "scope": "Project-owned presentation text and active demo history. Original archived evidence and multilingual input aliases are preserved.",
        "method_limit": "Regression vocabulary for prior Spanish copy; not a general language detector or OCR of screenshots.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["conforms"] else 1)
