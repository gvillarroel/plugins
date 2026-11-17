---
name: create-printify-product
description: Build Printify-compatible product assets, validation reports, upload steps, product creation payloads, Etsy-aware pricing checks, and real API-generated mockup downloads for tops, mugs, and future product families. Use when Codex needs to create programmatic Printify products, prepare PNGs for known print areas, fetch catalog IDs, upload art, price products with marketplace fees, create draft products, or turn a store spike into Printify API-ready files.
---

# Create Printify Product

Run bundled helpers by their absolute paths from the root of the store workspace. Resolve `scripts/` and `references/` next to this `SKILL.md`. Set `SKILL_DIR` to that skill directory in the shell examples below. Resolve `shared/` paths from the store workspace. For other stores, supply their own reference image or retrieve current catalog specifications with the documented Printify workflow.

## Overview

Use this skill to move from a store spike or product idea to Printify-ready assets and API payloads. It covers print-area specs, PNG generation, image validation, Media Library upload helpers, catalog lookup, and product payload creation.

## Workflow

1. Pick a product spec or family template from `references/product-specs.json`.
2. Read `references/printify-compatible-products.md` and `references/product-family-best-practices.md` to choose the correct product family, art contract, and composition rules before generating assets.
3. For current product-level composition sizes and options, read `shared/references/printify-composition-reference-2026-06-06/README.md` and `shared/references/printify-composition-reference-2026-06-06/index.json`.
4. For broader catalog/category context, read `shared/references/printify-catalog-2026-05-31/README.md` and `shared/references/printify-catalog-2026-05-31/catalog-summary.json`.
5. For quick local mockups, pick a reference image/template from `references/preview-templates.json`.
6. If the product is missing variant IDs, run `scripts/fetch_printify_catalog.py` with `PRINTIFY_API_TOKEN` and save useful output in the spike `RESOURCES.md`. If Python receives Cloudflare `1010`, retry the same lookup with `scripts/fetch_printify_catalog_node.js`; if API access is still blocked, use the Printify editor/browser route and record the fallback.
7. Generate print assets with `scripts/render_printify_asset.py` or a product-specific renderer such as `scripts/render_terminal_radial_shirt.py` from the sibling `create-shirt-product` skill.
8. Validate every production PNG with `scripts/validate_printify_asset.py` before upload.
9. Build an approximate local preview with `scripts/build_reference_preview.py` when a saved reference image exists.
10. Upload the image to Printify with `scripts/upload_printify_image.py`, using `PRINTIFY_API_TOKEN`; keep returned `image_id`.
11. Build the create-product payload with `scripts/build_printify_payload.py`.
12. Before final pricing or publishing, read `references/etsy-pod-pricing.md` and run `scripts/calculate_etsy_pod_margin.py` when the product may sell through Etsy or another fee-taking marketplace. Do not approve price from Printify gross margin alone.
13. Create or dry-run the product with `scripts/create_printify_product.py`, using `PRINTIFY_API_TOKEN` and `PRINTIFY_SHOP_ID`.
14. For real mockups from a newly created product, poll `GET /v1/shops/{shop_id}/products/{product_id}.json` until `images[]` is populated, then download `images[].src` outputs. For already-existing shop products, use `scripts/download_printify_mockups.js` to list shop products and download `product.images[]`. Do not confuse `print_areas[].placeholders[].images[].src` SVG placement assets with final mockups.
15. Preserve final assets, sanitized payloads/API responses, references, prompts, pricing assumptions, fee calculations, and commands in the spike `RESOURCES.md`.
16. Push generated images, previews, payload templates, docs, and other reviewable artifacts.

## Interactive Editor Automation

Use Playwright by default for Printify web-editor interaction: opening product editors, uploading local print PNGs, selecting variants/colors, adjusting placement, capturing screenshots, and downloading mockups. Use a named Playwright session so authenticated state, element snapshots, and screenshots are isolated for the spike.

