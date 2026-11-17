---
name: marketing
description: Generate multi-option marketing asset packs from a Printify product page URL such as `/marketing PRODUCT_URL`, pulling product truth images first and then producing prompt-driven AI campaign options aligned with IA-Referencias marketing policy. Use also when Codex needs to package or upload approved marketing/listing images to an existing Printify product as custom mockups, or prepare Instagram/social posts from the Printify-approved model/scene version of a product.
---

# Printify Marketing Generator

Run bundled helpers by their absolute paths from the root of the store workspace. Resolve `scripts/` and `references/` next to this `SKILL.md`. Set `SKILL_DIR` to that skill directory in the shell examples below.

## Goal

Use this skill when the request is specifically: "generate marketing images for a Printify product URL" (for example `/marketing https://printify.com/app/product-details/<id>?fromProductsPage=1`).

The skill:
- reads product imagery from the Printify product page or from the product's already downloaded real Printify mockups,
- selects model/person references before prompt writing,
- prepares a fixed campaign prompt pack with 4-6 options,
- generates campaign images through an approved reference-capable provider (Codex/OpenAI by default; Higgsfield when its documented route is selected),
- enforces the workspace marketing rules,
- packages approved listing images into an upload-ready folder,
- uploads approved listing images to the existing Printify product as custom mockups when requested,
- prepares Instagram/social upload packs from Printify-approved model/scene images when the product already has approved Printify mockups,
- and documents what was read/generated for reuse in spikes, products, and social flow.

## Mandatory marketing rules to apply

For `stores/ia-referencias/`, enforce:

- sharp, sarcastic, controversy-aware tone around AI/dev/workflow culture;
- satire that reveals contradiction explicitly, without unverifiable claims;
- no real-person impersonation unless explicitly allowed;
- no hate symbols or protected-class targeting;
- no claims that require proof in the final copy;
- store-facing generated image disclosure: visible corner label `AI Generated Image`;
- do not use product-look-alike previews as truth: use real Printify product truth as the source for campaign visuals.
- final handoff must include `assets/upload-ready/` in the active spike or product folder, with only the images intended for product/listing upload.
- upload-ready packs may include `00-review-contact-sheet-do-not-upload.jpg` for review only; never upload files prefixed `00`.
- generated campaign images must be produced through an approved reference-capable workflow; use Codex/OpenAI by default, or Higgsfield only under `references/higgsfield-integration.md`. Do not stop at prompt text when image generation is available.
- every marketing run must create and use a campaign-specific image folder inside the active spike: `assets/marketing/<campaign-slug>/`. Store generated campaign images, normalized review images, and contact sheets there before building any upload-ready pack.

For model campaign image generation in this store:
- select the best available model/person references before writing prompts.
- if no suitable model/person references are available, create neutral model/person reference images with an approved image provider first, save them under `assets/source/models/`, and record the provider and that they are generated source references.
- use at least two masculine-presenting and two feminine-presenting model references by default.
- default to four total generated campaign images unless the user requests a larger set; use up to six when the scenario set benefits from more coverage.
- use a different model/person reference for every generated campaign image.
- choose the satire or sarcasm scenario each model should perform before writing prompts.
- compose prompts using both reference types: the selected model/person reference and the direct Printify product reference.
- if the user asks for models wearing/using the product, the final campaign output must be photorealistic lifestyle/model imagery. Do not substitute deterministic posters, flat cards, collages, cutout composites, or copy-only ad layouts for this mode.
- never overlay, paste, patch, or composite product artwork onto AI-generated worn garments for final lifestyle/model images. If a product graphic, sleeve, body part, cape, strap, or laptop hides or distorts the shirt art, reject that image and generate a new one instead.
- for back-view shirt scenes, generate the full worn-shirt image with the back design naturally integrated into the fabric. Do not repair prompt drift by adding a flat layer over the shirt; layers that disappear behind people, capes, folds, arms, or props are a quality failure.
- if the active image generation path cannot accept visual references, stop the asset generation path and document the blocker instead of fabricating synthetic product-truth images. It is acceptable to build prompts and manifests, but not to mark the campaign images as finished.

For product truth:
- For an existing product/spike, prefer already downloaded real Printify `product.images[]` mockups saved under the product or spike asset tree.
- For a given product URL, prefer real `product-details`/editor truth images pulled during the run, saved under the spike asset tree.
- Read from `shared/references/printify-products` only when no product-specific Printify mockups exist.

