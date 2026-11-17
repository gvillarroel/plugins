---
name: index-knowledge-questions
description: Builds and compares question-oriented knowledge indexes using reviewed concept aliases, taxonomy paths, typed relations, and exact passage bindings. Use when packaging a knowledge skill or improving retrieval for recurring question families; keep source facts and evaluation answers separate from discovery metadata.
---

# Index Knowledge Questions

Build a portable, non-authoritative retrieval projection around the questions
the knowledge must support. Use the bundled standard-library helper for a
bounded corpus; preserve the existing knowledge builder and raw passages.

## Shape the index from the task

1. Collect representative **development** questions or the user's intended
   question families. Keep independent evaluation questions and their answers
   outside the indexing inputs. If no question log exists, propose families
   from the stated task and sources and mark them provisional.
2. For each family, describe the intent, expected answer shape, concepts,
   relation direction, qualifiers, and required evidence. Distinguish a lookup,
   taxonomy listing, and relation question. A question requiring a concept is
   not evidence that the concept or answer exists.
3. Read the relevant source passages. Author only the concepts, aliases,
   child-to-parent edges, passage annotations, predicates, and relation evidence
   justified by those passages or an explicitly supplied reviewed vocabulary.
   Preserve time, version, modality, exceptions, negation, and source authority.
   Split ambiguous terms and scoped identities instead of merging them by label.
4. Read [the input contract](references/input-contract.md). Write the closed
   input JSON in the user's workspace. Retain exact source/locator strings and
   source wording. Require every typed relation to have its actual passage IDs.
5. Build, validate, and search using the commands below. Keep lexical BM25 as a
   comparator. Review returned passages before making a factual answer.
6. Follow [evaluation and integration](references/evaluation-and-integration.md)
   to compare complete evidence coverage, diagnose regressions, or connect an
   existing knowledge package. Report annotation cost and corpus scope alongside
   retrieval gains. Keep this skill's directory read-only.

## Run

Resolve `scripts/question_index.py` against the loaded skill directory; run
from the user's workspace. Outputs belong outside the skill. Python 3.11+ and
the standard library suffice; `uv run --script` also works.

```sh
python -B SKILL_ROOT/scripts/question_index.py build input.json question-index.json
python -B SKILL_ROOT/scripts/question_index.py validate question-index.json
python -B SKILL_ROOT/scripts/question_index.py search question-index.json --query "Which systems depend on the gateway?" --mode lexical --top-k 3 --output lexical.json
python -B SKILL_ROOT/scripts/question_index.py search question-index.json --query "Which systems depend on the gateway?" --mode guided --top-k 3 --output guided.json
```

`SKILL_ROOT` is a placeholder for this loaded skill's actual path. Build into a
new path. A second build from unchanged input must produce identical bytes.
Use `--family ID` when the question plan supplies an explicit family; otherwise
the helper routes by reviewed cue phrases. This is a transparent baseline
router, not a language-understanding model. Family examples document workload;
the helper does not learn from or search them.

## Interpret the result

Guided mode fuses raw-text BM25 with alias/ancestor-enriched BM25, uses reviewed
descendants for taxonomy questions, and prioritizes declared relation evidence
bundles when predicate and concept mentions match. Read the schema reference
for exact behavior and limitations. A complete bundle means all its declared
passages fit in the returned budget; it does not certify semantic support.

Search scores, taxonomy paths, and relation matches are discovery signals.
The helper verifies its serialized input digest and structural references; it
does not read raw sources, prove source entailment, execute OWL reasoning,
resolve conflicting versions, or determine that an unanswered query is false.
Unsupported questions may still return candidates. Inspect evidence and abstain
when it does not support the requested claim.
