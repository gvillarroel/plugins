"""Small, explicit CLI shared by Claude and humans."""

import argparse
import json
import os
import sys
from pathlib import Path

from .workflow import Workflow


def main():
    # Windows redirected terminals may default to cp1252; lineage labels contain
    # Unicode arrows and Spanish text. CLI JSON is consistently UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="kc", description="Knowledge Catalog: explore → analyze → review → publish"
    )
    parser.add_argument("--home", default=os.environ.get("KC_HOME", str(Path.cwd() / ".kc")))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    configure = commands.add_parser("configure")
    configure.add_argument("--project")
    configure.add_argument("--location")
    configure.add_argument("--allow-project", action="append")
    configure.add_argument("--allow-root", action="append")
    write_mode = configure.add_mutually_exclusive_group()
    write_mode.add_argument("--enable-writes", action="store_true")
    write_mode.add_argument("--disable-writes", action="store_true")
    commands.add_parser("inventory")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--page-token", default="")
    get = commands.add_parser("get")
    get.add_argument("name")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("path")
    analyze.add_argument("--domain", default="retail")
    analyze.add_argument("--provenance", help="Path to downloaded provenance.json")
    review = commands.add_parser("review")
    review.add_argument("id", nargs="?")
    revise = commands.add_parser("revise")
    revise.add_argument("id")
    revise.add_argument("--json", required=True, help="Path to JSON object of evidence-backed metadata edits")
    plan = commands.add_parser("plan")
    plan.add_argument("id")
    plan.add_argument("--live", action="store_true")
    approve = commands.add_parser("approve")
    approve.add_argument("id")
    approve.add_argument("--digest", required=True)
    approve.add_argument("--reviewer", required=True)
    reject = commands.add_parser("reject")
    reject.add_argument("id")
    reject.add_argument("--reason", required=True)
    publish = commands.add_parser("publish")
    publish.add_argument("id")
    for command in (revise, plan, reject, publish):
        command.add_argument("--expect-digest", help="Reject an action if the reviewed revision changed")
    history = commands.add_parser("history")
    history.add_argument("id")
    history.add_argument("--before", type=int)
    history.add_argument("--limit", type=int, default=20)
    difference = commands.add_parser("diff")
    difference.add_argument("id")
    difference.add_argument("--from", dest="from_revision", type=int, required=True)
    difference.add_argument("--to", dest="to_revision", type=int)
    export = commands.add_parser("export")
    export.add_argument("id")
    export.add_argument("--format", choices=("json", "turtle", "plan"), default="json")
    export.add_argument("--output", required=True)
    recover = commands.add_parser("recover")
    recover.add_argument("id")
    recover.add_argument("--digest", required=True)
    recover.add_argument("--reason", required=True)
    download = commands.add_parser("download-kaggle")
    download.add_argument("handle")
    ui = commands.add_parser("ui")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--no-open", action="store_true")
    commands.add_parser("mcp")
    commands.add_parser("audit")
    demo = commands.add_parser("lineage-demo", help="Generate and execute a synthetic retail lineage domain")
    demo.add_argument("--seed", type=int, default=42)
    commands.add_parser("lineage-list")
    for operation in ("review", "history", "approve", "reject", "restore", "revise", "export"):
        command = commands.add_parser("lineage-" + operation)
        command.add_argument("id")
        if operation in {"approve", "reject", "restore", "revise"}:
            command.add_argument("--digest", required=True)
        if operation == "approve":
            command.add_argument("--reviewer", required=True)
        elif operation == "reject":
            command.add_argument("--reason", required=True)
        elif operation == "restore":
            command.add_argument("--revision", type=int, required=True)
        elif operation == "revise":
            command.add_argument("--json", required=True)
        elif operation == "export":
            command.add_argument(
                "--format", choices=("json", "html", "openlineage", "gcp-plan"), default="json"
            )
            command.add_argument("--project", default="")
            command.add_argument("--output", required=True)
    args = parser.parse_args()
    flow = Workflow(args.home)
    try:
        if args.command.startswith("lineage-"):
            from .lineage_interface import export_record, render_lineage, store

            lineage = store(flow.home)
            operation = args.command.removeprefix("lineage-")
            if operation == "demo":
                result = lineage.create_demo(args.seed)
            elif operation == "list":
                result = lineage.list()
            elif operation == "review":
                result = lineage.get(args.id)
            elif operation == "history":
                result = lineage.history(args.id)
            elif operation == "approve":
                result = lineage.approve(args.id, args.digest, args.reviewer)
            elif operation == "reject":
                result = lineage.reject(args.id, args.digest, args.reason)
            elif operation == "restore":
                result = lineage.restore(args.id, args.revision, args.digest)
            elif operation == "revise":
                edit_file = flow.allowed_path(args.json)
                if edit_file.stat().st_size > 1_000_000:
                    raise ValueError("Lineage edits exceed 1 MB")
                result = lineage.revise(
                    args.id, json.loads(edit_file.read_text(encoding="utf-8")), args.digest
                )
            elif operation == "export":
                record = lineage.get(args.id)
                value = (
                    render_lineage(record)
                    if args.format == "html"
                    else json.dumps(
                        export_record(
                            record,
                            args.format,
                            args.project or flow.config()["project"],
                            flow.config()["location"],
                        ),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                output = Path(args.output).expanduser().resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("x", encoding="utf-8", newline="\n") as destination:
                    destination.write(value + "\n")
                result = {
                    "output": str(output),
                    "revision": record["revision"],
                    "digest": record["digest"],
                    "export_only": True,
                }
        elif args.command == "configure":
            updates = {k: getattr(args, k) for k in ("project", "location") if getattr(args, k) is not None}
            if args.allow_project is not None:
                updates["allowed_projects"] = args.allow_project
            if args.allow_root is not None:
                updates["allowed_roots"] = args.allow_root
            if args.enable_writes or args.disable_writes:
                updates["writes_enabled"] = args.enable_writes and not args.disable_writes
            result = flow.configure(**updates)
        elif args.command == "status":
            result = {"config": flow.config(), "proposals": len(flow.list())}
        elif args.command in {"inventory", "search", "get"}:
            if not flow.config()["project"]:
                raise ValueError("Configure --project before accessing GCP")
            client = flow.client()
            result = (
                client.inventory()
                if args.command == "inventory"
                else client.search(args.query, page_token=args.page_token)
                if args.command == "search"
                else client.get_entry(args.name)
            )
        elif args.command == "analyze":
            provenance = None
            if args.provenance:
                provenance_path = flow.allowed_path(args.provenance)
                if provenance_path.stat().st_size > 1_000_000:
                    raise ValueError("Provenance file exceeds 1 MB")
                provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            result = flow.propose(args.path, args.domain, provenance)
        elif args.command == "review":
            result = flow.get(args.id) if args.id else flow.list()
        elif args.command == "revise":
            result = flow.revise(
                args.id,
                json.loads(Path(args.json).read_text(encoding="utf-8")),
                expected_digest=args.expect_digest,
            )
        elif args.command == "plan":
            if args.live and not flow.config()["project"]:
                raise ValueError("Configure --project first")
            result = flow.replan(args.id, live=args.live, expected_digest=args.expect_digest)
        elif args.command == "approve":
            result = flow.approve(args.id, args.digest, args.reviewer)
        elif args.command == "reject":
            result = flow.reject(args.id, args.reason, expected_digest=args.expect_digest)
        elif args.command == "publish":
            result = flow.publish(args.id, expected_digest=args.expect_digest)
        elif args.command == "history":
            result = flow.history(args.id, before_revision=args.before, limit=args.limit)
        elif args.command == "diff":
            result = flow.diff(args.id, args.from_revision, args.to_revision)
        elif args.command == "recover":
            result = flow.recover_publication(args.id, args.digest, args.reason)
        elif args.command == "export":
            proposal = flow.get(args.id)
            if args.format == "turtle":
                from .ontology import metadata_to_graph

                content = metadata_to_graph(proposal["metadata"]).serialize(format="turtle")
            else:
                value = (
                    proposal["plan"]
                    if args.format == "plan"
                    else {
                        key: proposal[key]
                        for key in ("id", "revision", "digest", "status", "metadata", "quality")
                    }
                )
                content = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8", newline="\n") as destination:
                destination.write(content)
            result = {
                "output": str(output),
                "format": args.format,
                "proposal_id": proposal["id"],
                "revision": proposal["revision"],
            }
        elif args.command == "download-kaggle":
            from .datasets import download_kaggle

            result = download_kaggle(args.handle, flow.home.parent / "data" / "kaggle")
        elif args.command == "audit":
            result = flow.events()
        elif args.command == "ui":
            from .ui import serve

            serve(flow, args.port, open_browser=not args.no_open)
            return
        elif args.command == "mcp":
            os.environ["KC_HOME"] = str(flow.home)
            from .server import main as serve_mcp

            serve_mcp()
            return
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(
            json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False), file=sys.stderr
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
