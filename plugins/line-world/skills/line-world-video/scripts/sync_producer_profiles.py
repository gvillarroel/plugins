"""Synchronize editable producer profiles and verify their shipping file fingerprints."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


VIDEO = Path(__file__).resolve().parents[1]
PROFILES = VIDEO / "assets" / "plugin-profiles"
PRODUCERS = ("line-world-d3", "line-world-hyperframes", "line-world-icons", "line-world-mermaid")
D3_FILES = ("scripts/video_chart.py", "assets/templates/video-chart.html",
            "scripts/video_chart_audit.js", "scripts/video_chart_motion_audit.js")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def changed(target, expected, write, changes):
    if target.is_file() and target.read_bytes() == expected:
        return
    changes.append(str(target.relative_to(VIDEO.parent)))
    if not write:
        return
    with tempfile.NamedTemporaryFile("wb", dir=target.parent, delete=False) as handle:
        temp = Path(handle.name)
        handle.write(expected)
    try:
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def synchronize(write=False):
    changes = []
    for name in PRODUCERS:
        skill = VIDEO.parent / name
        profile = PROFILES / (name + ".md.in")
        # Local edits belong to the shipping skill. Keep the older packaging inputs usable.
        instruction = (skill / "SKILL.md").read_bytes()
        changed(profile, instruction, write, changes)
        report_path = skill / "video-profile.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["profileSha256"] = digest(instruction)
        shared = {"attentionRuntimeSha256": "assets/runtime/attention.js", "focusRuntimeSha256": "assets/runtime/focus.js"}
        for key, relative in shared.items():
            data = (VIDEO / relative).read_bytes()
            changed(skill / relative, data, write, changes)
            report[key] = digest(data)
        for key, relative in {"sharedContractSha256": "references/video-contract.md", "paletteSha256": "assets/palettes/colorsets.json",
                              "videoPaletteSha256": "assets/palettes/video-colors.json"}.items():
            report[key] = digest((skill / relative).read_bytes())
        if name == "line-world-d3":
            changed(PROFILES / "video_chart.py.in", (skill / D3_FILES[0]).read_bytes(), write, changes)
            changed(PROFILES / "d3-operations.md.in", (skill / "references/producer-workflows.md").read_bytes(), write, changes)
            report["chartFiles"] = {path: digest((skill / path).read_bytes()) for path in D3_FILES}
        if report != json.loads(report_path.read_text(encoding="utf-8")):
            data = (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            changed(report_path, data, write, changes)
    return changes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Refresh the producer metadata and packaging copies.")
    args = parser.parse_args()
    differences = synchronize(args.write)
    print(json.dumps({"ok": args.write or not differences, "changed": differences}))
    raise SystemExit(0 if args.write or not differences else 1)
