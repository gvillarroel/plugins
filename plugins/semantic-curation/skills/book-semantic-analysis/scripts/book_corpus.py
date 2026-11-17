#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Prepare anchored TXT/Markdown passages and check evidence contracts, not meaning."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import unicodedata


SEMANTIC_LIMIT = (
    "Structural coverage and exact quotations do not prove model reading, entailment, "
    "interpretive quality, salience, or completeness of the original edition."
)
NEWLINE = r"(?:\r\n|\r(?!\n)|(?<!\r)\n)"
BREAK = re.compile(NEWLINE + r"[ \t]*" + NEWLINE)
CHAPTER = re.compile(r"^\s*(?:#{1,6}\s+)?(?:CHAPTER|CHAP\.?)\s+([IVXLCDM]+|\d+)\b[.:]?[ \t]*(.*?)\s*$", re.I)
MARKER = re.compile(r"^\s*\*{3}\s*(START|END) OF (?:THE|THIS) PROJECT GUTENBERG (?:EBOOK|ETEXT)\b.*?\*{3}\s*$", re.I)
CONTENTS = re.compile(r"^\s*(?:#{1,6}\s*)?(?:table of )?contents\s*$", re.I | re.M)


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def comparable(text: str) -> str:
    return normalized(unicodedata.normalize("NFKC", text).replace("’", "'")).casefold()


def lines_with_offsets(text: str) -> list[dict]:
    lines, offset = [], 0
    for line in text.splitlines(keepends=True):
        lines.append({"text": line.rstrip("\r\n"), "start": offset, "end": offset + len(line)})
        offset += len(line)
    return lines


def blocks(text: str, start: int, end: int):
    cursor = start
    for match in BREAK.finditer(text, start, end):
        segment_end = match.start()
        if text[cursor:segment_end].strip():
            left = cursor + len(text[cursor:segment_end]) - len(text[cursor:segment_end].lstrip())
            right = segment_end - (len(text[cursor:segment_end]) - len(text[cursor:segment_end].rstrip()))
            yield left, right, text[left:right]
        cursor = match.end()
    if text[cursor:end].strip():
        left = cursor + len(text[cursor:end]) - len(text[cursor:end].lstrip())
        right = end - (len(text[cursor:end]) - len(text[cursor:end].rstrip()))
        yield left, right, text[left:right]


def looks_like_subtitle(value: str) -> bool:
    if not value.strip() or len(value) > 160 or value.rstrip().endswith("."):
        return False
    words = re.findall(r"[^\W\d_]+(?:[’'][^\W\d_]+)*", value, re.UNICODE)
    major = [word for word in words if word.casefold() not in {"a", "an", "the", "and", "of", "from", "in", "to", "on", "with", "for"}]
    return bool(major) and sum(word[0].isupper() for word in major) / len(major) >= 0.75


