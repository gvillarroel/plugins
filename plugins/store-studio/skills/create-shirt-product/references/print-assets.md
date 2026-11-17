# Print Asset Reference

In these examples, `$SkillsDir` is the absolute `skills` folder of the installed `store-studio` plugin. Run commands from the store workspace.

## Store Context

The workspace manages two stores:

- `dibujos-infantiles`: products based on children's drawings.
- `ia-referencias`: products based on AI, developer, terminal, model, and workflow references.

Keep product concepts, assets, and social drafts separated by store. Shared scripts and neutral references can live under `shared/`.

## Shirt Deliverables

For each serious shirt spike, produce:

- `assets/print/<name>-4500x5400.png`: transparent production PNG.
- `assets/previews/<name>-preview.png`: preview composited on shirt color.
- `assets/intermediate/`: iteration images worth keeping for later comparison.
- `README.md`: concept, source, files, status, and open questions.
- `RESOURCES.md`: source links, local references, generated image inventory, scripts, commands, and iteration notes.
- `social/drafts.md`: initial social copy variants.

`RESOURCES.md` is required. It should be enough for a future agent to continue the prototype without reading the original chat.

## Printify Product Notes

Before generating assets for a known Printify product, check `shared/references/` for a product-specific note. For Gildan 5000 / Unisex Heavy Cotton Tee, use:

`shared/references/printify-unisex-heavy-cotton-tee-gildan-5000.md`

For broader Printify product candidates and reference mockup images, use:

- `shared/references/printify-catalog-2026-05-31/catalog-summary.json`
- `shared/references/printify-catalog-2026-05-31/product-details/`
- `shared/assets/references/printify-products/manifest.json`
- `$SkillsDir/create-printify-product/references/preview-templates.json`

Key extracted sizes:

- Front/back: `3951 × 4919 px`
- Sleeves: `960 × 960 px`
- Inner neck label: `750 × 750 px`

## Ultracost Radial Learnings

The ultracost prototype came from a terminal screenshot reference with:

- The final black-shirt version should be a transparent `4500x5400` PNG; black fabric supplies most of the terminal background.
- Preserve intentional terminal UI structure even when removing neutral screenshot backgrounds. In the current final pass, the grey command input row behind `/hallucinate` is restored as semi-transparent ink, including the subtle `>` prompt.
- Text should say `ultracost`, not `ultracode`.
- The section title can be rethemed (`Hallucination` in the current version), but patch old text by cloning nearby wave texture before redrawing to avoid a flat repair block.
- Black terminal bars from the screenshot should generally be removed, except intentional UI affordances such as command input rows or separator lines.
- Radial pulses should originate around the `ultracost` label and create circularity.
- Pixelated blocks should emulate terminal rendering, not random noise.
- Dark wave and clear gap should both be four simulated cells unless changed.
- The clean variant should not start a new wave if it would be clipped.
- The fill variant intentionally ignores edges and uses all available print space.
- Preserve original proportions for reference-derived terminal UI: the selector arrow aligns to the center of the selected label, the selected highlight barely overhangs the text, and option labels stay small enough to read as terminal UI rather than a logo.
- Use cache-safe final filenames after changing visible text or alpha behavior; otherwise Printify/browser previews can show stale assets.
- Real Printify checks should use Playwright by default, save both the uploaded final asset path and review evidence under `assets/previews/printify-page/`, plus DPI and print-layer width if visible.
- Chrome plugin upload is a fallback for Printify, not the default. If it is used and local file upload fails, enable local-file access for the Codex Chrome Extension or switch back to Playwright/API upload.

## Validation Notes

Use Pillow to inspect outputs:

```bash
python - <<'PY'
from PIL import Image
for path in ["asset.png"]:
    im = Image.open(path).convert("RGBA")
    print(path, im.size, im.getchannel("A").getbbox())
PY
```

Use visual previews for product judgment. A transparent PNG can look empty or misleading without the garment-color composite.

For quick catalog-image previews, use the Printify skill:

```bash
python "$SkillsDir/create-printify-product/scripts/build_reference_preview.py" \
  --template-key tops.tshirt_front \
  --art asset.png \
  --output preview-on-reference.png
```
