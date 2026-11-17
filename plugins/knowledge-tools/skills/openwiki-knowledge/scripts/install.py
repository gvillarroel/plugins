"""Install this portable skill and its companion without installing the knowledge CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runtime import SKILL, module

KnowledgeError = module("errors").KnowledgeError
install_skill = module("openwiki_skill").install_skill


def main() -> int:
    """Create isolated native OpenWiki state with the chosen host policy."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--io-root", type=Path, required=True)
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument("--allow-desktop-actions", action="store_true")
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--python-command", default="python")
    parser.add_argument("--forward-env", action="append", default=[])
    args = parser.parse_args()
    try:
        result = install_skill(SKILL, args.runtime, store=args.store, io_root=args.io_root,
                               allow_writes=args.allow_writes, python_command=args.python_command,
                               forward_env=args.forward_env, profiles=args.profiles,
                               allow_desktop_actions=args.allow_desktop_actions)
    except (KnowledgeError, OSError):
        print("Skill installation failed: invalid package, paths or existing runtime state.", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
