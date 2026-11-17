---
name: create-shirt-product
description: Create, iterate, validate, and package print-ready shirt product prototypes for store spikes, including IA-Referencias learned graphic defaults. Use when Codex needs to generate transparent PNG assets, previews on garment colors, product spike folders, Printify-sized shirt art, historical or iconic character quote layouts, terminal/pixel/radial graphics, phrase-led vector typography, or quality decisions for shirt designs.
---

# Create Shirt Product

In these examples, `$SkillsDir` is the absolute `skills` folder of the installed `store-studio` plugin. Run commands from the store workspace.

Run bundled helpers by their absolute paths from the root of the store workspace. Resolve `scripts/` and `references/` next to this `SKILL.md`. Set `SKILL_DIR` to that skill directory in the shell examples below.

## Workflow

1. Start or update a spike under `stores/<store>/spikes/<YYYY-MM-DD-slug>/`.
2. Create or update `RESOURCES.md` with source links, local reference files, generated images, intermediate images, scripts, and commands worth preserving.
3. Keep source inputs in `references/`, generated print files in `assets/print/`, previews in `assets/previews/`, intermediate explorations in `assets/intermediate/`, and social drafts in `social/`.
4. Generate transparent PNGs for print. For Printify-style shirts, default to `4500x5400`.
5. Use `references/composition-best-practices.md` before judging layout, hierarchy, typography, contrast, scale, or garment placement.
6. Always create a preview composited on the target shirt color. Do not judge transparent art without a garment-color preview.
7. Record quality status in the store spike index before finishing.

## IA-Referencias Learned Defaults

When the target store is `stores/ia-referencias/`, read the store identity and style memory before rendering: `stores/ia-referencias/IDENTITY.md`, `stores/ia-referencias/GRAPHIC_STYLE.md`, `stores/ia-referencias/DESIGN_STYLES.md`, `stores/ia-referencias/products/index.md`, and recent accepted product or spike notes that match the concept.

For short AI/dev slogans, default to the documented `vector-icon-text` / Clear Text + Simple Vector family. Start with at least three variants inside the same family:

- `stacked-lockup`: direct stacked typography with one small vector accent.
- `badge-emblem`: compact badge or seal that keeps the phrase dominant.
- `restrained-ui`: simple editor, terminal, cursor, prompt, or icon composition where the UI supports the phrase.

Treat the direct typographic lockup as the first hypothesis. Recent accepted and rejected mockups show that dense editor/terminal panels often shrink the joke on real product images, so a panel route must prove it reads better than the direct lockup at thumbnail scale.

Keep the design to one main phrase and at most one supporting phrase. Decorative logs, code panels, screenshots, or fake UI chrome must not carry critical meaning. Use deterministic/scripted text for final print PNGs; natural-language image-model text is only a rough visual reference and is not production art. When a user asks to run a layout through an image generator, use the generated result only for composition direction, record the useful takeaway in `RESOURCES.md`, then redraw the final typography/icon layout deterministically with a cache-safe variant name.

Default `ia-referencias` tee previews should use dark garment colors and strong contrast. When moving from prototype to product, prefer Bella+Canvas 3001 / Printify Choice via `create-printify-product` unless the spike documents why a cheaper or different garment is better.

Use real Printify mockups as the final composition judge. For compact phrase-led lockups, start Printify placement iteration around scale `1.18-1.35`; recent accepted references include `Slop Code By Myself Tee` at scale `1.35`, `Zero Days Full Safety Sign` at scale `1.32`, `Zero Days Security Issue` at scale `1.18`, and `Token Efficient Person` at scale `1.34`. Large two-sided front/back typography may need more aggressive scale, but only if real mockups prove it does not crowd the collar, seams, or hem. Full-canvas or panel designs may need lower scale. Record the selected route, scale, and rejection notes in `RESOURCES.md`.

For vertical back-print stacks with an icon, large headline, divider, and small final line, inspect a close crop of the real mockup around the changed area before accepting. If the final line reads too close to the headline, lower it and/or reduce it instead of shrinking the whole design. If the PNG crop is complete but the real Printify mockup clips the small final line, first reduce back placement scale and move the placement upward before redrawing the art. Compute divider and subline placement from the rendered alpha bounding box, not nominal font line height, because display fonts often extend below their measured text box. Move the superseded proof into `assets/intermediate/` with the rejection reason.

## Historical Character Quote Workflow

Use `references/historical-character-shirt-workflow.md` when the request is to make a polera/shirt around a historical, public-domain, or iconic character with:

- top text above the figure,
- the figure centered as the main visual,
- bottom text below the figure,
- a requested visual style,
- user approval before Printify upload, and
- post-approval Printify mockups plus campaign/model imagery.

The approval gate is part of the workflow: present the composed shirt image and garment preview to the user before uploading to Printify. After explicit approval, use `create-printify-product` to upload the exact approved PNG, create or update a draft product, poll real Printify mockups, and save downloaded shirt mockups before building campaign assets.

## Shirt Art Defaults

