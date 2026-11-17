---
name: curate-semantic-model
description: "Curate evidence-preserving semantic models, build reproducible taxonomy and ontology snapshots, and compare semantic changes between two versions of a document, repository, or pull request. Use for maintained typed knowledge, concept unification, and evidence-backed graph review."
---

# Curate a minimal semantic model

Build the smallest representation that answers the required questions and
supports the required decisions without losing meaning or provenance. Start
with typed records; add facets, hierarchy, or axioms only when they provide a
needed capability. Compare parsimony only among models that meet these duties.

## 1. Select the needed capabilities

- Use this skill's self-contained JSON workflow for source inventory, typed
  modeling, conservative reduction, conflict review, and coverage reporting.
- If source acquisition or synchronization is needed, optionally select `know`
  from the available skill catalog. Its provenance registry does not establish
  concept identity. Files already supplied can be inventoried directly.
- If formal RDF, OWL, or SHACL engineering is needed, optionally select
  `extract-ontologies` from the available catalog, or use an available formal
  processor. Keep the core JSON workflow usable without either companion.
  Report unavailable formal checks as not checked.
- Run the bundled standard-library helpers with Python 3.11 or later through
  `uv run --script`. In commands below, replace `<skill-dir>` with this skill's
  actual directory; write task inputs and outputs outside that directory.
  Use the same launcher for ad hoc scripts or an available Python 3 interpreter
  such as `python3`; do not assume bare `python` or optional tools such as `rg`
  are installed.
- Produce only the requested deliverables. Keep one authoritative model and
  derive tables, graphs, spreadsheets, or reports from it when useful.

## 2. Define preservation obligations

Inventory the original source units with stable IDs and locators. Preserve
their wording, votes, selected flags, weights, required status, and provenance.
Distinguish inventoried evidence from concepts extracted from that evidence.

Choose the least expressive sufficient representation: typed records, facets,
taxonomy, then ontology as needed. Do not force every stage into every task.
Declare types, allowed relations, attributes, cardinalities, endpoint rules,
open or closed attribute policy, and any predicate-specific cycle restriction.
For string attributes that denote local node IDs, optionally declare
`node_reference_types` in the contract so the helper checks exact existence and
allowed target types. Plain strings do not acquire reference semantics by name.
Define meaningful competency questions and expected answers before reduction.

Preserve numeric precision and source datatype. The file reader rejects real
number tokens that would lose decimal value during float conversion. Use a
declared typed literal object when exact lexical values must survive; follow
the numeric boundary in [model-contract.md](references/model-contract.md).

Read [methodology.md](references/methodology.md) for semantic distinctions and
[model-contract.md](references/model-contract.md) for the executable contract,
inline input examples, supported operators, and diagnostics. Acceptance fixtures
are maintenance resources, not required runtime inputs.

## 3. Propose and minimize conservatively

Separate retrieval similarity from identity. Distinguish aliases, equivalent
acceptance criteria, shared topics, ALL/ANY composition, part relations,
subclasses, and instances. Check homonyms and both directions of any proposed
merge; overlap or a shared parent does not establish transitive equivalence.
For example, retrieving, storing, and learning skills may remain separate
capabilities even when they share a topic.

Separate a source record from the category or individual it describes. A catalog
record is not automatically a domain class. Keep vocabulary properties distinct
from classes and from the instances whose relationships they describe.
Check every relation against its
declared endpoint types and direction; reify a source relation when it cannot
faithfully use a domain edge. Check each attribute's subject, predicate and
object as well: an existing target ID or a shared paragraph does not establish
that it is the object described by that particular assertion.

Reuse an existing concept when its definition and acceptance scope really fit.
Keep a useful sourced definition on the defined node when its qualifications
permit that representation. If a definition needs a separate scoped Claim,
connect it to its subject with a declared relation so graph queries can recover
the definition. A generic placeholder plus an unconnected descriptive claim does
not satisfy a competency question that needs a definition by persistent node ID.
Retain distinctions needed by queries, voters, required cases, or partial product
support. Preserve original selections through explicit source-to-concept maps;
do not transfer approval to unrelated children or count a composite and its
components twice without an explicit scoring policy.

Compare candidate representations by preserved answers, source coverage,
exceptions, complexity, and review effort. State when reduction is a local
heuristic; do not claim a formal MDL optimum or globally minimal ontology.
The helper only removes exact duplicate assertions and explicitly permitted
transitive materialization, retaining audit history. It does not merge nodes or
simplify definitions. `skos:broader` is not transitive by default. Verify each
proposed removal against the declared competency obligations, then measure the
resulting counts; an expected count or topology does not establish preservation.

