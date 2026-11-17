"""Markup and navigation contracts for the existing human review panel.

Browser/axe evidence complements these checks; this is not a WCAG certification.
"""

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "knowledge_catalog" / "review.html"


class PanelMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.stack = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = {"tag": tag, "attrs": dict(attrs), "parents": tuple(self.stack)}
        self.elements.append(element)
        if tag not in {"input", "meta", "link", "br", "hr", "img"}:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                self.stack = self.stack[:index]
                break


@pytest.fixture
def panel():
    return PanelMarkup(SOURCE.read_text(encoding="utf-8"))


def test_review_form_fields_have_persistent_accessible_names(panel):
    labels = {element["attrs"].get("for") for element in panel.elements if element["tag"] == "label"}
    unnamed = []
    for element in panel.elements:
        if element["tag"] not in {"input", "select", "textarea"}:
            continue
        attrs = element["attrs"]
        implicit = any(parent["tag"] == "label" for parent in element["parents"])
        if not (
            attrs.get("id") in labels or attrs.get("aria-label") or attrs.get("aria-labelledby") or implicit
        ):
            unnamed.append(attrs.get("id"))
    assert unnamed == []


def test_review_ids_and_aria_references_are_valid(panel):
    ids = [element["attrs"]["id"] for element in panel.elements if "id" in element["attrs"]]
    assert len(ids) == len(set(ids))
    for element in panel.elements:
        for attribute in ("aria-labelledby", "aria-describedby", "for"):
            for reference in element["attrs"].get(attribute, "").split():
                assert reference in ids, (attribute, reference)


def test_review_has_skip_target_and_durable_announcements(panel):
    by_id = {element["attrs"].get("id"): element for element in panel.elements}
    assert by_id["main"]["attrs"]["tabindex"] == "-1"
    assert any(
        element["tag"] == "a" and element["attrs"].get("href") == "#main" for element in panel.elements
    )
    assert by_id["operation-status"]["attrs"]["aria-live"] == "polite"
    assert by_id["error-summary"]["attrs"]["role"] == "alert"
    assert "hidden" in by_id["history-results"]["attrs"]
    assert by_id["lineage-link"]["attrs"]["href"] == "/lineage"


def test_review_tables_have_captions(panel):
    tables = [element for element in panel.elements if element["tag"] == "table"]
    for table in tables:
        assert any(element["tag"] == "caption" and table in element["parents"] for element in panel.elements)


def test_scrollable_evidence_is_named_and_keyboard_reachable(panel):
    blocks = [element for element in panel.elements if element["tag"] == "pre"]
    assert blocks
    for element in blocks:
        assert element["attrs"].get("tabindex") == "0"
        assert element["attrs"].get("aria-label")


@pytest.mark.skipif(
    not shutil.which("node"), reason="Node is required to compile the shipped browser JavaScript"
)
def test_review_javascript_compiles():
    html = SOURCE.read_text(encoding="utf-8")
    script = re.search(r"<script>(.*?)</script>", html, re.DOTALL).group(1)
    result = subprocess.run(
        [shutil.which("node"), "--check"], input=script, text=True, encoding="utf-8", capture_output=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
    not shutil.which("node"), reason="Node is required for the capability navigation regression"
)
@pytest.mark.parametrize("fragment", ["#review-help", "#main", ""])
def test_navigation_anchor_never_replaces_session_capability(fragment):
    html = SOURCE.read_text(encoding="utf-8")
    script = re.search(r"<script>(.*?)</script>", html, re.DOTALL).group(1)
    prefix = script[: script.index("let state")]
    harness = """
const vm = require('node:vm');
const input = JSON.parse(process.argv[1]);
const values = new Map([['kc-token', 'synthetic_qa_capability_with_43_characters_only']]);
let changes = 0;
vm.runInNewContext(input.code, {
  location:{hash:input.fragment,pathname:'/'},
  sessionStorage:{getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)},
  history:{replaceState:()=>changes++}
});
process.stdout.write(JSON.stringify({legacy:values.get('kc-token'),current:values.get('kc_token'),changes}));
"""
    result = subprocess.run(
        [shutil.which("node"), "-e", harness, json.dumps({"code": prefix, "fragment": fragment})],
        capture_output=True,
        text=True,
        check=True,
    )
    values = json.loads(result.stdout)
    assert values["legacy"] == values["current"] == "synthetic_qa_capability_with_43_characters_only"
    assert values["changes"] == 0
