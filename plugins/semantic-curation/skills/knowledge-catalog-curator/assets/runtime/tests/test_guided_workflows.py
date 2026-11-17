"""Task-stage disclosure contracts, complemented by real browser flow checks.

These checks prove where task controls belong and what the initial document
exposes. Runtime transitions, mode gates, focus and error recovery are exercised
in browser QA; the markup checks do not stand in for that evidence.
"""

from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src/knowledge_catalog"


class GuidedMarkup(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.elements = []
        self.stack = []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        element = {"tag": tag, "attrs": dict(attrs), "parents": tuple(self.stack), "text": ""}
        self.elements.append(element)
        if tag not in {"input", "meta", "link", "br", "hr", "img"}:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, value):
        for element in self.stack:
            element["text"] += value

    def by_id(self, element_id):
        matches = [element for element in self.elements if element["attrs"].get("id") == element_id]
        assert len(matches) == 1, f"Expected one stable task control: {element_id}"
        return matches[0]


SURFACES = [
    (
        "review.html",
        "metadata",
        ("choose", "describe", "quality", "plan", "decide"),
        "flow-heading",
        "metadata-step-status",
    ),
    (
        "lineage.html",
        "lineage",
        ("choose", "explore", "check", "decide", "share"),
        "lineage-stage-title",
        "lineage-guidance",
    ),
]


@pytest.mark.parametrize("filename,prefix,steps,heading_id,status_id", SURFACES)
def test_guidance_is_named_and_linked_to_one_initial_task(filename, prefix, steps, heading_id, status_id):
    markup = GuidedMarkup(ROOT / filename)
    buttons = [element for element in markup.elements if f"data-{prefix}-step" in element["attrs"]]
    assert {button["attrs"][f"data-{prefix}-step"] for button in buttons} == set(steps)
    current = []
    for button in buttons:
        key = button["attrs"][f"data-{prefix}-step"]
        assert button["tag"] == "button", "Stage navigation must work with a keyboard"
        assert button["attrs"].get("type") == "button", "A step must not submit an editor"
        assert button["attrs"].get("id") == f"{prefix}-step-{key}"
        assert button["attrs"].get("aria-controls") == f"{prefix}-page-{key}"
        assert button["attrs"].get("aria-label") or button["text"].strip()
        if button["attrs"].get("aria-current") == "step":
            current.append(key)
    assert current == ["choose"]

    pages = [element for element in markup.elements if f"data-{prefix}-page" in element["attrs"]]
    required_pages = {element["attrs"][f"data-{prefix}-page"]: element for element in pages}
    assert set(steps) <= set(required_pages)
    visible = []
    for key, page in required_pages.items():
        assert page["attrs"].get("id") == f"{prefix}-page-{key}"
        if not any("hidden" in element["attrs"] for element in (*page["parents"], page)):
            visible.append(key)
    assert visible == ["choose"], "The initial screen must not reveal later task panels"
    assert markup.by_id(heading_id)["attrs"].get("tabindex") == "-1"
    assert markup.by_id(status_id)["attrs"].get("aria-live") == "polite"
    for control in (f"{prefix}-back", f"{prefix}-next"):
        assert markup.by_id(control)["tag"] == "button"


@pytest.mark.parametrize(
    "filename,prefix,placements",
    [
        (
            "review.html",
            "metadata",
            {
                "path": "choose",
                "analyze": "choose",
                "edit-title": "describe",
                "edit-description": "describe",
                "advanced": "describe",
                "privacy": "quality",
                "data-quality": "quality",
                "plan": "plan",
                "reviewer": "decide",
                "approve": "decide",
                "publish": "decide",
            },
        ),
        (
            "lineage.html",
            "lineage",
            {
                "graph-select": "choose",
                "demo": "choose",
                "graph": "explore",
                "node-detail": "explore",
                "description-form": "check",
                "edge-form": "check",
                "approve": "decide",
                "reviewer": "decide",
                "export-json": "share",
                "export-ol": "share",
                "attach": "share",
            },
        ),
    ],
)
def test_task_controls_are_disclosed_in_their_decision_stage(filename, prefix, placements):
    markup = GuidedMarkup(ROOT / filename)
    for element_id, expected_stage in placements.items():
        element = markup.by_id(element_id)
        parents = [parent["attrs"].get(f"data-{prefix}-page") for parent in element["parents"]]
        assert expected_stage in parents, (
            f"{element_id} must be available in {expected_stage}, rather than on every screen"
        )