For Instagram/social posts from existing Printify products:
- use only the Printify-approved model/scene version: selected or approved model/scene images already present in Printify `product.images[]`.
- do not use generated campaign images, local simulated previews, approximate composites, product-only mockups, size charts, contact sheets, local ad cards, or non-selected Printify assets unless the user explicitly asks for a new creative generation run instead of an approved-model Instagram post.
- when possible, download the selected Printify images into `stores/ia-referencias/social/instagram/assets/approved-product-images/<product-slug>-printify-selected-YYYY-MM-DD/`, then copy only the final model/scene set into a short-path upload pack under `assets/ready/<product-slug>-printify-models-vN/`.
- document the hard filter in the draft, calendar row, upload-pack `README.md`, and any scheduling log: `only Printify-approved model/scene images from product.images[]`.
- validate each Instagram upload image dimensions and mode before scheduling; prefer `1080x1350` RGB JPEG when Printify provides that format.

## Provider routing

- Use Codex/OpenAI as the default image provider.
- Use Higgsfield only when the task benefits from its image-to-video, product-photoshoot, Marketing Studio, or virality-analysis routes and follow `references/higgsfield-integration.md`.
- Provider choice never relaxes Printify product truth, 2M/2F cast coverage for model campaigns, visible AI disclosure, no-overlay garment repair, credit limits, or publication authorization.

## Trigger contract

When user runs `/marketing <product-url>`:

- parse `product-url` and create/use a spike path under `stores/ia-referencias/spikes/YYYY-MM-DD-printify-marketing/`.
- call the extraction script to save product-truth images.
- select and save model/person references.
- choose a satirical scenario for each selected model/person.
- build a marketing prompt set from both model references and Printify product truth (default 4 options: 2M/2F).
- generate the campaign images through the selected approved reference-capable provider.
- after approved images exist, create an upload-ready pack with stable ordered filenames.
- write `RESOURCES.md` notes and a campaign manifest.

When the user asks to upload approved marketing images to a Printify product:

- use the product's existing `assets/upload-ready/<campaign-slug>/` folder as the source of truth.
- upload only the final listing images the user approved; do not upload contact sheets, raw sources, rejected generations, or duplicated product-truth files that already exist in the product's Printify mockups.
- use the Printify editor with Playwright by default and save the product as a draft. Do not publish unless the user explicitly asks to publish.
- document the upload in `RESOURCES.md` and a sanitized manifest. Never store Printify product IDs, upload IDs, shop IDs, API tokens, or private Printify URLs.

When the user asks to start or schedule an Instagram post for an existing Printify product using approved models:

- inspect the product's selected Printify `product.images[]` first.
- select only model/scene images already approved in Printify; keep product-only mockups, size charts, contact sheets, generated campaign images, and local composites out of the public Instagram upload pack.
- build the Instagram draft and calendar row from that approved model/scene upload pack.
- if scheduling through Meta Business Suite, record the scheduled date/time, account, post visibility, asset list, and proof screenshot in `stores/ia-referencias/social/instagram/calendar/`.
- do not start a paid promotion unless the user explicitly asks for promotion or ads in that turn.

## Script workflow

1. Parse and validate URL:
   - must contain `printify.com/app/product-details/<product_id>`.
2. Create/confirm spike scaffold:
   - `spike_dir=stores/ia-referencias/spikes/YYYY-MM-DD-printify-marketing`
   - `assets/source/models/`
   - `assets/source/printify/`
   - `assets/marketing/<campaign-slug>/`
   - `assets/upload-ready/<campaign-slug>/`
   - `references/`
3. Select model/person references:
   - use the best available references first, favoring useful pose, lighting, and product-holding compatibility.
   - save or link references under `assets/source/models/` and record source notes in `RESOURCES.md`.
   - default selection must include at least two masculine-presenting and two feminine-presenting references.
4. Pull product truth images:
   - run `scripts/extract_printify_product_images.js`.
   - this script attempts Playwright first and falls back with an explicit warning if not available.
   - once the product exists, use direct Printify product references only; never use autogenerated images, local simulated previews, or approximate composites as product-truth references.
   - if real Printify mockups were already downloaded in the product spike, copy or reference those directly and write a manifest instead of re-extracting.
5. Choose scenarios:
   - choose the satire/sarcasm scenario each model should perform before writing image prompts.
   - make the product contradiction visible without unverifiable claims, real-person impersonation, hate symbols, or clutter that hides the product.
   - honor user-provided scene directions first. For non-programming requests, prefer ordinary life settings such as gym, family/parenting, church/community, errands, outdoors, sports, commute, or social events.
