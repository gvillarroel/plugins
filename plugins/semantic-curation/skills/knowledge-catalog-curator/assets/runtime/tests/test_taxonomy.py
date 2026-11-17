"""Filtering, abstention and evidence boundaries for local SKOS alternatives."""

import copy
import hashlib
import json

import pytest

from knowledge_catalog import taxonomy


def metadata(name="customer_id", data_type="integer", **extra):
    return {"domain": "retail", "columns": [{"name": name, "data_type": data_type}], **extra}


def labels(result):
    return [candidate["label"] for candidate in result["candidates"]]


def test_product_identifier_does_not_match_a_fragment_of_product_return():
    result = taxonomy.suggest_concepts(metadata("product_id", "string"))
    assert "Return" not in labels(result)
    assert {"Identifier", "Product"} <= set(labels(result))
    assert result["filter_summary"]["partial_alias_match"] >= 1


def test_complete_multiword_alias_still_supports_its_concept():
    result = taxonomy.suggest_concepts(metadata("product_return", "integer"))
    assert "Return" in labels(result)


def vocabulary(*terms):
    prefix = f"""
@prefix retail: <{taxonomy.CONCEPT_BASE}> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
retail:Scheme a skos:ConceptScheme ; skos:prefLabel "Retail demonstration domain"@en .
"""
    return prefix + "\n".join(terms)


def term(name, *, scheme="retail:Scheme", label=None, definition="A documented local concept.", extra=""):
    preferred = label if label is not None else f'"{name}"@en'
    return (
        f"retail:{name} a skos:Concept ; skos:inScheme {scheme} ; "
        f"skos:prefLabel {preferred} ; skos:definition {json.dumps(definition)}@en {extra} ."
    )


def use_vocabulary(monkeypatch, text):
    monkeypatch.setattr(taxonomy, "_load_vocabulary", lambda: taxonomy._registry_from_turtle(text))


def test_identifier_suffix_outranks_entity_and_preserves_metadata():
    source = metadata()
    before = copy.deepcopy(source)
    result = taxonomy.suggest_concepts(source, column_name="customer_id")
    assert labels(result)[:2] == ["Identifier", "Customer"]
    candidate = result["candidates"][0]
    assert candidate["score"] > result["candidates"][1]["score"]
    assert candidate["matched_terms"] == ["id"]
    assert "suffix" in " ".join(candidate["evidence"])
    assert "primary key" in " ".join(candidate["warnings"])
    assert result["status"] == "suggested"
    assert result["method"]["score_is_probability"] is False
    assert source == before


@pytest.mark.parametrize(
    "name,data_type,expected",
    [("order_date", "date", "Date"), ("quantity", "integer", "Quantity"), ("revenue", "number", "Revenue")],
)
def test_observed_type_and_name_support_specific_interpretations(name, data_type, expected):
    result = taxonomy.suggest_concepts(metadata(name, data_type), column_name=name)
    assert labels(result)[0] == expected
    assert result["candidates"][0]["warnings"]
    assert "observed type" in " ".join(result["candidates"][0]["evidence"]).lower()


@pytest.mark.parametrize("name", ["price", "cost", "amount", "total", "sales_amount"])
def test_generic_monetary_names_do_not_claim_recognized_revenue(name):
    result = taxonomy.suggest_concepts(metadata(name, "number"), column_name=name)
    assert "Revenue" not in labels(result)
    assert result["filter_summary"]["unsupported_monetary_meaning"] == 1
    assert result["status"] == "no_reliable_match"
    explicit = taxonomy.suggest_concepts(
        metadata(name, "number"), column_name=name, query="recognized revenue"
    )
    assert labels(explicit)[0] == "Revenue"


@pytest.mark.parametrize("name", ["financial_return", "investment_return", "return_on_investment"])
def test_explicit_financial_returns_are_not_suggested_as_product_returns(name):
    result = taxonomy.suggest_concepts(metadata(name, "number"), column_name=name)
    assert "Return" not in labels(result)
    assert result["status"] == "no_reliable_match"
    assert result["filter_summary"]["context_conflict"] == 1
    assert "conflicts" in result["message"]