Chrome plugin automation is a fallback, not the default, for Printify. Use it only when the user explicitly asks for Chrome or when Playwright cannot access the authenticated page. If falling back to Chrome, record the reason in `RESOURCES.md`; file upload may require enabling local-file access for the Codex Chrome Extension.

When Playwright cannot upload because authentication state is missing, prefer either:

- reusing/saving a Playwright auth state for Printify, or
- uploading through the Printify API with `PRINTIFY_API_TOKEN` and then selecting the image from `My library`.

Do not treat local reference previews as completed Printify proof. They are useful fallbacks, but real Printify proof needs a page screenshot or downloaded mockup from the editor/preview flow.

Verified session note from 2026-06-02: Playwright could open Printify, but Chrome blocked attaching to the live default profile and copied Chrome profiles did not retain an authenticated Printify session. The successful fallback was live Chrome automation through Google SSO, then creating a scoped API token at `https://printify.com/app/account/api`. Record this fallback when used.

## Product Specs

Primary reference:

- `references/product-specs.json`

## IA-Referencias Store Defaults

For `stores/ia-referencias/` tee products, prefer the premium Bella+Canvas 3001 / Printify Choice route unless the spike documents a quality, cost, or availability reason to use another garment:

- Product key: `tops.bella_canvas_3001`.
- Printify API route: `blueprint_id` 12, `print_provider_id` 99, DTG.
- Default colors: Black, Vintage Black, Asphalt, Navy, Deep Teal, and Maroon.
- Default sizes: S, M, L, XL, 2XL, and 3XL.
- Default working art canvas: transparent `4500x5400` front PNG.
- Default starting price: `$32.99`, subject to Etsy fee and Offsite Ads stress checks before approval.

Use Gildan 5000 as a lower-cost/test route, not the default `ia-referencias` premium tee. When moving a phrase-led AI/dev shirt to Printify, read `stores/ia-referencias/products/index.md` and recent accepted product notes to compare selected scale, placement, colors, and price. Recent compact/direct typography references cluster around placement scale `1.18-1.35`; validate against real `product.images[]` mockups rather than local previews or print-area SVGs.

For accepted `ia-referencias` products, preserve sanitized pricing notes, selected variant strategy, mockup evidence, and placement decisions in the spike `RESOURCES.md`. Promote final reviewable assets to the product folder and approved assets folder; keep rejected API/mockup iterations out of final preview folders unless they are explicitly documented as final comparison evidence.

Current product families:

- `tops.bella_canvas_3001`: default premium `ia-referencias` tee route, verified from current Printify composition references and recent store drafts. Front art uses a `4500x5400` working canvas; selected provider/variant dimensions still need catalog lookup before publishing.
- `tops.gildan_5000`: verified from the authenticated Printify editor. Front/back are `3951x4919`; the preferred working canvas is `4500x5400`.
- `tops.generic_hoodie`: template spec for polerones/hoodies until a specific Printify blueprint and provider are selected.
- `mugs.mug_11oz`: official Printify API example for an 11 oz mug, using a `4350x5850` print image.
- `mugs.generic_wrap`: reusable mug wrap template when the exact blueprint is still undecided.

Catalog families observed in Printify:

- Tops: T-shirts, hoodies, sweatshirts, long sleeves, tank tops, sportswear, outerwear.
- Drinkware: mugs, glassware, bottles, tumblers.
- Wall art: posters, canvas, postcards.
- Accessories: mouse pads, phone cases, bags, socks, hats, stickers, stationery, sports/games.
- Home textiles: blankets, pillows, towels, bedding, rugs/mats.
- Production methods/special collections: DTG, dye sublimation, AOP clothing, embroidery, engraving, personalization picks, Printify Choice.

For full-family preparation rules across apparel, AOP, drinkware, wall art, stickers, accessories, bags, hats, textiles, home decor, pets, baby accessories, engraving, and seasonal products, read:

