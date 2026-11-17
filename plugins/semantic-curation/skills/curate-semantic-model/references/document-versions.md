# Compare two versions of one document

## Contents

- [Pin and align the source states](#pin-and-align-the-source-states)
- [Compare the meaning](#compare-the-meaning)
- [Compare two typed inventories](#compare-two-typed-inventories)
- [Produce a reproducible graph review when needed](#produce-a-reproducible-graph-review-when-needed)

Treat base and head as complete source states of the same document. Set the
scope of the review first: entire document, explicit sections, or questions
the comparison must answer. Report the scope actually covered.

## Pin and align the source states

Record revision IDs or raw-byte digests, original names, and stable locators.
Keep local captures read-only. For local UTF-8 files with different names, stage
byte-identical copies under the same logical name in separate directories,
then keep each original locator and digest in its origin metadata. Inventory
groups passages by logical path. Different logical paths produce file-level
removals and additions even for identical text.

```text
uv run --script SKILL/scripts/repository_sources.py inventory --root base --files document.md --output base-inventory.json
uv run --script SKILL/scripts/repository_sources.py inventory --root head --files document.md --output head-inventory.json
uv run --script SKILL/scripts/repository_sources.py changes --base-inventory base-inventory.json --head-inventory head-inventory.json --output passages.json
```

Replace `SKILL` with the bundle directory. Git revisions can use the same file
path with distinct `--ref` values. For wikis and extracted formats, also read
[wiki revisions](wiki-revisions.md) or [source roles](source-roles.md) as
appropriate. Preserve transformations and original locator mappings. When a
claim depends on a definition, exception, example, heading, or cross-reference,
inspect the necessary unchanged context on both sides.

## Compare the meaning

1. Identify the stable subject and the smallest assertion that answers the
   question. Keep identities across justified renames. Establish when a
   sentence has moved, is quoted as history, or now applies to a different
   case. Wording similarity alone cannot determine which rule it supports.
2. Compute each side independently in the same vocabulary. Capture actor,
   direction, object, modality, conditions, exceptions, time, and exact
   quantities where relevant. If the question asks about an outcome, apply the
   general rule and the relevant override to the same concrete scenario on
   each side. Keep absence, explicit denial, and unresolved meaning distinct.
3. Classify the change from the two values. Distinguish additions, removals,
   modifications, and retained claims, including editorial moves. Explain the
   scope of a widening, narrowing, or reassignment. For each side cite the
   shortest exact span or combination of spans that supports the value.
   For absent assertions, identify the searched scope and cite any surviving
   context needed to distinguish absence from denial.

For a bounded question, the resulting typed before/after table with two-sided
evidence can be the deliverable. When the requested output fits the schema
below, write the interpreted values and select the supporting line ranges.
Read both sources with explicit line numbers, for example with `nl -ba`.
Include an antecedent when a sentence names the subject only by a pronoun.
Choose one sufficient witness when multiple passages state the same rule.
For an override, select the clauses needed to establish the outcome.

```json
{"observations":[{"id":"renewal-period",
  "before":{"value":{"days":30},"lines":[[17,17]]},
  "after":{"value":{"days":45},"lines":[[21,21]]}}]}
```

```text
uv run --script SKILL/scripts/compare_document_versions.py --base policy-old.txt --head policy-new.txt --draft draft.json --output delta.json
```

The compiler adds `change` to each observation and replaces each state's
`lines` with exact evidence entries containing `start_line`, `end_line`, and
`quote`. Line ranges are inclusive and one-based within each file. Use
`value: null` for an absent assertion only when that is the agreed vocabulary.
The compiler compares JSON types and values and keeps arrays ordered. It
checks line ranges and copies text. It cannot decide whether a citation is
sufficient or a value accurately describes the document. Review those
choices before accepting the result.

## Compare two typed inventories

Use the snapshot mode when each revision already has its own reviewed classes,
subclasses, directed relations and typed constraints. Pass a JSON object with
`base` and `head` inventories and an optional `review` object.

```text
uv run --script SKILL/scripts/compare_document_versions.py --base old.txt --head new.txt --snapshot-pair pair.json --output delta.json
```

Each inventory has four arrays. Class rows contain `id`, `label` and
`evidence`. Subclass rows contain `child`, `parent` and `evidence`.
Relation rows contain `subject`, `predicate`, `object` and `evidence`.
Constraint rows add `kind` and `value` to the relation fields. Endpoints refer
to local class IDs. Use `required` or `forbidden` with true, or
`min-cardinality`, `max-cardinality` or `exact-cardinality` with a nonnegative
integer. Each evidence object has inclusive, one-based `start_line` and
`end_line` coordinates and a literal `quote` from the corresponding source.

The output selects added and removed rows by collection and zero-based index.
A unique replacement at the same directed constraint slot and within the same
kind family uses a `modified` selector with `before` and `after` indices.
The cardinality kinds form one family. Required and forbidden form another.
The compiler matches class and predicate names after NFC and whitespace
normalization while preserving case. Evidence movement and local ID changes
alone keep the structural delta `unchanged`. Align predicate aliases during
review before invoking it.

To retain different source labels for a reviewed equivalent class, pass
`--class-identity identities.json` with `--snapshot-pair`. The map contains
`pairs`, an array of one-to-one `{"base":"old-id","head":"new-id"}`
correspondences between local class IDs. It also contains
`source_sha256` with `base` and `head` digests, and `snapshot_pair_sha256`.
Use lowercase SHA-256 over each exact input file, including line endings.
Review the scoped equivalence before creating or refreshing the map.
The compiler rejects stale input digests, unknown IDs, collisions and pairs
that displace a literal-label match. It preserves original labels, evidence
and row selectors. Reusing a local ID alone establishes no correspondence.

Supply `review` with a caller-authored `reason` and arrays of exact `base`
and `head` citations when a reviewer declines to resolve the comparison.
The result has status `abstain` and empty operation arrays. The compiler
checks coordinates and quote text. The caller remains responsible for the
reason, the sufficiency of the citations, assertion meaning and coverage.

## Produce a reproducible graph review when needed

Use the catalog, assemble, check, and bind steps in
[repository review](repository-review.md). Start from an accepted base if one
exists. Use stable IDs and retain unchanged in-scope assertions. Represent a
qualified assertion as a typed claim with its qualifiers in graph fields and
links to its subject and object. Putting a qualifier only in relation review
metadata leaves it outside the content graph.

```text
uv run --script SKILL/scripts/repository_graph.py compare --base base-model.json --head head-model.json --contract contract.json --output review.json
uv run --script SKILL/scripts/render_repository_review.py --report review.json --output review.html
```

Keep passage edits, source changes, and reviewed semantic changes distinct.
An ordered passage alignment can report a relocation as a removal and an
addition. A wording change in a graph definition can change its fingerprint
while preserving its meaning. Reuse the accepted wording for equivalent
paraphrases when labels and exact wording are outside the comparison scope,
and refresh the evidence. Check unchanged controls and report uncovered or
ambiguous assertions separately. Replaying saved source-bound models and a
pinned contract gives deterministic results under the same helper version.
