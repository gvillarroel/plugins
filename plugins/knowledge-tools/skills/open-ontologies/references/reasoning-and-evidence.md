# Reasoning, scope, and evidence

## Contents

- [Keep the result categories separate](#keep-the-result-categories-separate)
- [Select the profile and its boundary](#select-the-profile-and-its-boundary)
- [Time and graph selection](#time-and-graph-selection)
- [Produce and check a certificate](#produce-and-check-a-certificate)
- [SHACL and failure handling](#shacl-and-failure-handling)
- [Primary sources](#primary-sources)

## Keep the result categories separate

| Result | What it supports |
| --- | --- |
| Syntax validation | The supplied document was accepted by the selected parser. |
| Lint / ontology defects | Particular modeling checks found or did not find their reported conditions. |
| SHACL conformance | The selected data graph satisfied the executed shape constraints. |
| Competency-query result | The query returned the reported answer over the selected graph. |
| Rule closure | The implemented rule table derived the reported triples. |
| Checked derivation certificate | The checker accepted those derivations relative to the supplied assertions and rules. |
| DL/solver answer | The actual reasoner or solver's result, subject to its fragment, budget, and certification path. |

None establishes the real-world truth of the input assertions. A parser pass,
clean lint, zero detected clashes, and an absent checker are different outcomes.

## Select the profile and its boundary

The engine exposes `rdfs`, `owl-rl`, `owl-rl-ext`, and `owl-dl` reasoning
profiles. The rule profiles implement particular rule tables; their names are
not complete W3C profile-conformance claims. Inspect `onto_dlp_boundary` after
loading and before relying on a rule result. It distinguishes axioms outside
the Horn fragment, rules that the engine does not implement, and partially
handled axioms. These require different responses.

The native `owl-dl` path targets SHIQ rather than all OWL 2 DL. Nominals,
datatype reasoning, approximated constructs, or resource budgets can limit an
answer. Preserve unsupported and `undetermined` results. No detected clash is
not a proof of consistency, and failure to derive a triple does not establish
its negation under open-world semantics.

For a non-materializing MCP check, discover and call `onto_reason` with:

```json
{"profile":"rdfs","materialize":false}
```

Ordinary CLI reasoning writes inferred triples to its working store. Use an
isolated scratch store for that workflow. There is no ordinary CLI `--dry-run`
flag. MCP `inference_graph:true` separates inferred triples for supported rule
profiles; inspect save format and graph-selection behavior when exporting.

## Time and graph selection

By default, reasoning reads the store's graphs together. That union can combine
versions that never coexisted. For a graph using the engine's temporal vocabulary,
choose `valid_at` and/or `as_of`, or deliberately request `all_versions`.
The engine can refuse an unscoped run rather than guess which version was meant.
Read the response's actual `scope` and preserve it with the result.

CLI reasoning with temporal selectors is non-materializing. Over MCP, request
`materialize:false` for a temporal run. A snapshot result must not be written as
an assertion that becomes visible to every time slice. Use separate SHACL and
reasoning calls when a combined convenience operation cannot express that scope.

## Produce and check a certificate

For a rule-profile run, add this command after load in the same CLI batch:

```json
{"command":"reason","args":["--profile","rdfs","--certificate","cert"]}
```

The MCP equivalent uses `certificate_dir`. The `owl-dl` path does not accept
this forward-chaining certificate option. Keep the original assertions separate
from prior materialization; otherwise a later certificate can take earlier
inferences as premises without their derivation history.

When proof checking is part of the task, use a selected upstream source checkout
at the recorded revision and its pinned Lean toolchain. From its `lean/` folder:

```text
lake build
lake exe oo-cert /ABSOLUTE/cert/asserted.tsv /ABSOLUTE/cert/derivations.tsv
```

Retain input/output hashes, the checker/toolchain identity, exit status, JSON
verdict, and certificate files. `oo-cert` exit 0 accepts derivations; exit 1
rejects a step; exit 2 indicates unreadable or malformed input. A generated
certificate that has not been checked remains unchecked.

Supplied Horn rules use their corresponding `oo-horn` certificate/checker path.
Preserve `entailed_under_supplied_rules` instead of shortening it to an
unconditional entailment. A checker verifies what follows from the supplied
assertions and rules; it does not discharge those assumptions. Keep `scope.tsv`
for a reviewer: the checker cannot establish that those triples came from the
intended files or temporal snapshot. Refutation, finite-model, and external
solver workflows have different checkers and limits; use their actual reported
verdict rather than treating solver agreement as a checked proof.

## SHACL and failure handling

Keep conformant, non-conformant, unsupported/undetermined, and processor-error
outcomes distinct. A report with no exercised focus nodes gives no evidence
about the records the shapes were intended to cover. Check targets and counts
with a known conforming and a deliberately failing record. In v2.0.1 inspect
aggregate `focus_nodes`, `unmatched_shapes`, and `skipped_constraints`.

The reviewed 2.1.0 source adds per-target counts and fixes lexical datatype
handling absent from v2.0.1. A passing cardinality fixture on the release does
not qualify comprehensive datatype validation. Keep these version limitations
explicit when lexical validity matters to a task.

The ordinary SHACL evaluator and optional verified evaluator have different
supported constructs. Inspect the selected build's `shacl --help` or MCP schema
before selecting one. A verifier's absence is an unavailable check, and changing
evaluators changes the validation contract. Report rather than silently discard
unsupported SHACL-SPARQL, custom constraints, or temporal scope.

If a check fails, fix the relevant input or configuration and repeat that check.
Retain original diagnostics. Do not convert skipped checks, timeouts, or
checker failures into conformance, consistency, or certification claims.

## Primary sources

- [Reasoning boundaries](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/docs/reasoning.md)
- [Certificate contract](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/docs/lean-certificates.md)
- [Trusted computing base](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/docs/trusted-computing-base.md)
