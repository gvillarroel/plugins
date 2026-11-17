"""Collect installed JavaScript dependency licenses alongside the offline bundle."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
lock = json.loads((ROOT / "web/package-lock.json").read_text(encoding="utf-8"))
parts = [
    "Third-party notices for the locally bundled MCP Apps bridge.\n"
    "Rebuild: cd web; npm ci; npm run build; then python scripts/build_web_notices.py.\n"
]
for relative, package in sorted(lock["packages"].items()):
    if not relative or "esbuild" in relative:
        continue  # Build-time executable is not part of the shipped browser script.
    directory = ROOT / "web" / relative
    if not directory.is_dir():
        continue
    name = relative.split("node_modules/")[-1]
    parts.append(f"\n{'=' * 72}\n{name} {package['version']} ({package.get('license', 'see license')})\n")
    licenses = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.lower().startswith(("license", "copying", "notice"))
    ]
    if not licenses:
        raise ValueError(f"Missing installed license: {name}")
    for path in sorted(licenses):
        parts.append(path.read_text(encoding="utf-8") + "\n")
(ROOT / "src/knowledge_catalog/host-bridge.NOTICES.txt").write_text("".join(parts), encoding="utf-8")
