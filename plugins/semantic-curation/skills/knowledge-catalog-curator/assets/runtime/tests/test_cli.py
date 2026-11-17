import json
import subprocess
import sys


def test_installed_cli_wiring_and_errors(tmp_path):
    def run(*args):
        return subprocess.run(
            [sys.executable, "-m", "knowledge_catalog.cli", "--home", str(tmp_path / ".kc"), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

    assert json.loads(run("status").stdout)["config"]["writes_enabled"] is False
    assert run("inventory").returncode == 1
    configured = run("configure", "--project", "test-project", "--allow-project", "test-project")
    assert configured.returncode == 0
    assert json.loads(configured.stdout)["writes_enabled"] is False
    source = tmp_path / "products.csv"
    source.write_text("product_id,quantity\n1,2\n", encoding="utf-8")
    analyzed = run("analyze", str(source))
    assert analyzed.returncode == 0, analyzed.stderr
    proposal = json.loads(analyzed.stdout)
    assert proposal["status"] == "draft" and proposal["approval"] is None
    assert json.loads(run("review", proposal["id"]).stdout)["digest"] == proposal["digest"]
    assert (
        run("approve", proposal["id"], "--digest", proposal["digest"], "--reviewer", "CLI test").returncode
        == 1
    )
    assert run("publish", proposal["id"]).returncode == 1
    audit = json.loads(run("audit").stdout)
    assert audit[0]["action"] == "proposed"
