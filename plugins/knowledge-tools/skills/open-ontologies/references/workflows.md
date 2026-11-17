# Operating workflows

## Contents

- [Load, inspect, and author](#load-inspect-and-author)
- [Ingest and validate structured data](#ingest-and-validate-structured-data)
- [Plan and apply a graph change](#plan-and-apply-a-graph-change)
- [Alignment and retrieval](#alignment-and-retrieval)
- [Extraction handoff](#extraction-handoff)
- [Primary sources](#primary-sources)

## Load, inspect, and author

Work from supplied files or explicitly authored Turtle. Validate syntax before
loading. In MCP, the core parameter shapes are:

| Tool | Example arguments |
| --- | --- |
| `onto_validate` | `{"input":"/absolute/input.ttl"}` or `{"input":"TURTLE_TEXT","inline":true}` |
| `onto_load` | `{"path":"/absolute/input.ttl"}` or `{"turtle":"TURTLE_TEXT"}` |
| `onto_query` | `{"query":"SELECT ?s WHERE { ?s a <https://example.org/Thing> }"}` |
| `onto_save` | Discover its path/format schema before writing the result. |

Inspect `onto_stats`, relevant lint messages, and `onto_defects` after load.
Defects checks the ontology's declarations; a clean report does not prove
consistency. Use explicit prefixes or full IRIs in competency queries. Keep
source evidence and consequential modeling decisions alongside authored axioms.

Run all stateful CLI operations in a single batch, or use explicit persistent
storage. A file-oriented lint/validate command may inspect a supplied file
rather than the current active graph; keep that input identity clear. Fix the
specific reported issue and rerun the affected checks. Preserve independent
warnings or unsupported constructs rather than iterating toward an empty report
by weakening the model.

When changing an existing active graph, inspect its load/merge behavior before
loading another ontology. `clear`, rollback, unload, and cache deletion have
distinct effects. Do not reset unrelated state simply to obtain expected counts.
Write the accepted Turtle to an explicit output; a running memory session alone
is not a durable delivery. Choose N-Quads or TriG instead when named graphs are
part of the result; ordinary Turtle serialization flattens those boundaries.

## Ingest and validate structured data

1. Inspect the actual schema, key columns, scalar types, nulls, and intended IRI
   policy. Load the selected ontology into the working session.
2. Use `onto_map` or CLI `map` to propose a mapping. Review column/property
   matches and identity collisions before ingestion.
3. Use `onto_ingest` or CLI `ingest` with the reviewed mapping and input format.
   The engine handles CSV, JSON/NDJSON, XML, YAML, XLSX, and Parquet through its
   declared adapters; confirm the selected build's supported formats.
4. Run `onto_shacl` with explicit shapes, or CLI `shacl shapes.ttl` in the same
   batch. Keep a conforming fixture and a fixture violating the intended rule.
   Record focus-node counts and constraint results, not only `conforms`.
5. Run the chosen reasoning profile only if the task needs inferred triples,
   then verify record counts, stable IDs, and competency queries. Save outputs
   with asserted/derived roles identified.

`onto_extend` combines ingestion, SHACL, and reasoning. Use the individual
operations when a stage needs review, a temporal scope, or separate evidence.
Do not rely on the convenience pipeline to supply missing temporal selectors.

For PostgreSQL/DuckDB, confirm the relevant compile-time feature and connection
scope before introspection or SQL ingestion. DuckDB extension and federation
effects depend on the query. Validate the operation's actual result instead of
assuming that every reachable SQL database is an authorized input.

## Plan and apply a graph change

A plan compares the loaded base with the **complete proposed Turtle graph**.
It is not a patch API. Retain instance assertions as well as schema triples in
that proposal, or their absence becomes a proposed deletion.
The lifecycle recipe below is for a selected plain graph. Turtle is not a
dataset proposal format: do not use this flow to promise preservation of named
or temporal graph boundaries. Such a migration needs a separately validated
dataset-level procedure, even when a N-Quads/TriG backup is available.

1. Record the base identity, current counts, and graph scope. For a plain default
   graph, retain a named version. For a dataset containing named, temporal, or
   inference graphs, archive N-Quads/TriG and verify a restore into a separate
   store before relying on that archive. Save the proposal as a separate file.
2. Run CLI `plan proposed.ttl` in the base's batch/session, or
   `onto_plan` with `{"new_turtle":"COMPLETE_PROPOSED_TURTLE"}`. Retain the
   returned `plan_id` and complete report.
3. Review added/removed triples and entities, locked IRIs, dependent triples,
   risk, and the conservativity block. In the reviewed baseline, conservativity
   is on by default. CLI `--no-conservativity` or MCP
   `check_conservativity:false` skips it; report the skip explicitly.
4. Conservativity is relative to a rule table, not arbitrary OWL DL. Inspect
   `ran`, profile, skipped/unknown outcomes, and newly derived consequences.
   Adding `rdfs:domain` can retype many individuals while the shape diff scores
   low. Do not treat a low blast radius as proof of semantic safety.
5. Run the chosen enforcement pack (`generic`, `boro`, `value_partition`, or
   an explicitly supplied custom rule set). Interpret modeling warnings against
   the actual domain rather than automatically suppressing them.
6. Recheck the actual live graph against the recorded base immediately before
   apply; counts alone cannot detect a same-sized change. A `plan_id` fixes the
   proposal, not the base: the engine recomputes its delta against current state.
   If the base changed, regenerate and review the plan. Keep a controlled store
   owner during this step; do not claim an atomic reviewed update on a graph
   that another writer can change concurrently.
7. When the user's request authorizes applying this reviewed change, apply the
   exact plan: CLI `apply safe --plan-id PLAN_ID`, or MCP `onto_apply` with
   `{"mode":"safe","plan_id":"PLAN_ID"}`. Keep the same persistent store or
   MCP session holding the base. Do not rely on "most recent" when plans coexist.
8. Verify resulting counts, queries, constraints, lineage, and intended drift.
   Retain the base archive needed for an authorized rollback.

Named `version` snapshots use N-Triples. They flatten graph names and omit the
engine's inference graph; `rollback` clears the store before loading that
snapshot. Use this path only when those semantics fit the selected default-graph
workflow. Preserve engine configuration/state separately when it is part of
the recovery contract. A dataset restore needs its own checked procedure.

`safe` describes an engine mode, not an independent authorization or a proof.
The implementation can use a triple delta and fall back to reloading when blank
nodes prevent a meaningful delta. `migrate` adds candidate equivalence bridges;
inspect every bridge and unbridged removal before accepting those logical
assertions. `force`, clearing a monitor block, or deleting locks changes the
governance boundary and is not an automatic recovery from rejection.

Watchers can log, notify a configured webhook, block an apply, or automatically
roll back. Inspect existing configuration before running monitoring or enabling
background watching. For a plan-only request, return its reviewable evidence.

## Alignment and retrieval

Use discovered alignment tools to generate candidates. Labels, structural
similarity, and learned feedback provide evidence for review, not proof of
`owl:equivalentClass`, `owl:equivalentProperty`, or `owl:sameAs`. Keep candidate
relations separate from accepted axioms and retain the basis for each decision.

For retrieval, distinguish a bounded neighborhood slice from a logical module.
Use dedicated projection/entailment checks when a downstream answer needs a
claim to remain derivable in the slice. Coverage or similarity alone does not
establish preservation. Embedding search requires its explicit optional runtime
and provider configuration.

## Extraction handoff

`onto_extract_scaffold` returns an extraction prompt/schema;
`onto_extract_validate` validates extraction JSON supplied by the caller.
Those tools do not themselves perform model extraction. Keep any separately
requested model call, its source scope, and its validation result explicit.

## Primary sources

- [Pinned input schemas](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/src/inputs.rs)
- [Pinned server behavior](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/src/server.rs)
- [Lifecycle guide](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/docs/lifecycle.md)
- [Data pipeline](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/docs/data-pipeline.md)
