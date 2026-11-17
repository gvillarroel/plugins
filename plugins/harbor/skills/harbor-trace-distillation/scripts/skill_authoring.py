#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Check skill authoring and resource integrity without executing bundle code."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote


POLICY_VERSION = "skill-authoring-v1"
MAX_NAME_CHARACTERS = 64
MAX_DESCRIPTION_CHARACTERS = 1024
# Claude recommends a body under 500 lines and a contents list above 100 lines.
BODY_LINE_LIMIT = 500
REFERENCE_CONTENTS_THRESHOLD = 100
PORTABLE_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
RESERVED_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
FRONTMATTER = re.compile(r"\A---\r?\n(?P<yaml>.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
INLINE_LINK = re.compile(r'\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+["\'][^"\']*["\'])?\)')
REFERENCE_LINK = re.compile(r'^ {0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)', re.MULTILINE)
HTML_LINK = re.compile(r'\b(?:href|src)=["\']([^"\']+)["\']', re.IGNORECASE)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER.match(text)
    if not match:
        raise ValueError("SKILL.md must begin with YAML frontmatter")
    try:
        import yaml
    except ImportError as error:
        raise ValueError("PyYAML is required; run this validator with uv run to use its declared dependency") from error

    class UniqueLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        loader.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                if key in result:
                    raise yaml.constructor.ConstructorError(None, None, "duplicate frontmatter key", key_node.start_mark)
                result[key] = loader.construct_object(value_node, deep=deep)
            except TypeError as error:
                raise yaml.constructor.ConstructorError(None, None, "invalid mapping key", key_node.start_mark) from error
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    try:
        metadata = yaml.load(match.group("yaml"), Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"SKILL.md frontmatter is invalid YAML: {error}") from error
    if not isinstance(metadata, dict):
        raise ValueError("SKILL.md frontmatter must be a mapping")
    return metadata, text[match.end():]


def validate_skill_text(text: str, expected_name: str | None = None) -> dict[str, Any]:
    metadata, body = parse_frontmatter(text)
    name = metadata.get("name")
    if not isinstance(name, str) or len(name) > MAX_NAME_CHARACTERS or not PORTABLE_NAME.fullmatch(name) or "--" in name or name in RESERVED_NAMES:
        raise ValueError("SKILL.md frontmatter.name must be an exact portable skill basename (1-64 lowercase letters, digits, or interior hyphens). No fallback name is used because it would change the installed identity.")
    if any(word in name for word in ("anthropic", "claude")):
        raise ValueError("SKILL.md frontmatter.name contains a reserved word: anthropic or claude")
    if expected_name is not None and name != expected_name:
        raise ValueError(f"SKILL.md frontmatter.name {name!r} does not match expected name {expected_name!r}")
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("SKILL.md frontmatter.description must be a non-empty string")
    if len(description) > MAX_DESCRIPTION_CHARACTERS:
        raise ValueError("SKILL.md frontmatter.description exceeds 1024 characters")
    if re.search(r"</?[A-Za-z][^>]*>", description):
        raise ValueError("SKILL.md frontmatter.description must not contain XML tags")
    extra = metadata.get("metadata", {})
    if not isinstance(extra, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in extra.items()):
        raise ValueError("SKILL.md metadata must map string keys to string values")
    for key in ("license", "compatibility", "allowed-tools"):
        if key in metadata and not isinstance(metadata[key], str):
            raise ValueError(f"SKILL.md {key} must be a string")
    if "compatibility" in metadata and not 1 <= len(metadata["compatibility"]) <= 500:
        raise ValueError("SKILL.md compatibility must contain 1-500 characters")
    if len(body.splitlines()) >= BODY_LINE_LIMIT:
        raise ValueError("SKILL.md body must remain under 500 lines; move conditional detail into linked references")
    if re.search(r"\[TODO[^\]]*\]|\bTODO:|\bTBD\b", prose(body)):
        raise ValueError("SKILL.md contains an unfinished authoring placeholder")
    return metadata


def prose(markdown: str) -> str:
    """Hide fenced examples while preserving line numbers for diagnostics."""
    result = []
    fence = None
    for line in markdown.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is None and marker:
            fence = marker.group(1)
            result.append("")
        elif fence is not None:
            if re.match(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*$", line):
                fence = None
            result.append("")
        else:
            result.append(line)
    return "\n".join(result)


def headings(markdown: str) -> list[tuple[str, str]]:
    result = []
    seen = {}
    for line in prose(markdown).splitlines():
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$", line)
        if not match:
            continue
        title = match.group(1)
        plain = re.sub(r"<[^>]*>", "", html.unescape(title)).lower()
        slug = re.sub(r"[^\w\- ]", "", plain).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.append((title, f"{slug}-{count}" if count else slug))
    return result


def links(markdown: str):
    source = prose(markdown)
    for pattern in (INLINE_LINK, REFERENCE_LINK, HTML_LINK):
        for match in pattern.finditer(source):
            yield html.unescape(match.group(1).strip("<>")), source[:match.start()].count("\n") + 1


def local_target(root: Path, source: Path, target: str, line: int) -> Path | None:
    label = f"{source.relative_to(root).as_posix()}:{line}"
    if "\\" in target or re.match(r"^[A-Za-z]:[/\\]", target):
        raise ValueError(f"{label}: use forward slashes and relative resource paths: {target}")
    if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", target, re.IGNORECASE):
        return None
    raw, _, fragment = target.partition("#")
    if re.search(r"%(?![0-9A-Fa-f]{2})", target):
        raise ValueError(f"{label}: invalid percent encoding in resource link: {target}")
    decoded = unquote(raw.split("?", 1)[0], errors="strict")
    if "\\" in decoded or decoded.startswith("/") or re.match(r"^[A-Za-z]:", decoded):
        raise ValueError(f"{label}: resource path must be portable and relative: {target}")
    destination = (source.parent / decoded).resolve() if decoded else source
    if not destination.is_relative_to(root):
        raise ValueError(f"{label}: link escapes the bundle: {target}")
    if not destination.exists():
        raise ValueError(f"{label}: link points to missing path: {target}")
    if fragment and destination.suffix.lower() == ".md":
        available = {slug for _, slug in headings(destination.read_text(encoding="utf-8"))}
        available.update(re.findall(r'\b(?:id|name)=["\']([^"\']+)["\']', destination.read_text(encoding="utf-8")))
        if unquote(fragment) not in available:
            raise ValueError(f"{label}: link points to missing heading: {target}")
    return destination


def bundle_files(root: Path, allow_internal_file_symlinks: bool) -> list[Path]:
    files = []
    if root.is_symlink() or getattr(root.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError("skill bundle root must not be a link, junction, or reparse point")
    for directory, folders, names in os.walk(root, followlinks=False):
        for name in sorted(folders + names):
            item = Path(directory) / name
            info = item.lstat()
            linked = item.is_symlink() or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            if linked:
                if not (allow_internal_file_symlinks and item.is_symlink() and item.is_file() and item.resolve().is_relative_to(root)):
                    raise ValueError(f"bundle resource must not be a link or reparse point: {item.relative_to(root).as_posix()}")
            elif not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValueError(f"bundle contains a non-regular resource: {item.relative_to(root).as_posix()}")
            if item.is_file():
                files.append(item)
    return sorted(files)


def validate_bundle(
    root: Path,
    expected_name: str | None = None,
    *,
    require_directory_name: bool = False,
    allow_internal_file_symlinks: bool = False,
    verify_syntax: bool = True,
) -> dict[str, Any]:
    """Check observable authoring rules; task quality still needs real evaluations."""
    root = Path(os.path.abspath(root))
    if not root.is_dir():
        raise ValueError(f"skill bundle directory does not exist: {root}")
    files = bundle_files(root, allow_internal_file_symlinks)
    root = root.resolve()
    entrypoint = root / "SKILL.md"
    try:
        source = entrypoint.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeError) as error:
        raise ValueError("skill bundle must contain UTF-8 SKILL.md") from error
    metadata = validate_skill_text(source, expected_name)
    if require_directory_name and root.name != metadata["name"]:
        raise ValueError(f"SKILL.md frontmatter.name {metadata['name']!r} does not match directory {root.name!r}")
    direct_references = {
        destination
        for target, line in links(source)
        if (destination := local_target(root, entrypoint, target, line)) is not None
    }
    preserved = preserved_resources(metadata, root, direct_references)
    references = []
    for file in files:
        relative = file.relative_to(root).as_posix()
        if file.suffix.lower() == ".md":
            markdown = file.read_text(encoding="utf-8")
            if re.search(r"(?:^|[^A-Za-z0-9_-])skills[\\/]harbor-[a-z0-9-]+", markdown):
                raise ValueError(f"{relative}: contains a repository-root Harbor skill path")
            for target, line in links(markdown):
                local_target(root, file, target, line)
            if relative.startswith("references/"):
                references.append(relative)
                if file.resolve() not in direct_references:
                    raise ValueError(f"{relative}: reference must link directly from SKILL.md with a read condition")
                if relative not in preserved and len(markdown.splitlines()) > REFERENCE_CONTENTS_THRESHOLD:
                    if not re.search(r"^#{1,3}\s+(?:Contents|Table of contents)\s*$", "\n".join(markdown.splitlines()[:40]), re.IGNORECASE | re.MULTILINE):
                        raise ValueError(f"{relative}: reference over 100 lines needs a contents list near the top")
                    if not any(target.startswith("#") for target, _ in links(markdown)):
                        raise ValueError(f"{relative}: contents list must link to reference sections")
        if verify_syntax and file.suffix.lower() == ".py":
            try:
                compile(file.read_bytes(), str(file), "exec")
            except (SyntaxError, UnicodeError) as error:
                raise ValueError(f"{relative}: Python syntax check failed: {error}") from error
    _, body = parse_frontmatter(source)
    return {"policyVersion": POLICY_VERSION, "name": metadata["name"], "descriptionCharacters": len(metadata["description"]), "bodyLines": len(body.splitlines()), "references": references, "preservedResources": sorted(preserved), "fileCount": len(files)}


def preserved_resources(metadata: dict[str, Any], root: Path, direct_references: set[Path]) -> set[str]:
    """Retain sealed compatibility inputs while routing agents to an indexed guide."""
    extra = metadata.get("metadata", {})

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("preserved resource declaration contains duplicate JSON keys")
            result[key] = value
        return result

    try:
        declarations = json.loads(extra.get("harbor-authoring-preserved-resources", "[]"), object_pairs_hook=unique_pairs)
    except json.JSONDecodeError as error:
        raise ValueError("metadata.harbor-authoring-preserved-resources must contain valid JSON") from error
    if not isinstance(declarations, list):
        raise ValueError("metadata.harbor-authoring-preserved-resources must contain a JSON list")
    preserved, guides = set(), set()
    for entry in declarations:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "guide", "reason"}:
            raise ValueError("preserved resource requires exact path, sha256, guide, and reason fields")
        if not all(isinstance(value, str) and value.strip() for value in entry.values()):
            raise ValueError("preserved resource fields must be non-empty strings")
        path, guide = entry["path"], entry["guide"]
        for value in (path, guide):
            if not value.startswith("references/") or not value.endswith(".md") or any(part in {"", ".", ".."} for part in value.split("/")) or "\\" in value or "%" in value or "#" in value or "?" in value:
                raise ValueError("preserved inputs and their guides must be exact portable reference Markdown paths")
        if path in preserved or path == guide:
            raise ValueError("preserved resource needs a distinct guide and a unique path")
        destination, guide_destination = root / path, root / guide
        if not destination.is_file() or not guide_destination.is_file() or not {destination.resolve(), guide_destination.resolve()} <= direct_references:
            raise ValueError("preserved resource and its guide must exist and link directly from SKILL.md")
        actual = "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest()
        if entry["sha256"] != actual:
            raise ValueError(f"preserved resource SHA-256 drift: {path}")
        preserved.add(path)
        guides.add(guide)
    if preserved & guides:
        raise ValueError("a preserved resource guide must remain active rather than preserved")
    return preserved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", type=Path)
    parser.add_argument("--batch-stdin", action="store_true", help="Read a JSON array of bundle paths from stdin")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable errors and bundle statistics")
    parser.add_argument("--require-directory-name", action="store_true")
    parser.add_argument("--skip-syntax", action="store_true")
    args = parser.parse_args()
    roots = args.roots
    if args.batch_stdin:
        try:
            values = json.load(sys.stdin)
        except (ValueError, UnicodeError):
            parser.error("batch input must be valid JSON")
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            parser.error("batch input must be an array of bundle path strings")
        roots.extend(Path(value) for value in values)
    if not roots:
        parser.error("provide at least one skill bundle directory")
    errors, bundles = [], []
    for root in roots:
        try:
            bundles.append(validate_bundle(root, require_directory_name=args.require_directory_name, verify_syntax=not args.skip_syntax))
        except (OSError, ValueError, RecursionError) as error:
            errors.append(f"{root.name}: {error}")
    result = {"policyVersion": POLICY_VERSION, "errors": errors, "bundles": bundles}
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    elif errors:
        print("Skill authoring check failed:\n" + "\n".join(f"- {error}" for error in errors), file=sys.stderr)
    else:
        print(f"Skill authoring check passed ({len(bundles)} bundles; {POLICY_VERSION}).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
