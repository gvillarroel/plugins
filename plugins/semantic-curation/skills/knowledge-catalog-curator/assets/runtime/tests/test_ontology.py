"""SHACL tests distinguish completeness from claims requiring human evidence."""

import copy

import pytest
from rdflib import RDF
from rdflib.namespace import DCAT, DCTERMS, FOAF

from knowledge_catalog.analysis import CONCEPT_BASE, analyze_file
from knowledge_catalog.ontology import metadata_to_graph, validate_metadata


@pytest.fixture
def complete_metadata(tmp_path):
    path = tmp_path / "retail_orders.csv"
    path.write_text("order_id,product_id,quantity\n1,P1,2\n2,P2,3\n", encoding="utf-8")
    draft = analyze_file(path, provenance={"url": "https://example.test/retail", "synthetic": True})
    draft.update(
        owner="Retail data stewardship team",
        license="CC0-1.0",
        synthetic_evidence="Test fixture generated locally in test_ontology.py.",
    )
    return draft


def codes(result):
    return {finding["code"] for finding in result["findings"]}


def test_complete_metadata_passes_without_mutation(complete_metadata):
    original = copy.deepcopy(complete_metadata)
    result = validate_metadata(complete_metadata)
    assert result["conforms"] is True, result["report"]
    assert result["score"] == 100
    assert complete_metadata == original


@pytest.mark.parametrize("field", ["owner", "license", "title", "description", "domain"])
def test_missing_required_field_fails_shacl(complete_metadata, field):
    complete_metadata.pop(field, None)
    result = validate_metadata(complete_metadata)
    assert result["conforms"] is False
    assert "SHACL_CONSTRAINT" in codes(result)
    assert result["score"] < 100


def test_no_fabricated_synthetic_evidence(complete_metadata):
    complete_metadata.pop("synthetic_evidence")
    result = validate_metadata(complete_metadata)
    assert result["conforms"] is False
    assert "SYNTHETIC_EVIDENCE_REQUIRED" in codes(result)


def test_pii_needs_explicit_review(complete_metadata):
    complete_metadata["columns"][0]["pii_flags"] = ["quasi_identifier"]
    result = validate_metadata(complete_metadata)
    assert result["conforms"] is False
    assert "PRIVACY_REVIEW_REQUIRED" in codes(result)
    complete_metadata["privacy_reviewed"] = "true"
    assert validate_metadata(complete_metadata)["conforms"] is False
    complete_metadata["privacy_reviewed"] = True
    assert validate_metadata(complete_metadata)["conforms"] is True


def test_unknown_concepts_and_domain_are_not_silently_accepted(complete_metadata):
    complete_metadata["concepts"] = [{"concept": CONCEPT_BASE + "Imaginary"}]
    complete_metadata["domain"] = "banking"
    result = validate_metadata(complete_metadata)
    assert result["conforms"] is False
    assert "SHACL_CONSTRAINT" in codes(result)


def test_forged_source_fingerprint_is_invalid(complete_metadata):
    complete_metadata["source"]["sha256"] = "not-a-fingerprint"
    assert validate_metadata(complete_metadata)["conforms"] is False


def test_dcat_mapping_has_distribution_license_and_owner(complete_metadata):
    graph = metadata_to_graph(complete_metadata)
    dataset = next(graph.subjects(RDF.type, DCAT.Dataset))
    distribution = graph.value(dataset, DCAT.distribution)
    assert (distribution, RDF.type, DCAT.Distribution) in graph
    assert graph.value(distribution, DCTERMS.license) == graph.value(dataset, DCTERMS.license)
    owner = graph.value(dataset, DCTERMS.publisher)
    assert (owner, RDF.type, FOAF.Agent) in graph


@pytest.mark.parametrize(
    "field,value",
    [
        ("columns", None),
        ("columns", ["bad"]),
        ("source", []),
        ("owner", {"execute": "bad"}),
        ("concepts", "retail"),
    ],
)
def test_malformed_human_edits_fail_closed_without_crashing(complete_metadata, field, value):
    complete_metadata[field] = value
    result = validate_metadata(complete_metadata)
    assert result["conforms"] is False
    assert result["score"] < 100


def test_nonobject_metadata_is_a_validation_error():
    assert validate_metadata([])["conforms"] is False


def test_sampling_reduces_score_but_human_can_review(complete_metadata):
    complete_metadata["profile"]["sampled"] = True
    result = validate_metadata(complete_metadata)
    assert result["conforms"] is True
    assert result["score"] == 97
    assert "SAMPLE_LIMITATION" in codes(result)


def test_source_temporal_errors_block_until_acknowledged_with_limitations(complete_metadata):
    finding = {
        "code": "RETURN_BEFORE_ORDER",
        "severity": "error",
        "message": "Return dates precede order dates.",
        "evidence": {"affected_rows": 2, "evaluated_rows": 5, "sample_scope": "prefix_sample"},
    }
    complete_metadata["quality_findings"].append(finding)
    assert "SOURCE_QUALITY_REVIEW_REQUIRED" in codes(validate_metadata(complete_metadata))
    complete_metadata["data_quality_reviewed"] = True
    assert "SOURCE_LIMITATION_REQUIRED" in codes(validate_metadata(complete_metadata))
    complete_metadata["limitations"] = (
        "Some returns predate their orders; unsuitable for elapsed-time modeling until corrected."
    )
    result = validate_metadata(complete_metadata)
    assert result["conforms"] is True
    assert result["score"] == 97
    assert "SOURCE_LIMITATION_ACKNOWLEDGED" in codes(result)
    assert finding in complete_metadata["quality_findings"]
    assert (
        next(item for item in result["findings"] if item["code"] == "SOURCE_LIMITATION_ACKNOWLEDGED")[
            "evidence"
        ]["affected_rows"]
        == 2
    )
    complete_metadata["limitations"] = [
        "Some returns predate their orders.",
        "Elapsed-time analysis requires corrected source data.",
    ]
    assert validate_metadata(complete_metadata)["conforms"] is True


def test_synthetic_claim_accepts_evidence_list_but_not_empty_list(complete_metadata):
    complete_metadata["synthetic_evidence"] = ["Publisher statement.", "Generation record."]
    assert validate_metadata(complete_metadata)["conforms"] is True
    complete_metadata["synthetic_evidence"] = []
    assert "SYNTHETIC_EVIDENCE_REQUIRED" in codes(validate_metadata(complete_metadata))


def test_upstream_unknown_license_cannot_be_overridden_in_metadata(complete_metadata):
    complete_metadata["source"]["publication_allowed"] = False
    complete_metadata["source"]["license"] = "Unknown"
    complete_metadata["license"] = "MIT"
    result = validate_metadata(complete_metadata)
    assert result["conforms"] is False
    assert "UNKNOWN_LICENSE" in codes(result)
