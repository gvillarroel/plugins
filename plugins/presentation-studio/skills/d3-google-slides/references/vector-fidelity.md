# Editable vector fidelity

## New deck with custom curves

Use the editable PPTX exporter and import it into Google Slides. Pass one settled SVG or local HTML source per slide. Use a common canvas and frame when sources form a deck. The default is 720 × 405 points. Supply `--page-size` and `--frame` in points, with 72 points per inch.

```sh
uv run --script <skill-directory>/scripts/editable_pptx.py --help
uv run --script <skill-directory>/scripts/editable_pptx.py --source sankey.svg --source partition.svg --output out/editable.pptx --preview-dir out/source-previews
```

- Native text boxes retain readable text, font, size, weight, and alignment. The destination may substitute fonts or reflow labels, so inspect its render.
- Straight lines, rectangles, and ellipses remain simple objects. Supported filled and stroked paths use DrawingML custom geometry. Cubic and quadratic Béziers retain their control geometry, and elliptical arcs are encoded as cubic segments.
- Compound paths preserve nonzero winding. The exporter normalizes supported even-odd contours. When exact contour normalization is ambiguous, it uses a polygonal region with the same fill topology and reports the approximation. Arbitrary dashes and transformed strokes can become editable filled outlines.
- Common start and end arrowheads from a local SVG marker with one solid filled path remain editable shapes. Complex markers and middle markers require a different representation.
- Simple horizontal or vertical linear gradients on unrotated shapes preserve stops, padding, and opacity. Radial, diagonal, referenced, or transformed gradients require another representation.
- Import through the connected Drive presentation action or an authorized Drive conversion client. Check that custom marks arrive as shapes, including any shape whose type is omitted by the readback. Compare the native thumbnail to the source preview for lost holes, arc clipping, gradient direction, stroke style, or missing text. A custom path may move and recolor as a whole. Inspect the editor before promising control-point editing.

Use the minimal DrawingML `a:path` geometry attributes and set paint on the shape. A writable native Slides API shape preset has no request field for arbitrary SVG path commands. Import is the route that carries those commands into the deck. [Slides createShape](https://developers.google.com/workspace/slides/api/reference/rest/v1/presentations/request#CreateShapeRequest) [Drive file conversion](https://developers.google.com/workspace/drive/api/guides/manage-uploads#convert_to_google_workspace_types)

## In-place native batch

- Rectangles, ellipses, straight lines, and single-line text use native primitives when the geometry fits. Source rotations and independent solid fill and stroke opacity are preserved. A D3 circle symbol represented by two arcs can remain an ellipse.
- More general fills and strokes are flattened at `--path-tolerance` in source CSS pixels (default 0.45), clipped to the captured viewport, and tessellated into affine Slides triangles. Fills respect nonzero and even-odd winding. Stroke geometry preserves supported dash lengths, rounded dots, caps, joins, and affine placement.
- Multiple pieces of a source mark become one selectable group. Ungroup to edit constituent shapes. Tight acute corners, small marks, and translucent mesh boundaries can show subtle seams at slide size. Increase tolerance for very dense source geometry if the complexity limit is reached. Inspect the shape counts and tolerance in the transfer report.
- To preserve custom geometry when reusing part of an existing deck, import the editable PPTX as a new presentation and copy or import the desired slides using the Slides editor. Use the direct batch when the existing page and its surrounding contents need an in-place edit.

## Unsupported effects

Composite opacity on an overlapping group, filters, masks, most SVG clipping paths, gradients outside the supported subset, styled text spans, external HTML overlays, and JavaScript behavior require source-specific handling. Keep image fallback explicit when the user requires editability. When an SVG visual is intentionally rasterized, preserve the whole captured composition, aspect ratio, and alternative text.