6. Build campaign prompt pack:
   - run `scripts/build_marketing_prompts.py`.
   - default output: 4 scenes in `references/marketing-candidates.json` and `references/marketing-candidates.md`.
   - ensure each prompt names both references it uses: model/person reference and Printify product reference.
   - use `--scenario-set nonprogramming-lifestyle` when the campaign should show people outside programming contexts.
7. Generate campaign images:
   - use the selected approved reference-capable provider for the final images.
   - save final generated images in the active spike under `assets/marketing/<campaign-slug>/`.
   - if the product already has a stable product folder, copy accepted generated campaign images to the product's `assets/marketing/<campaign-slug>/` folder as well.
   - preserve useful source/generated references and add approved assets to the store/product structure when applicable.
   - show the resulting image or a contact sheet to the user when possible.
8. Document output paths in:
   - `RESOURCES.md`
   - local manifest file generated by the scripts.
9. Build the upload-ready pack after final image selection:
   - put upload files in `assets/upload-ready/<campaign-slug>/`.
   - use stable ordered names: `01-...jpg` through `NN-...jpg`.
   - order images for upload: direct Printify product truth first, product/listing support shots next, generated campaign/lifestyle images last.
   - add `README.md` saying to upload files `01` through `NN` and not upload review-only files.
   - record this folder in `RESOURCES.md` and any local manifest.
10. Before final use, create a contact sheet or campaign contact sheet for quick review. If it is saved inside `assets/upload-ready/`, name it `00-review-contact-sheet-do-not-upload.jpg`.

## Printify custom mockup upload workflow

Use this when approved marketing/listing images already exist and the user asks to upload them to the Printify product.

1. Confirm source files:
   - read the upload-ready `README.md` and manifest if present.
   - upload only approved final images, usually ordered `01-...jpg` through `NN-...jpg`.
   - skip `00-review-contact-sheet-do-not-upload.jpg`.
   - skip product-truth front/back files if equivalent Printify mockups are already selected on the product.
2. Open the existing Printify product in a named Playwright session:
   - prefer the current authenticated session when the user says they left Printify open.
   - if authentication is missing, pause for login or use the documented Printify API route only for validation; do not fake a UI upload.
3. In the product details editor:
   - locate `Selected mockups`.
   - record the current selected count, such as `12/20 selected`.
   - click `Upload`.
4. In the `Upload mockups` modal:
   - ensure `Replace previous mockup selection` is unchecked before uploading.
   - set the file input to the approved image paths.
   - verify the uploaded thumbnails appear in the modal.
   - click `Confirm`.
5. In the mockup library:
   - open `My Uploads` if Printify does not automatically select the new files.
   - select the newly uploaded files with their checkbox controls, not by opening the preview image.
   - verify the selected count increases by the number of uploaded files.
   - click `Save selection`.
6. Back in product details:
   - verify the `Selected mockups` count reflects the new total.
   - click `Save as draft`.
   - never click `Publish` unless the user explicitly requested publishing in that turn.
7. Validate:
   - reload the product details page and verify the selected count and thumbnails render.
   - when `PRINTIFY_API_TOKEN` and `PRINTIFY_SHOP_ID` are available, run a sanitized API check for image count, selected count, and position counts only.
   - save a cropped proof screenshot of the mockup panel that avoids account names, shop IDs, private URLs, and side navigation when possible.
8. Document:
   - create a sanitized upload manifest under `references/`, including uploaded filenames, skipped files, before/after selected counts, validation counts, proof screenshot path, `saved_as_draft: true`, and `publish_clicked: false`.
   - update `RESOURCES.md` and the product README with the upload result and proof screenshot path.
   - scan touched docs/manifests for private Printify URLs, 24-character product IDs, shop IDs, API tokens, and account emails.
   - remove local Playwright trace/snapshot/log artifacts from the current run if they contain private Printify URLs or account details.

## Commands

Run from repo root unless context requires explicit path:

```bash
python -m pip install pillow
node "$SKILL_DIR/scripts/extract_printify_product_images.js" \
  --product-url "PRINTIFY_PRODUCT_URL" \
  --spike-dir "stores/ia-referencias/spikes/2026-06-06-printify-marketing" \
  --output-dir "stores/ia-referencias/spikes/2026-06-06-printify-marketing/assets/source/printify" \
  --manifest "stores/ia-referencias/spikes/2026-06-06-printify-marketing/references/printify-product-media.json"

python "$SKILL_DIR/scripts/build_marketing_prompts.py" \
  --input-manifest "stores/ia-referencias/spikes/2026-06-06-printify-marketing/references/printify-product-media.json" \
  --output-dir "stores/ia-referencias/spikes/2026-06-06-printify-marketing/references" \
  --model-reference-dir "stores/ia-referencias/spikes/2026-06-06-printify-marketing/assets/source/models" \
  --cast-pattern "2m2f" \
  --scenario-set "nonprogramming-lifestyle" \
  --max-options 4
```

## Output contract

- `assets/source/models/` contains or references selected model/person images and notes for why each was chosen.
- `assets/source/printify/` contains downloaded product-truth images (source references only).
- `assets/marketing/<campaign-slug>/` contains provider-generated campaign images, normalized final review images, and any contact sheet made for review.
- `assets/upload-ready/<campaign-slug>/` contains the final upload pack:
  - `01-...jpg` through `NN-...jpg` are the only product/listing upload files.
  - `00-review-contact-sheet-do-not-upload.jpg`, when present, is a visual checklist only and must not be uploaded.
  - `README.md` states the upload order and the do-not-upload rule for `00`.
- `references/printify-custom-mockup-upload-<campaign-slug>.json`, when images are uploaded to Printify, records the sanitized upload result without private IDs or URLs.
- `references/printify-product-media.json` includes URL, product-id, selected image list, and extraction metadata.
- `references/marketing-candidates.json` includes 4 generated campaign prompts with:
  - `slot`, `cast`, `model_reference`, `product_truth`, `scene`, `prompt`, `required label`.
- `references/marketing-candidates.md` is the human-readable copy pack.
- `RESOURCES.md` records URL, image sources, command outputs, prompt strategy, and the upload-ready folder contents.

## Quality rules for this skill

- Must keep campaign truth anchored to real Printify images.
- Must use both model/person references and direct Printify product references when composing generated image prompts.
- Must use distinct model/person references across a campaign unless the user explicitly asks for repeat talent.
- Must produce photorealistic model/lifestyle images when the user asks for people wearing or using the product.
- Must not use artwork overlays, pasted print layers, or flat patches as final fixes for model/lifestyle wearables. Regenerate the scene until the print appears naturally printed on the garment, or mark the image rejected.
- Must visually reject generated lifestyle/model images where the shirt graphic is cut off, covered by a layer that should be behind the person, text is unreadable, or the product art looks composited instead of worn.
- Must create `assets/marketing/<campaign-slug>/` inside the active spike before generating or saving campaign images, and report that path in the final handoff.
- Must not count deterministic posters, collages, cutout composites, local simulated previews, or text-only cards as completed lifestyle/model campaign images.
- Keep all generated scenes in the satirical/ironic register used by the store.
- Ensure output count is at least four and includes 2 masculine-presenting and 2 feminine-presenting outputs by default.
- Every AI-generated scene must include `AI Generated Image` as a visible corner label.
- Direct Printify mockups/product-truth images do not need the AI-generated label.
- The upload-ready folder must not include source-only references, rejected generations, intermediate files, synthetic product-truth substitutes, or unlabeled AI-generated campaign images.
- Instagram upload packs for existing Printify products must contain only the approved Printify model/scene images selected for that post.
- When uploading images to Printify, keep `Replace previous mockup selection` unchecked unless the user explicitly wants to replace existing mockups.
- Confirm that the selected mockup count increases as expected before saving the product as draft.
- Do not click `Publish` during marketing-image uploads unless the user explicitly asks for publishing.
- Do not invent product facts from the prompt alone; all product appearance references must come from extracted images and local manifest.
- Never write secrets into manifests.

## Fallback behavior

- If Playwright extraction fails:
  - do not continue with synthetic fake imagery as truth.
  - update `printify-product-media.json` with `extraction_status: failed`.
  - either point to a user-provided local mockup reference or pause with `paused` status in spike index.

## Dependencies

- Node.js and optional Playwright for extraction (`npm i -D playwright`).
- Pillow for optional poster/contact-sheet tasks in downstream scripts.

This skill is intentionally deterministic in prompt construction and non-judgmental in image semantics so that it can be reused as the default `/marketing` route for product-driven campaign generation.
