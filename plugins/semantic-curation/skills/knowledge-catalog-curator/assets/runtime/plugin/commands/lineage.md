---
description: Explore synthetic lineage, inspect evidence, and propose traceable corrections
argument-hint: [seed or identifier]
---

Use lineage_list to find existing graphs. If the user wants a demo, use
create_lineage_demo with an explicit seed (42 by default); it generates local
CSVs and executes recipes. Do not invent joins between Kaggle datasets.

Call review_lineage to show the MCP Apps view when the host supports it. Explain
upstream sources, downstream impact, transformations, column dependencies, and
findings. Distinguish executed evidence from declared hypotheses. The demo has
intentional teaching defects; do not describe it as already approved.

To improve it, use revise_lineage with the exact revision digest. Do not turn
new claims into observations. Compare with lineage_history. Edits invalidate
previous approvals.

Use open_lineage_panel for the person to review and approve in their browser.
Never approve for them or use files, shell, or Python to bypass their decision.

export_lineage returns JSON, OpenLineage, or a GCP plan without cloud writes.
Explain that the console can omit column facets from custom events.
attach_lineage can attach an approved simulation to a metadata proposal as an
independent domain; it invalidates that proposal's approval and retains its
existing publication workflow. Respond in English.
