import json
import subprocess
import sys

from rdflib import Graph

from knowledge_catalog.workflow import Workflow


def test_r40_cli_export_formats_history_and_no_overwrite(tmp_path):
    flow = Workflow(tmp_path / ".kc")
    source = tmp_path / "orders.csv"
    source.write_text("quantity,price\n1,2\n", encoding="utf-8")
    proposal = flow.propose(str(source), provenance={"owner": "CLI review team", "license": "MIT"})
    proposal = flow.revise(
        proposal["id"], {"description": "Synthetic quantities and prices for CLI export verification"}
    )

    def run(*args):
        return subprocess.run(
            [sys.executable, "-m", "knowledge_catalog.cli", "--home", str(flow.home), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

    for format_name, suffix in (("json", "json"), ("plan", "json"), ("turtle", "ttl")):
        target = tmp_path / f"export-{format_name}.{suffix}"
        result = run("export", proposal["id"], "--format", format_name, "--output", str(target))
        assert result.returncode == 0, result.stderr
        if format_name == "turtle":
            assert len(Graph().parse(target, format="turtle")) > 0
        else:
            document = json.loads(target.read_text(encoding="utf-8"))
            assert "metadata" in document
        original = target.read_bytes()
        assert run("export", proposal["id"], "--format", format_name, "--output", str(target)).returncode == 1
        assert target.read_bytes() == original
    assert len(json.loads(run("history", proposal["id"]).stdout)["revisions"]) == 2
    diff = json.loads(run("diff", proposal["id"], "--from", "1").stdout)
    assert any(change["path"] == "/metadata/description" for change in diff["changes"])
    assert flow.get(proposal["id"])["approval"] is None