@pytest.mark.parametrize("query", ["financial return", "investment portfolio", "return on investment"])
def test_steward_financial_context_also_excludes_product_return(query):
    result = taxonomy.suggest_concepts(metadata("return", "number"), column_name="return", query=query)
    assert "Return" not in labels(result)
    assert result["filter_summary"]["context_conflict"] >= 1


@pytest.mark.parametrize(
    "name,query",
    [
        ("investment_stock", ""),
        ("stock", "financial portfolio"),
        ("equity_stock", ""),
        ("inventory", "investment"),
    ],
)
def test_stock_alias_does_not_create_retail_product_suggestions_in_financial_context(name, query):
    result = taxonomy.suggest_concepts(metadata(name, "number"), column_name=name, query=query)
    assert "Product" not in labels(result)
    assert result["filter_summary"]["context_conflict"] >= 1


@pytest.mark.parametrize("name", ["user_agent", "http_user_agent", "database_user", "system_users"])
def test_known_technical_user_aliases_do_not_suggest_customer(name):
    result = taxonomy.suggest_concepts(metadata(name, "string"), column_name=name)
    assert "Customer" not in labels(result)
    assert result["filter_summary"]["context_conflict"] == 1


def test_technical_query_guard_preserves_stronger_customer_evidence_and_identifier_fields():
    weak = taxonomy.suggest_concepts(metadata("user", "string"), column_name="user", query="user agent")
    assert "Customer" not in labels(weak)
    strong = taxonomy.suggest_concepts(
        metadata("customer", "string"), column_name="customer", query="user agent"
    )
    assert "Customer" in labels(strong)
    for name in ("user_id", "users_id"):
        result = taxonomy.suggest_concepts(metadata(name, "integer"), column_name=name)
        assert labels(result)[:2] == ["Identifier", "Customer"]


def test_generic_retail_returns_and_inventory_remain_available_for_review():
    returned = taxonomy.suggest_concepts(metadata("product_return", "string"), column_name="product_return")
    assert "Return" in labels(returned)
    assert "not a financial return" in " ".join(
        next(item for item in returned["candidates"] if item["label"] == "Return")["warnings"]
    )
    stock = taxonomy.suggest_concepts(metadata("stock", "integer"), column_name="stock")
    assert "Product" in labels(stock)
    assert returned["filter_summary"]["context_conflict"] == 0
    assert stock["filter_summary"]["context_conflict"] == 0


@pytest.mark.parametrize(
    "name", ["unit_price", "unit_cost", "price_per_unit", "cost_per_unit", "unit_rate", "unit_amount_usd"]
)
def test_per_unit_monetary_fields_do_not_suggest_unit_counts(name):
    result = taxonomy.suggest_concepts(metadata(name, "number"), column_name=name)
    assert "Quantity" not in labels(result)
    # A singular unit is now rejected even earlier when it is only a fragment
    # of the complete SKOS alias "Unit count".
    assert (
        result["filter_summary"]["context_conflict"] + result["filter_summary"]["partial_alias_match"]
    ) >= 1


def test_explicit_plural_units_still_use_the_monetary_context_guard():
    result = taxonomy.suggest_concepts(metadata("units_price", "number"), column_name="units_price")
    assert "Quantity" not in labels(result)
    assert result["filter_summary"]["context_conflict"] >= 1


@pytest.mark.parametrize("name", ["unit_count", "units_sold", "units_total", "quantity_unit_price"])
def test_actual_counts_and_explicit_quantity_evidence_remain_reviewable(name):
    result = taxonomy.suggest_concepts(metadata(name, "number"), column_name=name)
    assert "Quantity" in labels(result)
    assert result["filter_summary"]["context_conflict"] == 0


def test_steward_query_can_expose_per_unit_money_context_without_broad_amount_assumptions():
    source = metadata("units", "number")
    monetary = taxonomy.suggest_concepts(source, column_name="units", query="price per unit")
    assert "Quantity" not in labels(monetary)
    assert monetary["filter_summary"]["context_conflict"] >= 1
    generic = taxonomy.suggest_concepts(source, column_name="units", query="amount")
    assert "Quantity" in labels(generic)
    assert generic["filter_summary"]["context_conflict"] == 0


