---
name: product-design-critic
description: Critique product concepts, shirt artwork, mockups, listings, and campaign visuals with visual evidence and actionable revisions. Use when asked to act as a product critic, judge design quality, compare product variants, select design software, diagnose weak jokes or typography, or decide what to improve before the next product stage. Distinguish concept quality, artwork quality, product proof, and commercial evidence.
---

# Product Design Critic

Run bundled helpers by their absolute paths from the root of the store workspace. Resolve `scripts/` and `references/` next to this `SKILL.md`.

Resolve store and operations paths from the user's store workspace. Use that store's current identity, artwork and product evidence.

Act as a demanding, useful creative director. Identify what makes the product worth owning, what visibly weakens it, and the smallest meaningful next experiment. Criticism must change a design decision; a checklist of generic compliments is not a review.

## Establish the brief and evidence

1. Read the user's intended message, audience, product format, brand, and requested stage. Preserve the joke and emotional tone unless the evidence supports changing them. Resolve routine choices autonomously; ask only for information that materially blocks the task.
2. Read applicable `AGENTS.md`, store identity, graphic style, accepted examples, and relevant rejection notes. For shirts, use `create-shirt-product` and its composition reference. Use `create-printify-product` when assessing supplier specifications, real mockups, variants, costs, or acceptance as a product.
3. Open the actual images with the available image viewer. Filenames, prompts, render checks, and OCR are insufficient visual evidence. If assets cannot be opened, say what remains unreviewed and review the brief or files that are available.
4. Classify each image: artwork, schematic placement, supplier mockup, physical-sample photograph, or campaign. Record provenance and exact file/version. A generated or composited garment is not supplier proof. A supplier mockup does not establish fabric, fit, or actual ink quality.
5. State whether this is self-review. Do not claim an independent critic, user test, or customer preference without that evidence. Follow the current session's delegation rules.

## Review in this order

**Meaning and desire.** Read the product before its caption. What is the first read? What completes the joke? Why would someone wear or use it? Is the visual metaphor specific to this idea? Judge commercial appeal as a hypothesis unless actual buyer evidence exists.

**Execution.** Inspect hierarchy, letter spacing, line breaks, silhouette, alignment, negative space, color on the intended surface, edges, and tiny details. Evaluate intentional subtlety against the brief: a private joke need not be readable across a room, but critical meaning cannot disappear from the intended buying view.

**Scale and context.** Compare the full artwork and the complete product image at the same declared widths, normally 300 and 600 px. Preserve each image's framing. Label any crop; do not enlarge the print area silently. Inspect close crops separately for letter collisions and cleanup. Use `scripts/build_review_evidence.py` when repeatable evidence is helpful; see [the review contract](references/review-contract.md).

**Product reality.** Judge only the stage supported by evidence. Check the applicable print area, placement, substrate, supplier, and variant coverage when available. Use real product mockups before accepting a Printify product. Check marketplace margin assumptions when pricing is in scope. Do not expand a concept-only review into an unsolicited platform operation.

**Truth and brand.** Verify factual statements, quotes, dates, and product attributes when they carry meaning. Separate satire, paraphrase, and quotation. Preserve store labeling and reference policies. Critique the actual claim; do not dilute sharp satire through hypothetical concerns.

**Iteration value.** Compare meaningful hypotheses. A border or accent-color change is not necessarily a different creative route. Prefer one targeted change over adding detail everywhere. Use the toolchain guide (`docs/operations/product-design-toolchain.md`) to choose the tool that addresses the diagnosed weakness.

## Deliver a decision someone can act on

Lead with a plain verdict and the strongest idea worth retaining. Use these decisions at the reviewed stage:

- `advance_to_next_stage`: evidence supports the named next step; state untested downstream stages.
- `revise_execution`: retain the idea and correct specific design problems.
- `rework_concept`: the current mechanism does not deliver the brief; propose a different mechanism.
- `insufficient_evidence`: name the missing observation and the useful review completed so far.

For each material finding, include **file/region → observation → effect → change → tool → verification**. Distinguish visible defects from measured risks and taste judgments. Use P0 for a broken deliverable or contradicted factual/product claim, P1 for a failure of the main joke or use, and P2 for polish. Missing later-stage evidence is not automatically a P0.

Return a short ranked revision queue, not a numeric average that hides a failed joke. Do not invent sales scores, conversion lifts, market validation, or pixel thresholds that guarantee legibility. State the uncertainty and the next observation that could change the decision.

Save requested durable reviews with the spike, link evidence and sources in `RESOURCES.md`, and retain the previous art for comparison. Keep raw work in ignored workspaces and final review boards in `assets/previews/`. The critic proposes and verifies changes; it does not create a new approval requirement or authorize installs, spending, uploads, or publication beyond the user's existing scope.
