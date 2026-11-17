# Historical Character Quote Shirt Workflow

In these examples, `$SkillsDir` is the absolute `skills` folder of the installed `store-studio` plugin. Run commands from the store workspace.

Use this workflow for poleras/shirts built around a historical, public-domain, or iconic character with a phrase area above the figure, the figure in the center, and a phrase area below the figure. The workflow is intentionally staged so the design can be approved before any Printify upload, then turned into real mockups and campaign material.

## Inputs

Collect or infer these from the user and current spike context:

- Store and spike slug.
- Character or figure.
- Top text and bottom text.
- Visual style, such as black-ink engraving, white ink on dark shirt, stencil, comic halftone, statue bust, terminal, collage, or another requested style.
- Shirt color and product target. Default to `tops.gildan_5000` and a front print on `4500x5400`.
- Audience, tone, language, and whether the campaign should be ironic, academic, developer-focused, political, minimalist, or absurdist.

If the user does not specify every field, make a conservative first pass and record assumptions in `README.md` and `RESOURCES.md`.

## Phase 1: Spike Setup

1. Create or reuse `stores/<store>/spikes/<YYYY-MM-DD-short-slug>/`.
2. Ensure the spike has:
   - `README.md`
   - `RESOURCES.md`
   - `assets/print/`
   - `assets/previews/`
   - `assets/intermediate/`
   - `assets/source/`
   - `references/`
   - `social/drafts.md`
3. Add or update the spike row in `stores/<store>/spikes/index.md` with status `in_progress`.
4. Record the requested character, copy, style, garment color, product target, and current assumptions.

## Phase 2: Source And Rights Check

Use public-domain, CC0, museum/open-access, or clearly reusable references when reference material is needed. Store useful links and local files in `RESOURCES.md`.

Rules:

- Prefer historical figures and public-domain references.
- Avoid living-person likenesses unless the user explicitly requests one and the usage is acceptable for the store.
- Avoid copyrighted character likenesses, logos, emblems, actor likenesses, and franchise-identifying props unless the output is deliberately transformed into a generic archetype or parody-safe direction.
- Do not directly trace or reproduce a source image. Generate or draw an original figure in the requested style.
- For light shirts, use true dark-ink assets. Do not recolor white-ink-on-dark assets into black ink because the lighting can read as a negative.
- For dark shirts, keep a separate white-ink route and preview it on the dark garment color.

## Phase 3: Figure Asset

Create or select a figure-only transparent PNG before adding text.

Target contract:

- `4500x5400` RGBA PNG.
- Transparent background and transparent corners.
- No baked shirt, paper, mockup, or background.
- No baked top/bottom text in the figure-only file.
- Centered figure with enough vertical room for text above and below.
- Style matches the request and remains readable at product-thumbnail size.

Recommended directories:

- Source references: `references/`
- Raw generated images: `assets/intermediate/`
- Processed figure-only PNGs: `assets/print/<character>-<style>-figure-4500x5400.png`
- Figure previews/contact sheets: `assets/previews/`

Validation:

- Check PNG size and mode.
- Check alpha bounding box and transparent corners.
- Inspect preview on the intended shirt color.
- Save any validation JSON under `references/`.

If the figure does not read as the intended person, iterate the figure-only asset before changing the shirt composition. Use a known public-domain or recorded historical reference as the identity reference, use the existing generated set or style image as the visual-style reference, and generate a new chroma-key source that keeps the same ink/alpha contract. If recognizability is more important than a head-only icon, allow a small upper bust, collar, or signature pose from the historical reference while preserving the requested style constraints.

For hard-to-recognize historical figures, prefer this identity-lock route:

1. Find a public-domain or museum/open-access portrait that has the iconic features the user expects.
2. Generate a chroma-key figure guided by that portrait and the requested style, explicitly naming the recognizability features to preserve.
3. Convert the generated chroma-key image to a transparent one-color ink PNG by code.
4. Apply deterministic code edits for small feature fixes such as empty eyes, darker moustache, chaotic hair edges, beard outline, or alpha cleanup.
5. Validate and inspect the figure-only PNG before re-rendering the top-text / figure / bottom-text composition.

Record the exact prompt, source image path, generated chroma-key file, processed transparent figure, code edits, and reason for the iteration in `RESOURCES.md`.

## Phase 4: Text And Composition

Build the approved print composition by placing:

1. Top text in the upper safe zone.
2. Figure in the central visual zone.
3. Bottom text in the lower safe zone.

Composition rules:

- Keep the final production file transparent.
- Do not bake garment color into the production PNG.
- Text must be readable at thumbnail scale.
- Use stable line breaks and font sizing so long words do not overflow.
- Keep top and bottom text visually subordinate to the figure unless the concept calls for typographic dominance.
- Match ink color and distress texture between the figure and text when the design is meant to look printed as one artwork.
- Save at least one preview on the target shirt color before making any quality decision.

Suggested output names:

- `assets/print/<character>-<short-copy>-<style>-front-4500x5400.png`
- `assets/previews/<character>-<short-copy>-<style>-front-on-<shirt-color>.png`
- `assets/previews/<character>-<short-copy>-<style>-approval-sheet.png`

## Phase 5: Approval Gate

