"""Import existing acquired evidence and explicit processed libraries into OpenWiki."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runtime import SKILL, module


def main(argv: list[str] | None = None) -> int:
    """Publish a lossless document import or independently verify a previous import."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, help="Existing registered source store; never synchronized or modified.")
    parser.add_argument("--library", action="append", default=[], metavar="NAME=PATH", help="Explicit processed-library root; repeat for additional libraries.")
    parser.add_argument("--output", type=Path, required=True, help="New import directory, or an existing import for --check.")
    parser.add_argument("--check", action="store_true", help="Validate immutable evidence and the initial native wiki mirror.")
    parser.add_argument("--verify-originals", action="store_true", help="Also compare the currently mounted original inputs.")
    parser.add_argument("--python-command", default="python", help="Safe Python executable name for the installed MCP companion.")
    parser.add_argument("--io-reader", choices=["python", "native-node"], default="python", help="Exact-byte reader; native-node uses the package-local bounded Node worker.")
    parser.add_argument("--node-command", default="node", help="Node executable used only with --io-reader native-node.")
    args = parser.parse_args(argv)
    documents = module("openwiki_documents")
    error = module("errors").KnowledgeError
    try:
        # Bind all executable resources, including the native reader, before use.
        module("openwiki_skill").validate_skill(SKILL)
        if args.check:
            if args.store is not None or args.library:
                parser.error("--check uses the recorded input roots; omit --store and --library")
            result = documents.validate_document_migration(
                args.output, verify_originals=args.verify_originals,
                io_reader=args.io_reader, node_command=args.node_command,
            )
        else:
            if args.verify_originals:
                parser.error("--verify-originals is a validation option; use it with --check")
            if args.store is None:
                parser.error("--store is required for an import")
            libraries = {}
            for value in args.library:
                name, separator, path = value.partition("=")
                if not separator or not name or not path or name in libraries:
                    parser.error("Each library needs a unique NAME=PATH binding")
                libraries[name] = Path(path)
            store = module("store").KnowledgeStore(args.store)
            result = documents.migrate_documents(
                store, libraries, args.output,
                io_reader=args.io_reader, node_command=args.node_command,
            )
            result["installation"] = module("openwiki_skill").install_skill(
                SKILL, args.output / "runtime", store=args.store,
                io_root=args.output / "runtime" / "artifacts",
                python_command=args.python_command,
            )
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
        return 0 if result.get("wiki_mirror_complete", True) else 1
    except (error, OSError, ValueError) as exc:
        print(f"Document migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
