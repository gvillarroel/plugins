"""DCAT/Dublin Core/SKOS mapping and SHACL-backed stewardship checks."""

from __future__ import annotations

import hashlib
import json
import math
import re
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from pyshacl import validate
from rdflib import RDF, RDFS, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, FOAF, SH, SKOS

KC = Namespace("https://example.org/knowledge-catalog/")
RETAIL = Namespace("https://example.org/knowledge-catalog/retail/")
CONCEPT_NAMES = {
    "Customer",
    "Order",
    "Product",
    "Payment",
    "Return",
    "Quantity",
    "Revenue",
    "Currency",
    "Date",
    "Identifier",
    "Category",
}


def _resource(name: str) -> str:
    packaged = resources.files("knowledge_catalog").joinpath("data", name)
    if packaged.is_file():
        return packaged.read_text(encoding="utf-8")
    return (Path(__file__).resolve().parents[2] / "ontology" / name).read_text(encoding="utf-8")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _evidence(value: object) -> bool:
    return _text(value) or (isinstance(value, list) and bool(value) and all(_text(item) for item in value))


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and (not isinstance(value, float) or math.isfinite(value))
    )


def _field(metadata: dict, name: str) -> object:
    source = metadata.get("source", {})
    value = metadata.get(name)
    return value if value is not None else (source.get(name) if isinstance(source, dict) else None)


def _safe_source_url(value: object) -> bool:
    if not _text(value) or re.search(r'[\s<>"{}|\\^`]', value):
        return False
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username is not None:
            return False
        if parts.fragment:
            return False
        sensitive = {
            "token",
            "key",
            "apikey",
            "auth",
            "authorization",
            "password",
            "secret",
            "signature",
            "credential",
            "email",
            "phone",
            "ssn",
        }
        return not any(set(re.split(r"[-_]", key.lower())) & sensitive for key, _ in parse_qsl(parts.query))
    except ValueError:
        return False


