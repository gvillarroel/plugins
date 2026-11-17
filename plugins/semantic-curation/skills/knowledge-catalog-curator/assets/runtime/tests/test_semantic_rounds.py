"""Independent regressions for the ten sequential semantic review rounds."""

import json

import pytest
from rdflib.namespace import DCTERMS, RDF, SKOS

from knowledge_catalog.analysis import AnalysisError, analyze_file
from knowledge_catalog.ontology import KC, RETAIL, metadata_to_graph, validate_metadata


def source(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def complete(tmp_path):
    return analyze_file(
        source(tmp_path, "orders.csv", "order_id,quantity\n1,2\n2,3\n"),
        provenance={"owner": "Retail stewardship", "license": "MIT"},
    )


@pytest.mark.parametrize(
    "header", ["order_id, order_id", "order_id,order_id\u200b", "quantity,quan\x00tity", "x" * 10001]
)
def test_r04_ambiguous_or_unsafe_headers_are_rejected(tmp_path, header):
    with pytest.raises(AnalysisError, match="column names|field names"):
        analyze_file(source(tmp_path, "orders.csv", header + "\n"))


def test_r04_quoted_bom_unicode_csv_is_preserved(tmp_path):
    draft = analyze_file(
        source(tmp_path, "orders.csv", '\ufefforder_id,"descripción"\r\n1,"a,b\nsegunda línea"\r\n')
    )
    assert draft["profile"]["row_count"] == 1
    assert draft["columns"][1]["name"] == "descripción"


def test_r05_json_cardinality_preserves_type_and_object_key_identity(tmp_path):
    rows = [
        {"quantity": value} for value in [True, "True", 1, "1", {"a": 1, "b": 2}, {"b": 2, "a": 1}, None, " "]
    ]
    draft = analyze_file(source(tmp_path, "orders.json", json.dumps(rows)))
    statistics = draft["columns"][0]["statistics"]
    assert statistics["distinct_count"] == 5
    assert statistics["non_null_count"] == 6
    assert statistics["null_count"] == 2
    assert "typed" in statistics["distinct_semantics"]


def test_r06_integer_extrema_remain_exact_above_binary64_precision(tmp_path):
    lower, upper = 10**40 + 1, 10**40 + 3
    draft = analyze_file(source(tmp_path, "orders.csv", f"quantity\n{lower}\n{upper}\n"))
    stats = draft["columns"][0]["statistics"]
    assert stats["minimum"] == lower and isinstance(stats["minimum"], int)
    assert stats["maximum"] == upper
    assert stats["mean_approximate"] is True
    json.dumps(draft, allow_nan=False)


def test_r06_huge_integer_mean_overflow_does_not_erase_exact_extrema(tmp_path):
    huge = 10**400
    draft = analyze_file(source(tmp_path, "orders.json", json.dumps([{"quantity": huge}])))
    assert draft["columns"][0]["statistics"]["maximum"] == huge
    assert "mean" not in draft["columns"][0]["statistics"]


def test_r07_unicode_pii_and_document_ip_boundaries(tmp_path):
    text = "Orders: contact ａｌｉｃｅ＠ｅｘａｍｐｌｅ．ｔｅｓｔ or élise@example.test, phone +34915123456. "
    text += "Network source 192.0.2.12 and IPv6 2001:db8::1; these are documentation addresses."
    draft = analyze_file(source(tmp_path, "orders.txt", text))
    assert {"email", "phone", "ip_address"} <= set(draft["pii_flags"])
    assert "élise" not in json.dumps(draft, ensure_ascii=False)
    assert "192.0.2.12" not in json.dumps(draft)
    invalid = analyze_file(
        source(
            tmp_path, "invalid.txt", "Orders network indicator is 999.999.999.999 in a long prose sentence."
        )
    )
    assert "ip_address" not in invalid["pii_flags"]


def test_r07_accented_headers_match_spanish_privacy_vocabulary(tmp_path):
    draft = analyze_file(source(tmp_path, "clientes.csv", "teléfono,dirección,código\n,,001\n"))
    assert "phone" in draft["columns"][0]["pii_flags"]
    assert "postal_address" in draft["columns"][1]["pii_flags"]
    assert draft["columns"][2]["semantic_type"] == "Identifier"


def test_r08_amounts_units_and_ambiguous_roles_remain_explicitly_unverified(tmp_path):
    draft = analyze_file(
        source(tmp_path, "orders.csv", "price,quantity,order_date,customer_order\n10,2,2025-01-01,1\n")
    )
    columns = {column["name"]: column for column in draft["columns"]}
    assert "does not establish recognized revenue" in " ".join(columns["price"]["semantic_caveats"])
    assert "unit of measure" in " ".join(columns["quantity"]["semantic_caveats"])
    assert "timezone" in " ".join(columns["order_date"]["semantic_caveats"])
    assert not any(key in columns["price"] for key in ("currency", "unit", "recognized_revenue"))
    assert any(item["code"] == "BUSINESS_MEANING_REQUIRED" for item in draft["quality_findings"])


def test_r09_temporal_offsets_and_invalid_timestamp_suffixes_are_not_truncated_to_dates(tmp_path):
    text = "Order_Date,Return_Date,Days_to_Return\n2025-01-02T00:30:00+02:00,2025-01-01T23:00:00Z,0\n2025-01-03Tnonsense,2025-01-01,0\n2025-01-01,,\n"
    draft = analyze_file(source(tmp_path, "returns.csv", text))
    assert not any(item["code"] == "RETURN_BEFORE_ORDER" for item in draft["quality_findings"])
    precision = next(
        item for item in draft["quality_findings"] if item["code"] == "TEMPORAL_PRECISION_REVIEW"
    )
    assert precision["evidence"]["timestamp_pairs"] == 1
    assert precision["evidence"]["invalid_rows"] == 1


def test_r09_naive_aware_pair_has_no_fabricated_timezone(tmp_path):
    draft = analyze_file(
        source(
            tmp_path,
            "returns.csv",
            "Order_Date,Return_Date,Days_to_Return\n2025-01-03T10:00:00,2025-01-02T10:00:00Z,0\n",
        )
    )
    assert not any(item["severity"] == "error" for item in draft["quality_findings"])
    precision = next(
        item for item in draft["quality_findings"] if item["code"] == "TEMPORAL_PRECISION_REVIEW"
    )
    assert precision["evidence"]["incompatible_pairs"] == 1
    negative = analyze_file(
        source(
            tmp_path,
            "negative.csv",
            "Order_Date,Return_Date,Days_to_Return\n2025-01-03T10:00:00,2025-01-02T10:00:00Z,-2\n",
        )
    )
    assert {item["code"] for item in negative["quality_findings"] if item["severity"] == "error"} == {
        "NEGATIVE_RETURN_INTERVAL"
    }


def test_r10_columns_export_explicit_skos_subject_links_without_asserting_joins(tmp_path):
    draft = complete(tmp_path)
    graph = metadata_to_graph(draft)
    for column in graph.subjects(RDF.type, KC.Column):
        subject = graph.value(column, DCTERMS.subject)
        assert subject is not None
        assert (subject, RDF.type, SKOS.Concept) in graph
        assert (subject, SKOS.inScheme, RETAIL.Scheme) in graph
    assert not any("foreignKey" in str(predicate) for _, predicate, _ in graph)
    assert validate_metadata(draft)["conforms"] is True


def test_r10_misleading_column_concept_labels_are_rejected(tmp_path):
    draft = complete(tmp_path)
    draft["columns"][0]["concepts"] = [{"concept": str(RETAIL.Customer), "label": "Product"}]
    result = validate_metadata(draft)
    assert result["conforms"] is False
    assert any(finding["code"] == "CONCEPT_LABEL_MISMATCH" for finding in result["findings"])


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.test/orders",
        "https://example.test/orders?access_token=private",
        "https://example.test/orders?X-Goog-Signature=private",
        "https://example.test/orders#private",
        "https://example.test/unsafe path",
    ],
)
def test_r11_sensitive_source_links_block_approval_and_do_not_enter_rdf(tmp_path, url):
    draft = complete(tmp_path)
    draft["source"]["source_url"] = url
    result = validate_metadata(draft)
    assert result["conforms"] is False
    assert any(item["code"] == "SENSITIVE_OR_INVALID_SOURCE_URL" for item in result["findings"])
    turtle = metadata_to_graph(draft).serialize(format="turtle")
    assert url not in turtle and "private" not in turtle and "secret" not in turtle