- Prefer transparent PNG for the final print asset.
- Treat garment color as the background. Do not bake the shirt color into the final PNG unless explicitly requested.
- Start every serious design with one primary hook, one secondary support, and one clear tone. If the first read is unclear at thumbnail scale, simplify before polishing.
- Keep full-front adult compositions chest-high and centered by default. Avoid low belly placement, collar crowding, side-seam crowding, and full-canvas poster rectangles unless intentional.
- Leave practical breathing room around the artwork. For `4500x5400` shirt assets, reserve the outer 8-12 percent as a default safety margin unless the concept is deliberately oversized and mockups prove it works.
- Use 1-2 fonts for most text-led shirts, 3 only with a clear hierarchy reason. Make the main hook the largest and boldest text.
- Prefer high-contrast ink against the chosen garment color, and preview on that garment before judging quality.
- Avoid tiny details, thin critical strokes, paragraphs of text, and ornaments that disappear in a 300 px wide thumbnail preview.
- For violet shirt designs, use a preview base around `#a682db`.
- For terminal/radial designs, use pixelated rectangular blocks with subtle blur, no random noise, and text drawn as terminal-style monospace with slight chromatic offsets.
- For radial wave designs, keep dark wave thickness and gap thickness equal unless the user requests otherwise.
- For black-shirt terminal designs, let the shirt supply the neutral black terminal background. Remove or fade neutral black/gray screenshot pixels, but preserve intentional UI affordances such as a command input shadow row as semi-transparent ink.
- When preserving a terminal command row on a transparent asset, keep the row full-width, low-contrast gray, and redraw subtle prompt markers such as `>` if transparency cleanup removes them.
- For reference-derived terminal art, keep proportions faithful: selected labels should be centered under their pointer, highlights should barely exceed the text, and option labels should remain comparable to the original UI scale.
- When patching text over an existing terminal wavefield, clone nearby texture under the old text before redrawing so the repair does not create a flat rectangular patch.
- Generate both variants when useful:
  - `clean`: complete radial circles without clipped wave starts.
  - `fill`: waves continue across the full canvas and may be cut by edges.

## Terminal Radial Script

Use `scripts/render_terminal_radial_shirt.py` for the ultracost-style terminal radial layout.

Example:

```bash
python "$SKILL_DIR/scripts/render_terminal_radial_shirt.py" \
  --output stores/ia-referencias/spikes/2026-05-31-ultracost-radial-shirt/assets/print/ultracost-clean-4500x5400.png \
  --preview stores/ia-referencias/spikes/2026-05-31-ultracost-radial-shirt/assets/previews/ultracost-clean-preview.png \
  --label ultracost \
  --bottom "xhigh + workflows" \
  --mode clean
```

Fill-canvas variant:

```bash
python "$SKILL_DIR/scripts/render_terminal_radial_shirt.py" \
  --output stores/ia-referencias/spikes/2026-05-31-ultracost-radial-shirt/assets/print/ultracost-fill-4500x5400.png \
  --preview stores/ia-referencias/spikes/2026-05-31-ultracost-radial-shirt/assets/previews/ultracost-fill-preview.png \
  --label ultracost \
  --bottom "xhigh + workflows" \
  --mode fill
```

Important parameters:

- `--width 4500 --height 5400`: print target.
- `--y-frac 0.31`: moves the art upward in the print area.
- `--radius-ref 350`: clean-circle radius in reference coordinates.
- `--square-cell-ref 12.5`: simulated radial cell size.
- `--draw-cell-ref 6`: rendered block sampling size. Lower means smoother circles with more blocks.

## Quality Gate

Check these before marking a spike accepted:

- Final PNG is transparent and at target size.
- Preview exists on the actual garment color.
- Composition passes `references/composition-best-practices.md`: one clear first read, readable hierarchy, enough breathing room, strong contrast on the garment, and chest-appropriate placement.
- For black-shirt terminal assets, inspect a black-background crop to confirm the terminal background is transparent while command-row shadows, separators, purple panel, and UI text remain visible.
- Text is not unintentionally cropped.
- Main label is readable at product-thumbnail scale.
- Radial waves match the requested rule: complete circles for `clean`, full canvas for `fill`.
- No stray blocks, noise, or accidental background color in the print PNG.
- Use a cache-safe final filename after visible copy or alpha changes so review tools and Printify do not show stale images.
- For Printify checks, use Playwright by default. Upload the exact final PNG, select the target garment color, maximize width without clipping, capture a screenshot or downloaded mockup, and record DPI/layer width when Printify reports it.
- For programmatic shirt mockups, use `create-printify-product`: upload the validated PNG, create a draft product, poll `product.images`, and download real front mockups. Treat print-area SVG placement assets as intermediates, not final mockups.
- For Etsy-bound shirt pricing, use `$SkillsDir/create-printify-product/references/etsy-pod-pricing.md` and `$SkillsDir/create-printify-product/scripts/calculate_etsy_pod_margin.py`; do not approve price from Printify gross margin alone.
- For historical-character quote shirts, do not upload to Printify until the user has explicitly approved the composed top-text / figure / bottom-text design and its garment-color preview.
- For accepted `ia-referencias` shirts, promote the selected print PNG into `stores/ia-referencias/products/<product-slug>/` and `stores/ia-referencias/assets/approved/<product-slug>/`; keep rejected Printify proof images out of `assets/previews/` and summarize them in `RESOURCES.md`.
- `RESOURCES.md` lists useful links, local reference files, intermediate outputs, final print files, previews, and generation commands.
- Spike index has a clear status: `in_progress`, `accepted`, `rejected_quality`, `rejected_concept`, or `paused`.

For more detail, read `references/print-assets.md` and `references/composition-best-practices.md`.

For Printify catalog/product selection, API payloads, and reference-image mockups, use `create-printify-product`.
