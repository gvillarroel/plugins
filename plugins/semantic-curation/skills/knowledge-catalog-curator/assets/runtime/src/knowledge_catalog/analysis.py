"""Bounded local profiling; source content is data, never executable instructions.

Semantic suggestions use TF-IDF against an explicit retail vocabulary. Scores are
similarities, not calibrated probabilities; stewardship still requires a human.
No source values, excerpts, top values, or raw PII samples leave this module.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import ipaddress
import json
import math
import re
import statistics
import unicodedata
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 5_000
MAX_COLUMNS = 250
MAX_TEXT_CHARS = 200_000
MAX_PDF_PAGES = 50
MAX_CELL_CHARS = 10_000
CONCEPT_BASE = "https://example.org/knowledge-catalog/retail/"
CONCEPTS = {
    "Customer": "customer customers client clients buyer buyers user users cliente clientes usuario usuarios",
    "Order": "order orders purchase purchases transaction transactions venta ventas pedido pedidos",
    "Product": "product products sku item items producto productos stock inventory inventario",
    "Payment": "payment payments paid card invoice billing pago pagos factura tarjeta",
    "Return": "return returns returned refund refunds retorno devolucion devoluciones reembolso",
    "Quantity": "quantity quantities units count cantidad unidades",
    "Revenue": "revenue amount price total subtotal cost sales ingreso ingresos importe precio monto",
    "Currency": "currency currencies moneda monedas usd eur gbp",
    "Date": "date dates timestamp created updated fecha fechas time datetime",
    "Identifier": "identifier id key code codigo identificador",
    "Category": "category categories segment department categoria categorias segmento",
}
_EMAIL = re.compile(r"(?<![\w.+-])[\w.%+-]+@[\w.-]+\.[^\W\d_]{2,}(?![\w-])", re.IGNORECASE)
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_PHONE = re.compile(r"(?<!\w)(?:\+\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}(?!\w)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_INJECTION = re.compile(
    r"ignore\s+(?:all\s+|the\s+)?(?:previous|prior|system)\s+instructions|"
    r"(?:system|assistant)\s*:\s*|(?:auto[- ]?approve|bypass\s+(?:approval|review))",
    re.IGNORECASE,
)


class AnalysisError(ValueError):
    """Source could not be profiled safely or has an unsupported format."""


def _finding(code: str, message: str, severity: str = "warning", **extra: Any) -> dict:
    return {"code": code, "severity": severity, "message": message, **extra}


def _words(value: str) -> str:
    value = "".join(char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char))
    return re.sub(r"[^\w]+", " ", re.sub(r"([a-z])([A-Z])", r"\1 \2", value)).replace("_", " ").lower()


def _semantic(text: str) -> list[dict]:
    corpus = list(CONCEPTS.values())
    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[^\W\d_]{2,}\b", lowercase=True)
    matrix = vectorizer.fit_transform(corpus)
    scores = cosine_similarity(vectorizer.transform([_words(text)]), matrix)[0]
    return [
        {
            "concept": CONCEPT_BASE + name,
            "label": name,
            "confidence": round(float(score), 4),
            "evidence": "TF-IDF similarity to curated vocabulary; requires human verification",
        }
        for name, score in sorted(zip(CONCEPTS, scores), key=lambda item: (-item[1], item[0]))
        if score > 0
    ][:6]


def _luhn(value: str) -> bool:
    digits = [int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _pii(text: str, header: str = "") -> list[str]:
    text = unicodedata.normalize("NFKC", text)
    flags: set[str] = set()
    normalized = _words(header)
    tokens = set(normalized.split())
    if tokens & {"email", "correo"} or _EMAIL.search(text):
        flags.add("email")
    if (
        tokens & {"phone", "telephone", "mobile", "telefono"}
        or _PHONE.search(text)
        or re.search(r"(?<!\w)\+[1-9]\d{8,14}(?!\d)", text)
    ):
        flags.add("phone")
    if tokens & {"ssn", "passport", "dni", "nationalid"} or _SSN.search(text):
        flags.add("government_identifier")
    if tokens & {"name", "nombre", "surname", "apellido"} and not tokens & {
        "product",
        "producto",
        "item",
        "brand",
        "category",
        "company",
        "organization",
    }:
        flags.add("person_name")
    if tokens & {"address", "direccion", "street", "postcode", "zipcode"}:
        flags.add("postal_address")
    if tokens & {"card", "tarjeta", "iban"} or any(_luhn(match.group()) for match in _CARD.finditer(text)):
        flags.add("financial_identifier")
    if tokens & {"customer", "client", "cliente", "buyer", "user", "usuario"} and tokens & {
        "id",
        "identifier",
        "key",
        "age",
        "gender",
        "location",
        "edad",
        "genero",
        "ubicacion",
    }:
        flags.add("quasi_identifier")
    if tokens & {"ip", "ipv4", "ipv6"}:
        flags.add("ip_address")
    candidates = [text.strip()] if len(text) < 50 else []
    candidates.extend(re.findall(r"(?<![\w:])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])", text))
    candidates.extend(re.findall(r"(?<!\w)(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:]{0,4}(?!\w)", text))
    for candidate in candidates:
        try:
            ipaddress.ip_address(candidate)
            flags.add("ip_address")
        except ValueError:
            pass
    return sorted(flags)


def _kind(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (dict, list)):
        return "json"
    text = str(value).strip()
    if text.lower() in {"true", "false"}:
        return "boolean"
    if re.fullmatch(r"[-+]?\d+", text):
        # Keep zero-padded codes as strings so their lexical identity is visible.
        if len(text.lstrip("+-")) > 1 and text.lstrip("+-").startswith("0"):
            return "string"
        return "integer"
    try:
        if math.isfinite(float(text)):
            return "number"
    except (ValueError, OverflowError):
        pass
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            date.fromisoformat(text)
            return "date"
        if re.match(r"^\d{4}-\d{2}-\d{2}T", text):
            datetime.fromisoformat(text)
            return "datetime"
    except ValueError:
        pass
    return "string"


def _column(name: str, values: list[Any]) -> dict:
    present = [value for value in values if value is not None and str(value).strip() != ""]
    texts = [
        json.dumps(value, sort_keys=True, ensure_ascii=False)
        if isinstance(value, (dict, list))
        else str(value)
        for value in present
    ]
    types = Counter(_kind(value) for value in present)
    observed = set(types)
    data_type = "unknown" if not observed else (next(iter(observed)) if len(observed) == 1 else "mixed")
    if observed == {"integer", "number"}:
        data_type = "number"
    flags = set(_pii("", name))
    for text in texts:
        flags.update(_pii(text))
    stats: dict[str, Any] = {
        "observed_count": len(values),
        "non_null_count": len(present),
        "null_count": len(values) - len(present),
        "distinct_count": len(
            {
                json.dumps([type(value).__name__, value], sort_keys=True, ensure_ascii=False)
                for value in present
            }
        ),
        "distinct_semantics": "typed observed representation; excludes null and blank strings",
        "null_fraction": round((len(values) - len(present)) / len(values), 4) if values else 0.0,
        "type_counts": dict(sorted(types.items())),
    }
    if texts:
        stats.update(min_length=min(map(len, texts)), max_length=max(map(len, texts)))
    if present and data_type in {"integer", "number"} and not flags:
        try:
            numbers = [int(value) if data_type == "integer" else float(value) for value in present]
            if all(math.isfinite(value) for value in numbers):
                stats.update(minimum=min(numbers), maximum=max(numbers))
                stats.update(mean=statistics.fmean(numbers), mean_precision="IEEE-754 floating point")
                if data_type == "integer" and any(abs(value) > 2**53 for value in numbers):
                    stats["mean_approximate"] = True
        except (ValueError, OverflowError):
            if data_type == "integer":
                exact = [int(value) for value in present]
                stats.update(minimum=min(exact), maximum=max(exact))
    concepts = _semantic(name)
    semantic_type = concepts[0]["label"] if concepts else "Unknown"
    caveats = []
    labels = {item["label"] for item in concepts}
    if "Revenue" in labels:
        caveats.append(
            "A monetary lexical match does not establish recognized revenue; currency, taxes and aggregation require source evidence."
        )
    if "Quantity" in labels:
        caveats.append("The unit of measure and aggregation period require source evidence.")
    if "Date" in labels:
        caveats.append("The event meaning and timezone require source evidence; none is assumed.")
    if len(concepts) > 1 and concepts[1]["confidence"] >= concepts[0]["confidence"] * 0.8:
        caveats.append(
            "Multiple vocabulary concepts have similar lexical scores; confirm the intended business meaning."
        )
    return {
        "name": name,
        "data_type": data_type,
        "semantic_type": semantic_type,
        "semantic_confidence": concepts[0]["confidence"] if concepts else 0.0,
        "concepts": concepts,
        "semantic_caveats": caveats,
        "pii_flags": sorted(flags),
        "statistics": stats,
        "description": f"Observed {data_type} field; suggested concept: {semantic_type}.",
    }


def _decode(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise AnalysisError("Input must use UTF-8 encoding; convert the source before analysis.") from exc


def _validate_headers(header: list[str], kind: str) -> None:
    normalized = [unicodedata.normalize("NFKC", name).strip() for name in header]
    if (
        any(not name or len(name) > MAX_CELL_CHARS for name in normalized)
        or len(set(normalized)) != len(normalized)
        or any(unicodedata.category(char).startswith("C") for name in header for char in name)
    ):
        raise AnalysisError(
            f"{kind} column names / field names must be unique, nonempty, bounded, and free of control or invisible format characters."
        )


def _csv_rows(path: Path) -> tuple[list[dict], list[str], bool]:
    rows: list[dict] = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            header = next(reader, None)
            if not header or not any(name.strip() for name in header):
                raise AnalysisError("CSV has no nonempty header.")
            if len(header) > MAX_COLUMNS:
                raise AnalysisError(f"CSV exceeds {MAX_COLUMNS} columns.")
            _validate_headers(header, "CSV")
            for index, row in enumerate(reader):
                if not row:
                    continue
                if len(row) != len(header):
                    raise AnalysisError(f"CSV row {index + 2} has {len(row)} fields; expected {len(header)}.")
                if any(len(value) > MAX_CELL_CHARS for value in row):
                    raise AnalysisError(f"CSV row {index + 2} exceeds the cell length limit.")
                if len(rows) == MAX_ROWS:
                    return rows, header, True
                rows.append(dict(zip(header, row)))
            return rows, header, False
    except UnicodeDecodeError as exc:
        raise AnalysisError("Input must use UTF-8 encoding; convert the source before analysis.") from exc
    except csv.Error as exc:
        raise AnalysisError(f"Malformed CSV: {exc}") from exc


def _json_rows(path: Path) -> tuple[list[dict], list[str], bool]:
    def finite_float(text: str) -> float:
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("Non-finite JSON number")
        return value

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    try:
        data = json.loads(
            _decode(path),
            parse_float=finite_float,
            object_pairs_hook=unique_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (ValueError, RecursionError) as exc:
        raise AnalysisError(
            "Malformed JSON; use finite numbers and a reasonably nested object or array of objects."
        ) from exc
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise AnalysisError("JSON must be an object or an array of objects.")
    sampled = len(data) > MAX_ROWS
    data = data[:MAX_ROWS]
    header = list(dict.fromkeys(key for row in data for key in row))
    if len(header) > MAX_COLUMNS:
        raise AnalysisError(f"JSON exceeds {MAX_COLUMNS} columns.")
    _validate_headers(header, "JSON")
    if any(
        len(json.dumps(value, ensure_ascii=False)) > MAX_CELL_CHARS for row in data for value in row.values()
    ):
        raise AnalysisError("JSON exceeds the cell length limit.")
    return data, header, sampled


def _document(path: Path) -> tuple[str, bool]:
    suffix = path.suffix.lower()
    truncated = False
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(path)
            if reader.is_encrypted:
                raise AnalysisError("Encrypted PDFs are unsupported; supply an authorized unencrypted copy.")
            parts: list[str] = []
            char_count = 0
            truncated = len(reader.pages) > MAX_PDF_PAGES
            for page in reader.pages[:MAX_PDF_PAGES]:
                page_text = page.extract_text() or ""
                parts.append(page_text[: MAX_TEXT_CHARS - char_count])
                char_count += len(page_text)
                if char_count >= MAX_TEXT_CHARS:
                    truncated = True
                    break
            text = "\n".join(parts)
        elif suffix == ".docx":
            from docx import Document

            with zipfile.ZipFile(path) as archive:
                if sum(info.file_size for info in archive.infolist()) > 50 * 1024 * 1024:
                    raise AnalysisError("DOCX expanded content exceeds 50 MiB.")
            document = Document(path)
            parts = [paragraph.text for paragraph in document.paragraphs]
            parts.extend(
                " ".join(cell.text for cell in row.cells) for table in document.tables for row in table.rows
            )
            text = "\n".join(parts)
        else:
            text = _decode(path)
    except AnalysisError:
        raise
    except Exception as exc:
        # Parsers sometimes include source excerpts in exception text; do not relay those.
        raise AnalysisError(
            f"Cannot parse {suffix.lstrip('.').upper()} document ({type(exc).__name__})."
        ) from exc
    return text[:MAX_TEXT_CHARS], truncated or len(text) > MAX_TEXT_CHARS


def _temporal_quality(rows: list[dict], header: list[str], sampled: bool) -> list[dict]:
    """Check explicitly named retail return fields; infer no return-policy window."""
    normalized = {_words(name): name for name in header}

    def named(aliases: set[str]) -> str | None:
        matches = [normalized[name] for name in sorted(aliases) if name in normalized]
        return matches[0] if len(matches) == 1 else None

    order_name = named({"order date", "purchase date", "fecha pedido", "fecha compra"})
    return_name = named({"return date", "returned date", "fecha devolucion"})
    days_name = named({"days to return", "return days", "days until return", "dias devolucion"})

    def day(value: Any) -> date | datetime | None:
        text = str(value or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?", text):
            return None
        try:
            return datetime.fromisoformat(text) if "T" in text else date.fromisoformat(text)
        except ValueError:
            return None

    def number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            result = float(value)
            return result if math.isfinite(result) else None
        except (ValueError, TypeError, OverflowError):
            return None

    counts = Counter()
    for row in rows:
        order_date = day(row.get(order_name)) if order_name else None
        return_date = day(row.get(return_name)) if return_name else None
        days = number(row.get(days_name)) if days_name else None
        if days is not None:
            counts["days_evaluated"] += 1
            if days < 0:
                counts["negative_affected"] += 1
        if order_date is not None and return_date is not None:
            both_dates = type(order_date) is date and type(return_date) is date
            both_timestamps = isinstance(order_date, datetime) and isinstance(return_date, datetime)
            comparable_timestamps = both_timestamps and bool(order_date.tzinfo) == bool(return_date.tzinfo)
            if not both_dates and not comparable_timestamps:
                counts["precision_skipped"] += 1
                continue
            counts["date_evaluated"] += 1
            if return_date < order_date:
                counts["chronology_affected"] += 1
            if both_timestamps:
                counts["timestamp_pairs"] += 1
            if days is not None and both_dates:
                counts["interval_evaluated"] += 1
                if not math.isclose(days, (return_date - order_date).days, abs_tol=1e-8):
                    counts["interval_affected"] += 1
        elif (
            order_name
            and return_name
            and any(row.get(name) not in (None, "") for name in (order_name, return_name))
        ):
            if any(
                row.get(name) not in (None, "") and day(row.get(name)) is None
                for name in (order_name, return_name)
            ):
                counts["invalid_temporal_rows"] += 1
    findings = []
    if counts["timestamp_pairs"] or counts["precision_skipped"] or counts["invalid_temporal_rows"]:
        findings.append(
            _finding(
                "TEMPORAL_PRECISION_REVIEW",
                "Timestamp chronology uses comparable instants or local times; days-to-return calendar differences are checked only for date-only pairs. Invalid or incompatible temporal values are excluded.",
                evidence={
                    "timestamp_pairs": counts["timestamp_pairs"],
                    "incompatible_pairs": counts["precision_skipped"],
                    "invalid_rows": counts["invalid_temporal_rows"],
                    "sample_scope": "prefix_sample" if sampled else "all_parsed_rows",
                },
            )
        )
    for code, counter, evaluated, message, names in (
        (
            "RETURN_BEFORE_ORDER",
            "chronology_affected",
            "date_evaluated",
            "Return dates precede order dates; verify the source chronology and document its limitation.",
            [order_name, return_name],
        ),
        (
            "NEGATIVE_RETURN_INTERVAL",
            "negative_affected",
            "days_evaluated",
            "Observed days-to-return values are negative; verify the source or document its limitation.",
            [days_name],
        ),
        (
            "RETURN_INTERVAL_MISMATCH",
            "interval_affected",
            "interval_evaluated",
            "Days-to-return differs from the calendar-day difference of return and order dates; confirm the field definition.",
            [order_name, return_name, days_name],
        ),
    ):
        if counts[counter]:
            findings.append(
                _finding(
                    code,
                    message,
                    "error",
                    evidence={
                        "affected_rows": counts[counter],
                        "evaluated_rows": counts[evaluated],
                        "sample_scope": "prefix_sample" if sampled else "all_parsed_rows",
                        "columns": [name for name in names if name],
                    },
                )
            )
    return findings


def analyze_file(path: str | Path, domain: str = "retail", provenance: dict | None = None) -> dict:
    """Return a JSON-serializable draft without executing content or accessing a network.

    Sampling is the first 5,000 rows / 200,000 text characters / 50 PDF pages;
    statistics describe that sample only. Missing ownership, licenses, and claims
    of synthetic generation must be supplied with evidence by a human reviewer.
    """
    if domain != "retail":
        raise AnalysisError("Only the curated 'retail' domain is currently supported.")
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise AnalysisError("Source must be an existing regular file.")
    size = source_path.stat().st_size
    if size > MAX_BYTES:
        raise AnalysisError(f"Source exceeds the {MAX_BYTES // (1024 * 1024)} MiB input limit.")
    suffix = source_path.suffix.lower()
    if suffix not in {".csv", ".json", ".txt", ".md", ".pdf", ".docx"}:
        raise AnalysisError("Supported sources: CSV, JSON, TXT, MD, PDF, DOCX.")
    digest = hashlib.sha256()
    with source_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if provenance is not None and not isinstance(provenance, dict):
        raise AnalysisError("provenance must be an object containing source evidence.")
    source = copy.deepcopy(provenance or {})
    # Downloader transport paths describe the workstation, not the dataset.
    for key in ("local_files", "local_directory", "local_path", "archive_path", "raw_metadata_path"):
        source.pop(key, None)
    if isinstance(source.get("license"), dict):
        license_details = source.pop("license")
        source["license_details"] = license_details
        known_license = license_details.get("spdx_id") or license_details.get("name")
        if isinstance(known_license, str) and known_license.strip():
            source["license"] = known_license
    if isinstance(source.get("synthetic"), dict):
        synthetic_claim = source.pop("synthetic")
        source["synthetic_claim"] = synthetic_claim
        if isinstance(synthetic_claim.get("publisher_claim"), bool):
            source["synthetic"] = synthetic_claim["publisher_claim"]
        if synthetic_claim.get("evidence"):
            source["synthetic_evidence"] = synthetic_claim["evidence"]
    # Observed facts cannot be replaced by supplied provenance.
    source.update(filename=source_path.name, sha256=digest.hexdigest(), size_bytes=size, format=suffix[1:])
    findings = [
        _finding(
            "HEURISTIC_SEMANTICS",
            "Semantic suggestions use lexical similarity; a steward must verify their meaning.",
            "info",
        )
    ]
    columns: list[dict] = []
    if suffix in {".csv", ".json"}:
        rows, header, sampled = _csv_rows(source_path) if suffix == ".csv" else _json_rows(source_path)
        columns = [_column(name, [row.get(name) for row in rows]) for name in header]
        semantic_text = " ".join(header)
        profile = {
            "kind": "tabular",
            "sampled_rows": len(rows),
            "row_count": None if sampled else len(rows),
            "column_count": len(header),
            "sampled": sampled,
            "sampling_method": "first_rows",
            "row_limit": MAX_ROWS,
        }
        description = (
            f"{source_path.suffix[1:].upper()} dataset with {len(header)} columns; {len(rows)} rows profiled"
        )
        description += " from a bounded prefix sample." if sampled else "."
        flags = sorted({flag for column in columns for flag in column["pii_flags"]})
        findings.extend(_temporal_quality(rows, header, sampled))
        for column in columns:
            if column["semantic_caveats"]:
                findings.append(
                    _finding(
                        "BUSINESS_MEANING_REQUIRED",
                        "Confirm the field meaning and unknown units or temporal context; lexical suggestions alone do not establish them.",
                        column=column["name"],
                        caveats=column["semantic_caveats"],
                    )
                )
            if column["data_type"] == "mixed":
                findings.append(
                    _finding("MIXED_TYPES", "Column has mixed observed types.", column=column["name"])
                )
            if column["statistics"]["null_fraction"] > 0.2:
                findings.append(
                    _finding(
                        "MISSING_VALUES",
                        "More than 20% of sampled values are missing.",
                        column=column["name"],
                    )
                )
        if not rows:
            findings.append(_finding("EMPTY_SOURCE", "No data records were available for profiling."))
    else:
        semantic_text, sampled = _document(source_path)
        profile = {
            "kind": "document",
            "sampled": sampled,
            "sampled_characters": len(semantic_text),
            "character_limit": MAX_TEXT_CHARS,
            "pdf_page_limit": MAX_PDF_PAGES,
            "sampling_method": "prefix",
        }
        description = f"{source_path.suffix[1:].upper()} document; {len(semantic_text)} text characters analyzed locally."
        flags = _pii(semantic_text)
        if not semantic_text.strip():
            findings.append(
                _finding(
                    "NO_EXTRACTABLE_TEXT",
                    "No text could be extracted; scanned PDFs require a separate OCR workflow.",
                )
            )
    if sampled:
        findings.append(
            _finding(
                "SAMPLED_SOURCE",
                "Only a bounded prefix was profiled. Statistics and PII detection do not establish properties of the entire source.",
            )
        )
    if flags:
        findings.append(
            _finding(
                "POTENTIAL_PII",
                "Potential personal or sensitive identifiers require steward review; no source values are exported.",
                pii_flags=flags,
            )
        )
    if _INJECTION.search(semantic_text):
        findings.append(
            _finding(
                "UNTRUSTED_INSTRUCTIONS",
                "Instruction-like source content was treated only as data; it cannot approve or publish metadata.",
            )
        )
    concepts = _semantic(semantic_text)
    return {
        "schema_version": "1.0",
        "title": source_path.stem.replace("_", " ").replace("-", " "),
        "description": description,
        "domain": domain,
        "source": source,
        "profile": profile,
        "columns": columns,
        "keywords": [item["label"].lower() for item in concepts],
        "concepts": concepts,
        "pii_flags": flags,
        "quality_findings": findings,
        "semantic_method": {
            "name": "TF-IDF curated retail vocabulary",
            "library": "scikit-learn",
            "confidence_interpretation": "cosine similarity, not probability",
            "limitations": "No contextual language model; lexical matches do not prove meaning or correctness.",
        },
    }
