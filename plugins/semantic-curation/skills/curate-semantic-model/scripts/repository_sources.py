#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Pin local UTF-8 passages and plan bounded, replayable extraction proposals.

No network, model calls, or automatic acceptance. Git inputs are read as blobs;
repository code, hooks and configuration are never executed.
"""
import argparse
import copy
from difflib import SequenceMatcher
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

from semantic_model import EngineError, exact_json_equal, read_json, require

VERSION = "1.3.0"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def bytes_hash(value):
    return hashlib.sha256(value).hexdigest()


def is_sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def is_git_revision(value):
    return (isinstance(value, str) and len(value) in (40, 64)
            and all(character in "0123456789abcdef" for character in value))


def has_json_string_keys(value, active=None):
    """Reject cycles and Python values that JSON would silently rewrite."""
    if isinstance(value, (dict, list)):
        active = set() if active is None else active
        if id(value) in active:
            return False
        active.add(id(value))
        try:
            if isinstance(value, dict):
                return all(isinstance(key, str) and has_json_string_keys(item, active)
                           for key, item in value.items())
            return all(has_json_string_keys(item, active) for item in value)
        finally:
            active.remove(id(value))
    return value is None or isinstance(value, (str, bool, int, float))


def json_object(value, code):
    """Check the Python API's JSON boundary without validating domain meaning."""
    try:
        require(isinstance(value, dict) and has_json_string_keys(value),
                "Expected a JSON object with string keys and finite JSON values", code=code)
        return json.loads(encoded(value).decode("utf-8"))
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError) as exc:
        raise EngineError(code, "Expected a finite, acyclic JSON object with string keys") from exc


def safe_path(value):
    require(isinstance(value, str), "Source path must be a string", code="UNSAFE_PATH")
    path = PurePosixPath(value)
    require(isinstance(value, str) and bool(value) and not path.is_absolute()
            and ".." not in path.parts and "\\" not in value and ":" not in value
            and path.as_posix() == value and value != ".",
            "Use a normalized repository-relative POSIX file path", code="UNSAFE_PATH")
    return path


