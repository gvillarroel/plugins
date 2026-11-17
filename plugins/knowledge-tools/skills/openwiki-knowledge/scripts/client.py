"""Supply finite typed operation output to a host Television source or preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runtime import module

KnowledgeOperations = module("openwiki_operations").KnowledgeOperations
KnowledgeError = module("errors").KnowledgeError
load_host_profiles = module("openwiki_skill").load_host_profiles


def main() -> int:
    """Render only cataloged operations and their typed parameters, without shell dispatch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--io-root", type=Path, required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--parameters-json", default="{}")
    parser.add_argument("--format", choices=["json", "television", "television-preview"], default="json")
    parser.add_argument("--entry")
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument("--allow-desktop-actions", action="store_true")
    parser.add_argument("--profiles", type=Path)
    args = parser.parse_args()
    try:
        operations = KnowledgeOperations(args.store, io_root=args.io_root, allow_writes=args.allow_writes,
                                         allow_desktop_actions=args.allow_desktop_actions,
                                         **load_host_profiles(args.profiles, args.io_root))
        parameters = json.loads(args.parameters_json)
        if not isinstance(parameters, dict) or args.operation not in operations.catalog:
            raise KnowledgeError("Invalid typed operation")
        properties = operations.catalog[args.operation]["schema"]["properties"]
        if "format" in properties:
            parameters["format"] = args.format
        if args.entry is not None:
            parameters["entry"] = args.entry
        arguments = {"operation": args.operation, "parameters": parameters}
        mutates = operations.catalog[args.operation]["mutates"]
        if mutates:
            arguments["write_intent"] = args.operation
        result = operations.call_tool("knowledge_change" if mutates else "knowledge_query", arguments)
        if isinstance(result, dict) and "result_id" in result:
            identity, result_format = result["result_id"], result["result_format"]
            text = result["text"]
            while result["next_offset"] is not None:
                result = operations.call_tool("knowledge_read_result", {"id": identity, "offset": result["next_offset"]})
                text += result["text"]
            result = json.loads(text) if result_format == "json" else text
    except (KnowledgeError, OSError, ValueError, TypeError):
        print("Typed operation failed or is unavailable under the host policy.", file=sys.stderr)
        return 1
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str))
    return 1 if isinstance(result, dict) and result.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
