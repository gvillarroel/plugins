# Composition and extended recipes

The runner executes the ten techniques in the technique reference. The additional constructions below are implementation recipes, not extra CLI keys. Implement them inside the active project when requested; record their actual operations and validate them on that project's input.

## Decide what the combination changes

Use a small number of mechanisms with different roles:

1. **Structure:** regions, adaptive cells, tiles, facets, contours or depth layers when real depth exists.
2. **Mark:** points, hatching, stitch-like lines, grain, stamp coverage or ordered dithering.
3. **Surface and color:** a restricted pigment set, preserved source color, edge reserve or procedural paper.
4. **Geometry:** local displacement, strip offsets, homographies or remapping with declared boundaries.

Keep one role dominant. Compare the parent methods and the combination using the same source and seed. A large number of outputs or operators does not establish visual variety.

### Sequential composition

Repeated `--technique` flags process the previous result. `region-hatching → directional-glass` bends the authored pigment and line field. Reversing the order segments a displaced image. Both are valid experiments, but they have different meanings.

Applying a gradient-based method to a screen can make it follow the screen instead of the original subject. Use this deliberately; otherwise derive the guidance from the original and render branches in parallel.

### Shared-guidance composition

For adaptive cells plus stitches, derive the quadtree and structure tensor from the original. Use the cells to allocate resolution and the tensor to orient marks. Render both into one canvas. This is not equivalent to applying a full quadtree raster and then detecting its artificial boundaries as new subject structure.

For color regions plus engraving, derive labels and tone independently from the original, then constrain the engraving to those labels. Reserve a boundary only if it contributes to the desired image rather than tracing every color difference.

### Masked composition

Use edge strength, luminance, color labels or an authored mask to place a treatment selectively. These masks are image statistics unless a semantic model or manual annotation actually supplies object labels. Feather a mask in proportion to its working dimensions; preserve the user's alpha separately.

## Extended families

| Family | Reproducible construction | Important limit |
| --- | --- | --- |
| Aquatint and porous stamp | Smooth tone; apply seeded correlated noise or coverage thresholds; vary ink loss and paper reserve. | Retain seed and threshold. Do not manufacture grain to make a valid constant image pass a contrast threshold. |
| Crosshatching and wavy engraving | Use multiple periodic carriers with tone-dependent widths; modulate their phase or local orientation. | Anchor spacing in isotropic pixels; avoid thumbnail aliasing and accidental moiré. |
| Parallel line halftone | Convert tone to local line width or duty cycle along one carrier. | Screen spacing and line width are separate controls. |
| Ordered dithering | Compare reduced luminance against a normalized Bayer threshold matrix; enlarge with nearest sampling. | Bayer dithering is different from a camera's Bayer CFA color mosaic. |
| Visible color sensor mosaic | Sample channels on a CFA and reconstruct or expose the color grid. | Check the library's CFA convention; handle parity without cropping the source. |
| CMYK-style screens | Compute a declared approximate ink separation, use different screen angles, then composite a preview. | RGB multiplication is not an ICC-managed press separation. |
| Jacquard and woven frequency bands | Split low/high spatial frequencies; interleave them on warp/weft or checker supports. | Preserve the source's aspect ratio at every reduced working size. |
| Cross stitches | Sample tone and color on a grid, then draw paired diagonal marks with tonal width or length. | It is a raster stitch appearance unless actual stitch instructions are exported and checked. |
| Adaptive color mosaic | Split rectangles by variance or regional diversity; fill them with local colors and optional joints. | Guarantee complete coverage of odd and narrow dimensions. |
| Voronoi or weighted cells | Seed sites from a grid or content map; assign pixels to nearest or weighted sites; compute regional planes and seams. | A local neighbor approximation is not an exact global weighted tessellation. |
| Triangular collage and paper planes | Triangulate sites, reconstruct each piece with a palette or transformed local patch, and composite overlaps explicitly. | Declare whether pieces move, sample displaced texture, or merely recolor. |
| Parquet, folded grids and quilts | Partition the source and give pieces controlled affine or projective transforms. | Choose a fill rule for holes and overlaps; do not silently crop missing corners. |
| Contour-distance engraving | Detect contours, compute a distance field and turn isodistances into marks. | No detected contours requires a defined fallback; infinite distance must not generate invalid pixels. |
| Four nested shadow shells | Form cumulative tonal masks, optionally close them, then render differences between levels. | Thresholds are dimensionless. Discrete masks do not provide end-to-end gradients. |
| Phase/XOR screens | Combine two periodic binary grids so relative phase reconstructs local coverage. | Record phase, angle and period; distinguish tone reconstruction from optical display claims. |
| Shock refinement | Advance an explicit edge-aware sharpening equation on luminance and recompose color. | Bound step size and iteration count; check stability rather than assuming every iteration improves the image. |
| Residual rectangular reconstruction | Greedily place rectangular color updates where they reduce a declared image error. | Report the objective at the measured stage; drawing visible block borders afterward changes that objective. |
| Procedural paper and chemical patterns | Generate original noise, reaction-diffusion or texture fields and use them as a declared layer or source. | Do not call a synthetic texture a captured material measurement. |

## Additional-input methods

Some earlier artistic experiments require more than one still image. Do not infer the missing evidence from an arbitrary photo:

- **Temporal paint, optical flow and light accumulation:** require a real sequence, or an explicitly labeled synthetic animation. Stabilize patterns over time to avoid independent-frame flicker.
- **Depth bands, parallax and camera studies:** require measured, supplied, analytically constructed or explicitly estimated depth, with its convention recorded. Brightness is not measured geometry.
- **Cross-image collage and correspondence:** require a donor/reference image and a provenance entry for each source. A synthetic second view is not a second camera capture.
- **Perceptual optimization or style transfer:** requires a specified reference, objective, model/weights and actual optimization. Report loss and gradient evidence only when computed; decreasing loss is not aesthetic approval.
- **Audio-driven marks or multispectral studies:** require supplied signals, or clearly labeled synthetic signals. A false-color picture is not an infrared acquisition.
- **Physical printing, embroidery, projection and interactive installations:** separate the digital proposal, fabrication files and tests actually performed. A preview alone does not prove physical production.
