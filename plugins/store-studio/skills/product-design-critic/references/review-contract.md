# Review contract

In these examples, `$SkillsDir` is the absolute `skills` folder of the installed `store-studio` plugin. Run commands from the store workspace.

## Evidence and confidence

| Evidence | Supports | Does not establish |
| --- | --- | --- |
| Artwork | Copy, hierarchy, alpha, edges, intended colors | Placement, fabric, print quality |
| Schematic product | An approximate relationship between art and surface | Supplier placement or realistic folds |
| Supplier mockup | Supplier-rendered placement and variant appearance | Physical ink, feel, fit, durability |
| Physical sample photo | Visible result on that sample under those conditions | Every size, color, batch, or wash outcome |
| Campaign | Message, framing, visibility of the offered product | Authentic product geometry if generated without verified references |
| Buyer behavior | Observed behavior for the tested audience and conditions | A universal sales forecast |

Keep unknowns distinct from failures. A valid print PNG can still be a weak design; an attractive campaign can conceal an unproven product. The script below prepares evidence. The reviewing agent supplies visual interpretation and creative judgment.

## Compact report

1. Brief, stage, assets inspected, provenance, and self-review status.
2. Verdict at that stage and what is worth retaining.
3. Findings, each with location, observable evidence, consequence, targeted change, tool, and check.
4. Ranked next iterations and conditions for moving forward.
5. Untested claims and evidence that could change the decision.

Do not force every criterion into a score. If a score is explicitly requested, show the rubric and evidence per criterion; a critical failure cannot be averaged away.

## Reproducible viewing evidence

Run from the repository root:

```powershell
python "$SkillsDir/product-design-critic/scripts/build_review_evidence.py" --manifest PATH_TO_MANIFEST.json --out-dir PATH_TO_FINAL_REVIEW_DIRECTORY --report PATH_TO_REPORT.json
```

Requires Python and Pillow. All paths must remain inside this repository. Image paths in the manifest are relative to that manifest. This tool neither calls image-generation services nor modifies source art. It writes versioned review boards, one per group, and a JSON measurement report. Choose a new output directory when an earlier review should be preserved.

```json
{
  "title": "A named review",
  "font_path": "C:/Windows/Fonts/arial.ttf",
  "widths": [300, 600],
  "small_text_risk_px": 8,
  "items": [
    {
      "id": "example-art",
      "group": "example",
      "image": "../assets/print/example.png",
      "kind": "artwork",
      "provenance": "Deterministic source export; not a product proof",
      "background": "#121415",
      "regions": [
        {"label": "Essential punchline", "box": [100, 900, 1900, 1030]}
      ]
    }
  ]
}
```

The optional `font_path` is a read-only font dependency and may be outside the repository; no fonts are copied. Omit it to use Pillow's bundled default. IDs and group names are filename-safe slugs. `widths` has one or two distinct values between 100 and 1200. `kind` is one of `artwork`, `schematic_product`, `supplier_mockup`, `physical_sample_photo`, `campaign`. `provenance` is required but is a declaration to verify, not authenticated by the script.

For a contact-sheet source, supply `crop: [left, top, right, bottom]` and `crop_note` that identifies the complete product cell and excluded material. Coordinates for both crops and text boxes refer to the original source image. The script rejects boxes outside the declared crop rather than silently clipping them. Never crop to only the design when labeling a view as the complete product.

The script reports the projected height of supplied text-region boxes at each viewing width. Label these as bounding-box projections, not measured human readability or x-height. The default 8 px threshold is a **review warning**, not a pass/fail standard or proof of print failure. It neither recognizes text nor infers what is important. Include complete critical regions and inspect the resulting image; omitting regions does not mean there are no problems.

Boards preserve image aspect ratios and the declared framing, with one row per image and one column per target width. Review them at 100% or open individual image areas at native size; fitting an entire board to a narrow window changes the apparent pixel size. Only source images are resampled; review headings sit outside them. Reports include SHA-256 hashes for traceability and explicitly leave aesthetic quality, product acceptance, and sales unassessed.

Run `python $SkillsDir/product-design-critic/scripts/test_review_evidence.py` to verify framing/scale behavior, rejection of hidden clipping, and protection of source files and the repository boundary. These tests exercise the evidence tool, not the quality of an agent's taste or the market appeal of a product.
