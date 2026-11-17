# Evaluation and integration

## Question-to-index design

Build a compact competency table before authoring the vocabulary:

| Family | Answer shape | Index requirement | Evidence check |
| --- | --- | --- | --- |
| Definition or synonym | One qualified description | Reviewed aliases and annotated concept | Exact defining passage |
| Category listing | Supported members and exclusions | Child-to-parent taxonomy with scope | Each listed member has source support |
| Dependency or ownership | Directed relation | Typed subject, predicate, object | All required passages and role direction |
| Comparison | Aligned attributes | Separate scoped identities | Evidence for both sides |
| Exception, version, negation | Qualified rule | Preserve qualifier in source and identity | Conditions and counterevidence retained |

The bundled helper implements lookup, taxonomy and declared relation discovery.
For comparison or exception questions, use lookup or an explicit relation plan
and review the evidence; do not invent a new family kind. A language model may
draft mappings from sources, but they remain proposed until reviewed. Missing
evidence must stay a gap. Never manufacture a relation to satisfy a question.

Avoid building an exhaustive ontology before the workload is understood. Start
with the smallest reviewed vocabulary that covers the intended answer shapes.
Add an alias, edge, or route only when its source and expected failure reduction
are concrete. Preserve excluded source fields in the ingestion receipt: an
excellent index cannot recover body text that the builder omitted.

## Compare retrieval fairly

1. Freeze corpus, passage IDs, vocabulary, code, top-k and metric definitions.
   Record whether annotations are manually authored or model-generated and
   their cost. The helper does not evaluate ontology generation quality.
2. Use development queries to find failures. Keep a separate question-family or
   domain cohort untouched until one candidate is frozen. Record all outcomes;
   a revision after seeing independent failures needs a fresh cohort.
3. Compare lexical and guided routes on identical inputs and passage budgets.
   Also remove aliases, taxonomy edges, and relations in separate ablations to
   identify what helped. Treat a manually supplied family as a separate planned
   condition from automatic routing.
4. Measure **all-required-evidence@k** (every required passage returned), macro
   passage recall@k, MRR of the first relevant passage, direct-lookup regressions,
   and unsupported-query behavior. Report by question family. Multiple runs of
   deterministic retrieval establish reproducibility, not independent samples.
5. Include ambiguous aliases, reversed roles, sibling distractors, absent facts,
   scoped versions, and bundles larger than k. The helper returns candidates
   for absent facts; measure actual answer abstention separately.
6. Verify physical citations, original qualifiers and final answer support in a
   separate answer evaluation. Retrieval coverage does not prove correctness.

Do not select or promote a universal winner from a small diagnostic. Preserve
an incumbent whenever the declared independent or runtime gates are unmet.

## Connect an existing package

Create an **additional discovery projection** in a new output folder. Export
retained passage text, stable record IDs and exact physical citations from the
existing authoritative snapshot into this input contract. Do not silently add
fields to a builder's closed plan, change its native ranks, replace its ontology,
or rewrite a digest-bound generated expert in place.

Keep the source builder and the answer-generation procedure frozen while
comparing retrieval projections. Include this projection only by rebuilding a
new version of the package with its own validation, citation mapping and digest
bindings. A generated consumer must carry its own helper and input index; it
must not require a sibling skill or the original repository to be present.

There is no native Semantic OKF adapter in this bundle. The JSON conversion and
consumer binding require explicit validation in the owning pipeline. Source
fidelity, closed-tree validation and native builder/consultant parity remain
the original package's responsibilities.

## Research basis and limits

- [Document Expansion by Query Prediction](https://arxiv.org/abs/1904.08375)
  studies adding predicted query terms to documents. This helper uses reviewed
  labels and aliases; it does not implement the paper's trained query generator.
- [CQ4OE](https://arxiv.org/abs/2609.26029) distinguishes predicting required
  terms from constructing adequate ontology structure. A question-to-term
  checklist is not proof of a correct ontology or an answer.
- [Generating and Filtering Competency Questions](https://aclanthology.org/2025.ldk-1.15/)
  reports scope/relevance and quality limitations in automated CQ generation.
  Keep generation, review, retrieval and answer metrics distinct.
- [RAPTOR](https://arxiv.org/abs/2401.18059) motivates retrieval at several
  abstraction levels. Its recursive summaries are a different technique from
  this reviewed child-to-parent taxonomy; no RAPTOR result is claimed here.
