---
name: kornia-artistic-transforms
description: Applies reproducible Kornia and PyTorch artistic transformations to supplied raster images, including adaptive engraving, pigment regions, halftones, stitches, ink strata and cellular mosaics. Supports ordered combinations, comparison galleries and feedback-led iteration while preserving image proportions. Use for algorithmic image reinterpretation and technique exploration; generative image creation, SVG tracing and measured depth reconstruction are separate tasks.
---

# Kornia Artistic Transforms

Transform an existing image into deliberate graphic constructions. Deliver actual renders and reproducible settings. Use the bundled CPU runner; no trained model, original demonstration images or external project is required.

## Choose the treatment

Inspect the source and the requested outcome before selecting recipes. Preserve the complete composition unless a crop is requested. Separate the user's chosen style from personal preferences inferred in another project.

- For a compact comparison, start with `quadtree-engraving`, `region-hatching`, `ink-strata` and `linked-cells`. They explore different mechanisms: local mark direction, pigment regions, alternating ink bands and connected negative space. They are starting points, not universal aesthetic winners.
- For a specific look, read only [the ten executable techniques](references/techniques.md). Tune scale and strength before accumulating more effects.
- For a new construction, read [composition and extended recipes](references/composition.md). This distinguishes the executable set from additional methods that need implementation or extra inputs.
- For transparency, unusual color modes, tiny images or final-size exports, read [input handling and visual quality](references/input-and-quality.md).
- When selections or ratings are supplied, read [review and learning](references/review-and-learning.md) before changing an active collection.

## Render

Resolve the script from the loaded skill directory. The examples below assume that directory is `skills/kornia-artistic-transforms`; replace that prefix with its actual location when installed elsewhere. Write results in the active workspace, outside the skill bundle.

The script declares its Python and CPU dependencies for `uv`. First use may install them. This isolated environment does not install Pillow, NumPy or Kornia into an ambient `python`. For an additional image-check script, declare its own uv dependencies, for example `uv run --with pillow --with numpy python check.py`. Inspect `--help` or `--list` instead of reading the complete engine for ordinary use.

```sh
uv run --script skills/kornia-artistic-transforms/scripts/artistic_transform.py --list
```

Render one exact output, with its reproducibility report beside it:

```sh
uv run --script skills/kornia-artistic-transforms/scripts/artistic_transform.py input.jpg -o engraving.png --technique quadtree-engraving --seed 42 --max-edge 1024
```

The default single-image report replaces the PNG suffix with `.json`. When the user requests an exact different JSON path, pass `--report that-path.json` during rendering; do not guess a `.meta.json` default or rename self-referencing reports afterward.

Create independent alternatives from the same original:

```sh
uv run --script skills/kornia-artistic-transforms/scripts/artistic_transform.py input.png --output-dir comparison --techniques quadtree-engraving,region-hatching,ink-strata,linked-cells --seed 42
```

The batch creates PNGs, `source.png`, `manifest.json`, `contact-sheet.png` and a local responsive `gallery.html`. `--techniques all` renders all ten methods. For several source images, use a separate output directory for each source; keep each source hash and its results together.

Resolve paths using each document's location: `manifest.json` output entries use collection-relative paths such as `images/001-quadtree-engraving.png`; the report inside `images/` uses its own directory as the base, such as `001-quadtree-engraving.png`. These records are not literally identical JSON objects. Compare their substantive metadata and resolved artifacts, not unnormalized path strings.

Repeat `--technique` to compose ordered stages into one image:

```sh
uv run --script skills/kornia-artistic-transforms/scripts/artistic_transform.py input.png -o combined.png --report combined.meta.json --technique region-hatching --technique directional-glass --strength 0.65 --scale 1.2 --seed 42
```

Order matters: the second stage analyzes the first stage's result. Compare each constituent against the combination. For a construction whose partitions and marks must both follow the untouched source, implement parallel branches and merge them explicitly rather than presenting a sequential composition as equivalent.

## Preserve the input contract

- Default resizing limits the long edge to 1024 pixels and preserves aspect ratio; it does not crop or upscale. Use `--max-edge 0` for the oriented source dimensions. Re-render at final size rather than enlarging a preview and claiming restored detail.
- Keep `--scale` separate from output size. It scales marks, cells and displacement relative to the short edge. Luminance thresholds remain dimensionless.
- Preserve alpha by default. The runner anchors the input alpha to the original canvas while transforming RGB; geometric displacement does not claim to warp the cutout. Use `--background FFFFFF` only when flattening onto that background is wanted.
- The runner refuses source overwrite and existing targets. Choose a fresh output path; use `--overwrite` only for an authorized replacement of generated artifacts.
- Read the report's orientation, input mode and alpha policy. Do not silently convert an animated sequence, HDR image or color-managed print source into an equivalent still-image claim.

## Review and deliver

Use the bundled verifier for artifact, path, metadata, decoded-pixel hash and source-alpha checks instead of reimplementing those checks in ad hoc shell snippets:

```sh
uv run --script skills/kornia-artistic-transforms/scripts/validate_art.py comparison/manifest.json --input input.png --expect-count 4
```

It also accepts individual report JSONs, including several reports in one call. Pass the actual original with `--input` so its bytes, dimensions and alpha are independently checked. Without that input, source verification remains explicitly limited. This checker does not grade taste or infer whether a treatment is beautiful.

Inspect the contact sheet and at least the relevant full-size outputs. Look for unintended crop, lost silhouette, empty cells, halos, clipped highlights, illegible mark density, deformed small features and resampling blur. Check the original and result together at display size. Flat or intentionally subtle sources are valid; contrast and pixel distance are diagnostics, not taste scores.

When a gallery is requested, open the local HTML or provide a contact sheet through an available display surface. A loopback URL is only accessible on the computer serving it. Use an available hosting workflow only when requested; creating these artifacts does not itself publish them.

Return the actual outputs, their technique names, important settings and material limitations. Keep source hashes, seeds, ordered stages and parameters in the reports. Mark new candidates as unreviewed until the user rates them. Preserve supplied notes and distinguish accepted, explicitly rejected and merely unselected work.
