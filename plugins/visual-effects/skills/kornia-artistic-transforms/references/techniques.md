# Executable techniques

These ten keys are implemented by the bundled runner. Parameters shared by the CLI are `--seed`, `--strength`, `--scale` and `--palette source|ink`; implementation-specific effective settings are recorded in its reports. Use one image to compare techniques, then vary one control before comparing new images.

| Key | Construction | Useful visual question | First adjustment |
| --- | --- | --- | --- |
| `quadtree-engraving` | Adaptive rectangular subdivision and local directional engraving. | Can variable cell size and mark direction build the subject? | Increase scale for larger, clearer marks; reduce strength if details disappear. |
| `region-hatching` | Lab color regions and region-dependent hatch fields. | Can a small set of pigment regions carry the composition? | Compare source color against ink; inspect thin regions and boundaries. |
| `ink-strata` | Alternating oblique ink layers with controlled local offsets. | Can bands, silhouette and negative space become the main structure? | Tune scale before strength; broad bands are a different composition, not a resolution fix. |
| `linked-cells` | Adaptive cells, tonal cavities and neighboring connections. | Can occupied and empty space reconstruct the image? | Inspect both dark and light areas; retain cell coverage on odd dimensions. |
| `hex-halftone` | Hexagonal sampling with tone-dependent mark coverage. | Can a regular screen make the tonal structure readable? | Set mark scale for the intended display size. |
| `flow-stitch` | Directional stitch-like marks guided by local structure. | Can orientation and stitch density suggest form? | Reduce mark density on small faces and thin lines. |
| `hybrid-mezzotint` | Ordered and seeded stochastic tonal marks. | Can grain carry shadows while reserving light? | Hold seed fixed while adjusting strength; inspect at 100% and thumbnail size. |
| `contour-strata` | Displacement or layered treatment derived from tonal contours. | Can contour layers create a graphic relief? | Reduce strength around eyes, lettering and narrow architecture. |
| `directional-glass` | Regionally directed refractive-style sampling. | Can local directional displacement produce useful facets? | Look for smear and doubled edges; reduce strength before adding sharpening. |
| `cell-facets` | Cellular reconstruction with local planes or faceted color. | Can larger pieces organize a busy image? | Compare fine and coarse scales while holding the source and palette fixed. |

## Four useful starting constructions

### Adaptive engraving

Derive grayscale, smoothing and spatial gradients with Kornia. Use rectangular quadtree leaves selected by local tonal variation. Assign each leaf a stable orientation from the gradient or structure tensor. Rasterize line coverage, crosshatching or reserved paper with the leaf bounds enforced.

Preserve leftover rows and columns when splitting odd dimensions: use half-open bounds `[x0,x1) × [y0,y1)`, splitting each axis independently. A low-coherence region needs a stable fallback direction. Do not let an uninitialized leaf become accidental black paper.

### Pigment regions with writing

Convert RGB to Lab, cluster a bounded sample and assign the working pixels to color centers. Reduce duplicate centers on low-color images. Order centers consistently before assigning hatch angles, so a label permutation does not arbitrarily change the image. Preserve region boundaries as a reserve or contour only when they improve the intended construction.

The clusters are color groups, not semantic segmentation. A region is not automatically a leaf, face or building. An ink palette is a graphic choice; it is not calibrated printing output.

### Alternating ink strata

Define oblique strips in pixel coordinates. Alternate silhouette, tonal screen and paper reserve. If offsetting strips, sample with an explicit boundary mode and preserve the full canvas. Scale displacement, strip width and seam width together. Keep the source and strip phase fixed while assessing a parameter change.

### Linked cavities

Build an adaptive partition. Draw pieces and internal reserves whose areas depend on local tone. Connect compatible neighbors using a bounded distance and alignment rule. Separate piece size from cavity ratio: enlarging a hole and enlarging a cell produce different readings. In a narrow rectangle, use each cell's actual width and height.

## Implementation attribution

Kornia supplies image-space operations such as grayscale, Lab conversion, blur, gradients and coordinate sampling. Partition rules, region clustering, hatch fields, seeded grain, stitch geometry, cavities, neighbor graphs and compositing are authored procedures. A method using Kornia filters is not necessarily a built-in Kornia artistic effect.

These renderers include discrete labels, thresholds, geometry and rasterization. Do not describe them as differentiable end to end. “Glass,” “mezzotint,” “stitch” and “ink” describe digital appearances; no physical refraction, embroidery, chemical etching or press calibration is asserted.

Official API references: [Kornia color](https://kornia.readthedocs.io/en/latest/color.html), [filters](https://kornia.readthedocs.io/en/latest/filters.html), and [geometric transforms](https://kornia.readthedocs.io/en/latest/geometry.transform.html). Follow the installed API and the bundled tested versions when examples in newer documentation differ.
