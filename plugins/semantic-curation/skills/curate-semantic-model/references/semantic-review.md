# Source-bound review of a proposed graph

Review the actual source, complete proposed states and stated question. Structural
conformity, a valid citation and a plausible explanation are separate checks.
An inexpensive reviewer is another fallible proposal source; its conclusions
need decisive evidence and must not replace processor reports or the baseline.

## Contents

- [Make each conclusion inspectable](#make-each-conclusion-inspectable)
- [Inspect assertions, not only their citations](#inspect-assertions-not-only-their-citations)
- [Compare states and explanations separately](#compare-states-and-explanations-separately)

## Make each conclusion inspectable

Bind the review to the exact source inventories, model and contract hashes,
extraction policy and reviewer configuration. Keep one case's relevant context
together; avoid carrying unrelated cases or earlier reviewer conclusions into a
fresh independent pass. Use the caller's configured inexpensive model and budget.

For each preservation obligation or expected change, record its ID, declared
side, source reference and the actual node/relation fields that represent it.
Check the required side: a correct head assertion does not establish a base
obligation, and a head-only obligation does not require the same base assertion.
Distinguish requirements about graph content, explanation cards, retained source
evidence and interpretation context. Context need not become a graph node unless
the task requires that representation.

Decide whether the selected source establishes the complete criterion before
scoring its representation:

- **Found:** the source establishes the criterion and the required representation
  retains its material meaning and qualifications.
- **Partial:** the source establishes the criterion, but the representation retains
  only part of it. Identify the omitted field, condition or relation.
- **Missed:** the source establishes the criterion, but the required assertion is
  absent from the representation.
- **Unassessable:** selected evidence does not establish a required part of the
  criterion. Related facts do not turn an unavailable assertion into a partial
  extraction success or an extraction failure.
- **Ambiguous:** supplied evidence leaves a material scope, identity or
  interpretation unresolved. State the competing readings rather than choosing
  an unsupported one.

Adapt these names to the requested output schema, preserving the distinctions.
Keep an invalid graph inspectable as a draft; do not call it accepted or
source-faithful because some individual criteria are represented.

## Inspect assertions, not only their citations

A source paragraph containing a condition does not put that condition into a
node. Inspect definitions, typed attributes, relation endpoints and their scope.
When a definition is reified, verify that its subject is explicitly linked and
that the required graph question can follow that link. A nonempty generic
definition and a disconnected claim containing the real meaning can pass string
validation while failing definition retrieval. Record that query/coverage gap
separately from a false or unsupported assertion; do not reject a supported
generic description solely because it is less informative.
If a rule says “when authenticated is true, a read is allowed,” a node saying
only “reads are allowed” has lost its guard. Keep distinct conditional branches
separate when their outcomes differ, or use an explicit shared condition model
whose links let the required questions recover each branch. A generic description
of an exclusive boundary is not automatically a complete encoding of all
validation branches that use that boundary.

Bind each range and modifier to its own clause. If one sentence describes a
family for widths `k >= 2` and another states a result at fixed width `2`, the
range does not make the fixed-width result universal over that family. Separate
independent assertions from a shared paragraph when combining them would move a
guard or quantifier to the wrong subject.

An opaque object attribute can preserve values without validating their meaning.
Inspect the subject, predicate and object, numeric datatype, units, modal force,
negation, quantifiers, time, attribution and branch guards. Use the declared
source role for quoted historical wording and replacement wording; retain
unresolved antecedents instead of assigning a document a defining role by topic.

Preserve field membership as well as values. An absent member, explicit JSON
null, empty object, empty array, false and an unavailable value are different
states. Do not fill a removed record's unavailable fields with null unless the
representation declares that sentinel convention separately from source values.
Prefer an explicit status envelope such as `{"status":"absent"}` for absence;
use `{"status":"present","value":null}` when the source supplies null. Choose
and validate the envelope before extraction; it is a modeling policy, not an
assertion that the source contained those wrapper keys.

## Compare states and explanations separately

Compare before and after definitions, attributes and relations directly. A graph
can represent a changed type or dependency through those states without another
node saying “this changed since the previous version.” Put comparison history in
review explanations rather than rewriting unchanged concept definitions.
Separate inherited baseline errors from newly introduced changes.

Inspect the actual explanation records, including their summaries, before/after
references and uncertainty. Do not infer that an explanation is missing solely
because an optional mechanical coverage field or generated card-ID array is
empty. The requested card schema determines which records count as explanations.
Conversely, a correct explanation does not repair missing graph content.

Report unsupported assertions with the exact proposed field and source mismatch.
Flag an assertion the candidate actually makes; do not report a hypothetical
future interpretation as an unsupported claim when the candidate leaves it
unresolved. Distinguish statements about a source's wording from assertions
about the domain described by that source.
Keep source-scope gaps, representational ambiguity and false semantic changes
distinct. Preserve original reviewer outputs when correcting a mistaken judgment;
record the evidence and reason for adjudication separately. These checks support
review decisions, not automatic ontology adoption or formal entailment claims.
