---
name: knowledge-catalog-curator
description: Explore GCP Knowledge Catalog, profile datasets and documents, compare taxonomy concepts with the native Open Ontologies engine, and review metadata or synthetic lineage before human-approved publication. Use for catalog curation and the bundled Claude/MCP review tool.
---

# Knowledge Catalog Curator

Use the bundled Python runtime and English Colorset 1 interfaces to turn source
evidence into reviewable metadata. Keep actual catalog resources, synthetic
lineage, suggested concepts, and human decisions distinct.

## Establish the runtime

Locate this skill's directory from its loaded path. Treat it as a read-only
resource. Run the following commands using that directory's actual path:

```sh
uv run --script scripts/curator.py inspect
uv run --script scripts/curator.py install --destination ./curator-runtime --home ./.kc
uv run --script scripts/curator.py run --installation ./curator-runtime -- status
```

Run from the user's working directory, with the script path resolved relative
to the skill directory. Installation copies the complete runtime outside the
skill and installs its locked dependencies as a wheel. The JSON result contains
the exact interpreter, state path, and MCP configuration. Reuse that installation;
do not read repository siblings or the previous development checkout.
For direct Python snippets, use the returned interpreter with `-I` so host
`PYTHONHOME` or `PYTHONPATH` values cannot mix another interpreter's libraries.

Read [installation.md](references/installation.md) for GitHub installation,
Claude Code/Desktop registration, engine setup, migration, and removal.

## Curate one decision at a time

- Inspect `status`, `inventory`, `search`, or `get` for catalog questions. Remote
  reads need a configured project/location and authorized user ADC.
- Run `analyze PATH` for supported local documents and datasets. Add the actual
  source folder to `allowed_roots` when needed. Retain provenance and limitations.
- Open `ui` for **Choose → Describe → Check quality → Plan → Decide**. Concept
  selection stages an edit; **Save draft** creates a revision. Compare real
  Open Ontologies evidence separately from explicit **Local comparison**.
- Run `lineage-demo --seed 42` for a reproducible synthetic exercise. Use
  **Choose → Explore → Check and correct → Decide → Share** to inspect dependencies,
  correct claims, review quality, and export. The demo does not establish GCP jobs.
- Read [curation.md](references/curation.md) for commands, taxonomy evidence,
  vocabulary constraints, host capabilities, and publication conditions.

Make the next useful action visible without exposing all technical details at
once. Preserve the English presentation and the included palette. A host's
native chrome remains controlled by that host.

## Preserve decision boundaries

Source facts and engine scores are evidence, not approval. Do not call the human
approval CLI on a user's behalf. MCP exposes comparison, review, revision, and
export tools but no approval tool. Editing invalidates existing approval.
Prepare a live plan and let the user approve the exact current revision in the
review interface before publication. Writes also require explicit project
allowlisting and enabled writes. Data Lineage access is read/export only.

Keep `.kc`, downloaded data, virtual environments, credentials, and native engine
binaries outside the skill. Do not claim successful GCP publication, Claude
authentication, or ChatGPT rendering without observing it. For detailed trust
and provenance limits, read the bundled [security boundaries](assets/runtime/SECURITY.md).
