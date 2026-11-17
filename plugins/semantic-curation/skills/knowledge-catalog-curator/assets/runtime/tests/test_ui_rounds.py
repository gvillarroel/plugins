"""Reviewer UI regressions for rounds R36–R43."""

import base64
import hashlib
import json
import re
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from knowledge_catalog.ui import make_server
from knowledge_catalog.workflow import Workflow


@pytest.fixture
def panel(tmp_path):
    flow = Workflow(tmp_path / ".kc")
    server, url = make_server(flow, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base, token = url.split("#")
    yield base, token, flow
    server.shutdown()
    server.server_close()
    thread.join()


def api_request(panel, body):
    base, token, _ = panel
    return Request(
        base + "api/action",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Origin": base.rstrip("/"),
            "Content-Type": "application/json",
        },
    )


def test_r36_html_has_exact_script_hash_and_rejects_foreign_host(panel):
    base, _, _ = panel
    with urlopen(base) as response:
        html = response.read().decode()
        csp = response.headers["Content-Security-Policy"]
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert scripts
    for script in scripts:
        expected = "sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        assert expected in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp
    with pytest.raises(HTTPError) as exc:
        urlopen(Request(base, headers={"Host": "attacker.invalid"}))
    assert exc.value.code == 403


@pytest.mark.parametrize("body", [[], {"action": "plan", "live": "false"}])
def test_r36_malformed_body_is_an_actionable_error(panel, body):
    with pytest.raises(HTTPError) as exc:
        urlopen(api_request(panel, body))
    assert exc.value.code == 400
    error = json.load(exc.value)["error"]
    assert "JSON object" in error or "boolean" in error


def test_r36_non_ascii_bearer_is_rejected_without_crashing(panel):
    base, _, _ = panel
    with pytest.raises(HTTPError) as exc:
        urlopen(Request(base + "api/state", headers={"Authorization": "Bearer ö"}))
    assert exc.value.code == 401


@pytest.mark.parametrize("action", ["revise", "reject", "plan"])
def test_r37_stale_browser_action_cannot_overwrite_current_revision(panel, tmp_path, action):
    _, _, flow = panel
    source = tmp_path / "orders.csv"
    source.write_text("quantity,price\n1,2\n", encoding="utf-8")
    proposal = flow.propose(str(source), provenance={"owner": "UI test team", "license": "MIT"})
    revised = flow.revise(proposal["id"], {"title": "Latest reviewed title"})
    body = {
        "action": action,
        "id": proposal["id"],
        "expected_digest": proposal["digest"],
        "updates": {"title": "Stale title"},
        "reason": "Stale rejection",
        "live": False,
    }
    with pytest.raises(HTTPError) as exc:
        urlopen(api_request(panel, body))
    assert exc.value.code == 409
    assert flow.get(proposal["id"])["digest"] == revised["digest"]


def test_r38_ui_history_diff_shows_prior_metadata_and_keeps_approval_empty(panel, tmp_path):
    _, _, flow = panel
    source = tmp_path / "products.csv"
    source.write_text("product_id,quantity\n1,2\n", encoding="utf-8")
    original = flow.propose(str(source), provenance={"owner": "Review team", "license": "MIT"})
    updated = flow.revise(
        original["id"], {"description": "Product quantities for the synthetic review exercise"}
    )
    history = json.load(urlopen(api_request(panel, {"action": "history", "id": original["id"]})))
    assert [row["revision"] for row in history["revisions"]] == [2, 1]
    difference = json.load(
        urlopen(api_request(panel, {"action": "diff", "id": original["id"], "from_revision": 1}))
    )
    assert any(
        row["path"] == "/metadata/description" and row["after"] == updated["metadata"]["description"]
        for row in difference["changes"]
    )
    assert flow.get(original["id"])["approval"] is None


def test_r43_http_recovery_clears_uncertain_attempt_without_cloud_retry(panel, tmp_path):
    _, _, flow = panel
    source = tmp_path / "orders.csv"
    source.write_text("quantity,price\n1,2\n", encoding="utf-8")
    proposal = flow.propose(str(source), provenance={"owner": "Recovery test team", "license": "MIT"})
    proposal["status"] = "publishing"
    proposal["publication"] = {"attempt": "interrupted-test", "started_at": 1}
    with flow.connect() as connection:
        flow._save(connection, proposal, "test_interruption")
    result = json.load(
        urlopen(
            api_request(
                panel,
                {
                    "action": "recover",
                    "id": proposal["id"],
                    "expected_digest": proposal["digest"],
                    "reason": "Automated isolated recovery verification; no remote request was made",
                },
            )
        )
    )
    assert result["status"] == "failed" and result["approval"] is None
    assert result["plan"]["snapshot"]["mode"] == "unverified"
    assert "unknown" in result["publication"]["outcome"]
