---
name: open-ontologies
description: "Operates the Open Ontologies Rust engine through its CLI or onto_* MCP tools to load, query, validate, reason over, ingest into, and govern RDF/OWL graphs. Use when configuring or using fabio-rovai/open-ontologies, checking SHACL results or inference certificates, or planning and applying ontology changes with this engine. Generic ontology modeling without this engine is outside its scope."
---

# Open Ontologies

Use the engine to turn an ontology task into reproducible operations and
inspectable results. Choose CLI batch execution or one connected MCP session;
preserve the distinction between asserted facts, inferred facts, validation
results, and independently checked evidence.

## Standalone boundary

This package contains complete operating instructions and local references.
It requires an explicitly selected `open-ontologies` executable or a connected
Open Ontologies MCP server, plus the user's ontology/data files. It needs no
sibling skill, knowledge-store checkout, or Python package. Optional SQL,
embedding, plugin, and proof-checking dependencies apply only to those modes.

The operating baseline is upstream release **v2.0.1**, commit
`d118719043905132d314611dcee9f0cac5f87868`. The later source review at
`fec2b4713bbab52596adbde55decd862e443b020` declares Cargo **2.1.0**; that is a
source identity, not a claim that a matching binary has been released.

Read [runtime.md](references/runtime.md) for installation, preflight, state
selection, CLI batches, or MCP configuration. Read
[workflows.md](references/workflows.md) for ingestion, alignment, and lifecycle
changes. Read [reasoning-and-evidence.md](references/reasoning-and-evidence.md)
before interpreting reasoning, temporal scope, SHACL, or proof results.

## Establish the execution context

1. Identify the requested task, source files, allowed output/store directory,
   and whether the task authorizes changing an existing graph or remote target.
2. Run `open-ontologies --help` and the relevant subcommand's `--help`, or
   discover connected MCP tool schemas and call `onto_status`. Record the
   actual build/release and enabled features rather than assuming a tool count.
3. Bind an explicit workspace `--data-dir`. For isolated CLI work, also use
   `--no-connect` so an existing daemon does not receive the commands.
4. Choose state deliberately: the default graph is **in memory per process**.
   Keep load, query, reasoning, and save in one batch/MCP session, or explicitly
   enable persistent storage. A successful standalone `load` does not make the
   next memory-mode CLI process see those triples.

The baseline command is:

```text
open-ontologies --no-connect --data-dir WORKSPACE_STORE --json batch commands.json --bail
```

Use a JSON array of `{"command":"load","args":["input.ttl"]}` records for
batches, especially with Windows paths or SPARQL. Arguments are resolved from
the process working directory. Check each result's content as well as exit
status; SHACL non-conformance can be a successfully executed check.

## Select the workflow

| Task | Operations and decisions |
| --- | --- |
| Author or repair a graph | Edit Turtle; validate syntax; load into a chosen session; inspect stats, lint, and ontology defects; run explicit competency queries; save the accepted result. |
| Query an existing graph | Load once, confirm the intended graph and counts, then query. `onto_query` accepts SPARQL queries, not SPARQL UPDATE. |
| Check constraints | Load the exact data/ontology graph and run SHACL against explicit shapes. Report conformance, violations, unsupported constructs, or processor failure separately. |
| Reason or export a certificate | Inspect the axiom boundary and choose a profile and graph scope. Ordinary CLI reasoning materializes; use a scratch store or MCP `materialize:false` for a dry run. |
| Ingest structured data | Inspect the schema, review a mapping, ingest into a selected store, validate shapes, and verify expected rows/IRIs with queries. |
| Change a governed ontology | Snapshot the base, plan the complete desired graph, inspect the plan and locks, enforce the selected rules, then apply its exact `plan_id` when authorized. |
| Align or prepare retrieval context | Inspect alignment candidates or graph slices; verify consequential equivalences and the support for each downstream claim. Similarity alone is insufficient. |

Discover the required MCP tools and schemas. Release v2.0.1 supports allow/deny
filters; use named tool profiles only when installed help advertises them.
Filtering narrows capabilities and does not grant permission to mutate a graph.
Do not substitute a different operation when a required tool is unavailable.

## Preserve consequential boundaries

- A proposed lifecycle graph is the **whole desired state**, including retained
  instance data. Sending only new triples can plan removal of everything else.
  A low shape-risk score does not establish unchanged meaning: inspect the
  conservativity result, whether it ran, and its rule profile.
  Plain-Turtle lifecycle operations do not establish preservation of a named
  or temporal dataset; use a separately checked dataset migration for that case.
- Inference is a graph change by default. CLI `reason` has no generic
  `--dry-run` or `--materialize` flag. MCP `onto_reason` exposes
  `materialize:false`; use the discovered schema.
- A new session can create SQLite state, caches, and lineage even when the graph
  is in memory. Keep those files under the selected workspace.
- Core local-file workflows need no model provider. Imports, marketplace
  downloads, remote embeddings, SQL federation, push/pull, and configured
  watcher/webhook actions have additional effects. Use them only within the
  user's requested scope and inspect the relevant configuration first.
- Save assertions and derived data with their roles intact. Preserve returned
  `undetermined`, skipped checks, truncation, temporal scope, and checker-absent
  outcomes; none is an implicit pass.

## Deliver the result

Report the actual runtime/build, selected store/session and storage mode,
input identities, operations executed, validation/reasoning profile and graph
scope, output files, and any unresolved result. Cite relevant source IRIs and
evidence artifacts when explaining conclusions. For a plan-only request,
deliver the plan and its consequences; execute an apply only when the user's
request authorizes it. Keep existing authorization across the workflow.

Example requests this skill supports:

- "Load my local ontology, verify the competency queries, and save a reviewed
  Turtle result with Open Ontologies."
- "Map this CSV into the graph and show which records fail these SHACL shapes."
- "Plan this complete ontology replacement, including semantic consequences,
  and give me the evidence before any production change."
