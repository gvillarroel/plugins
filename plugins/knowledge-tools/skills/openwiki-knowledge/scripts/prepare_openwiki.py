"""Apply the reviewed OpenWiki 0.7.1 bounded graph reader to an explicit package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runtime import SKILL, module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True, help="Explicit installed openwiki npm package root.")
    parser.add_argument("--check", action="store_true", help="Inspect the reviewed graph bytes without changing the package.")
    args = parser.parse_args(argv)
    error = module("errors").KnowledgeError
    try:
        module("openwiki_skill").validate_skill(SKILL)
        native = module("openwiki_native")
        operation = native.inspect_openwiki_graph if args.check else native.prepare_openwiki_graph
        print(json.dumps(operation(args.package), indent=2, sort_keys=True, ensure_ascii=True))
        return 0
    except (error, OSError, ValueError) as exc:
        print(f"Native graph preparation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
