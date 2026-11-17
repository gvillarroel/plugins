# Question-oriented index contract

## Input

Use UTF-8 JSON with exactly these root fields. All arrays are required;
`passages` must be nonempty. All fields shown for each item are required. Empty
aliases, parents, concepts, predicates, annotations, relations, or families are
valid. IDs must be unique within each collection and references must resolve.

```json
{
  "schema_version": 1,
  "passages": [
    {"id": "p-gate", "text": "Orion forwards requests to Vega.", "source": "architecture.md", "locator": "L10"},
    {"id": "p-vega", "text": "Vega processes the requests received from Orion.", "source": "architecture.md", "locator": "L12"}
  ],
  "concepts": [
    {"id": "service", "label": "service", "aliases": [], "parents": []},
    {"id": "orion", "label": "Orion", "aliases": ["entry gateway"], "parents": ["service"]},
    {"id": "vega", "label": "Vega", "aliases": ["request processor"], "parents": ["service"]}
  ],
  "predicates": [
    {"id": "forwards-to", "label": "forwards to", "aliases": ["sends requests to"]}
  ],
  "annotations": [
    {"passage_id": "p-gate", "concept_ids": ["orion", "vega"]},
    {"passage_id": "p-vega", "concept_ids": ["vega"]}
  ],
  "relations": [
    {"id": "orion-to-vega", "subject": "orion", "predicate": "forwards-to", "object": "vega", "evidence": ["p-gate", "p-vega"]}
  ],
  "families": [
    {"id": "definitions", "kind": "lookup", "cues": ["what is"], "examples": ["What is an entry service?"]},
    {"id": "members", "kind": "taxonomy", "cues": ["which services", "types of"], "examples": []},
    {"id": "routing", "kind": "relation", "cues": ["forwards to", "sends requests to"], "examples": []}
  ]
}
```

This is synthetic explanatory data. Aliases must come from reviewed vocabulary
in a real task. Record the review origin in the accompanying task notes.

`source` and `locator` are opaque citation metadata, never filesystem paths to
execute or open automatically. `text` is the retained passage. The tool checks
that metadata is nonempty; the caller must check that it locates the actual
source wording. A digest detects accidental input drift, not malicious edits
or the truth of supplied annotations.

Use narrow, stable passage boundaries. Include a shared definition or antecedent
in a relation's evidence when the requested meaning requires it. Keep parent
edges directed **child → parent**. Multiple parents are permitted; cycles and
dangling IDs fail. `predicate` is a reviewed relation ID, not free-form text.

## Runtime behavior

- `build INPUT OUTPUT` validates input and writes a deterministic JSON envelope
  containing `schema_version`, `input`, and canonical `input_sha256`. The
  destination must not exist. No source fetch, embedding download, or network
  service is involved.
- `validate INDEX` checks the closed schema, digest, and references again.
- `search INDEX --query TEXT --mode lexical|guided --top-k N` returns JSON.
  `--output PATH` saves it. `--family ID` selects one declared family explicitly.
- Lexical mode ranks raw passage text by BM25. Guided mode also indexes reviewed
  concept labels, aliases and ancestor labels and fuses the two rankings.
  Ancestor labels can increase sibling noise; they are not inherited facts.
- Auto routing uses cue phrase matches; the stable fallback is lookup. Examples
  are descriptive metadata only. Ambiguous aliases can match more than one
  concept; inspect the result and use a scoped concept registry.
- Taxonomy routing uses reviewed parent reachability to favor matching
  descendants. A broad term need not correspond to a supported domain answer.
- Relation routing matches declared predicate and endpoint mentions and packs
  the relation's declared evidence within the same passage cutoff. It does not
  parse argument roles, polarity, conditions, inverse relations, or time from
  natural language. Do not treat a matching bundle as the answer to those
  distinctions. Inspect the typed subject/object and all original qualifiers.
- The search contract includes `hits`, `bundles`, `warnings`, the input digest,
  and `authority: "retrieval-candidates-only"`. Hit citations retain the exact
  input `source` and `locator`. `complete` is budget coverage, not entailment.

The helper is an inspectable small-corpus reference implementation. It
recomputes statistics at query time and has no latency or scale guarantee.
For a large deployment preserve the schema and evidence contracts while
measuring an actual fielded index implementation separately.
