---
name: rapid-image-prototype
description: Rapidly prototype image-generation outputs from a target prompt plus current prototype images. Use when Codex needs to inspect one or more existing image prototypes, infer what the user was trying to achieve, generate five improved image variants, and vary the execution by improving composition, clarity, style, production quality, or replacing weak components.
---

# Rapid Image Prototype

## Overview

Use this skill to turn a user intent prompt and current prototype images into five stronger image-generation candidates. The goal is fast visual learning: each output must test a different improvement hypothesis, not just random style variation.

## Inputs

Accept any combination of:

- Target prompt or brief: what the user wanted the image to communicate.
- Current prototypes: attached images, local image paths, generated images from the thread, screenshots, mockups, or URLs.
- Constraints: aspect ratio, product/use case, brand/store style, forbidden elements, required text, garment/product color, target audience, or output folder.

If the target prompt is missing, infer it from the user's request and the prototype images. If the prototype images are missing, proceed from the prompt but say that the iteration is prompt-only.

## Workflow

1. Inspect the current prototypes.
   - Use visual inspection for local or attached images before writing prompts.
   - Identify the intended idea, what is already working, and the two or three weakest execution points.
   - Watch for text errors, clutter, weak hierarchy, unreadable small details, odd anatomy, generic stock composition, mismatched style, and components that fight the main idea.

2. Define five improvement hypotheses.
   - Variant 1: preserve the concept and improve execution quality.
   - Variant 2: improve composition, hierarchy, crop, or focal point.
   - Variant 3: replace the weakest component with a stronger visual metaphor.
   - Variant 4: push the style or scenario harder while keeping the idea legible.
   - Variant 5: simplify toward a production-ready, readable version.

3. Write five generation prompts.
   - Each prompt must include the target intent, key preserved elements, the specific change being tested, composition/camera/framing, style, quality bar, and negative constraints.
   - Do not ask for unverifiable claims, real-person impersonation, hate symbols, confidential data, or tiny text that must be read unless the use case explicitly requires text and the image model is suitable.
   - When using current prototypes as references, describe what to inherit and what to change; do not blindly copy defects from the prototype.

4. Generate five images.
   - Use the available image generation/editing tool for bitmap outputs.
   - Generate exactly five candidate images unless the user requested a different count.
   - If the tool can use image references, include the selected prototype references. If it cannot, base the prompt on the visual inspection summary.
   - Keep outputs comparable: same aspect ratio and same broad target use case unless one variant intentionally tests a different crop.

5. Save and present results.
   - Save generated files when the environment exposes file paths. Use names like `rapid-prototype-01-preserve-improve.png`.
   - Build or request a contact sheet when practical so the five options can be compared at once.
   - Provide a compact scorecard: one sentence per variant explaining what changed and why it may be better.
   - Recommend the strongest one or two next iterations, with concrete edits.

## Quality Gate

Before finishing:

- Confirm there are five generated candidates or clearly state why generation was blocked.
- Confirm each candidate tests a distinct hypothesis.
- Inspect the outputs when possible; do not judge only from prompts.
- Reject or mark candidates with severe unreadable text, broken anatomy, incoherent objects, hidden product, or visual clutter that defeats the concept.
- For store-facing generated images in this workspace, follow the repository AI-generated image labeling rule when applicable.

## Output Format

Return:

- A short summary of the interpreted target.
- The five candidate images or links/paths to them.
- A five-row scorecard with `variant`, `hypothesis`, `what changed`, and `risk`.
- A recommendation for the next pass.
