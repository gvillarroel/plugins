# Input handling and visual quality

## Prepare a working image

Orient the image before measuring or resizing it. EXIF orientation can exchange width and height. Preserve all of the oriented composition with one uniform resize factor; never force an arbitrary rectangle into a square. Pillow's [EXIF transpose](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose) applies the orientation transform and removes the orientation metadata it handles.

For new implementations, represent color as float RGB in `[0,1]`, normally a `1×3×H×W` tensor for Kornia. Keep masks and alpha separate. Derive `H`, `W` and grids from the actual input. Keep intermediate sample sizes proportional too: a square thumbnail used inside clustering can distort spatial structure even when the final output is rectangular.

Use short-edge units for artistic distances, for example `unit = min(H,W)/640 × scale`. Scale radii, hatch periods, line widths, seam widths, displacement and smoothing distances coherently. Do not multiply tone thresholds, color ranges or coherence thresholds by that unit. Clamp rasterized thickness to a meaningful minimum at tiny sizes and record effective settings.

## Alpha and color

The bundled default preserves the oriented, resized alpha on the same canvas while transforming RGB. It does not deform the transparency silhouette with a geometric treatment. During analysis it fills fully invisible RGB from the nearest nonzero-alpha pixels, preventing arbitrary hidden colors from contaminating clustering and gradients; output alpha stays unchanged. If an artwork needs a warped cutout, transform its alpha with the same sampling map in a new, explicitly recorded implementation.

Use `--background HEX` to flatten only when a paper or other opaque background is intended. Do not silently replace transparency with black. Review on both light and dark backgrounds when an alpha edge is important.

The comparison page and contact-sheet framing use Colorset 1 neutrals and red. These interface paints are separate from the artwork: source-color treatments retain their regional colors, while `ink` selects an explicit dark-teal, rust and paper study preset. Neither mode claims exact colorset remapping of source pixels or color-managed press output.

L and LA inputs can be expanded to RGB while retaining luminance and alpha. Palette images may contain transparency. Do not assume that all Pillow modes have sRGB semantics: CMYK, ICC-tagged print sources, 16-bit data and HDR require a color-managed conversion or an explicit limited-input policy. Read the runner's reported conversion policy; prepare an sRGB PNG separately if exact color handling is required. A convenient `convert('RGB')` is not a calibrated proof.

Only process a selected still frame from an animated or multipage source. State the frame chosen; producing one PNG does not preserve animation. SVG/PDF inputs require a real renderer before this raster workflow; renaming their extension is not conversion.

## Numerical checks with artistic meaning

- A flat image is a legitimate input. A quantile normalizer should preserve its valid constant tone rather than mapping it to zero through an epsilon denominator.
- Few-color images need fewer distinct clustering centers. Label order should be stable if it controls angle or palette assignment.
- Rectangular quadtree leaves must cover each pixel exactly once, including odd final rows and columns.
- Small dimensions can invalidate reflection padding or a large kernel. Bound kernels or use an intentional fallback; do not enlarge the user's source without recording it.
- Verify finite pixels and readable outputs. Measure clipping and change from the source to diagnose failures; do not use fixed contrast or image-distance thresholds to reject intentional white paper, subtle effects or abstract work.
- Keep source bytes and generated results distinct. Refuse input/output aliasing, including symlink aliases, and decide collisions before writing a multi-file batch.

## Visual review

Inspect at intended display size as well as 100%. Ask whether the treatment produces the intended mark system, readable regional organization and useful negative space. Check texture-scale aliasing, solid-black collapse, blown highlights, border halos, transparent-edge contamination, small-feature loss and unintended resampling blur.

A face, building or line drawing can tolerate different deformation. Treat these as image-specific artistic decisions rather than inferring semantics from a generic gradient field. Compare an abstraction against its own visual goal; retaining photographic detail is not always the goal.

For final export, re-render from the source at the requested dimensions with coherent style scaling. Preview enlargement adds pixels without restoring source detail. For material output, test actual size and support separately from screen previews.
