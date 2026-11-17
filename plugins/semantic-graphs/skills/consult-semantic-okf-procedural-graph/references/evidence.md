# Exact Source Evidence

Search identifies candidates; only an original source record supports a claim.
Each record has a source-scoped `(source_id, record_id)` identity. Preserve
`concept_path`, `source_path`, `record_sha256`, `locator`, and `text_sha256`
from the read result. Never derive source identity from a title or preview.

`{"kind":"record"}` hashes the complete original record body. A character-range
locator uses half-open `[start,end)` Unicode code-point offsets and hashes that
exact substring in UTF-8. This includes newlines and Unicode characters.

The canonical task envelope has question_id, answer and evidence. A non-null
answer has summary and claims; every claim has statement and zero-based
evidence_indices. Every evidence row must support at least one claim.
The summary contains at most 450 words. Tasks may impose additional source
counts, key order or output restrictions; follow the actual task contract.

The separate `procedural-graphs-source-facts/1.0` validation contract additionally
requires an answer.facts object with task-declared keys, values and units.
It keeps the same evidence format. Only use this extension when requested by
the task; do not add facts to a canonical benchmark response.

The agent-visible checker verifies envelope and exact source provenance.
It cannot inspect hidden reference answers, facts or semantic rubrics.
A passing check does not prove that a citation entails the associated claim.
