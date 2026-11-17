---
description: Compare filtered alternatives with the real Open Ontologies engine
argument-hint: <proposal-id> [column-name]
---
Read review_proposal for $ARGUMENTS and call open_ontologies_status, then
compare_taxonomy_with_open_ontologies for the saved proposal and, when specified,
the exact observed column name. Use the current digest. Explain the best three
eligible concepts, their definitions, engine evidence and scoring-signal coverage,
ambiguity, filtering reasons, and the installed vocabulary's scope and version.
Call the numeric value alignment support, never a probability of correctness.
If the verified engine is unavailable, report that clearly. The separate local
suggest_taxonomy(provider="local") comparison must be labeled as local; never
present it as an Open Ontologies result or silently fall back.

Keep the field unmapped when the installed vocabulary has no reliable meaning.
Do not infer revenue from price/cost alone, invent units, or treat identifiers as
proven joins. External ontology terms are references until their scheme has been
registered and validated; never insert an arbitrary external URI into concepts.
Open the review panel so a person can stage a choice in Describe and save a new
draft. Lookup does not edit, approve, or publish anything. Respond in English.
