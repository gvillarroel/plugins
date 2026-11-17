"""Bounded, local SKOS alternatives; relevance scores never grant approval.

Only the installed demonstration vocabulary is eligible. Source values,
generated descriptions and existing assignments are not ranking evidence.
No URLs, RDF imports or external services are resolved by this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from importlib import resources
from pathlib import Path

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import OWL, SKOS

from .analysis import CONCEPT_BASE, CONCEPTS, _words

SCHEME = CONCEPT_BASE + "Scheme"
MAX_QUERY = 300
# Bump this identifier when changing ranking or eligibility rules. The method
# digest also binds the separately maintained lexical alias corpus.
RANKING_POLICY_VERSION = "skos-lexical-v3"
_REASONS = (
    "unknown_uri",
    "wrong_scheme",
    "missing_english_label",
    "missing_english_definition",
    "label_mismatch",
    "obsolete",
    "cyclic_hierarchy",
    "domain_mismatch",
    "unsupported_type",
    "no_lexical_evidence",
    "partial_alias_match",
    "unsupported_monetary_meaning",
    "context_conflict",
    "low_relevance",
    "outside_limit",
)
_TYPES = {"unknown", "mixed", "string", "integer", "number", "boolean", "date", "datetime", "json"}
_COMPATIBLE = {
    "Identifier": {"string", "integer", "number", "unknown", "mixed"},
    "Date": {"string", "date", "datetime", "unknown", "mixed"},
    "Quantity": {"integer", "number", "unknown", "mixed"},
    "Revenue": {"integer", "number", "unknown", "mixed"},
    "Currency": {"string", "integer", "unknown", "mixed"},
}
_FINANCIAL_CONTEXT = {
    "financial",
    "finance",
    "investment",
    "investments",
    "portfolio",
    "portfolios",
    "equity",
    "equities",
    "dividend",
    "dividends",
    "securities",
    "roi",
}
_USER_ALIASES = {"user", "users", "usuario", "usuarios"}
_PER_UNIT_MONETARY_CUES = {"price", "prices", "cost", "costs", "rate", "rates"}
_MONETARY_CONTEXT = {"monetary", "money", "currency", "currencies", "usd", "eur", "gbp"}
_TECHNICAL_USER_PHRASES = (
    "user agent",
    "user agents",
    "database user",
    "database users",
    "system user",
    "system users",
)
_WARNINGS = {
    "Identifier": "A matching identifier name does not establish uniqueness or a primary key.",
    "Date": "Confirm the event meaning and timezone; neither is inferred.",
    "Quantity": "Confirm the unit of measure and aggregation period.",
    "Revenue": "Confirm recognized revenue, currency, taxes and aggregation from source evidence.",
    "Currency": "Confirm the monetary denomination; no default currency is assumed.",
    "Return": "This concept means a product return, not a financial return.",
    "Customer": "Confirm the customer role and review any personal identifiers separately.",
}


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[^\W\d_][\w]*", _words(value), re.UNICODE))


def _method_version() -> str:
    inputs = {"policy": RANKING_POLICY_VERSION, "aliases": CONCEPTS}
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _english(graph: Graph, node: URIRef, predicate: URIRef) -> list[str]:
    return sorted(
        {
            str(value).strip()
            for value in graph.objects(node, predicate)
            if isinstance(value, Literal)
            and (value.language or "").lower().split("-")[0] == "en"
            and str(value).strip()
            and len(str(value)) <= 2000
        }
    )


def _registry_from_turtle(text: str) -> tuple[dict, list[dict], dict]:
    """Parse supplied local text only; useful for testing malformed vocabularies."""
    if not isinstance(text, str) or len(text.encode("utf-8")) > 500_000:
        raise ValueError("The installed vocabulary must be local Turtle text under 500 KB")
    graph = Graph().parse(data=text, format="turtle")
    version = hashlib.sha256(text.encode("utf-8")).hexdigest()
    labels = _english(graph, URIRef(SCHEME), SKOS.prefLabel)
    vocabulary = {
        "id": SCHEME,
        "label": labels[0] if labels else "Retail demonstration domain",
        "version": version,
        "license": "Apache-2.0",
        "status": "demonstration",
    }
    rejected = dict.fromkeys(_REASONS, 0)
    terms = []
    obsolete_predicates = (OWL.deprecated, URIRef("http://www.geneontology.org/formats/oboInOwl#is_obsolete"))
    for node in sorted(set(graph.subjects(RDF.type, SKOS.Concept)), key=str):
        uri = str(node)
        name = uri.removeprefix(CONCEPT_BASE)
        if not isinstance(node, URIRef) or name not in CONCEPTS or uri != CONCEPT_BASE + name:
            rejected["unknown_uri"] += 1
            continue
        if set(graph.objects(node, SKOS.inScheme)) != {URIRef(SCHEME)}:
            rejected["wrong_scheme"] += 1
            continue
        if any(
            str(value).strip().lower() in {"true", "1"}
            for predicate in obsolete_predicates
            for value in graph.objects(node, predicate)
        ):
            rejected["obsolete"] += 1
            continue
        preferred = _english(graph, node, SKOS.prefLabel)
        definitions = _english(graph, node, SKOS.definition)
        if len(preferred) != 1:
            rejected["missing_english_label"] += 1
            continue
        if preferred[0] != name:
            rejected["label_mismatch"] += 1
            continue
        if not definitions:
            rejected["missing_english_definition"] += 1
            continue
        terms.append(
            {
                "concept": uri,
                "label": name,
                "definition": definitions[0],
                "aliases": sorted({name, *_english(graph, node, SKOS.altLabel)}),
                "parents": sorted({str(parent) for parent in graph.objects(node, SKOS.broader)}),
            }
        )
    by_uri = {term["concept"]: term for term in terms}
    cyclic: set[str] = set()

    for uri in by_uri:
        pending = list(by_uri[uri]["parents"])
        visited = set()
        while pending:
            parent = pending.pop()
            if parent == uri:
                cyclic.add(uri)
                break
            if parent in by_uri and parent not in visited:
                visited.add(parent)
                pending.extend(by_uri[parent]["parents"])
    rejected["cyclic_hierarchy"] = len(cyclic)
    return vocabulary, [term for term in terms if term["concept"] not in cyclic], rejected


def _load_vocabulary() -> tuple[dict, list[dict], dict]:
    packaged = resources.files("knowledge_catalog").joinpath("data", "domain.ttl")
    source = packaged if packaged.is_file() else Path(__file__).resolve().parents[2] / "ontology/domain.ttl"
    return _registry_from_turtle(source.read_text(encoding="utf-8"))


def _phrase_in(phrase: str, context: str) -> bool:
    return bool(phrase) and f" {phrase} " in f" {context} "


def suggest_concepts(
    metadata: dict, *, column_name: str | None = None, query: str = "", limit: int = 3
) -> dict:
    """Return filtered, explained alternatives without mutating metadata or state."""
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    if not isinstance(query, str) or len(query) > MAX_QUERY:
        raise ValueError("query must be a string of at most 300 characters")
    if any(ord(char) < 32 and char not in "\n\t" for char in query):
        raise ValueError("query contains unsupported control characters")
    if type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError("limit must be an integer between 1 and 5")
    if column_name is not None and (not isinstance(column_name, str) or not column_name.strip()):
        raise ValueError("column_name must identify an observed column")
    columns = metadata.get("columns", [])
    if not isinstance(columns, list) or len(columns) > 250:
        raise ValueError("columns must be a list containing at most 250 observed fields")
    observed = [
        column for column in columns if isinstance(column, dict) and isinstance(column.get("name"), str)
    ]
    column = None
    if column_name is not None:
        matches = [item for item in observed if item["name"] == column_name]
        if len(matches) != 1:
            raise ValueError("column_name must uniquely identify an observed column")
        column = matches[0]
    vocabulary, terms, rejected = _load_vocabulary()
    by_uri = {term["concept"]: term for term in terms}
    result = {
        "status": "no_reliable_match",
        "candidates": [],
        "vocabulary": vocabulary,
        "filter_summary": rejected,
        "method": {
            "name": "Deterministic local SKOS lexical ranking",
            "score_is_probability": False,
            "policy_version": RANKING_POLICY_VERSION,
            "version": _method_version(),
        },
        "message": "No reliable local alternative matches the available evidence. Keep the meaning unresolved or add steward search context.",
    }
    if metadata.get("domain", "retail") != "retail":
        rejected["domain_mismatch"] += len(terms)
        result["message"] = (
            "The installed vocabulary supports retail only. No cross-domain alternatives were suggested."
        )
        return result
    names = [column["name"]] if column else [item["name"] for item in observed]
    normalized_name = _words(" ".join(name[:500] for name in names))
    normalized_query = _words(query)
    name_tokens, query_tokens = _tokens(normalized_name), _tokens(normalized_query)
    contexts = (normalized_name, normalized_query)
    financial_context = bool((name_tokens | query_tokens) & _FINANCIAL_CONTEXT)
    context_tokens = name_tokens | query_tokens
    per_unit_monetary_context = bool(context_tokens & _PER_UNIT_MONETARY_CUES) or bool(
        context_tokens & {"amount", "amounts"} and context_tokens & _MONETARY_CONTEXT
    )
    technical_user_context = any(
        _phrase_in(phrase, context) for phrase in _TECHNICAL_USER_PHRASES for context in contexts
    )
    data_type = column.get("data_type", "unknown") if column else None
    candidates = []
    for term in terms:
        label = term["label"]
        alias_tokens = _tokens(CONCEPTS[label])
        phrase_tokens = set()
        for alias in term["aliases"]:
            words = _tokens(alias)
            phrase_tokens.update(words)
            if len(words) == 1 or any(_phrase_in(_words(alias), context) for context in contexts):
                alias_tokens.update(words)
        name_matches, query_matches = name_tokens & alias_tokens, query_tokens & alias_tokens
        matches = name_matches | query_matches
        if not matches:
            reason = (
                "partial_alias_match"
                if (name_tokens | query_tokens) & phrase_tokens
                else "no_lexical_evidence"
            )
            rejected[reason] += 1
            continue
        # These phrases have established non-retail meanings. A warning after
        # ranking would still promote the wrong meaning as a suggested choice.
        if (
            (label == "Return" and financial_context)
            or (label == "Product" and financial_context and matches <= {"stock", "inventory", "inventario"})
            or (label == "Customer" and technical_user_context and matches <= _USER_ALIASES)
            or (label == "Quantity" and per_unit_monetary_context and matches <= {"unit", "units"})
        ):
            rejected["context_conflict"] += 1
            continue
        if column is not None and (
            not isinstance(data_type, str)
            or data_type not in _TYPES
            or data_type not in _COMPATIBLE.get(label, _TYPES)
        ):
            rejected["unsupported_type"] += 1
            continue
        if label == "Revenue" and not (name_tokens | query_tokens) & {
            "revenue",
            "revenues",
            "ingreso",
            "ingresos",
        }:
            rejected["unsupported_monetary_meaning"] += 1
            continue
        preferred_match = any(_phrase_in(_words(label), context) for context in contexts)
        synonym_match = any(
            _phrase_in(_words(alias), context) for alias in term["aliases"] for context in contexts
        )
        score = 0.5 + min(0.12, 0.04 * (len(matches) - 1))
        score += 0.1 if preferred_match else 0.08 if synonym_match else 0
        score += 0.08 if name_matches else 0.02
        evidence = []
        if name_matches:
            prefix = "Observed column name" if column else "Observed column names"
            evidence.append(prefix + " matches vocabulary terms: " + ", ".join(sorted(name_matches)) + ".")
        if query_matches:
            evidence.append(
                "Steward query matches vocabulary terms: " + ", ".join(sorted(query_matches)) + "."
            )
        words = normalized_name.split()
        if column and label == "Identifier" and words and words[-1] in {"id", "identifier", "key", "code"}:
            score = max(score, 0.94)
            evidence.append("The observed column name has an identifier suffix.")
        if column and label == "Date" and words and words[-1] in {"date", "datetime", "timestamp", "time"}:
            score += 0.12
            evidence.append("The observed column name has a temporal suffix.")
        if column and (
            (label in {"Quantity", "Revenue"} and data_type in {"integer", "number"})
            or (label == "Date" and data_type in {"date", "datetime"})
        ):
            score += 0.1
            evidence.append("The observed type is compatible with this interpretation.")
        score = round(min(score, 0.98), 4)
        if not math.isfinite(score) or not evidence or score < 0.5:
            rejected["low_relevance"] += 1
            continue
        warnings = [_WARNINGS[label]] if label in _WARNINGS else []
        if column and data_type in {"unknown", "mixed"}:
            warnings.append(
                "The observed type is unresolved; this lexical suggestion requires additional evidence."
            )
        candidates.append(
            {
                "concept": term["concept"],
                "label": label,
                "definition": term["definition"],
                "score": score,
                "matched_terms": sorted(matches)[:12],
                "evidence": evidence,
                "warnings": warnings,
                "broader": [
                    {"concept": parent, "label": by_uri[parent]["label"]}
                    for parent in term["parents"]
                    if parent in by_uri
                ],
                "source": {
                    "scheme": vocabulary["id"],
                    "version": vocabulary["version"],
                    "license": vocabulary["license"],
                    "status": vocabulary["status"],
                },
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["concept"]))
    rejected["outside_limit"] = max(0, len(candidates) - limit)
    if candidates:
        ambiguous = len(candidates) > 1 and candidates[0]["score"] - candidates[1]["score"] <= 0.08
        result["status"] = "ambiguous" if ambiguous else "suggested"
        result["message"] = (
            "Several local concepts have similar lexical support. Compare their definitions; no alternative is selected automatically."
            if ambiguous
            else "Review these local alternatives and their evidence. Relevance is not a probability, and no alternative is selected automatically."
        )
    elif rejected["context_conflict"]:
        result["message"] = (
            "The observed name or steward query conflicts with the installed retail meanings. "
            "No reliable local alternative was suggested."
        )
    result["candidates"] = candidates[:limit]
    return result