@pytest.mark.parametrize(
    "name,data_type,excluded",
    [
        ("quantity", "string", "Quantity"),
        ("revenue", "boolean", "Revenue"),
        ("order_date", "number", "Date"),
        ("customer_id", "boolean", "Identifier"),
    ],
)
def test_incompatible_observed_types_are_filtered(name, data_type, excluded):
    result = taxonomy.suggest_concepts(metadata(name, data_type), column_name=name)
    assert excluded not in labels(result)
    assert result["filter_summary"]["unsupported_type"] >= 1


def test_unknown_type_is_disclosed_without_inventing_observed_support():
    result = taxonomy.suggest_concepts(metadata("quantity", "unknown"), column_name="quantity")
    candidate = result["candidates"][0]
    assert "unresolved" in " ".join(candidate["warnings"])
    assert "observed type" not in " ".join(candidate["evidence"]).lower()


def test_irrelevant_inputs_and_documents_without_explicit_context_abstain():
    result = taxonomy.suggest_concepts(metadata("zxq", "string"), column_name="zxq")
    assert result["status"] == "no_reliable_match"
    assert result["candidates"] == []
    assert result["filter_summary"]["no_lexical_evidence"] == 11
    document = {"domain": "retail", "columns": [], "description": "Order customer product revenue"}
    assert taxonomy.suggest_concepts(document)["candidates"] == []
    assert labels(taxonomy.suggest_concepts(document, query="customer")) == ["Customer"]


def test_existing_assignments_generated_descriptions_and_rows_cannot_reinforce_themselves():
    source = metadata("zxq", "string")
    baseline = taxonomy.suggest_concepts(source, column_name="zxq")
    source.update(
        description="Order customer product", semantic_type="Customer", concepts=[{"label": "Order"}]
    )
    source["columns"][0].update(
        semantic_type="Revenue",
        description="Observed field; suggested concept: Revenue.",
        concepts=[{"label": "Payment"}],
        statistics={"values": ["revenue", "quantity", "customer"]},
    )
    assert taxonomy.suggest_concepts(source, column_name="zxq") == baseline


def test_close_scores_are_ambiguous_even_when_limit_is_one():
    source = metadata("customer_order", "string")
    result = taxonomy.suggest_concepts(source, column_name="customer_order", limit=1)
    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 1
    assert "no alternative is selected automatically" in result["message"]
    assert result["filter_summary"]["outside_limit"] == 1


def test_domain_filter_never_relaxes_the_installed_retail_contract():
    result = taxonomy.suggest_concepts(metadata(domain="biomedical"), column_name="customer_id")
    assert result["status"] == "no_reliable_match"
    assert result["candidates"] == []
    assert result["filter_summary"]["domain_mismatch"] == 11


def test_registry_rejects_unknown_obsolete_wrong_scheme_and_malformed_terms(monkeypatch):
    text = vocabulary(
        term("Customer"),
        term("Imaginary"),
        term("Order", scheme="retail:Other"),
        term("Product", extra="; owl:deprecated true"),
        term("Quantity", label='"Quantity"@fr'),
        term("Revenue", definition=""),
        term("Payment", label='"Wrong label"@en'),
    )
    use_vocabulary(monkeypatch, text)
    result = taxonomy.suggest_concepts(metadata("customer_order_product_quantity_revenue_payment", "integer"))
    assert labels(result) == ["Customer"]
    for reason in (
        "unknown_uri",
        "wrong_scheme",
        "obsolete",
        "missing_english_label",
        "missing_english_definition",
        "label_mismatch",
    ):
        assert result["filter_summary"][reason] == 1


def test_english_definition_is_required_and_duplicate_triples_do_not_duplicate_candidates(monkeypatch):
    text = vocabulary(
        term("Customer"),
        term("Customer"),
        term("Order").replace('"A documented local concept."@en', '"A documented local concept."@fr'),
    )
    use_vocabulary(monkeypatch, text)
    result = taxonomy.suggest_concepts(metadata("customer_order", "string"))
    assert labels(result) == ["Customer"]
    assert result["filter_summary"]["missing_english_definition"] == 1
    assert result["vocabulary"]["version"] == hashlib.sha256(text.encode()).hexdigest()
    assert result["candidates"][0]["source"]["version"] == result["vocabulary"]["version"]


