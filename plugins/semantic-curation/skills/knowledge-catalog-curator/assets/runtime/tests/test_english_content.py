import importlib.util
import json
import sqlite3
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "audit_english", Path(__file__).resolve().parents[1] / "scripts/audit_english_content.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_checks_visible_copy_even_when_html_claims_english(tmp_path):
    page = tmp_path / "src/knowledge_catalog/lineage.html"
    page.parent.mkdir(parents=True)
    page.write_text('<html lang="en"><button>Guardar descripción</button></html>', encoding="utf-8")
    result = module.audit(tmp_path)
    assert not result["conforms"] and result["findings"][0]["file"].endswith("lineage.html")
    page.write_text('<html lang="en"><button>Save description</button></html>', encoding="utf-8")
    assert module.audit(tmp_path)["conforms"]


def test_history_display_text_is_checked_but_original_source_evidence_is_preserved(tmp_path):
    home = tmp_path / ".kc"
    home.mkdir()
    connection = sqlite3.connect(home / "catalog.sqlite3")
    try:
        connection.execute("CREATE TABLE revisions (body TEXT)")
        record = {
            "id": "demo",
            "revision": 1,
            "metadata": {"title": "Synthetic product catalog", "source": {"title": "Catálogo original"}},
        }
        connection.execute("INSERT INTO revisions VALUES (?)", (json.dumps(record),))
        connection.commit()
        assert module.audit(tmp_path)["conforms"]
        record["metadata"]["description"] = "Descripción sintética de productos."
        connection.execute("UPDATE revisions SET body=?", (json.dumps(record),))
        connection.commit()
        result = module.audit(tmp_path)
        assert not result["conforms"] and result["findings"][0]["pointer"] == "/description"
    finally:
        connection.close()