Before uploading to Printify, present an approval packet to the user:

- The composed production PNG path.
- The shirt-color preview path.
- A contact sheet if there are multiple variants.
- A short note listing character, top text, bottom text, style, shirt color, and any known quality caveat.

Do not upload to Printify until the user explicitly approves the design. If the user asks for changes, iterate the design, update `RESOURCES.md`, regenerate previews, and present a new approval packet.

Do not present generated/local model images or saved catalog-reference product overlays as approval mockups. Those are not reliable: shirt cut, neck spacing, scale, garment color, model pose, and fabric folds must come from Printify after product creation. Local previews may be kept as internal development artifacts only, clearly labeled as approximate and not user-facing approval evidence.

## Phase 6: Printify Upload And Real Mockups

After explicit approval, switch to `$SkillsDir/create-printify-product` for Printify-specific work.

Programmatic route:

1. Validate the exact approved PNG with:
   - `$SkillsDir/create-printify-product/scripts/validate_printify_asset.py`
2. Choose the Printify product and variant colors before building the payload.
   - Default product: Gildan 5000 / `tops.gildan_5000`, front print.
   - For dark-ink art, prefer light garments such as `White`, `Ash`, `Sport Grey`, `Ice Grey`, `Natural`, `Sand`, and `Light Blue` when available.
   - Exclude garment colors that do not give enough contrast, such as `Black`, `Navy`, `Dark Heather`, `Charcoal`, or similarly dark colors, unless a separate light-ink design exists.
   - Fetch current variant IDs through the Printify catalog/API or use a verified saved variant map; do not guess IDs.
3. Upload the approved PNG to Printify Media Library with `PRINTIFY_API_TOKEN`.
4. Build the create-product payload using the returned image ID, selected product, selected color/size variants, price, title, description, and front placement scale.
5. Create a draft product with `PRINTIFY_SHOP_ID`.
6. Poll `GET /v1/shops/{shop_id}/products/{product_id}.json` until `product.images[]` is populated.
7. Download real mockups from `product.images[].src`.
8. Save real Printify mockups under `assets/previews/printify-real/`.
9. Build a contact sheet from the downloaded Printify mockups for review.
10. Save sanitized payloads, responses, and mockup manifests under `references/`.

Interactive route:

- Use Playwright by default for Printify editor uploads, placement checks, screenshots, and downloads.
- Use Chrome only when explicitly requested or when Playwright cannot access authenticated Printify state.
- Record the fallback reason in `RESOURCES.md`.

Printify rules:

- Upload the exact file approved by the user.
- Create or update a Printify product before claiming there is a product mockup.
- Do not treat local reference previews or Printify placement SVGs as final mockups.
- Do not use generated model-wearing-shirt images as proof of product placement.
- Do not publish the product unless publication is explicitly requested.
- Do not commit API tokens, shop IDs, private product IDs, upload image IDs, OAuth URLs, customer data, or order data.

## Phase 7: Campaign Assets

Use the downloaded real Printify shirt mockup as the product truth for campaign work.

Campaign package:

- Select 3 to 5 model/ad directions that fit the concept and store.
- Generate or composite model images with the approved shirt visible and the design faithful to the Printify mockup.
- Keep raw model bases in `assets/intermediate/model-bases/`.
- Save campaign drafts under `assets/previews/promo/model-drafts/`.
- Save a contact sheet for review.
- Write ad copy, captions, hooks, and hashtags in `social/drafts.md`.
- Record prompts, source files, commands, and rejected directions in `RESOURCES.md`.

Model/campaign rules:

- Do not use a real person's likeness unless the user explicitly provides or requests that likeness and it is acceptable for the campaign.
- Do not make campaign/model images until real Printify mockups have been downloaded for the approved product.
- Do not let generation redraw or alter the approved shirt art. If AI generation distorts the design, composite the approved shirt/mockup onto the scene instead.
- Keep the product visible, readable, and not covered by hands, props, or folds unless the ad direction intentionally uses a secondary lifestyle crop.
- Produce at least one straightforward product-forward campaign image before experimental variants.

## Phase 8: Closeout

Before finishing the spike:

- `README.md` summarizes the final concept, files, status, and open decisions.
- `RESOURCES.md` can reconstruct the work without chat history.
- `social/drafts.md` contains usable campaign copy.
- Final print PNGs, previews, real Printify mockups, campaign images, manifests, and validation reports are saved in the spike.
- The spike index has a current status.
- Generated reviewable artifacts are committed and pushed when the workflow reaches a stable review point.

## Quality Gate

Do not mark the design accepted unless:

- The production PNG is transparent RGBA at `4500x5400`.
- Top text, figure, and bottom text are readable and balanced.
- Text is not clipped, cramped, or overflowing.
- The figure reads as the intended historical/iconic character without copying a protected source image.
- The style route matches the shirt color: dark ink for light shirts, white ink for dark shirts, or another explicitly intentional ink/color system.
- The garment preview looks production-ready.
- The user has explicitly approved the composition before Printify upload.
- Post-approval shirt/product mockups come only from a real Printify product: `product.images[].src` or Printify editor downloads.
- Selected Printify colors/variants match the ink route and maintain contrast.
- Campaign assets preserve the approved shirt art and include at least one product-forward image.
