---
name: design-store-graphics
description: Create or improve product artwork for IA Referencias using reference-led composition, typography, image integration, and restrained texture. Use for new graphic concepts, editorial merch, posters, collage, or revisions with weak hierarchy or visual coherence. Applies practical lessons from Dan George Hill while preserving the store's style and product requirements. Pair with the product-family skill for production.
---

# Design graphics for the store

Resolve paths beginning with `stores/` or `docs/` from the store project's root. For another store, use its current identity and catalog.

Turn the idea into a composition that works on the product. Use references to make decisions about hierarchy, framing, contrast and texture. Produce the requested artwork, open it and correct visible problems. A prompt or a list of suggestions is sufficient when that is what the user requested.

This skill draws on a review of eight videos by **Dan George Hill / DGH Graphic Design**. Consult the current store and product documents for their requirements. [Sources, timestamps and review scope](references/dgh-video-notes.md)

## 1. Establish the message and surface

- Read the request and the applicable `AGENTS.md`. For IA Referencias, consult the identity (`stores/ia-referencias/IDENTITY.md`), art direction (`stores/ia-referencias/GRAPHIC_STYLE.md`), design families (`stores/ia-referencias/DESIGN_STYLES.md`) and catalog (`stores/ia-referencias/products/index.md`).
- For a revision, open the exact artwork and the most recent product decisions. Keep the original as a control. A user's exclusion takes precedence over an older approval label. For Fox Rockett proposals, consult the corrected selection in `stores/ia-referencias/spikes/2026-09-26-fox-rockett-approved-products/README.md`.
- Record the audience, exact phrase, contradiction, intended first read, product, surface color and requested stage. Identify which text must appear and which details are optional. Use the [brief and review template](references/brief-and-review.md) to keep these decisions with the design study.
- Choose an existing family. Start a short slogan with `vector-icon-text`. The alternatives are `segmented-photo-collage` and `targeted-accent-intervention`. For Dibujos Infantiles, consult its identity and preserve the artist's drawing and linework. Apply only the principles that serve that brief.

## 2. Choose references for a specific decision

Use the recipe for the selected family. Select references that resolve type scale, visual weight, crop, image integration or ink treatment. Record what you took from each reference and what you adapted. Build the motif, wording and composition around the store's concept. [Design recipes](references/design-recipes.md)

Before selecting purchased assets, read `docs/operations/fox-rockett-assets.md` and the product review in `stores/ia-referencias/spikes/2026-09-26-fox-rockett-product-review/README.md`. Use an asset when it clarifies the metaphor. Record its ID, adaptation and license. Retain motifs the user has selected. Use original material or material with documented permission. Tutorials alone do not establish commercial rights to the photos, fonts, characters or packs they show.

## 3. Resolve composition before finishing

1. Build a clean, editable version. Set the reading order of the phrase, image and supporting detail. Check the balance of light and dark areas first.
2. Derive a simple grid from the content and the surface. Align to meaningful edges and axes, then adjust optically. Leave enough space for the phrase to read and the silhouette to be recognizable.
3. Use type size, weight, meaningful line breaks and separation between levels to organize the message. The 1.618 ratio shown in the DGH material is a starting point to try. Choose the final size by checking the text on the product.
4. For images, check crop, orientation, lighting, tonal values and overlap. Adjust scale or masking to integrate the parts. When mirroring an image, recheck lettering, logos and any detail whose orientation carries meaning.
5. For a substantial IA Referencias design study, compare at least three hypotheses within the chosen family. For a slogan tee, try a direct stacked composition, a compact emblem and a restrained UI element or icon. Explain the decision each tests. Respect a narrower request for a single output or a targeted correction.

For a short slogan, take hierarchy and alignment from the denser reference posters. Keep one main phrase and at most one secondary phrase according to the store's style.

## 4. Give color and texture a job

- Use the accent to identify the punchline, distinguish a state or connect elements. Check the composition in grayscale.
- Keep the clean control if texture helps the idea. Treat individual elements or masks first, then integrate the overall finish. A large headline can tolerate distressing that erases a smaller line. Check edges, letter counters and pattern seams.
- For collage, try a common tonal adjustment and correct each cutout before adding global noise. Reduce or remove any effect that costs contrast or hides the metaphor on the actual surface.
- Separate artwork, print texture and presentation layers. Keep paper backgrounds and mockup shadows out of a transparent print PNG. Preserve editable text and a reproducible export.

## 5. Choose the tool for the job

| Task | Tool or resource |
| --- | --- |
| Typography, symbols, grid and precise export | SVG, code or an available vector editor. Consult `docs/operations/product-design-toolchain.md`. |
| Cutouts, lighting, masks, wear or texture | A raster editor or scripts suited to the treatment. Preserve layers and parameters. |
| New illustration or photography using a model | An available image generation skill. Specify composition, surface and visual purpose. Typeset the exact final wording with deterministic tools. |
| Tee artwork, PNGs and previews | [Create a shirt product](../create-shirt-product/SKILL.md), including its composition reference. |
| Print specifications, variants, provider, price, upload or real mockup | [Create a Printify product](../create-printify-product/SKILL.md). |
| A campaign or models wearing an existing product | [Marketing](../marketing/SKILL.md), using current product references. |
| Detailed critique or a difficult comparison | [Product design critic](../product-design-critic/SKILL.md). |

Photoshop and DGH's asset packs are optional. Adapt the operation to the available tools and authorized assets. Finish the requested artwork stage. Any external action depends on the scope the user authorized. Follow the store's current policy for the visible `AI Generated Image` label.

## 6. Inspect the result and close the iteration

- Open the actual images. Compare full artwork and full product views at both 300 and 600 px. Keep framing consistent within each comparison and inspect critical details separately. Use the existing evidence generator for repeatable review sheets when helpful. OCR and measurements can flag risks. Inspect the visual result to decide. [Evidence contract](../product-design-critic/references/review-contract.md)
- After reducing the image, check the exact wording, punchline, contrast, spacing, crops, edges and texture. Inspect areas that product geometry could hide or distort, including handles, spines, seams and curves.
- Choose on the strength of the idea and its visible execution. A clean version can win. Correct the highest-impact defect and compare the affected area again. Stop when the brief and stage checks are met. If evidence is missing, deliver what can be verified and identify the limitation.
- For Printify acceptance, use the actual product mockups and the checks in its skill. A tutorial titled “print ready,” a simulation or a flattened file cannot establish physical print quality or replace the product specification.
- Record sources, selected approach, file versions, parameters, evidence and reasons for rejecting alternatives in `RESOURCES.md`. Keep iterations in the ignored directories. Deliver final artwork and comparison sheets to the study's designated locations and update its index when appropriate. Show the result, explain the improvement and identify which observations come from your own review or from buyer testing.