def test_r11_public_versioned_source_url_remains_exportable(tmp_path):
    draft = complete(tmp_path)
    draft["source"]["source_url"] = "https://example.test/orders?datasetVersionNumber=1"
    assert validate_metadata(draft)["conforms"] is True
    assert draft["source"]["source_url"] in metadata_to_graph(draft).serialize(format="turtle")


def test_r12_unmapped_columns_and_conditional_nulls_affect_coverage_without_inventing_errors(tmp_path):
    draft = analyze_file(
        source(tmp_path, "orders.csv", "opaque,quantity\nalpha,2\nbeta,\n"),
        provenance={"owner": "Retail stewardship", "license": "MIT"},
    )
    result = validate_metadata(draft)
    assert result["conforms"] is True
    assert result["score"] == 94
    assert result["coverage"] == {"mapped_columns": 1, "total_columns": 2, "mapping_fraction": 0.5}
    assert {item["code"] for item in result["findings"]} >= {"UNMAPPED_COLUMN", "COLUMN_COMPLETENESS_GAP"}
    assert all(item["severity"] != "error" for item in result["findings"])


def test_r12_mixed_types_are_visible_in_the_ontology_quality_score(tmp_path):
    draft = analyze_file(
        source(tmp_path, "orders.csv", "quantity\n2\nunknown\n"),
        provenance={"owner": "Retail stewardship", "license": "MIT"},
    )
    result = validate_metadata(draft)
    assert result["score"] == 97
    assert any(item["code"] == "MIXED_COLUMN_TYPES" for item in result["findings"])


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("observed_count", -1, "INVALID_COLUMN_COUNTS"),
        ("null_count", 1, "INCONSISTENT_COLUMN_COUNTS"),
        ("distinct_count", 99, "INCONSISTENT_DISTINCT_COUNT"),
        ("null_fraction", float("nan"), "INVALID_NULL_FRACTION"),
        ("null_fraction", 0.5, "INCONSISTENT_NULL_FRACTION"),
        ("type_counts", {"integer": 99}, "INCONSISTENT_TYPE_COUNTS"),
        ("type_counts", {"integer": True}, "INVALID_TYPE_COUNTS"),
        ("minimum", float("inf"), "INVALID_NUMERIC_STATISTICS"),
        ("minimum", 999, "INCONSISTENT_NUMERIC_RANGE"),
    ],
)
def test_r13_inconsistent_edited_statistics_fail_closed(tmp_path, field, value, code):
    draft = complete(tmp_path)
    draft["columns"][1]["statistics"][field] = value
    result = validate_metadata(draft)
    assert result["conforms"] is False
    assert any(item["code"] == code for item in result["findings"])


def test_r13_schema_cannot_silently_drop_observed_fields_and_malformed_semantics_do_not_crash(tmp_path):
    draft = complete(tmp_path)
    draft["columns"].pop()
    result = validate_metadata(draft)
    assert any(item["code"] == "SCHEMA_PROFILE_MISMATCH" for item in result["findings"])
    draft = complete(tmp_path)
    draft["columns"][0]["semantic_type"] = ["Order"]
    assert validate_metadata(draft)["conforms"] is False


def test_r13_profile_row_and_column_sample_invariants(tmp_path):
    draft = complete(tmp_path)
    draft["profile"]["row_count"] = 1
    draft["columns"][0]["statistics"]["observed_count"] = 4
    result = validate_metadata(draft)
    assert result["conforms"] is False
    assert {item["code"] for item in result["findings"]} >= {"ROW_PROFILE_MISMATCH", "COLUMN_SAMPLE_MISMATCH"}