def find_sections(text: str, start: int, end: int, excluded: list, notes: list) -> list[dict]:
    lines = [line for line in lines_with_offsets(text) if start <= line["start"] < end]
    candidates = []
    for index, line in enumerate(lines):
        match = CHAPTER.fullmatch(line["text"])
        if match:
            candidates.append({**line, "number": match[1].upper(), "inlineTitle": match[2], "lineIndex": index})
    toc = set()
    position = 0
    while position < len(candidates):
        stop = position + 1
        while (stop < len(candidates)
               and candidates[stop]["number"] not in {item["number"] for item in candidates[position:stop]}
               and not text[candidates[stop - 1]["end"]:candidates[stop]["start"]].strip()):
            stop += 1
        group = candidates[position:stop]
        before = text[start:group[0]["start"]] if group else ""
        later = candidates[stop:]
        repeated = len(later) >= 2 and [item["number"] for item in later[:2]] == [item["number"] for item in group[:2]]
        if len(group) >= 2 and CONTENTS.search(before) and repeated:
            for candidate in group:
                toc.add(candidate["start"])
                excluded.append({"start": candidate["start"], "end": candidate["end"], "reason": "table-of-contents-entry"})
        position = stop
    candidates = [candidate for candidate in candidates if candidate["start"] not in toc]
    if not candidates:
        markdown = []
        for line in lines:
            match = re.fullmatch(r"\s*(#{1,6})\s+(.+?)\s*#*\s*", line["text"])
            if match and not CONTENTS.fullmatch(line["text"]):
                markdown.append({**line, "level": len(match[1]), "title": match[2]})
        if markdown:
            level = min(item["level"] for item in markdown)
            candidates = [item for item in markdown if item["level"] == level]
            notes.append("Section IDs follow the highest-level Markdown headings; these are not verified literary chapter boundaries.")
        else:
            notes.append("No explicit chapter/Markdown boundaries found; one unsectioned source section is retained.")
            return [{"start": start, "end": end, "title": "Unsectioned text", "headingStart": None}]
    sections = []
    for index, candidate in enumerate(candidates):
        heading_end = candidate["end"]
        title = candidate.get("title") or candidate.get("inlineTitle") or candidate["text"].strip()
        line_index = candidate.get("lineIndex")
        if line_index is not None and not candidate["inlineTitle"] and line_index + 2 < len(lines):
            subtitle = lines[line_index + 1]
            if not lines[line_index + 2]["text"].strip() and looks_like_subtitle(subtitle["text"]):
                title = subtitle["text"].strip()
                heading_end = subtitle["end"]
        excluded.append({"start": candidate["start"], "end": heading_end, "reason": "source-section-heading"})
        sections.append({"start": heading_end, "end": candidates[index + 1]["start"] if index + 1 < len(candidates) else end,
                         "title": title, "headingStart": candidate["start"]})
    if candidates[0]["start"] > start:
        sections.insert(0, {"start": start, "end": candidates[0]["start"], "title": "Front matter / preface", "headingStart": None})
    return sections


def fragments(text: str, byte_budget: int) -> list[str]:
    output = []
    while len(text.encode("utf-8")) > byte_budget:
        low, high = 1, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if len(text[:middle].encode("utf-8")) <= byte_budget:
                low = middle
            else:
                high = middle - 1
        split = text.rfind(" ", 0, low + 1)
        if split < low // 2:
            split = low
        output.append(text[:split].rstrip())
        text = text[split:].lstrip()
    if text:
        output.append(text)
    return output


