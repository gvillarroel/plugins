"""Serve the installed skill's own operation library as an OpenWiki MCP companion."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runtime import module

serve_operations = module("openwiki_operations").serve_operations
load_host_profiles = module("openwiki_skill").load_host_profiles


def main() -> None:
    """Use only explicit store and artifact paths; stdout is the MCP protocol."""
    # Native stdio clients use UTF-8 even when Windows pipes default to cp1252.
    sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--io-root", type=Path, required=True)
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument("--allow-desktop-actions", action="store_true")
    parser.add_argument("--profiles", type=Path)
    args = parser.parse_args()
    profiles = load_host_profiles(args.profiles, args.io_root)
    serve_operations(args.store, io_root=args.io_root, allow_writes=args.allow_writes,
                     allow_desktop_actions=args.allow_desktop_actions, **profiles)


if __name__ == "__main__":
    main()
