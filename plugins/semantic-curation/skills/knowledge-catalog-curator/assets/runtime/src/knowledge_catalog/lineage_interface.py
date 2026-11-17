"""Shared Python, CLI, HTTP and MCP interface for local lineage decisions."""

from __future__ import annotations

import copy
import json
import re
from importlib.resources import files
from pathlib import Path


def store(home):
    from .lineage import LineageStore

    return LineageStore(Path(home))


def export_record(record, format="json", project="", location="us-central1"):
    if format == "json":
        return copy.deepcopy(record)
    if format not in {"openlineage", "gcp-plan"}:
        raise ValueError("format must be json, openlineage or gcp-plan")
    from .lineage_gcp import build_lineage_plan, export_openlineage

    value = (export_openlineage if format == "openlineage" else build_lineage_plan)(
        record["graph"], project, location
    )
    return {
        **value,
        "review": {key: record[key] for key in ("id", "revision", "digest", "status", "approval")},
        "export_only": True,
    }


def attach_record(flow, lineage_id, proposal_id, expected_digest, proposal_digest):
    """Attach an approved simulated graph to metadata; catalog approval is invalidated."""
    if not isinstance(proposal_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", proposal_digest):
        raise ValueError("proposal_digest must be the SHA-256 of the reviewed metadata revision")
    record = store(flow.home).verified_approved(lineage_id, expected_digest)
    proposal = flow.get(proposal_id)
    relationships = proposal["metadata"].get("relationships", [])
    if not isinstance(relationships, list):
        raise ValueError("Existing relationships must be reviewed as a list before attaching")
    relationships = [
        item
        for item in relationships
        if not (
            isinstance(item, dict)
            and item.get("type") == "synthetic_lineage"
            and item.get("lineage_id") == lineage_id
        )
    ]
    relationships.append(
        {
            "type": "synthetic_lineage",
            "lineage_id": record["id"],
            "revision": record["revision"],
            "digest": record["digest"],
            "synthetic": True,
            "scope": "Independent simulation; not observed lineage of this source dataset",
            "graph": record["graph"],
        }
    )
    return flow.revise(proposal_id, {"relationships": relationships}, expected_digest=proposal_digest)


def render_lineage(record=None, *, embedded=False):
    """Return a complete HTML view. A supplied record is an offline, non-writing snapshot.

    Python notebooks can display HTML(render_lineage(record)); save the returned
    string to an HTML file when the notebook blocks scripts. Persistent decisions
    use LineageStore or kc ui. No IPython runtime dependency is needed.
    """
    template = files("knowledge_catalog").joinpath("lineage.html").read_text(encoding="utf-8")
    if record is not None:
        payload = json.dumps(record, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
        template = template.replace(
            "<!--INITIAL_RECORD-->",
            '<script type="application/json" id="initial-record">' + payload + "</script>",
        )
    if embedded:
        script = files("knowledge_catalog").joinpath("host-bridge.js").read_text(encoding="utf-8")
        template = template.replace(
            "<!--HOST_BRIDGE-->", "<script>" + script.replace("</script", "<\\/script") + "</script>"
        )
    return template