def prepare(input_path: Path, output: Path, title: str, author: str, source_url: str = "", max_reading_bytes: int = 18000) -> dict:
    if input_path.suffix.casefold() not in {".txt", ".md", ".markdown"}:
        raise ValueError("This helper accepts UTF-8 TXT or Markdown. PDF needs text extraction/OCR and inspection first; EPUB needs conversion before preparation.")
    if not title.strip() or not author.strip():
        raise ValueError("Title and author must be nonempty.")
    if not 2000 <= max_reading_bytes <= 20000:
        raise ValueError("max-reading-bytes must be between 2000 and 20000.")
    raw = input_path.read_bytes()
    text = raw.decode("utf-8")
    if "\x00" in text:
        raise ValueError("Input contains NUL bytes; convert the source to inspected UTF-8 text first.")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; use a new directory to preserve prior evidence.")
    excluded, notes = [], []
    lines = lines_with_offsets(text)
    markers = [(line, MARKER.fullmatch(line["text"])) for line in lines if MARKER.fullmatch(line["text"])]
    starts = [line for line, match in markers if match[1].upper() == "START"]
    ends = [line for line, match in markers if match[1].upper() == "END"]
    start, end = 0, len(text)
    if markers:
        if len(starts) != 1 or len(ends) != 1 or starts[0]["end"] >= ends[0]["start"]:
            raise ValueError("Ambiguous or unpaired Gutenberg START/END markers; inspect and extract the intended text before preparation.")
        start, end = starts[0]["end"], ends[0]["start"]
        excluded.extend([{"start": 0, "end": start, "reason": "gutenberg-header"}, {"start": end, "end": len(text), "reason": "gutenberg-footer"}])
    sections = find_sections(text, start, end, excluded, notes)
    passages, chapters = [], []
    for section in sections:
        pending = []
        for left, right, original in blocks(text, section["start"], section["end"]):
            value = normalized(original).lstrip("\ufeff")
            if not value:
                continue
            overlaps = [span for span in excluded if span["start"] < right and span["end"] > left]
            # TOC lines may form one multiline paragraph; remove only their exact spans.
            if overlaps:
                cursor = left
                pieces = []
                for span in sorted(overlaps, key=lambda item: item["start"]):
                    if cursor < span["start"]:
                        pieces.append((cursor, min(right, span["start"])))
                    cursor = max(cursor, span["end"])
                if cursor < right:
                    pieces.append((cursor, right))
                for piece_start, piece_end in pieces:
                    pending.extend((a, b, normalized(c).lstrip("\ufeff")) for a, b, c in blocks(text, piece_start, piece_end))
                continue
            known_front = section["headingStart"] is None and section["title"] == "Front matter / preface"
            front_label = comparable(value)
            is_front = known_front and (
                front_label in {comparable(title), comparable(f"by {author}"), comparable(author), "contents", "table of contents"}
                or (len(value) <= 160 and "edition" in front_label and value.upper() == value)
            )
            if is_front or value == "[Illustration]" or value == "THE END":
                excluded.append({"start": left, "end": right, "reason": "recognized-front-matter" if is_front else "non-prose-marker"})
            else:
                pending.append((left, right, value))
        pending = [item for item in pending if item[2]]
        if not pending:
            if section["headingStart"] is not None:
                raise ValueError(f"Section {section['title']!r} has no body paragraphs; inspect possible TOC/heading ambiguity.")
            continue
        chapter_id = f"ch{len(chapters) + 1:02d}"
        passage_ids = []
        for index, (left, right, value) in enumerate(pending, 1):
            passage_id = f"{chapter_id}-p{index:04d}"
            passage_ids.append(passage_id)
            passages.append({"id": passage_id, "chapterId": chapter_id, "text": value, "rawStart": left, "rawEnd": right})
        chapters.append({"id": chapter_id, "title": section["title"], "passageIds": passage_ids, "readingFiles": []})
    if not passages:
        raise ValueError("No body paragraphs remain after explicit source preparation.")
    source_sha = hashlib.sha256(raw).hexdigest()
    corpus = {
        "schemaVersion": 1,
        "book": {"title": title.strip(), "author": author.strip(), "sourceUrl": source_url, "sourceSha256": source_sha},
        "chapters": chapters, "passages": passages,
        "preparation": {
            "inputFormat": input_path.suffix.casefold(), "sourceCharacterCount": len(text),
            "offsetUnit": "Unicode code points in the original UTF-8-decoded source; half-open rawStart/rawEnd",
            "normalization": "Whitespace is collapsed to one space; punctuation, case and inline source markup are preserved. Poetic lineation requires consulting the original source.",
            "excludedSpans": sorted(excluded, key=lambda item: (item["start"], item["end"])),
            "limitations": notes + [SEMANTIC_LIMIT],
            "coverage": {"chapterCount": len(chapters), "bodyParagraphCount": len(passages), "bodyParagraphsAssignedExactlyOnce": True, "modelReadingVerified": False},
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "readings").mkdir()
    lookup = {passage["id"]: passage for passage in passages}
    for chapter in chapters:
        header = f"# {chapter['id']} · {chapter['title']}\n\nSource SHA-256: `{source_sha}`\n\n"
        budget = max_reading_bytes - len(header.encode("utf-8"))
        if budget < 1000:
            raise ValueError("Section title is too large for a bounded reading file.")
        units = []
        for passage_id in chapter["passageIds"]:
            parts = fragments(lookup[passage_id]["text"], budget - 160)
            for part_number, part in enumerate(parts, 1):
                label = passage_id if len(parts) == 1 else f"{passage_id} · fragment {part_number}/{len(parts)}"
                units.append(f"## {label}\n\n{part}\n\n")
        payload, chunk = header, 1
        for unit in units:
            if len((payload + unit).encode("utf-8")) > max_reading_bytes:
                name = f"readings/{chapter['id']}-{chunk:02d}.md"
                (output / name).write_text(payload, encoding="utf-8", newline="\n")
                chapter["readingFiles"].append(name)
                payload, chunk = header, chunk + 1
            payload += unit
        name = f"readings/{chapter['id']}-{chunk:02d}.md"
        (output / name).write_text(payload, encoding="utf-8", newline="\n")
        chapter["readingFiles"].append(name)
    (output / "corpus.json").write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    index = [f"# {title}\n", f"Author: {author}\n", f"Source SHA-256: `{source_sha}`\n", f"{len(chapters)} sections; {len(passages)} body paragraphs. Corpus preparation is not proof of reading.\n"]
    for chapter in chapters:
        files = ", ".join(f"[{Path(name).name}]({name})" for name in chapter["readingFiles"])
        index.append(f"- **{chapter['id']} · {chapter['title']}** — {len(chapter['passageIds'])} paragraphs; {files}")
    (output / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8", newline="\n")
    return {"passed": True, "corpus": str(output / "corpus.json"), "sourceSha256": source_sha, "chapters": len(chapters), "passages": len(passages), "readingFiles": sum(len(chapter["readingFiles"]) for chapter in chapters), "limitations": corpus["preparation"]["limitations"]}


def check(corpus: object, analysis: object) -> dict:
    """Validate structural evidence fidelity only; do not grade meaning."""
    findings = []

    def issue(path, message):
        findings.append({"path": path, "message": message})

    def text(value, path, allow_empty=False):
        if not isinstance(value, str) or (not allow_empty and not value.strip()):
            issue(path, "Expected a string." if allow_empty else "Expected a nonempty string.")
            return False
        return True

    def array(value, path, nonempty=False):
        if not isinstance(value, list) or (nonempty and not value):
            issue(path, "Expected a nonempty array." if nonempty else "Expected an array.")
            return []
        return value

    def strings(value, path, nonempty=False, unique=False):
        values = array(value, path, nonempty)
        valid = [item for index, item in enumerate(values) if text(item, f"{path}[{index}]")]
        if unique and len(valid) != len(set(valid)):
            issue(path, "Values must be unique.")
        return valid

    def object_(value, path):
        if not isinstance(value, dict):
            issue(path, "Expected an object.")
            return {}
        return value

    def records(value, path, nonempty=False):
        result = {}
        for index, value in enumerate(array(value, path, nonempty)):
            row = object_(value, f"{path}[{index}]")
            identifier = row.get("id")
            if text(identifier, f"{path}[{index}].id"):
                if identifier in result:
                    issue(f"{path}[{index}].id", "Duplicate ID within this collection.")
                else:
                    result[identifier] = row
        return result

    corpus = object_(corpus, "corpus")
    analysis = object_(analysis, "analysis")
    for document, prefix in [(corpus, "corpus"), (analysis, "analysis")]:
        if type(document.get("schemaVersion")) is not int or document.get("schemaVersion") != 1:
            issue(f"{prefix}.schemaVersion", "Expected integer schemaVersion 1.")
    book = object_(corpus.get("book"), "corpus.book")
    claimed_book = object_(analysis.get("book"), "analysis.book")
    for key in ["title", "author", "sourceSha256"]:
        text(book.get(key), f"corpus.book.{key}")
        text(claimed_book.get(key), f"analysis.book.{key}")
        if book.get(key) != claimed_book.get(key):
            issue(f"analysis.book.{key}", "Must exactly match the prepared corpus book.")
    for value, path in [(book.get("sourceSha256"), "corpus.book.sourceSha256"), (claimed_book.get("sourceSha256"), "analysis.book.sourceSha256")]:
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
            issue(path, "Expected a lowercase SHA-256 hex digest.")
    if "sourceUrl" in book:
        text(book["sourceUrl"], "corpus.book.sourceUrl", True)
    chapters = records(corpus.get("chapters"), "corpus.chapters", True)
    passages = records(corpus.get("passages"), "corpus.passages", True)
    membership = Counter()
    for chapter_id, chapter in chapters.items():
        prefix = f"corpus.chapters[{chapter_id}]"
        text(chapter.get("title"), f"{prefix}.title")
        for passage_id in strings(chapter.get("passageIds"), f"{prefix}.passageIds", True, True):
            membership[passage_id] += 1
            if passage_id not in passages:
                issue(f"{prefix}.passageIds", f"Unknown passage ID {passage_id}.")
            elif passages[passage_id].get("chapterId") != chapter_id:
                issue(f"{prefix}.passageIds", f"Passage {passage_id} belongs to another chapter.")
        for name in strings(chapter.get("readingFiles"), f"{prefix}.readingFiles", True, True):
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name or ":" in name:
                issue(f"{prefix}.readingFiles", "Reading paths must stay relative to the corpus output directory.")
    for passage_id, passage in passages.items():
        prefix = f"corpus.passages[{passage_id}]"
        text(passage.get("text"), f"{prefix}.text")
        if not isinstance(passage.get("chapterId"), str) or passage.get("chapterId") not in chapters:
            issue(f"{prefix}.chapterId", "Unknown chapter ID.")
        if membership[passage_id] != 1:
            issue(prefix, "Every passage must occur in exactly one chapter's passageIds.")
        if "rawStart" in passage or "rawEnd" in passage:
            left, right = passage.get("rawStart"), passage.get("rawEnd")
            if type(left) is not int or type(right) is not int or not 0 <= left < right:
                issue(prefix, "Raw offsets must be integer half-open positions with 0 <= start < end.")
    scope = object_(analysis.get("scope"), "analysis.scope")
    if not isinstance(scope.get("kind"), str) or scope.get("kind") not in {"whole-book", "excerpt"}:
        issue("analysis.scope.kind", "Expected whole-book or excerpt.")
    reviewed = strings(scope.get("reviewedChapterIds"), "analysis.scope.reviewedChapterIds", True, True)
    strings(scope.get("limitations"), "analysis.scope.limitations")
    if set(reviewed) - set(chapters):
        issue("analysis.scope.reviewedChapterIds", "Contains chapter IDs absent from corpus.")
    if scope.get("kind") == "whole-book" and set(reviewed) != set(chapters):
        issue("analysis.scope.reviewedChapterIds", "Whole-book scope must enumerate exactly the corpus chapter set; this is a declared scope check, not proof of reading.")
    themes = records(analysis.get("themes"), "analysis.themes", True)
    claims = records(analysis.get("claims"), "analysis.claims", True)
    relations = records(analysis.get("relations"), "analysis.relations")
    assigned = Counter()
    for theme_id, theme in themes.items():
        prefix = f"analysis.themes[{theme_id}]"
        text(theme.get("label"), f"{prefix}.label")
        text(theme.get("summary"), f"{prefix}.summary")
        for claim_id in strings(theme.get("claimIds"), f"{prefix}.claimIds", True, True):
            assigned[claim_id] += 1
            if claim_id not in claims:
                issue(f"{prefix}.claimIds", f"Unknown claim ID {claim_id}.")
            elif claims[claim_id].get("themeId") != theme_id:
                issue(f"{prefix}.claimIds", f"Claim {claim_id} belongs to another theme.")

    def evidence(values, path):
        supports = 0
        for index, value in enumerate(array(values, path, True)):
            prefix = f"{path}[{index}]"
            row = object_(value, prefix)
            passage_id = row.get("passageId")
            valid_id = text(passage_id, f"{prefix}.passageId")
            valid_quote = text(row.get("quote"), f"{prefix}.quote")
            text(row.get("rationale"), f"{prefix}.rationale")
            if not isinstance(row.get("role"), str) or row.get("role") not in {"supports", "complicates"}:
                issue(f"{prefix}.role", "Expected supports or complicates.")
            supports += row.get("role") == "supports"
            if valid_id and passage_id not in passages:
                issue(f"{prefix}.passageId", "Unknown passage ID.")
            elif valid_id:
                passage = passages[passage_id]
                if valid_quote and (not isinstance(passage.get("text"), str) or row["quote"] not in passage["text"]):
                    issue(f"{prefix}.quote", "Quote must be an exact contiguous substring of the normalized passage; invented ellipses or changed punctuation are invalid.")
                if passage.get("chapterId") not in reviewed:
                    issue(f"{prefix}.passageId", "Evidence belongs to a chapter outside reviewedChapterIds.")
        return supports

    for claim_id, claim in claims.items():
        prefix = f"analysis.claims[{claim_id}]"
        if "label" in claim:
            text(claim["label"], f"{prefix}.label")
        for key in ["text", "themeId"]:
            text(claim.get(key), f"{prefix}.{key}")
        if not isinstance(claim.get("themeId"), str) or claim.get("themeId") not in themes:
            issue(f"{prefix}.themeId", "Unknown theme ID.")
        if assigned[claim_id] != 1:
            issue(prefix, "Every claim must occur in exactly one theme's claimIds.")
        if not isinstance(claim.get("stance"), str) or claim.get("stance") not in {"interpretation", "textual-observation"}:
            issue(f"{prefix}.stance", "Expected interpretation or textual-observation.")
        if not isinstance(claim.get("confidence"), str) or claim.get("confidence") not in {"strong", "plausible", "tentative"}:
            issue(f"{prefix}.confidence", "Expected strong, plausible or tentative.")
        alternatives = strings(claim.get("alternatives"), f"{prefix}.alternatives")
        if claim.get("stance") == "interpretation" and not alternatives:
            issue(f"{prefix}.alternatives", "An interpretation requires at least one nonempty alternative reading.")
        text(claim.get("limits"), f"{prefix}.limits", True)
        if evidence(claim.get("evidence"), f"{prefix}.evidence") < 1:
            issue(f"{prefix}.evidence", "Every claim needs at least one supports evidence record.")
    for relation_id, relation in relations.items():
        prefix = f"analysis.relations[{relation_id}]"
        for key in ["fromClaimId", "toClaimId"]:
            if text(relation.get(key), f"{prefix}.{key}") and relation[key] not in claims:
                issue(f"{prefix}.{key}", "Unknown claim ID.")
        if not isinstance(relation.get("type"), str) or relation.get("type") not in {"supports", "contrasts", "develops", "complicates"}:
            issue(f"{prefix}.type", "Unsupported relation type.")
        text(relation.get("rationale"), f"{prefix}.rationale")
        evidence(relation.get("evidence"), f"{prefix}.evidence")
    return {"passed": not findings, "findings": findings,
            "counts": {"chapters": len(chapters), "passages": len(passages), "reviewedChapters": len(set(reviewed)), "themes": len(themes), "claims": len(claims), "relations": len(relations)},
            "semanticQuality": "not-assessed", "limitations": [SEMANTIC_LIMIT]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="Prepare UTF-8 TXT/Markdown, preserving stable passage anchors.")
    prepare_parser.add_argument("--input", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--title", required=True)
    prepare_parser.add_argument("--author", required=True)
    prepare_parser.add_argument("--source-url", default="")
    prepare_parser.add_argument("--max-reading-bytes", type=int, default=18000)
    check_parser = commands.add_parser("check", help="Check evidence structure; diagnostic mode returns JSON even on findings.")
    check_parser.add_argument("--corpus", type=Path, required=True)
    check_parser.add_argument("--analysis", type=Path, required=True)
    check_parser.add_argument("--output", type=Path)
    check_parser.add_argument("--fail-on-findings", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.input, args.output, args.title, args.author, args.source_url, args.max_reading_bytes)
        else:
            result = check(json.loads(args.corpus.read_text(encoding="utf-8-sig")), json.loads(args.analysis.read_text(encoding="utf-8-sig")))
    except (OSError, UnicodeError, ValueError) as error:
        result = {"passed": False, "findings": [{"path": args.command, "message": str(error)}], "semanticQuality": "not-assessed", "limitations": [SEMANTIC_LIMIT]}
    if args.command == "check" and args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if not result["passed"] and (args.command == "prepare" or args.fail_on_findings) else 0


if __name__ == "__main__":
    sys.exit(main())