def metadata_to_graph(metadata: dict) -> Graph:
    """Map known metadata properties only. No remote RDF or imports are resolved."""
    graph = Graph()
    for prefix, namespace in (
        ("kc", KC),
        ("retail", RETAIL),
        ("dcat", DCAT),
        ("dct", DCTERMS),
        ("skos", SKOS),
        ("foaf", FOAF),
    ):
        graph.bind(prefix, namespace)
    source = metadata.get("source", {})
    source = source if isinstance(source, dict) else {}
    sha = source.get("sha256", "")
    identity = (
        sha
        if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha)
        else hashlib.sha256(json.dumps(metadata, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    )
    dataset = URIRef(f"urn:sha256:{identity}")
    distribution = URIRef(f"urn:sha256:{identity}:distribution")
    graph.add((dataset, RDF.type, DCAT.Dataset))
    graph.add((distribution, RDF.type, DCAT.Distribution))
    graph.add((dataset, DCAT.distribution, distribution))
    for key, predicate in (
        ("title", DCTERMS.title),
        ("description", DCTERMS.description),
        ("domain", KC.domain),
    ):
        if _text(metadata.get(key)):
            graph.add((dataset, predicate, Literal(metadata[key])))
    if _text(sha):
        graph.add((dataset, KC.sha256, Literal(sha)))
    if _text(source.get("format")):
        graph.add((distribution, DCTERMS.format, Literal(source["format"])))
    for key in ("url", "dataset_url", "source_url"):
        if _safe_source_url(source.get(key)):
            graph.add((dataset, DCAT.landingPage, URIRef(source[key])))
            graph.add((distribution, DCAT.accessURL, URIRef(source[key])))
            break
    owner = _field(metadata, "owner")
    if _text(owner):
        agent = BNode()
        graph.add((agent, RDF.type, FOAF.Agent))
        graph.add((agent, FOAF.name, Literal(owner.strip())))
        graph.add((dataset, DCTERMS.publisher, agent))
    license_name = _field(metadata, "license")
    if _text(license_name):
        license_node = BNode()
        graph.add((license_node, RDF.type, DCTERMS.LicenseDocument))
        graph.add((license_node, RDFS.label, Literal(license_name.strip())))
        graph.add((dataset, DCTERMS.license, license_node))
        graph.add((distribution, DCTERMS.license, license_node))
    concepts = metadata.get("concepts", [])
    for concept in concepts if isinstance(concepts, list) else []:
        uri = concept.get("concept") if isinstance(concept, dict) else None
        if isinstance(uri, str) and uri.startswith(str(RETAIL)):
            graph.add((dataset, DCAT.theme, URIRef(uri)))
    for keyword in metadata.get("keywords", []) if isinstance(metadata.get("keywords", []), list) else []:
        if _text(keyword):
            graph.add((dataset, DCAT.keyword, Literal(keyword)))
    columns = metadata.get("columns", [])
    for index, column in enumerate(columns if isinstance(columns, list) else []):
        if not isinstance(column, dict):
            continue
        node = URIRef(f"{dataset}:column:{index}")
        graph.add((node, RDF.type, KC.Column))
        graph.add((dataset, DCTERMS.hasPart, node))
        for key, predicate in (
            ("name", DCTERMS.title),
            ("data_type", KC.dataType),
            ("semantic_type", KC.semanticType),
        ):
            if _text(column.get(key)):
                graph.add((node, predicate, Literal(column[key])))
        semantic_type = column.get("semantic_type")
        if isinstance(semantic_type, str) and semantic_type in CONCEPT_NAMES:
            concept = RETAIL[semantic_type]
            graph.add((node, DCTERMS.subject, concept))
            graph.add((concept, RDF.type, SKOS.Concept))
            graph.add((concept, SKOS.prefLabel, Literal(semantic_type, lang="en")))
            graph.add((concept, SKOS.inScheme, RETAIL.Scheme))
    return graph


def validate_metadata(metadata: dict) -> dict:
    """Return shape conformance, a transparent rubric score, and actionable findings.

    SHACL validates structure and vocabulary, not factual truth. Extra checks gate
    unreviewed PII and unsupported synthetic claims. A score of 100 never replaces
    human approval or independently verifies a license or ownership assertion.
    """
    if not isinstance(metadata, dict):
        return {
            "score": 0,
            "conforms": False,
            "findings": [
                {
                    "code": "INVALID_METADATA",
                    "severity": "error",
                    "message": "Metadata must be a JSON object.",
                }
            ],
            "report": "Metadata must be a JSON object.",
        }
    findings: list[dict] = []

    def add(code: str, message: str, severity: str = "error", **details: object) -> None:
        findings.append({"code": code, "severity": severity, "message": message, **details})

    if not isinstance(metadata.get("source"), dict):
        add("INVALID_SOURCE", "source must be an object containing observed source provenance.")
    elif metadata["source"].get("publication_allowed") is False:
        add(
            "UNKNOWN_LICENSE",
            "Source provenance records an unrecognized license and disallows publication. Correct the upstream license evidence and reanalyze the source; a metadata override cannot remove this restriction.",
        )
    source = metadata.get("source", {})
    if isinstance(source, dict):
        for key in ("url", "dataset_url", "source_url", "uri"):
            if (
                key == "uri"
                and isinstance(source.get(key), str)
                and not source[key].startswith(("https://", "http://"))
            ):
                continue  # Cloud resource identifiers are not public web landing URLs.
            if key in source and not _safe_source_url(source[key]):
                add(
                    "SENSITIVE_OR_INVALID_SOURCE_URL",
                    "Source URLs must be public HTTP(S) references without credentials, sensitive query parameters or fragments. Replace the link with a public landing page before approval.",
                    field=key,
                )
    if not isinstance(metadata.get("columns", []), list):
        add("INVALID_COLUMNS", "columns must be a list.")
    else:
        columns = metadata.get("columns", [])
        if any(not isinstance(column, dict) for column in columns):
            add("INVALID_COLUMN", "Each column must be a JSON object.")
        names = [column.get("name") for column in columns if isinstance(column, dict)]
        string_names = [name for name in names if isinstance(name, str)]
        if len(string_names) != len(set(string_names)):
            add("DUPLICATE_COLUMN", "Column names must be unique.")
    if not isinstance(metadata.get("concepts", []), list):
        add("INVALID_CONCEPTS", "concepts must be a list of suggested concept objects.")
    else:
        for concept in metadata.get("concepts", []):
            if not isinstance(concept, dict) or not _text(concept.get("concept")):
                add("INVALID_CONCEPT", "Each concept must include its vocabulary URI.")
            elif not concept["concept"].startswith(str(RETAIL)):
                add("UNKNOWN_CONCEPT", "Use concepts from the installed retail vocabulary.")
    for name in ("title", "description", "domain", "owner", "license"):
        value = _field(metadata, name)
        if value is not None and not _text(value):
            add("INVALID_FIELD", f"{name} must be a nonempty string.", field=name)
    synthetic = _field(metadata, "synthetic")
    if synthetic is not None and not isinstance(synthetic, bool):
        add("INVALID_SYNTHETIC_CLAIM", "synthetic must be true or false, with evidence for true.")
    if synthetic is True and not _evidence(_field(metadata, "synthetic_evidence")):
        add(
            "SYNTHETIC_EVIDENCE_REQUIRED",
            "A synthetic-data claim needs a source statement or generation record; a dataset name is insufficient.",
        )
    columns = metadata.get("columns", [])
    columns = columns if isinstance(columns, list) else []
    mapped_columns = 0
    for column in columns:
        if not isinstance(column, dict):
            continue
        if isinstance(column.get("semantic_type"), str) and column["semantic_type"] in CONCEPT_NAMES:
            mapped_columns += 1
        elif column.get("semantic_type") == "Unknown":
            add(
                "UNMAPPED_COLUMN",
                "The column has no mapped business concept; record its meaning or retain this explicit coverage gap.",
                "warning",
                column=column.get("name", ""),
            )
        if column.get("data_type") == "mixed":
            add(
                "MIXED_COLUMN_TYPES",
                "Observed types are mixed; confirm the schema or document the source inconsistency.",
                "warning",
                column=column.get("name", ""),
            )
        statistics = column.get("statistics", {})
        if not isinstance(statistics, dict):
            add("INVALID_COLUMN_STATISTICS", "Column statistics must be an object.")
        else:
            counts = {
                key: statistics[key]
                for key in (
                    "observed_count",
                    "non_null_count",
                    "null_count",
                    "distinct_count",
                    "min_length",
                    "max_length",
                )
                if key in statistics
            }
            if any(not _count(value) for value in counts.values()):
                add(
                    "INVALID_COLUMN_COUNTS",
                    "Observed counts and lengths must be nonnegative integers.",
                    column=column.get("name", ""),
                )
            else:
                if (
                    all(key in counts for key in ("observed_count", "non_null_count", "null_count"))
                    and counts["observed_count"] != counts["non_null_count"] + counts["null_count"]
                ):
                    add(
                        "INCONSISTENT_COLUMN_COUNTS",
                        "Observed count must equal non-null plus null counts.",
                        column=column.get("name", ""),
                    )
                if (
                    "distinct_count" in counts
                    and "non_null_count" in counts
                    and counts["distinct_count"] > counts["non_null_count"]
                ):
                    add(
                        "INCONSISTENT_DISTINCT_COUNT",
                        "Distinct count cannot exceed the non-null count.",
                        column=column.get("name", ""),
                    )
                if (
                    "min_length" in counts
                    and "max_length" in counts
                    and counts["min_length"] > counts["max_length"]
                ):
                    add("INCONSISTENT_LENGTH_RANGE", "Minimum length cannot exceed maximum length.")
            fraction = statistics.get("null_fraction")
            if fraction is not None:
                if not _finite_number(fraction) or not 0 <= fraction <= 1:
                    add("INVALID_NULL_FRACTION", "Null fraction must be finite and between zero and one.")
                elif _count(counts.get("observed_count")) and _count(counts.get("null_count")):
                    expected = (
                        counts["null_count"] / counts["observed_count"] if counts["observed_count"] else 0
                    )
                    if not math.isclose(fraction, expected, abs_tol=0.000051):
                        add("INCONSISTENT_NULL_FRACTION", "Null fraction must agree with observed counts.")
            type_counts = statistics.get("type_counts")
            if type_counts is not None:
                if not isinstance(type_counts, dict) or any(
                    not _count(value) for value in type_counts.values()
                ):
                    add("INVALID_TYPE_COUNTS", "Type counts must be an object of nonnegative integers.")
                elif (
                    _count(statistics.get("non_null_count"))
                    and sum(type_counts.values()) != statistics["non_null_count"]
                ):
                    add("INCONSISTENT_TYPE_COUNTS", "Type counts must sum to the non-null count.")
            extrema = {key: statistics[key] for key in ("minimum", "maximum", "mean") if key in statistics}
            if any(not _finite_number(value) for value in extrema.values()):
                add("INVALID_NUMERIC_STATISTICS", "Numeric aggregates must be finite numbers.")
            elif "minimum" in extrema and "maximum" in extrema and extrema["minimum"] > extrema["maximum"]:
                add("INCONSISTENT_NUMERIC_RANGE", "Minimum cannot exceed maximum.")
        fraction = statistics.get("null_fraction") if isinstance(statistics, dict) else None
        if isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and fraction > 0.2:
            add(
                "COLUMN_COMPLETENESS_GAP",
                "More than 20% of the observed column values are missing; this may be conditional and requires domain interpretation.",
                "warning",
                column=column.get("name", ""),
            )
        candidates = column.get("concepts", [])
        if not isinstance(candidates, list):
            add("INVALID_COLUMN_CONCEPTS", "Column concept suggestions must be a list.")
            continue
        for candidate in candidates:
            uri = candidate.get("concept") if isinstance(candidate, dict) else None
            label = uri.removeprefix(str(RETAIL)) if isinstance(uri, str) else None
            if label not in CONCEPT_NAMES:
                add(
                    "UNKNOWN_COLUMN_CONCEPT",
                    "Column concept suggestions must reference the installed retail vocabulary.",
                )
            elif candidate.get("label", label) != label:
                add("CONCEPT_LABEL_MISMATCH", "A column concept label must match its vocabulary URI.")
    pii = bool(metadata.get("pii_flags")) or any(
        isinstance(column, dict) and bool(column.get("pii_flags")) for column in columns
    )
    if pii and metadata.get("privacy_reviewed") is not True:
        add(
            "PRIVACY_REVIEW_REQUIRED",
            "A steward must review detected personal or sensitive identifiers and explicitly set privacy_reviewed=true.",
        )
    elif pii:
        add(
            "PII_REVIEW_RECORDED",
            "The draft records a human privacy review; this assertion is not independently verified.",
            "info",
        )
    source_findings = metadata.get("quality_findings", [])
    source_errors = (
        [item for item in source_findings if isinstance(item, dict) and item.get("severity") == "error"]
        if isinstance(source_findings, list)
        else []
    )
    for item in source_errors:
        # Evidence remains attached to the immutable profiler finding even after
        # a steward acknowledges the limitation; acknowledgment is not a repair.
        details = {"source_code": item.get("code", "SOURCE_QUALITY"), "evidence": item.get("evidence", {})}
        if metadata.get("data_quality_reviewed") is True:
            add(
                "SOURCE_LIMITATION_ACKNOWLEDGED",
                "A steward acknowledged a source quality limitation; review the retained original evidence.",
                "warning",
                **details,
            )
        else:
            add(
                "SOURCE_QUALITY_REVIEW_REQUIRED",
                "Source quality errors require an explicit data_quality_reviewed=true acknowledgment and documented limitations before approval.",
                **details,
            )
    if (
        source_errors
        and metadata.get("data_quality_reviewed") is True
        and not _evidence(metadata.get("limitations"))
    ):
        add(
            "SOURCE_LIMITATION_REQUIRED",
            "Document the observed source quality limitations when acknowledging them.",
        )
    profile = metadata.get("profile", {})
    if not isinstance(profile, dict):
        add("INVALID_PROFILE", "Source profile must be an object.")
    elif profile.get("kind") == "tabular":
        sampled_rows = profile.get("sampled_rows")
        if not _count(sampled_rows) or not isinstance(profile.get("sampled"), bool):
            add(
                "INVALID_SAMPLE_PROFILE",
                "Tabular profiles require a nonnegative sampled_rows integer and sampled boolean.",
            )
        if profile.get("column_count") != len(columns) or not _count(profile.get("column_count")):
            add("SCHEMA_PROFILE_MISMATCH", "The editable schema must retain the observed column count.")
        row_count = profile.get("row_count")
        if row_count is not None and (
            not _count(row_count)
            or (
                _count(sampled_rows)
                and (
                    row_count < sampled_rows
                    or (profile.get("sampled") is False and row_count != sampled_rows)
                )
            )
        ):
            add("ROW_PROFILE_MISMATCH", "Known total rows must agree with the declared sample scope.")
        for column in columns:
            stats = column.get("statistics", {}) if isinstance(column, dict) else {}
            if (
                isinstance(stats, dict)
                and "observed_count" in stats
                and stats["observed_count"] != sampled_rows
            ):
                add("COLUMN_SAMPLE_MISMATCH", "Column observations must agree with sampled_rows.")
    if isinstance(profile, dict) and profile.get("sampled"):
        add(
            "SAMPLE_LIMITATION",
            "Statistics and PII checks cover only a prefix sample; verify whole-source expectations separately.",
            "warning",
        )
    if isinstance(profile, dict) and profile.get("kind") == "tabular" and profile.get("sampled_rows") == 0:
        add("EMPTY_SOURCE", "No data rows support the proposed schema or semantic interpretation.", "warning")
    if (
        isinstance(profile, dict)
        and profile.get("kind") == "document"
        and profile.get("sampled_characters") == 0
    ):
        add(
            "NO_DOCUMENT_EVIDENCE",
            "No document text was extracted to support its proposed semantics.",
            "warning",
        )
    try:
        graph = metadata_to_graph(metadata)
        ontology = Graph().parse(data=_resource("domain.ttl"), format="turtle")
        shapes = Graph().parse(data=_resource("shapes.ttl"), format="turtle")
        conforms, report_graph, report_text = validate(
            graph,
            shacl_graph=shapes,
            ont_graph=ontology,
            inference="none",
            abort_on_first=False,
            allow_infos=True,
            allow_warnings=True,
            advanced=False,
            js=False,
            do_owl_imports=False,
        )
        if not isinstance(report_graph, Graph):
            add("VALIDATOR_FAILURE", "The SHACL validator could not produce a validation graph.")
            conforms = False
        else:
            for result in report_graph.subjects(RDF.type, SH.ValidationResult):
                messages = list(report_graph.objects(result, SH.resultMessage))
                path = report_graph.value(result, SH.resultPath)
                severity = report_graph.value(result, SH.resultSeverity)
                add(
                    "SHACL_CONSTRAINT",
                    str(messages[0]) if messages else "Metadata violates a SHACL constraint.",
                    "warning" if severity == SH.Warning else "error",
                    path=str(path) if path else "",
                )
    except Exception as exc:  # noqa: BLE001 -- malformed RDF or validator failures must fail closed
        # Fail closed; report only exception classes, never arbitrary metadata values.
        conforms = False
        report_text = f"Ontology validation could not complete ({type(exc).__name__})."
        add("VALIDATOR_FAILURE", report_text)
    # Nested SHACL constraints can have duplicate messages; count unique findings.
    findings = list({json.dumps(item, sort_keys=True): item for item in findings}.values())
    findings.sort(key=lambda item: (item["severity"], item["code"], item.get("path", "")))
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "score": max(0, 100 - 12 * errors - 3 * warnings),
        "conforms": bool(conforms) and errors == 0,
        "findings": findings,
        "report": str(report_text),
        "rubric": "100 minus 12 per unique error and 3 per warning; heuristic completeness, not factual accuracy.",
        "coverage": {
            "mapped_columns": mapped_columns,
            "total_columns": len(columns),
            "mapping_fraction": mapped_columns / len(columns) if columns else None,
        },
    }
