# Native JSON values

`native_json_values.py` projects selected JSON documents into a typed
value graph. It records document structure and exact JSON values; it does not
interpret domain meaning, execute embedded content, infer an ontology, or
claim formal equivalence. It is an optional utility, selected when the question
requires JSON values and structure.

## Run

```text
uv run --script <skill-dir>/scripts/native_json_values.py project --root ./snapshot --files a.json b.json --model-output ./out/model.json --contract-output ./out/contract.json --report-output ./out/report.json
```

The selected input paths are explicit and relative to `--root`. The optional
origin file is parsed as JSON and bound as provenance metadata; it is not
interpreted as authority or truth. Outputs must be three distinct new paths,
must not alias inputs, and are never overwritten. Parent directories are
created when needed. A later output I/O error can leave earlier output files
present. Error results use engine status `error` and exit code 2; a completed
projection with source or contract validation errors exits 1; a valid completed
projection exits 0. No model or inference calls occur.

Add `--origin ./origin.json` when caller-supplied capture provenance is needed.
The origin file is limited to 1 MB.
Use each generated model with its generated contract in the bundled
`repository_graph.py compare` command. This comparison identifies declared JSON
value and structure changes; interpreting a schema keyword or a knowledge-base
statement still needs the appropriate source semantics and review.

## Declared value policy

The generated contract is `json-values-exact-decimal-v2`. Object member order
does not affect graph content. Array positions remain ordered and are encoded
as JSON Pointer indices. Pointers escape `~` as `~0` and `/` as `~1`. Missing
pointers have no value node and remain distinct from explicit `null`, empty
objects, empty arrays, and empty strings. Boolean, null, string, number,
object, and array values retain distinct kinds.

Numbers are parsed from their source tokens, without binary floating-point
conversion. Equality is exact base-ten numeric value: exponent spelling and
redundant trailing fractional zeroes normalize, and positive and negative
zero are equal. A literal stores a canonical signed coefficient multiplied by
a power of ten (for example `1.2500` becomes `125e-2`). This policy does not
infer measurement precision or units. Raw tokens remain available in the
selected source documents and their byte hashes, but are not graph literals.

Input files must be strict UTF-8 without a BOM, valid JSON, duplicate-free by
decoded object key, and contain only Unicode scalar values. Non-finite numbers,
unsupported or over-limit inputs fail closed. Limits are declared in the
report: 2 MB per file, 10 MB total, 100 files, 20,000 values per file, 100,000
values total, depth 100, and at most 8 significant exponent digits (leading
zeroes and an optional sign in the exponent do not count toward that bound).
Repeated selections of the same physical input file fail, including hard links
and filesystem case aliases; distinct case-different paths remain separate
when the filesystem treats them as separate files. The helper
inventory is created first and each file's bytes are then hashed and compared
with that inventory before parsing. This detects changed content but does not
provide an operating-system sandbox or eliminate filesystem races.

The model binds each inventoried source passage to the document artifact and
all values from that document. Because this evidence fan-out can grow roughly
with passages multiplied by values, the projection preflights a total budget
of 250,000 source-reference occurrences across node links, relation links,
and binding targets. A running serialized-model estimate stops construction
early; a final exact UTF-8 serialized-size check enforces a 32 MB model limit.
The report exposes these limits and observed counts. Repository-source validation and the bundled
graph helper produce deterministic model, contract, and graph digests. These
hashes and a deterministic self-comparison are reproducibility aids, not a
proof of semantic equivalence. The report explicitly sets semantic status to
`not_run` and domain semantics to `unassessed`.

## Standards context

The input syntax follows [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259),
but the projection's normalization policy is its own declared policy, not a
claim of RFC canonicalization. JSON-LD context processing and RDF datatype or
equivalence semantics are outside this utility's scope; see the
[JSON-LD 1.1 specification](https://www.w3.org/TR/json-ld11/) and
[RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/) for those separate
data models.