- `references/printify-compatible-products.md`
- `references/product-family-best-practices.md`

For product-level composition sizes, options, providers, placements, and art-contract routes across the current API blueprint snapshot, read:

- `shared/references/printify-composition-reference-2026-06-06/README.md`
- `shared/references/printify-composition-reference-2026-06-06/index.json`

For Gildan 5000 details, also read:

- `shared/references/printify-unisex-heavy-cotton-tee-gildan-5000.md`

For the 2026-05-31 catalog crawl, read:

- `shared/references/printify-catalog-2026-05-31/README.md`
- `shared/references/printify-catalog-2026-05-31/catalog-summary.json`
- `shared/assets/references/printify-products/manifest.json`

## API Notes

Read `references/printify-api.md` before creating payloads. Store credentials only in environment variables:

- `PRINTIFY_API_TOKEN`
- `PRINTIFY_SHOP_ID`

Known-good scoped token permissions for mockup generation: `shops.read`, `catalog.read`, `products.read`, `products.write`, `uploads.read`, `uploads.write`, and `print_providers.read`.

Never commit API tokens, shop-specific private responses, product IDs for private drafts, upload image IDs, customer data, or OAuth URLs. It is fine to commit sanitized payload templates, generated assets, downloaded mockups, and catalog notes.

## Scripts

Generate a print PNG and preview:

```bash
python "$SKILL_DIR/scripts/render_printify_asset.py" \
  --product-key tops.bella_canvas_3001 \
  --placement front \
  --text "I don't need AI creating Slop Code" \
  --subtitle "I can do it by myself" \
  --style vector-icon-text \
  --output shared/assets/examples/printify/bella-3001-front-example.png \
  --preview shared/assets/examples/printify/bella-3001-front-preview.png
```

Validate a PNG against a spec:

```bash
python "$SKILL_DIR/scripts/validate_printify_asset.py" \
  --product-key tops.bella_canvas_3001 \
  --placement front \
  --image shared/assets/examples/printify/bella-3001-front-example.png
```

Build a quick local reference preview:

```bash
python "$SKILL_DIR/scripts/build_reference_preview.py" \
  --template-key mugs.front \
  --art shared/assets/examples/printify/mug-11oz-wrap-example.png \
  --fit cover \
  --output shared/assets/examples/printify/mug-11oz-reference-preview.png
```

Fetch catalog variants when authenticated:

```bash
python "$SKILL_DIR/scripts/fetch_printify_catalog.py" variants \
  --blueprint-id 12 \
  --print-provider-id 99 \
  --show-out-of-stock \
  --output shared/references/printify-bella-3001-provider-99-variants.json
```

Node fallback for catalog lookup when Python `urllib` hits Cloudflare `1010`:

```bash
node "$SKILL_DIR/scripts/fetch_printify_catalog_node.js" blueprints \
  --output shared/references/printify-catalog-YYYY-MM-DD/blueprints.json
```

Build or resume the product-level composition reference:

```bash
node "$SKILL_DIR/scripts/build_printify_composition_reference.js" \
  --output-dir shared/references/printify-composition-reference-YYYY-MM-DD \
  --concurrency 1 \
  --delay-ms 1000 \
  --retries 10 \
  --retry-base-ms 10000
```

Upload an image to Printify:

```bash
python "$SKILL_DIR/scripts/upload_printify_image.py" \
  --file shared/assets/examples/printify/mug-11oz-wrap-example.png \
  --output shared/assets/examples/printify/mug-11oz-upload-response.json
```

Build a create-product payload:

```bash
python "$SKILL_DIR/scripts/build_printify_payload.py" \
  --product-key mugs.mug_11oz \
  --placement front \
  --title "Example Mug" \
  --description "Replace this copy before publishing." \
  --image-id REPLACE_WITH_UPLOAD_ID \
  --price 1999 \
  --output shared/assets/examples/printify/mug-11oz-payload-template.json
```