## 4. Validate complete proposed states

```text
uv run --script <skill-dir>/scripts/semantic_model.py validate --model model.json --contract contract.json --report validation.json
uv run --script <skill-dir>/scripts/semantic_model.py stage --base model.json --addition addition.json --contract contract.json --candidate candidate.json --report staging.json
uv run --script <skill-dir>/scripts/semantic_model.py reduce --model model.json --contract contract.json --candidate reduced.json --report reduction.json
```

Validate the baseline, then the entire candidate, including interactions with
existing nodes. Do not overwrite inputs or existing candidates, silently weaken
rules, or repair source wording to obtain a pass. Follow the user's existing
authorization when applying a valid change; a request for validation alone does
not authorize integration. Routine checks do not require another approval.

Preserve actual bundled helper reports verbatim at their requested paths.
Keep manual interpretation and scratch helper experiments separately attributed;
do not substitute them for a requested bundled report. When the helper is an
authorized maintenance target, repair it within that scope and identify the
revised implementation when rerunning.

Keep `contract_status`, `semantic_status`, and `engine_status` distinct. Core exit
codes are 0 for conformity, 1 for data violations, and 2 for unsupported contracts,
malformed input, processor errors, or I/O errors. Core semantic review remains
`not_run` even when the JSON contract passes. A missing formal processor is not
a semantic pass. For RDF workflows, pin the ontology/imports, processor version,
and inference regime; report SHACL conformity and OWL reasoning separately.

Honor task-specific command constraints. When an exact invocation is requested,
run it unchanged and inspect its tool result. For every other helper invocation,
including first validation of newly authored inputs, capture the exit with
`subprocess.run(..., check=False)` or a shell conditional. Inspect its report
and branch on documented codes 0/1/2. Inspect actual
diagnostics before asserting an error code; different invalid states can fail
at different validation layers. Keep conformity and data findings distinct
from engine errors. Diagnose an engine error and repair owned inputs or
authorized processor code before rerunning; never report the failed check
as a completed semantic result.

## 5. Expose contradictions for a user decision

Normalize subject, predicate, value, polarity, context, version, time, and unit
without inventing missing facts. Absence is not negation; different values are
not contradictory unless the predicate is exclusive in comparable scopes.
Inspect free-text conditions, quantifiers, exceptions, and evidence as well as
the typed graph. A conflict may reveal a bad rule or representation.
For a source-bound graph or change review, follow
[semantic-review.md](references/semantic-review.md): establish assessability and
the required side before judging coverage, and inspect the actual modeled fields
and explanation records. A source quotation alone does not encode its guard.
Keep parameter ranges and conditions separate from measurement units. A broader
statement and a narrower special case do not by themselves contradict each other.

Create review cards showing both assertions, source passages and locators,
the applicable rule/version, uncertainty, and consequences for queries,
selections, and coverage. Distinguish confirmed conflicts, possible conflicts,
scope differences, and constraint conflicts. Read
[contradiction-review.md](references/contradiction-review.md).

```text
uv run --script <skill-dir>/scripts/review_conflicts.py scan --model model.json --contract contract.json --claims claims.json --report review.json --markdown review.md
uv run --script <skill-dir>/scripts/review_conflicts.py scan --model model.json --contract contract.json --addition addition.json --report addition-review.json
uv run --script <skill-dir>/scripts/review_conflicts.py decide --review review.json --decisions decisions.json --report decisions-report.json --markdown decisions-report.md
```

The addition is inspected in memory. These checks are bounded; they do not
claim exhaustive natural-language contradiction detection or OWL reasoning.
Offer concrete choices: prefer an assertion, separate scopes, correct wording,
request evidence, or defer; offer explicit rule revision when appropriate.
Do not resolve automatically by recency, confidence, or votes. A user-approved
precedence policy may be applied with its provenance. Bind decisions to the
review revision and conflict fingerprint. Recorded decisions remain pending
validation: apply an authorized candidate, preserve evidence, rerun checks, and
rescan before declaring the conflict resolved.

## 6. Compare ontologies by cases and residual gaps

Inspect candidate ontology classes, axioms, relations, identity rules, and
constraints for internal contradictions, not just disagreement with external
documents. Preserve ontology IRI, version, artifact hash, imports, and inference
configuration. Freeze a shared suite of cases, expected answers, methods,
required flags, and weights. Read
[ontology-coverage.md](references/ontology-coverage.md).

```text
uv run --script <skill-dir>/scripts/ontology_coverage.py --input coverage-input.json --report coverage.json --markdown coverage.md
uv run --script <skill-dir>/scripts/ontology_coverage.py --input coverage-input.json --previous previous-coverage.json --report coverage.json
```