def git(root, *args):
    result = subprocess.run(["git", "--no-replace-objects", "-C", str(root), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, result.stderr.decode("utf-8", errors="replace").strip(),
            code="GIT_INPUT_ERROR")
    return result.stdout


def passages(path, text, document_sha256, max_chars):
    """Paragraph-first exact line spans; split oversized paragraphs by whole lines."""
    # GitHub line anchors count LF, not Unicode paragraph/line separators.
    pieces = text.split("\n")
    lines = [piece + "\n" for piece in pieces[:-1]] + ([pieces[-1]] if pieces[-1] else [])
    groups, start, length = [], None, 0
    for index, line in enumerate(lines):
        require(len(line) <= max_chars, "A line exceeds max_chars; reflow the input or raise the bound",
                code="PASSAGE_TOO_LARGE", actual={"path": path, "line": index + 1})
        if start is not None and (not line.strip() or length + len(line) > max_chars):
            groups.append((start, index))
            start, length = None, 0
        if line.strip():
            if start is None:
                start = index
            length += len(line)
    if start is not None:
        groups.append((start, len(lines)))
    occurrences, result = Counter(), []
    for first, end in groups:
        quote = "".join(lines[first:end])
        identity = digest({"path": path, "text": quote})
        occurrences[identity] += 1
        result.append({"id": "passage:" + identity + ":" + str(occurrences[identity]),
                       "locator": f"{path}#L{first + 1}-L{end}", "text": quote,
                       "path": path, "start_line": first + 1, "end_line": end,
                       "document_sha256": document_sha256, "passage_sha256": bytes_hash(quote.encode("utf-8"))})
    return result


def inventory(root, files, ref=None, max_chars=3000):
    require(type(max_chars) is int and max_chars > 0, "max_chars must be a positive integer")
    root = Path(root).resolve(strict=True)
    require(root.is_dir(), "Source root must be a directory")
    require(bool(files) and len(set(files)) == len(files), "Supply distinct explicit files")
    revision = None
    if ref:
        top = Path(git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
        require(top == root, "With --ref, --root must be the Git repository root", code="GIT_ROOT_MISMATCH")
        revision = git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()
    documents, sources = [], []
    for name in sorted(files):
        path = safe_path(name)
        if revision:
            # ls-tree mode rejects links/submodules even if their blob is UTF-8.
            entry = git(root, "ls-tree", "-z", revision, "--", name)
            require(entry.startswith(b"100644 blob ") or entry.startswith(b"100755 blob "),
                    "Git source must be a regular tracked blob", code="UNSAFE_SOURCE", actual=name)
            raw = git(root, "cat-file", "blob", revision + ":" + name)
        else:
            source = root.joinpath(*path.parts).resolve(strict=True)
            require(source.is_relative_to(root) and source.is_file(), "Source escapes root or is not a file",
                    code="UNSAFE_SOURCE", actual=name)
            raw = source.read_bytes()
        try:
            text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError as exc:
            raise EngineError("SOURCE_ENCODING", "Source must be UTF-8 text", actual=name) from exc
        require("\x00" not in text, "Binary source is unsupported", code="SOURCE_ENCODING", actual=name)
        content_hash = bytes_hash(text.encode("utf-8"))
        documents.append({"path": name, "blob_sha256": bytes_hash(raw), "content_sha256": content_hash,
                          "text": text})
        sources.extend(passages(name, text, content_hash, max_chars))
    result = {"schema_version": "1", "tool": "repository-sources", "version": VERSION,
              "revision": revision, "max_chars": max_chars, "documents": documents, "sources": sources}
    result["inventory_sha256"] = digest(result)
    return result


def verify_inventory(value):
    require(isinstance(value, dict) and value.get("schema_version") == "1", "Unsupported inventory")
    unsigned = {key: item for key, item in value.items() if key != "inventory_sha256"}
    require(value.get("inventory_sha256") == digest(unsigned), "Inventory digest mismatch", code="STALE_INVENTORY")
    require(type(value.get("max_chars")) is int and value["max_chars"] > 0, "Invalid passage bound")
    require("revision" in value and (value["revision"] is None or is_git_revision(value["revision"])),
            "Inventory revision must be null or a full Git object ID", code="INVALID_SOURCE_METADATA")
    docs, sources = value.get("documents"), value.get("sources")
    require(isinstance(docs, list) and isinstance(sources, list), "Invalid inventory collections")
    expected, seen = [], set()
    for doc in docs:
        require(isinstance(doc, dict) and isinstance(doc.get("text"), str), "Malformed document")
        require(is_sha256(doc.get("blob_sha256")) and is_sha256(doc.get("content_sha256")),
                "Document raw and normalized SHA-256 fields must be lowercase 64-character hex",
                code="INVALID_SOURCE_METADATA", actual=doc.get("path"))
        name = doc.get("path")
        safe_path(name)
        require(name not in seen, "Duplicate source path")
        seen.add(name)
        require(doc.get("content_sha256") == bytes_hash(doc["text"].encode("utf-8")),
                "Document content digest mismatch", code="STALE_INVENTORY")
        expected.extend(passages(name, doc["text"], doc["content_sha256"], value["max_chars"]))
    require(exact_json_equal(sources, expected), "Passages do not match exact document spans", code="STALE_INVENTORY")
    return value


def plan(value, contract, registry, policy, cache=None):
    from repository_graph import canonical_contract, canonical_model
    verify_inventory(value)
    require(isinstance(policy, dict) and isinstance(policy.get("model"), str) and bool(policy["model"].strip()),
            "Policy must pin an explicit low-cost model identifier")
    require(isinstance(policy.get("prompt_version"), str) and bool(policy["prompt_version"].strip()),
            "Policy must version extraction instructions")
    require(isinstance(policy.get("instructions"), str) and bool(policy["instructions"].strip()),
            "Policy must include the exact extraction instructions in the cache key")
    require(type(policy.get("max_jobs")) is int and policy["max_jobs"] >= 0, "Policy needs a max_jobs budget")
    require(type(policy.get("max_input_chars")) is int and policy["max_input_chars"] > 0,
            "Policy needs max_input_chars")
    context = {"contract_sha256": digest(canonical_contract(contract)),
               "registry_sha256": digest(canonical_model(registry)), "policy_sha256": digest(policy),
               "planner_version": VERSION}
    cached = {}
    if cache is not None:
        require(isinstance(cache, dict) and isinstance(cache.get("entries"), list), "Cache requires entries array")
        for entry in cache["entries"]:
            require(isinstance(entry, dict) and isinstance(entry.get("request_sha256"), str), "Malformed cache entry")
            key = entry["request_sha256"]
            require(key not in cached and "response" in entry and entry.get("response_sha256") == digest(entry["response"]),
                    "Duplicate or corrupt cached response", code="CACHE_INTEGRITY")
            cached[key] = entry
    jobs = []
    for source in value["sources"]:
        request = {"context": context, "source_id": source["id"], "text": source["text"],
                   "document_sha256": source["document_sha256"]}
        key = digest(request)
        require(len(source["text"]) <= policy["max_input_chars"], "Passage exceeds configured input budget",
                code="INPUT_BUDGET", actual=source["id"])
        job = {"request_sha256": key, "source_id": source["id"], "locator": source["locator"],
               "text": source["text"], "document_sha256": source["document_sha256"],
               "status": "replay_candidate" if key in cached else "needs_proposal"}
        if key in cached:
            job["cached_proposal"] = cached[key]["response"]
        jobs.append(job)
    pending = sum(job["status"] == "needs_proposal" for job in jobs)
    return {"schema_version": "1", "tool": "repository-extraction-plan", "version": VERSION,
            "engine_status": "completed", "semantic_status": "not_run", "model": policy["model"],
            "context": context, "inventory_sha256": value["inventory_sha256"], "jobs": jobs,
            "summary": {"passages": len(jobs), "model_jobs": pending, "cache_hits": len(jobs) - pending,
                        "within_budget": pending <= policy["max_jobs"], "max_jobs": policy["max_jobs"]},
            "note": "No model was called. Cached proposals are untrusted candidates, not accepted assertions. "
                    "The input bound covers passage characters only; budget contract, registry, prompt and output separately."}


def check_sources(value, model):
    verify_inventory(value)
    known = {source["id"]: source for source in value["sources"]}
    require(isinstance(model, dict) and isinstance(model.get("sources"), list), "Model needs sources array")
    errors, seen = [], set()
    for source in model["sources"]:
        require(isinstance(source, dict) and isinstance(source.get("id"), str), "Malformed model source")
        sid = source["id"]
        if sid in seen:
            errors.append({"code": "DUPLICATE_SOURCE", "entity_id": sid})
        seen.add(sid)
        if sid not in known:
            errors.append({"code": "UNPINNED_SOURCE", "entity_id": sid})
        else:
            # Minimal id/text/locator records remain supported. If a caller
            # retains generated span/hash fields, those fields must also agree.
            fields = {"text", "locator"} | (set(source) & set(known[sid]))
            if any(not exact_json_equal(source.get(field), known[sid][field]) for field in fields):
                errors.append({"code": "SOURCE_SPAN_MISMATCH", "entity_id": sid, "expected": known[sid], "actual": source})
    return {"schema_version": "1", "engine_status": "completed", "semantic_status": "not_run",
            "inventory_sha256": value["inventory_sha256"], "source_status": "invalid" if errors else "valid",
            "represented_passages": len(known.keys() & seen), "unrepresented_passage_ids": sorted(known.keys() - seen),
            "errors": errors, "note": "Exact spans are checked; support for an interpretation and corpus completeness are not established."}


def reference_catalog(value, prefix="passage"):
    """Give the proposing model short references without asking it to copy text."""
    verify_inventory(value)
    require(isinstance(prefix, str) and 1 <= len(prefix) <= 24
            and all(character in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in prefix),
            "Catalog prefix must be 1-24 lowercase ASCII letters, digits or hyphens", code="INVALID_CATALOG")
    return {"schema_version": "1", "inventory_sha256": value["inventory_sha256"], "prefix": prefix,
            "passages": [{"ref": f"{prefix}-{index:04d}", "source_id": item["id"],
                          "locator": item["locator"], "text": item["text"]}
                         for index, item in enumerate(value["sources"], 1)]}


def inventory_changes(base, head):
    """Map exact passage additions/removals/replacements and unchanged correspondence by path."""
    verify_inventory(base)
    verify_inventory(head)
    base_catalog = reference_catalog(base, "base")
    head_catalog = reference_catalog(head, "head")
    base_refs = {item["source_id"]: item["ref"] for item in base_catalog["passages"]}
    head_refs = {item["source_id"]: item["ref"] for item in head_catalog["passages"]}
    base_by_path, head_by_path = {}, {}
    for item in base["sources"]:
        base_by_path.setdefault(item["path"], []).append(item)
    for item in head["sources"]:
        head_by_path.setdefault(item["path"], []).append(item)

    groups, unchanged = [], []
    for path in sorted(base_by_path.keys() | head_by_path.keys()):
        before, after = base_by_path.get(path, []), head_by_path.get(path, [])
        matcher = SequenceMatcher(None, [p["text"] for p in before],
                                  [p["text"] for p in after], autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                unchanged.extend({"base_ref": base_refs[p["id"]], "head_ref": head_refs[q["id"]]}
                                 for p, q in zip(before[i1:i2], after[j1:j2]))
                continue
            left, right = before[i1:i2], after[j1:j2]
            kind = "added" if not left else "removed" if not right else "replaced"
            group = {"kind": kind, "path": path,
                     "base_refs": [base_refs[item["id"]] for item in left],
                     "head_refs": [head_refs[item["id"]] for item in right]}
            group["fingerprint_sha256"] = digest(group)
            group["id"] = f"change-{len(groups) + 1:04d}"
            groups.append(group)

    return {"schema_version": "1", "tool": "repository-source-changes", "version": VERSION,
            "base_inventory_sha256": base["inventory_sha256"],
            "head_inventory_sha256": head["inventory_sha256"],
            "groups": groups, "unchanged": unchanged,
            "counts": {"added": sum(g["kind"] == "added" for g in groups),
                       "removed": sum(g["kind"] == "removed" for g in groups),
                       "replaced": sum(g["kind"] == "replaced" for g in groups),
                       "unchanged": len(unchanged)}}


def assemble(value, draft, catalog=None):
    """Resolve model-proposed quotations to exact inventory passages, never truth."""
    from repository_graph import canonical_model
    verify_inventory(value)
    references_by_id = {}
    if catalog is not None:
        require(isinstance(catalog, dict) and catalog == reference_catalog(value, catalog.get("prefix")),
                "Catalog must exactly match the supplied inventory and prefix", code="STALE_CATALOG")
        references_by_id = {item["ref"]: item for item in catalog["passages"]}
    require(isinstance(draft, dict) and set(draft) <= {"schema_version", "contract_id", "contract_version", "nodes", "relations", "metadata"},
            "Draft accepts model header, nodes, relations and optional metadata only", code="INVALID_DRAFT")
    model = {key: item for key, item in draft.items() if key not in ("nodes", "relations")}
    model.update({"nodes": [], "relations": [], "sources": [], "bindings": {}})
    selected, bindings, review = {}, {}, []
    for collection in ("nodes", "relations"):
        require(isinstance(draft.get(collection), list), "Draft requires nodes and relations arrays", code="INVALID_DRAFT")
        for record in draft[collection]:
            require(isinstance(record, dict) and "source_ids" not in record,
                    "Draft records must use evidence quotations instead of source_ids", code="INVALID_DRAFT")
            references = record.get("evidence")
            require(isinstance(references, list) and bool(references), "Every draft assertion needs evidence",
                    code="MISSING_EVIDENCE", actual=record.get("id"))
            source_ids = []
            for reference in references:
                if isinstance(reference, dict) and "ref" in reference:
                    require(set(reference) == {"ref"} and isinstance(reference["ref"], str)
                            and reference["ref"] in references_by_id,
                            "Short evidence references require a matching catalog and exact ref", code="INVALID_EVIDENCE_REF")
                    selected_reference = references_by_id[reference["ref"]]
                    reference = {"quote": selected_reference["text"], "locator": selected_reference["locator"]}
                require(isinstance(reference, dict) and set(reference) <= {"quote", "locator"}
                        and isinstance(reference.get("quote"), str) and bool(reference["quote"].strip()),
                        "Evidence needs an exact nonempty quote and optional locator", code="INVALID_EVIDENCE")
                quote = reference["quote"]
                matches = [item for item in value["sources"] if quote in item["text"]
                           and ("locator" not in reference or reference["locator"] == item["locator"])]
                require(len(matches) == 1, "Quote must identify exactly one inventory passage; provide a locator for ambiguity",
                        code="EVIDENCE_MATCH", actual={"entity": record.get("id"), "matches": len(matches), "quote": quote})
                passage = matches[0]
                selected[passage["id"]] = passage
                source_ids.append(passage["id"])
                endpoints = [record.get("id")] if collection == "nodes" else [record.get("from"), record.get("to")]
                require(all(isinstance(item, str) and bool(item) for item in endpoints), "Evidence record needs explicit IDs/endpoints")
                bindings.setdefault(passage["id"], set()).update(endpoints)
                review.append({"collection": collection, "entity_id": record.get("id"), "source_id": passage["id"],
                               "locator": passage["locator"], "quote": quote, "status": "support_not_reviewed"})
            output = {key: item for key, item in record.items() if key != "evidence"}
            output["source_ids"] = sorted(set(source_ids))
            model[collection].append(output)
    model["sources"] = list(selected.values())
    model["bindings"] = {sid: sorted(ids) for sid, ids in bindings.items()}
    # Keep chosen quotations as source metadata so subsequent semantic review can
    # inspect exactly which words were proposed to support each assertion.
    for passage in model["sources"]:
        model_source = dict(passage)
        model_source["proposed_support"] = sorted([item for item in review if item["source_id"] == passage["id"]],
                                                 key=lambda item: (item["collection"], item["entity_id"], item["quote"]))
        selected[passage["id"]] = model_source
    model["sources"] = list(selected.values())
    return canonical_model(model)


def bind_provenance(value, model, origin=None):
    """Bind a verified source inventory to a model without changing its graph.

    The binding records inventory and document digests plus the selected Git
    revision. It is provenance metadata only: no source or caller origin is
    authenticated by this local operation.
    """
    verify_inventory(value)
    json_object(model, "INVALID_MODEL")
    require(isinstance(model.get("sources"), list), "Model needs sources array", code="INVALID_MODEL")
    check = check_sources(value, model)
    if check["source_status"] != "valid":
        first = check["errors"][0]
        raise EngineError(first["code"], "Model source does not match the supplied inventory",
                          actual=first)
    known_ids = {item["id"] for item in model["sources"]}
    for collection in ("nodes", "relations"):
        rows = model.get(collection, [])
        require(isinstance(rows, list), "Model collections must be arrays", code="INVALID_MODEL")
        for row in rows:
            require(isinstance(row, dict), "Model records must be objects", code="INVALID_MODEL")
            source_ids = row.get("source_ids", [])
            require(isinstance(source_ids, list) and all(isinstance(item, str) for item in source_ids),
                    "Record source_ids must be an array of strings", code="INVALID_MODEL")
            require(set(source_ids) <= known_ids,
                    "Record references a source absent from the model source collection",
                    code="UNPINNED_SOURCE", actual={"collection": collection, "id": row.get("id"),
                                                       "source_ids": sorted(set(source_ids) - known_ids)})

    origin_value = None
    if origin is not None:
        origin_value = json_object(origin, "INVALID_ORIGIN")

    binding = {
        "schema_version": "1",
        "inventory_sha256": value["inventory_sha256"],
        "revision": value.get("revision"),
        "documents": [{key: doc[key] for key in ("path", "blob_sha256", "content_sha256")}
                       for doc in value["documents"]],
        "authenticity": "not_authenticated",
    }
    if origin_value is not None:
        binding["origin"] = {"value": origin_value, "sha256": digest(origin_value),
                             "authenticity": "not_authenticated"}

    result = copy.deepcopy(model)
    metadata = result.get("metadata", {})
    require(isinstance(metadata, dict), "Model metadata must be an object", code="INVALID_MODEL")
    if "repository_sources" in metadata:
        require(exact_json_equal(metadata["repository_sources"], binding),
                "Model already has a different repository source binding", code="PROVENANCE_CONFLICT")
        return result
    metadata["repository_sources"] = binding
    result["metadata"] = metadata
    return result


def write_new(path, value, inputs):
    target = Path(path).resolve()
    require(all(target != Path(item).resolve() for item in inputs if item), "Output aliases an input", code="OUTPUT_ALIAS")
    with target.open("xb") as stream:
        stream.write(encoded(value))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("inventory")
    prepare.add_argument("--root", required=True)
    prepare.add_argument("--files", required=True, nargs="+")
    prepare.add_argument("--ref")
    prepare.add_argument("--max-chars", type=int, default=3000)
    prepare.add_argument("--output", required=True)
    jobs = commands.add_parser("plan")
    for field in ("inventory", "contract", "registry", "policy", "output"):
        jobs.add_argument("--" + field, required=True)
    jobs.add_argument("--cache")
    check = commands.add_parser("check")
    for field in ("inventory", "model", "output"):
        check.add_argument("--" + field, required=True)
    compile_draft = commands.add_parser("assemble")
    for field in ("inventory", "draft", "output"):
        compile_draft.add_argument("--" + field, required=True)
    compile_draft.add_argument("--catalog")
    catalog_command = commands.add_parser("catalog")
    catalog_command.add_argument("--inventory", required=True)
    catalog_command.add_argument("--prefix", default="passage")
    catalog_command.add_argument("--output", required=True)
    changes_command = commands.add_parser("changes")
    changes_command.add_argument("--base-inventory", required=True)
    changes_command.add_argument("--head-inventory", required=True)
    changes_command.add_argument("--output", required=True)
    bind_command = commands.add_parser("bind")
    bind_command.add_argument("--inventory", required=True)
    bind_command.add_argument("--model", required=True)
    bind_command.add_argument("--origin")
    bind_command.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory(args.root, args.files, args.ref, args.max_chars)
            inputs = [Path(args.root) / item for item in args.files]
            code = 0
        elif args.command == "plan":
            result = plan(read_json(args.inventory), read_json(args.contract), read_json(args.registry),
                          read_json(args.policy), read_json(args.cache) if args.cache else None)
            inputs = [args.inventory, args.contract, args.registry, args.policy, args.cache]
            code = 0 if result["summary"]["within_budget"] else 1
        elif args.command == "check":
            result = check_sources(read_json(args.inventory), read_json(args.model))
            inputs = [args.inventory, args.model]
            code = 0 if result["source_status"] == "valid" else 1
        elif args.command == "catalog":
            result = reference_catalog(read_json(args.inventory), args.prefix)
            inputs = [args.inventory]
            code = 0
        elif args.command == "changes":
            result = inventory_changes(read_json(args.base_inventory), read_json(args.head_inventory))
            inputs = [args.base_inventory, args.head_inventory]
            code = 0
        elif args.command == "bind":
            result = bind_provenance(read_json(args.inventory), read_json(args.model),
                                     read_json(args.origin) if args.origin else None)
            inputs = [args.inventory, args.model, args.origin]
            code = 0
        else:
            result = assemble(read_json(args.inventory), read_json(args.draft),
                              read_json(args.catalog) if args.catalog else None)
            inputs = [args.inventory, args.draft, args.catalog]
            code = 0
        write_new(args.output, result, inputs)
        if args.command == "bind":
            bound = result["metadata"]["repository_sources"]
            summary = {"engine_status": "completed", "semantic_status": "not_run",
                       "inventory_sha256": bound["inventory_sha256"], "revision": bound["revision"],
                       "binding_sha256": digest(bound)}
        else:
            summary = {key: value for key, value in result.items()
                       if key not in ("documents", "sources", "jobs", "passages")}
        print(json.dumps(summary, ensure_ascii=True, allow_nan=False))
        return code
    except (EngineError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"engine_status": "error", "semantic_status": "not_run",
                          "errors": [{"code": exc.code if isinstance(exc, EngineError) else "INPUT_OUTPUT_ERROR",
                                      "message": str(exc)}]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