Create the product after manual review:

```bash
python "$SKILL_DIR/scripts/create_printify_product.py" \
  --payload shared/assets/examples/printify/mug-11oz-payload-template.json \
  --output shared/assets/examples/printify/mug-11oz-create-response.json
```

After POSTing a product, wait for `product.images` before downloading real mockups. In the verified Gildan 5000 API test, `images` was initially empty and later contained front/back/other mockups; front images were 1200x1200 JPEGs from `images-api.printify.com`.

Download real mockups for existing shop shirt products:

```bash
node "$SKILL_DIR/scripts/download_printify_mockups.js" \
  --output-dir stores/ia-referencias/spikes/YYYY-MM-DD-slug/assets/previews/printify-real \
  --manifest stores/ia-referencias/spikes/YYYY-MM-DD-slug/references/printify-mockups-manifest.json \
  --product-filter shirts
```

Build a contact sheet from the sanitized mockup manifest:

```bash
python "$SKILL_DIR/scripts/build_mockup_contact_sheet.py" \
  --manifest stores/ia-referencias/spikes/YYYY-MM-DD-slug/references/printify-mockups-manifest.json \
  --output stores/ia-referencias/spikes/YYYY-MM-DD-slug/assets/previews/printify-real/printify-mockups-contact-sheet.jpg
```

Useful filters for the downloader:

- `--positions front,back,other`: restrict downloaded mockup positions.
- `--selected-only`: download only mockups selected for publishing.
- `--visible-only`: skip hidden products.
- `--title-match "Heavy Cotton"` or `--blueprint-id 6`: target specific products.
- `--product-filter all`: download from every product type, not just shirts.

The downloader intentionally omits API tokens, shop IDs, product IDs, mockup IDs, upload image IDs, variant IDs, and source URLs from the manifest. It stores product title, blueprint/provider IDs, colors, sizes, positions, file paths, bytes, and image dimensions after contact-sheet generation.

Calculate Etsy-aware POD margins before final pricing:

```bash
python "$SKILL_DIR/scripts/calculate_etsy_pod_margin.py" \
  --price-cents 2999 \
  --cost-cents 1129,1382,1612 \
  --target-net-margin-pct 35
```

Stress an Offsite Ads sale:

```bash
python "$SKILL_DIR/scripts/calculate_etsy_pod_margin.py" \
  --price-cents 3299 \
  --cost-cents 1129,1382,1612 \
  --offsite-ads-pct 15 \
  --target-net-margin-pct 20
```

## Quality Gate

- Production PNG dimensions meet or exceed the Printify print area.
- Product-family art contract is correct: transparent placement, opaque full-bleed, wrap, AOP panel art, embroidery-style art, engraving line art, or paper/trim-safe art as appropriate.
- For products covered by the composition reference, selected provider/variant dimensions and options have been checked in `shared/references/printify-composition-reference-2026-06-06/products/`.
- Transparent art is actually transparent where the garment/product color should show.
- Opaque mug art includes intentional background color.
- Preview exists on the expected product color or mug background.
- Approximate local reference previews are marked as previews, not final Printify mockups.
- Payload uses real `image_id` values returned by Printify uploads before POSTing.
- Variant IDs match the chosen blueprint and print provider.
- Real mockups come from `product.images[].src`; placeholder SVGs under print areas are not accepted as final mockups.
- Etsy-bound pricing includes marketplace fees before approval: at minimum listing/sold-renewal fee, Etsy transaction fee, payment processing, and an Offsite Ads stress case when relevant. Save assumptions and calculated margin ranges in `RESOURCES.md` or a sanitized summary.
- Sanitized manifests omit API tokens, shop IDs, private draft product IDs, and upload image IDs.
- Spike `RESOURCES.md` lists source links, local references, generated files, API/catalog outputs, and commands.