def test_local_broader_terms_are_explained_and_hierarchy_cycles_are_filtered(monkeypatch):
    text = vocabulary(term("Customer"), term("Order", extra="; skos:broader retail:Customer"))
    use_vocabulary(monkeypatch, text)
    result = taxonomy.suggest_concepts(metadata("order", "integer"))
    assert result["candidates"][0]["broader"] == [
        {"concept": taxonomy.CONCEPT_BASE + "Customer", "label": "Customer"}
    ]
    text = vocabulary(
        term("Customer", extra="; skos:broader retail:Order"),
        term("Order", extra="; skos:broader retail:Customer"),
    )
    use_vocabulary(monkeypatch, text)
    result = taxonomy.suggest_concepts(metadata("customer_order", "integer"))
    assert result["candidates"] == []
    assert result["filter_summary"]["cyclic_hierarchy"] == 2


def test_ranking_is_deterministic_and_scores_are_finite_bounded_and_explained():
    source = metadata("customer_order_product_quantity_date_id", "integer")
    first = taxonomy.suggest_concepts(source, limit=5)
    assert first == taxonomy.suggest_concepts(source, limit=5)
    assert 1 <= len(first["candidates"]) <= 5
    assert len({item["concept"] for item in first["candidates"]}) == len(first["candidates"])
    for item in first["candidates"]:
        assert 0 <= item["score"] <= 1
        assert item["matched_terms"] and item["evidence"]
        assert item["definition"] and item["source"]["status"] == "demonstration"


def test_method_version_binds_aliases_without_misrepresenting_vocabulary_version(monkeypatch):
    source = metadata()
    original = taxonomy.suggest_concepts(source, column_name="customer_id")
    monkeypatch.setitem(taxonomy.CONCEPTS, "Customer", taxonomy.CONCEPTS["Customer"] + " shopper")
    revised = taxonomy.suggest_concepts(source, column_name="customer_id")
    assert revised["vocabulary"]["version"] == original["vocabulary"]["version"]
    assert revised["method"]["version"] != original["method"]["version"]
    assert revised["method"]["policy_version"] == taxonomy.RANKING_POLICY_VERSION
    assert len(revised["method"]["version"]) == 64


def test_method_version_also_binds_the_explicit_ranking_policy(monkeypatch):
    source = metadata()
    original = taxonomy.suggest_concepts(source, column_name="customer_id")
    monkeypatch.setattr(taxonomy, "RANKING_POLICY_VERSION", "test-policy-next")
    revised = taxonomy.suggest_concepts(source, column_name="customer_id")
    assert revised["vocabulary"]["version"] == original["vocabulary"]["version"]
    assert revised["method"]["version"] != original["method"]["version"]
    assert revised["method"]["policy_version"] == "test-policy-next"


def test_local_rdf_imports_and_metadata_urls_are_never_resolved(monkeypatch):
    def unexpected_network(*args, **kwargs):
        raise AssertionError("Taxonomy suggestions must remain local")

    monkeypatch.setattr("urllib.request.urlopen", unexpected_network)
    monkeypatch.setattr("requests.sessions.Session.request", unexpected_network)
    text = (
        vocabulary(term("Customer"))
        + "\n<urn:local:ontology> owl:imports <https://example.invalid/private.owl> ."
    )
    use_vocabulary(monkeypatch, text)
    source = metadata("customer", "string", source={"url": "https://example.invalid/source.csv"})
    assert labels(taxonomy.suggest_concepts(source, column_name="customer")) == ["Customer"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": None},
        {"query": "x" * 301},
        {"query": "\x00"},
        {"limit": True},
        {"limit": 0},
        {"limit": 6},
        {"column_name": []},
        {"column_name": ""},
        {"column_name": "absent"},
    ],
)
def test_invalid_requests_fail_clearly(kwargs):
    with pytest.raises(ValueError):
        taxonomy.suggest_concepts(metadata(), **kwargs)


def test_duplicate_column_identity_and_malformed_metadata_are_rejected():
    source = metadata()
    source["columns"].append(copy.deepcopy(source["columns"][0]))
    with pytest.raises(ValueError, match="uniquely"):
        taxonomy.suggest_concepts(source, column_name="customer_id")
    for invalid in (None, [], "metadata"):
        with pytest.raises(ValueError):
            taxonomy.suggest_concepts(invalid)
