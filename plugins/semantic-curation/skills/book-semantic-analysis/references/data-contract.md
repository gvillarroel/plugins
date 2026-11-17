# Corpus and analysis contracts

Use UTF-8 JSON. Both documents use `schemaVersion: 1`. Run the bundled helper's `--help` for CLI options rather than reading its implementation during normal use.

## Prepared corpus

`prepare` accepts TXT or Markdown and emits:

```text
corpus/
  corpus.json
  index.md
  readings/ch01-01.md
  ...
```

The corpus contains `book` with `title`, `author`, `sourceUrl`, and `sourceSha256`; `chapters` with stable `id`, `title`, `passageIds`, and `readingFiles`; and `passages` with `id`, `chapterId`, and normalized `text`. Passage IDs have the form `ch01-p0001`. Extra raw offsets, when supplied, refer to Unicode code points in the original decoded text, not byte positions or pages.

Read the generated index and the actual chapter chunks. Inspect chapter segmentation; headings and publisher boilerplate vary. Do not assume any parser can identify every edition's structure correctly. Keep the original source file for provenance.

## Analysis document

The following shape illustrates the schema, not a ready-made analysis. Replace placeholder values with actual source-bound content.

```json
{
  "schemaVersion": 1,
  "book": {"title": "Supplied title", "author": "Author", "sourceSha256": "64-character source SHA-256"},
  "scope": {"kind": "excerpt", "reviewedChapterIds": ["ch01"], "limitations": ["Only the supplied chapter was reviewed."]},
  "themes": [{"id": "theme-a", "label": "A concise theme", "summary": "Its relevance to the user's question.", "claimIds": ["claim-a"]}],
  "claims": [{
    "id": "claim-a", "themeId": "theme-a", "label": "A faithful compact label", "text": "A source-bound proposition.",
    "stance": "interpretation", "confidence": "plausible",
    "evidence": [{"passageId": "ch01-p0001", "quote": "An exact substring of the cited paragraph", "role": "supports", "rationale": "How this passage supports the proposition."}],
    "alternatives": ["A credible competing explanation."], "limits": "Where the inference stops."
  }],
  "relations": []
}
```

Required enumerations:

| Field | Values |
| --- | --- |
| `scope.kind` | `whole-book`, `excerpt` |
| `claims[].stance` | `textual-observation`, `interpretation` |
| `claims[].confidence` | `strong`, `plausible`, `tentative` |
| `evidence[].role` | `supports`, `complicates` |
| `relations[].type` | `supports`, `contrasts`, `develops`, `complicates` |

Each relation requires `id`, `fromClaimId`, `toClaimId`, `type`, `rationale`, and `evidence` in the same passage/quote/role/rationale shape. Do not create relations merely to fill the array. Claim and theme membership must agree in both directions. Every interpretation needs an alternative; every claim needs supporting evidence. Review and quote only chapters included in `reviewedChapterIds`.

`claims[].label` is an optional nonempty string for graph display. Prefer a concise two-to-eight-word phrase that preserves the claim's meaning and qualification; keep its full proposition in `text`. The label is an editorial summary, not a quotation or an additional finding. Old analyses without labels remain valid and require a readable full-text fallback, rather than indistinguishable truncated prefixes.

Read relation direction consistently:

| Type | Meaning of source → target | Display label |
| --- | --- | --- |
| `supports` | The source strengthens the target's stated proposition or warrant. | supports |
| `complicates` | The source qualifies or weakens the target's stated proposition or warrant. | complicates |
| `develops` | The target extends, refines or transforms the mechanism or position in the source. This is not automatically temporal or causal. | develops into |
| `contrasts` | The two claims are meaningfully juxtaposed. The source/target order is for navigation; the contrast itself is symmetric. | contrasts with |

Compare the rationale with the actual wording of both endpoint claims. Evidence that supports a target must not be typed `complicates` merely because it challenges a stronger position the target never asserted. An exact source quote and a coherent pair of claims do not establish that their edge type is correct. Keep a proposed relation interpretive, expose its qualifications, and omit it when the link remains unsupported. Theme membership is grouping metadata, never a semantic support or causal edge.

`whole-book` requires the reviewed chapter set to match every prepared chapter. `excerpt` must identify the reviewed subset and include an explicit scope limitation. Neither declaration proves that reading happened. If the supplied file itself is only an excerpt, use `excerpt` even when all supplied chapters were read.

## Exact quotation workflow

Use a small Python snippet to load `corpus.json`, select the identified passage, and assign a contiguous slice to `quote`. Preserve its normalized punctuation and whitespace. Do not type a remembered quotation and then silently alter the corpus to make it pass. Use multiple evidence entries when excerpts are separated. A quote may be exact and still fail to support the attached claim; inspect the rationale and context separately.

Run `check`, inspect its JSON `passed` field and findings, repair, then use `--fail-on-findings` for final acceptance. The checker validates existence and structure, with semantic quality explicitly unassessed. Keep its JSON result with the report.

The renderer takes the full corpus and checked analysis, includes full paragraphs cited by claims or relations, and retains chapter metadata. It safely embeds JSON as data rather than markup. Keep generated files outside the skill. The compact display corpus is for inspection and is not a substitute for the full reading corpus.
