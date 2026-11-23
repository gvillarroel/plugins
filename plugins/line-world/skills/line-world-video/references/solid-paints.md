# Source paint review

Keep authored geometry and labels opaque and solid. Use a flat fill, a
hard-edged shape or an outline to distinguish surfaces and states. Keep the
original appearance of photos, footage, and screenshot artwork.

Install `assets/runtime/review-solid-paints.js` with Playwright's
`page.add_init_script(path=...)` before the scene navigates. The inspector
captures Canvas 2D paint calls from page startup and reads computed HTML and
SVG styles after seeking. An ordinary CSS/Canvas antialiased outline remains
an opaque source paint.

```javascript
async ({seconds, frame}) => {
  window.lineWorldPaintReview.begin(frame);
  await window.renderAt(seconds, frame, window.lineWorldScene);
  if (document.fonts.status === "loading") await document.fonts.ready;
  return window.lineWorldPaintReview.inspect();
}
```

The result has `frame`, `surface`, `covered` and `findings` fields. Each
finding has `kind`, `target`, and `detail`. The kinds are `gradient`,
`pattern`, `shadow`, `opacity`, and `filter` for a blur. Correct the
identified paint where it is authored and seek back to the affected frame.

- A viewport-size `canvas[data-export-surface]` uses `canvas-2d` coverage.
  The inspector reads fill, stroke and text calls, and tracks paints on
  instrumented offscreen canvases copied into the export. A full clear or
  opaque replacement of the entire surface removes previous observations.
- A viewport screenshot uses `dom` coverage for computed HTML and SVG styles
  and any visible instrumented 2D canvases. The inspector resolves local SVG
  paint servers, visible uses of local definitions, authored CSS gradients,
  diffuse shadows, blur, and partial color or group alpha.
- A viewport-size canvas with another context reports `canvas-unsupported`
  and an empty `covered` array. Review its authored geometry separately.

Known image and video elements and raster inputs to `drawImage` retain their
source treatment. Coverage is based on author styles and instrumented drawing.
Review complex clipping and occlusion, worker-owned or WebGL canvases, raster
assets and filter graphs in the actual output where relevant.

Run `uv run --script scripts/test_solid_paints.py` from the skill directory
for the Chromium regression checks.
