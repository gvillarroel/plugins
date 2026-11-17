"""Portable authoring checks shared by the audit and standalone generators.

The limits follow Anthropic's Skill authoring best practices. Semantic trigger
quality and model behavior still require review; these checks do not certify them.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


MAX_NAME_CHARACTERS = 64
MAX_DESCRIPTION_CHARACTERS = 1024
MAX_BODY_LINES = 499  # The authoring guide recommends a body under 500 lines.
LONG_REFERENCE_LINES = 100
NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\Z")
XML_TAG_RE = re.compile(r"<[/!?]?[A-Za-z][^>]*>")
CONTENTS_RE = re.compile(
    r"^#{1,6}\s+(?:table of contents|contents|navigation)\s*$", re.IGNORECASE
)
LINK_RE = re.compile(r"\[[^\]\n]+\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)")


class SkillAuthoringError(ValueError):
    """Describe a mechanically verifiable skill authoring violation."""


def validate_skill_name(name: str) -> None:
    """Require a portable name without the platform's reserved words."""

    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise SkillAuthoringError(
            "Skill name must use 1-64 lowercase letters, digits, or hyphens "
            "without leading or trailing hyphens"
        )
    if any(word in name for word in ("anthropic", "claude")):
        raise SkillAuthoringError("Skill name contains a reserved word: anthropic or claude")


def validate_skill_description(description: str) -> None:
    """Require nonempty, bounded discovery metadata without XML tags."""

    if not isinstance(description, str) or not description.strip():
        raise SkillAuthoringError("Description must not be empty")
    if len(description) > MAX_DESCRIPTION_CHARACTERS:
        raise SkillAuthoringError("Description must contain at most 1,024 characters")
    if XML_TAG_RE.search(description):
        raise SkillAuthoringError("Description must not contain XML tags")


def skill_name_literal(name: str) -> str:
    """Quote names that a YAML loader could interpret as scalars or dates."""

    validate_skill_name(name)
    if name[0].isdigit() or name in {"y", "n", "yes", "no", "on", "off", "true", "false", "null"}:
        return json.dumps(name)
    return name


def split_skill_document(text: str) -> tuple[str, str]:
    """Separate a fenced YAML header from the Markdown instructions."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        raise SkillAuthoringError("SKILL.md must start with YAML frontmatter")
    metadata, separator, body = normalized[4:].partition("\n---\n")
    if not separator:
        raise SkillAuthoringError("SKILL.md frontmatter lacks a closing fence")
    return metadata, body


def validate_skill_body(body: str) -> None:
    """Require useful instructions within the progressive disclosure limit."""

    if not body.strip():
        raise SkillAuthoringError("SKILL.md body must not be empty")
    if len(body.splitlines()) > MAX_BODY_LINES:
        raise SkillAuthoringError(
            "SKILL.md body must stay under 500 lines; move conditional detail into references"
        )


def validate_generated_document(text: str, *, name: str, description: str) -> None:
    """Validate generated metadata exactly without a YAML runtime dependency.

    Generators deliberately emit a plain name and JSON-quoted description, a
    restricted YAML subset. Exact comparison rejects extra or duplicate fields
    and manifest/header disagreement without imposing that subset on authored skills.
    """

    validate_skill_name(name)
    validate_skill_description(description)
    metadata, body = split_skill_document(text)
    expected = f"name: {skill_name_literal(name)}\ndescription: {json.dumps(description, ensure_ascii=False)}"
    if metadata != expected:
        raise SkillAuthoringError("Generated SKILL.md frontmatter differs from its manifest")
    validate_skill_body(body)


def validate_reference_navigation(text: str) -> None:
    """Require a useful early contents section in long instruction references.

    Source evidence, embedded knowledge and assets are not instruction references
    and must not be passed to this check or modified to satisfy it.
    """

    lines = text.splitlines()
    if len(lines) <= LONG_REFERENCE_LINES:
        return
    for index, line in enumerate(lines[:50]):
        if CONTENTS_RE.fullmatch(line.strip()):
            entries = []
            for entry in lines[index + 1:]:
                if re.match(r"^#{1,6}\s", entry):
                    break
                if re.match(r"^\s*(?:[-*+] |\d+[.)] )", entry):
                    entries.append(entry)
            if entries:
                return
    raise SkillAuthoringError(
        "Instruction references over 100 lines need an early contents section"
    )


def instruction_link_targets(
    text: str, *, document: Path, root: Path,
) -> tuple[set[Path], list[str]]:
    """Resolve instruction links and report missing, escaping or nonportable targets."""

    prose = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            marker, suffix = match.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not suffix.strip():
                fence = None
            continue
        if fence is None:
            prose.append(line)
    targets: set[Path] = set()
    errors = []
    root = root.resolve()
    for raw in LINK_RE.findall("\n".join(prose)):
        target = raw.removeprefix("<").removesuffix(">")
        if target.startswith("#"):
            continue
        if "\\" in target or re.match(r"^[A-Za-z]:", target):
            errors.append(f"Nonportable link: {target}")
            continue
        parsed = urlsplit(target)
        if parsed.scheme:
            continue
        candidate = (document.parent / unquote(parsed.path)).resolve()
        if not candidate.is_relative_to(root):
            errors.append(f"Link leaves the standalone package: {target}")
        elif not candidate.is_file():
            errors.append(f"Missing local reference: {target}")
        else:
            targets.add(candidate)
    return targets, errors


def validate_package_navigation(root: Path) -> None:
    """Check generated instruction references without interpreting immutable knowledge."""

    root = root.resolve()
    entrypoint = root / "SKILL.md"
    targets, errors = instruction_link_targets(
        entrypoint.read_text(encoding="utf-8"), document=entrypoint, root=root,
    )
    references = root / "references"
    for reference in sorted(references.rglob("*.md")):
        relative = reference.relative_to(references)
        if relative.parts[0] == "knowledge":
            continue
        label = reference.relative_to(root).as_posix()
        if reference.resolve() not in targets:
            errors.append(f"Reference needs a direct SKILL.md link: {label}")
        text = reference.read_text(encoding="utf-8")
        # The retained native SKILL.md is an entrypoint, not a long reference.
        if reference.name != "SKILL.md":
            validate_reference_navigation(text)
        _, reference_errors = instruction_link_targets(text, document=reference, root=root)
        errors.extend(f"{label}: {error}" for error in reference_errors)
    if errors:
        raise SkillAuthoringError("; ".join(errors))