This helper aggregates supplied evidence; it does not run queries or reasoners.
Report full passes over all applicable cases, the denominator, and every
residual failure, partial result, unknown, engine error, or conflicted result.
Nine passes and one unknown mean 90% covered and 10% unverified, not a proved
10% failure. Keep weighted coverage separate and expose required-case failures.
Keep SHACL and OWL statuses distinct. An adoption threshold is not permission
to ignore required cases or unresolved contradictions. Test a composition as
a new candidate; do not add coverage percentages. Compare progress only for
the same frozen suite, and let the user decide which residual gaps to accept.

## 7. Verify and deliver

Exercise meaningful positive and invalid cases for important rules. First
collect each probe's actual exit, status, and diagnostics without speculative
assertions. Check rejection and its direct evidence; assert a particular code
only when its validation layer was reached. During skill maintenance, run the
bundled helper tests; normal runtime tasks can create their own small inputs
without reading acceptance fixtures. Deliver the
canonical model, contract, source map, changes and competency results, together
with actionable errors, conflict choices, coverage denominators, and remaining
uncertainty as the task requires. Derive only useful views and avoid a broad
benchmark for every small update. Use the user's requested delivery language.

Review the interpretation itself against both source states and actual graph
content. A source-reference-only relationship update is not a new assertion;
an incorrect inherited edge is different from a false claim about what changed.
Verify each claimed added or removed qualifier in the passages, including
unchanged context, before reporting a semantic difference.

## 8. Review repository and pull-request changes reproducibly

For two states of the same document, read
[document-versions.md](references/document-versions.md). Track claims and their
conditions across moves and rewrites before computing the graph delta.
For a typed before/after table with exact line citations, use the reference's
deterministic compiler to calculate change classes and copy evidence.
For two reviewed typed inventories, use the reference's snapshot mode to
compute the delta. When a class keeps its identity across different source
labels, supply the reviewed correspondence and bind it to both source files
and the snapshot pair.

When the question concerns explicit JSON data values and structure, optionally
use [native-json-values.md](references/native-json-values.md) to project them
deterministically before domain interpretation. Its exact value policy is
declared; a JSON value graph does not interpret JSON Schema, JSON-LD contexts,
statement rank, or domain taxonomy. Keep that source projection separate from
the curated concepts and their semantic review.

For standards, amendments, quoted OLD/NEW material, or transformed source
formats, read [source-roles.md](references/source-roles.md) before assigning
current meaning or choosing evidence.

For Wikipedia or other wiki revision comparisons, also read
[wiki-revisions.md](references/wiki-revisions.md) for pinned wikitext, template
boundaries, temporal claims and editorial controls.

For a file-based knowledge repository, read
[repository-review.md](references/repository-review.md). Pin the base and head
commit IDs and explicit source files, retain an accepted concept registry with
persistent IDs, and build snapshots with `repository_graph.py`. Use
`repository_sources.py` to inventory exact passages, verify source spans, and
plan bounded extraction work. These helpers run locally without a model or network.
For real Markdown, generate a passage catalog and let the model select its
short references; compile exact citations mechanically instead of asking the
model to reproduce Markdown formatting or count source lines.
Generate a passage change map to focus extraction on edits and their unchanged
context. Define predicate meanings explicitly, preserve changed rule conditions
and exceptions, and check graph coverage separately from a prose change summary.

Compare the entire candidate against the baseline contract. Report a proposed
contract change separately, including what still fails under the original
rules. Derive the offline graph and evidence interface with
`render_repository_review.py`; exported choices are revision-bound drafts,
not applied changes or resolved conflicts.
For source-backed semantic concerns beyond the declared structural rules, use
the optional `import_semantic_review.py` workflow in
[repository-review.md](references/repository-review.md#import-source-backed-semantic-review-proposals).
It checks exact citations and field anchors, then exposes attributed, unvalidated
review proposals in the same interface while preserving both compared models.

Use an explicitly selected inexpensive model only for new semantic proposals
or ambiguous evidence. Preserve exact instructions and responses for replay;
never regenerate accepted concepts or merge identities just to rebuild a graph.
Claim deterministic bytes only for the versioned builder, pinned inputs,
accepted registry, and contract. Structural validity, source fidelity, model
proposal quality, and human semantic acceptance are separate results.

Prefer a reviewed deterministic parser for explicit structured assertions when
the source grammar supports it. Version the projection policy, preserve exact
raw evidence, and expose unparsed fields and unresolved targets. A bounded
projection is not a complete ontology interpretation or an implicit reasoner.
