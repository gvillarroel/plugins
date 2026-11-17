#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow==12.2.0"]
# ///
"""Exercise installed-layout workflows from a separate workspace, without remote services."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

PLUGINS = Path(__file__).resolve().parents[1] / "plugins"


def main():
    with tempfile.TemporaryDirectory(prefix="plugin-work-") as temporary:
        work = Path(temporary)

        def run(script, *args):
            result = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", str(PLUGINS / script), *args],
                cwd=work, encoding="utf-8", errors="replace", capture_output=True, timeout=90,
            )
            if result.returncode:
                raise RuntimeError(f"{script}\n{result.stdout}\n{result.stderr}")
            return result.stdout

        inspect = json.loads(run("semantic-curation/skills/knowledge-catalog-curator/scripts/curator.py",
                                 "inspect"))
        if not inspect["valid"]:
            raise ValueError("Curator rejected its embedded runtime")
        evidence = json.loads(run(
            "knowledge-authoring/skills/review-knowledge-methodology/scripts/query_expert_knowledge.py",
            "verify",
        ))
        if evidence["status"] != "pass" or not evidence["record_count"]:
            raise ValueError("Knowledge verification failed")

        wiki = PLUGINS / "knowledge-tools/skills/openwiki-knowledge"
        for module, digest in json.loads((wiki / "runtime-manifest.json").read_bytes())["modules"].items():
            if hashlib.sha256((wiki / "assets/runtime/knowledge" / module).read_bytes()).hexdigest() != digest:
                raise ValueError(f"OpenWiki runtime mismatch: {module}")
        for suite in ("editorial-research/skills/choose-contextual-gif/scripts/test_download_gif.py",
                      "editorial-research/skills/choose-contextual-gif/scripts/test_select_gif.py",
                      "store-studio/skills/product-design-critic/scripts/test_review_evidence.py"):
            run(suite)

        Image.new("RGB", (80, 80), "white").save(work / "reference.png")
        Image.new("RGBA", (30, 30), "red").save(work / "art.png")
        run("store-studio/skills/create-printify-product/scripts/build_reference_preview.py",
            "--reference-image", "reference.png", "--art", "art.png", "--box", "0.25,0.25,0.5,0.5",
            "--opacity", "1", "--output", "result/preview.png")
        with Image.open(work / "result/preview.png") as preview:
            if preview.convert("RGB").getpixel((40, 40)) != (255, 0, 0):
                raise ValueError("Artwork is missing from the preview")
    print("Curator, expert corpus, OpenWiki, GIF selection/download, review evidence and print preview passed.")


if __name__ == "__main__":
    main()
