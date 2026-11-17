# Source roles and transformed evidence

Apply this guide when a model compares standards, amendments, quoted revisions, examples, or extracted source formats. Keep each assertion tied to the role and version of the evidence that actually supports it.

## Identify what each passage is doing

Before extracting meaning, inspect headings, labels, document status, and nearby instructions. Distinguish operative normative text from amendment instructions, quoted `OLD` text, proposed `NEW` text, examples, historical statements, and claims about implementations. A quote's presence in a document does not make it an operative rule. Do not assume that every passage labeled `OLD` is obsolete: confirm whether the document adopts, rejects, replaces, or merely discusses it.

An amendment may change only named clauses. Verify which underlying clauses remain in force using the amendment and current base text. Cite verified unchanged normative context when it is needed to support a current assertion. If the selected sources do not establish that context, mark it unestablished or omit the extra current-state claim. A citation to a base-only passage cannot, by itself, prove that the same rule is operative on the amended side. Citation existence is not support: check that the cited passage supports the exact claim, version, condition, and modality assigned to it.

Resolve phrases such as “this document” inside their actual quotation and document context. A reference list naming a standard does not establish that it defines, updates or adopts a rule. Audit every proposed current assertion, including inherited qualifications, against operative evidence on that side; do not carry a qualification forward solely because it appears in a quoted old paragraph. Keep an unestablished continuation distinct from a repeal.

Keep document edition and amendment lineage as provenance. Put semantic version, scope, condition, and modality on the assertion they qualify; do not turn an edition change into a changed domain fact by itself.

## Preserve raw and transformed sources

Keep fetched source bytes unchanged, with a digest, media type, and immutable version locator where available. Store derived excerpts separately and record their exact line ranges or structured pointers, transformation, and source-to-output mapping. For JSON, reject duplicate object keys and non-finite numbers before selecting values; record the JSON Pointer and verify that a serialization-only control parses back to the same typed value. For HTML or other formats, state whether extraction decodes entities, strips markup, normalizes whitespace, or changes line endings. A generated formatting variant is a control, not an upstream revision.

## Preserve native vocabulary assertions

When the source already declares a schema or vocabulary, consider a pinned local
parser before asking a model to recreate its explicit assertions. Keep the native
term IDs, declared types, literal datatypes and languages, predicate direction,
view or version qualifiers, and source mappings. Disable implicit import or
remote-context retrieval. Distinguish a faithful source projection from an
adopted ontology, inferred consequences, and free-text interpretation; a limited
projection must state its selection and demonstrate a round trip of the selected
assertions. Reject unsupported identity structures rather than assigning them
apparently persistent IDs.

Keep classes, properties, source records and their described instances distinct.
For example, `p owl:inverseOf q` relates two properties; references to the classes
whose instances might use those properties do not encode that source assertion.
Likewise, a vocabulary's domain/range annotation is not automatically an input
requirement or evidence of deployed validator behavior. If the task concerns
source-declared relationships, represent their actual subjects and objects.
Retain literal definitions and usage conditions for separate semantic review.
Changing only the publication edition does not require new IDs or new semantic
scope for an otherwise preserved assertion.

## Keep opaque fields honest

A core object-type check does not validate arbitrary nested `scope` fields or resolve local IDs stored inside attributes. Declare and run the reference checks those fields need, or model the connection as a typed edge with evidence. Store a non-calendar duration as plain `time_text` when its unit or calendar interpretation is unspecified; do not invent a date or day count.


## Bind a portable model to its source state

An inventory preserves its revision and raw/normalized document hashes. Legacy
`assemble` resolves exact passages but does not automatically copy the complete
inventory identity into the model. When review decisions must remain bound to a
particular source state, use the opt-in binder after assembly and before snapshot
comparison (replace `SKILL` with this bundle's directory):

```text
uv run --script SKILL/scripts/repository_sources.py bind --inventory head-inventory.json --model head-model.json --origin origin.json --output bound-head-model.json
```

Omit `--origin` when no additional acquisition descriptor is needed. Provide a
compact JSON object with stable source locators/versions, raw content digests and
transformation mappings; omit credentials and unrelated capture data. Keep raw
captures outside the model. The binder verifies the selected source spans against
the inventory, preserves graph records, and adds `metadata.repository_sources`.
It rejects a conflicting existing binding; it does not replace an accepted
model's provenance silently. Repeat the same binding to check idempotence.

Full model and review fingerprints then distinguish source states even when the
content graph is identical. The binding and caller origin are marked
`not_authenticated`: local integrity checks do not establish remote authenticity,
source authority, semantic support or domain truth. Validate acquisition
separately and preserve the exact inventory/origin inputs for replay.
