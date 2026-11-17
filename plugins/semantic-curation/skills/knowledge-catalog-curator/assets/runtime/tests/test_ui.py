import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from knowledge_catalog.ui import make_server
from knowledge_catalog.workflow import Workflow


@pytest.fixture
def ui(tmp_path):
    flow = Workflow(tmp_path / ".kc")
    server, url = make_server(flow, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base, token = url.split("#")
    yield base, token, flow
    server.shutdown()
    server.server_close()
    thread.join()


def test_auth_and_no_secret_in_html(ui):
    base, token, _ = ui
    page = urlopen(base).read().decode()
    assert token not in page and "Semantic curation" in page
    with pytest.raises(HTTPError) as exc:
        urlopen(base + "api/state")
    assert exc.value.code == 401
    request = Request(base + "api/state", headers={"Authorization": "Bearer " + token})
    assert json.load(urlopen(request))["config"]["writes_enabled"] is False


def test_origin_blocks_cross_site_approval(ui):
    base, token, _ = ui
    request = Request(
        base + "api/action",
        data=b'{"action":"approve"}',
        headers={
            "Authorization": "Bearer " + token,
            "Origin": "https://attacker.invalid",
            "Content-Type": "application/json",
        },
    )
    with pytest.raises(HTTPError) as exc:
        urlopen(request)
    assert exc.value.code == 403


def test_host_blocks_dns_rebinding(ui):
    base, token, _ = ui
    request = Request(
        base + "api/state", headers={"Authorization": "Bearer " + token, "Host": "attacker.invalid"}
    )
    with pytest.raises(HTTPError) as exc:
        urlopen(request)
    assert exc.value.code == 403


def test_action_errors_do_not_crash_server(ui):
    base, token, _ = ui
    request = Request(
        base + "api/action",
        data=b'{"action":"unknown"}',
        headers={
            "Authorization": "Bearer " + token,
            "Origin": base.rstrip("/"),
            "Content-Type": "application/json",
        },
    )
    with pytest.raises(HTTPError) as exc:
        urlopen(request)
    assert exc.value.code == 400
    assert "Unknown action" in exc.value.read().decode()


def test_open_panel_reuses_service_without_exposing_capability(ui, monkeypatch):
    from knowledge_catalog.ui import open_panel

    base, token, flow = ui
    (flow.home / "review-session.json").write_text(json.dumps({"url": base + "#" + token}), encoding="utf-8")
    opened = []
    monkeypatch.setattr("knowledge_catalog.ui.webbrowser.open", lambda url: opened.append(url) or True)
    result = open_panel(flow)
    assert len(opened) == 1 and opened[0].startswith(base + "?ui=en&view=")
    assert opened[0].endswith("#" + token)
    assert result["opened"] is True and token not in json.dumps(result)
    assert flow.list() == []


def test_fresh_english_navigation_query_keeps_html_and_auth_contract(ui):
    base, token, _ = ui
    for path, heading in (
        ("?ui=en&view=fresh", "Semantic curation"),
        ("lineage?ui=en&view=fresh", "Review one decision at a time"),
    ):
        with urlopen(base + path) as response:
            html = response.read().decode()
            assert 'lang="en"' in html and heading in html and token not in html
            assert response.headers["Cache-Control"] == "no-store"
