"""Run one typed skill operation for host automation, without the know executable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runtime import module

KnowledgeError = module("errors").KnowledgeError
KnowledgeOperations = module("openwiki_operations").KnowledgeOperations
load_host_profiles = module("openwiki_skill").load_host_profiles


def main() -> int:
    """Read a typed JSON request and execute it within explicit host path scopes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--io-root", type=Path, required=True)
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument("--allow-desktop-actions", action="store_true")
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--request-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = json.loads(args.request_file.read_text(encoding="utf-8"))
        if not isinstance(request, dict) or set(request) != {"tool", "arguments"}:
            raise KnowledgeError("Invalid typed request")
        operations = KnowledgeOperations(args.store, io_root=args.io_root, allow_writes=args.allow_writes,
                                         allow_desktop_actions=args.allow_desktop_actions,
                                         **load_host_profiles(args.profiles, args.io_root))
        result = operations.call_tool(request["tool"], request["arguments"])
    except (KnowledgeError, OSError, ValueError, TypeError):
        print("Skill operation failed: invalid request, host policy or unavailable dependency.", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 1 if isinstance(result, dict) and (result.get("isError") or result.get("failed")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
