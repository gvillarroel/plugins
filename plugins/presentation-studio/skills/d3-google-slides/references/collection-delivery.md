# Collection and motion delivery

## Inventory the source

Use stable artifact IDs, then match each ID to one exact SVG or HTML selector, chosen state, and optional authorized original URL. Treat palette variants and capture states as distinct items. Reconcile the result with the inventory count before calling the collection complete.

```sh
uv run --script <skill-directory>/scripts/collection_slides.py --source local-gallery.html --selector '[data-example] .viz-frame > svg' --expected 225 --frame-seconds 4.6 --previews --output-dir out/gallery
```

Use `--manifest collection.json` for multiple documents, controlled state changes, or an exact case ID or link. Selector discovery derives IDs from markup and appends a source anchor to the original URL when it finds one. Manifest paths are relative to the manifest.

```json
{
  "cases": [
    {"id": "settled", "source": "chart.svg", "selector": "svg", "frameSeconds": 2.4},
    {"id": "detail", "source": "dashboard.html", "selector": "#detail",
     "select": {"#mode": "detail"}, "waitAfterMs": 400},
    {"id": "original", "title": "Interactive original", "link": "https://example.org/demo.html"}
  ]
}
```

Use `fragment` for a local hash ID or `click` for a trusted local control. For one HTML page with several captured states, use distinct IDs and frame times. A reference-only entry preserves a source report, metadata file, or original experience through an authorized HTTPS link. Keep the original locally when there is no authorized URL.

## Preserve editability and appearance

The collection exporter creates its output directory and writes ordered PPTX volumes and a `coverage.json` report. Use `--name sample` for volume names like `sample-01.pptx` and `--volume-size` to keep imports small. Use `--mark-limit` to bound the editable objects per visual.

In `--mode auto`, fully supported scenes use native objects. If a visible effect is outside the editable subset, the exporter isolates its top-level SVG paint unit and checks that the resulting layers recomposite to the original browser frame before retaining neighboring editable marks. The hybrid report records mean RGB error and the pixel count above the strong-difference tolerance after one pixel of edge smoothing. Dependent compositing, unknown geometry, and HTML or raster sources use a snapshot when required. The report distinguishes `editable`, `hybrid`, `image`, and `reference` and records object counts and fallback reasons. Use `--mode editable` to require editable visual content.

Use `--wait-ms` for initialization or JavaScript transitions. Use `--frame-seconds` from 0 through 60 to sample explicit SVG and CSS animation time. This freezes the browser's actual rendered animation state. It does not seek arbitrary application JavaScript, so drive that state with controls before capture. The single-visual batch and editable PPTX exporter accept the same frame-time option.

Keep the browser offline for trusted local source dependencies. For a known local gallery with decorative Google Fonts links, use `--system-fonts` to block those requests and use installed fonts. The collection report records blocked font URLs. Check the final title fit and typography in the destination.

## Fit the visual for presentation

Mark interactive chrome with `data-d3-export-ignore` or pass a specific `--exclude 'selector'` for trusted sources you cannot edit. Run state-setting controls first. Exclusions preserve layout and apply to the source preview, editable extraction, and raster layers. Review the selection so no data labels or necessary controls are accidentally removed.

Mark a top-level SVG paint unit with `data-d3-export-raster` when exact display lettering or source rendering matters more than editing that unit. Auto mode checks its isolated raster layer and keeps other eligible elements editable. Record the reason in the attribute value.

Use `data-d3-export-frame="x y width height"` on an SVG root for a deliberate crop in SVG user coordinates. The frame must fit inside the rendered SVG. Editable paths and fills remain native where the crop permits it. An intersected primitive or text box can require a snapshot, so check the report or use editable mode to reject it. For collections with excessive flat margins, opt into `--trim-padding`. The exporter keeps a margin around exact visible paint, limits enlargement, and retains the original frame if native primitives cannot be kept cleanly.

Check `framePt` for the actual visual rectangle in slide points and `sourceCropPx` for any cropped source pixel box. Compare against the clean PNG at final display size. Inspect projected text, overlaps, negative space, and title/footer separation in native previews. Use a deterministic layout gate for detectable defects and inspect the artwork to judge intentional whitespace and hierarchy.

## Keep interaction and timed playback available

Add the verified original HTML URL for true D3 interactions such as brush, zoom, tooltips, or custom playback. Use several linked states when the user wants to present branches or steps inside the deck. For visible timed playback, prepare a GIF or H.264 MP4 from the source and check that successive frames actually differ. Use an already authorized accessible GIF URL or a processed Drive video visible to the presentation audience.

```sh
uv run --script <skill-directory>/scripts/media_slide.py --slide-id existing-slide --id-prefix d3-demo --drive-video-id DRIVE_ID --video-size 1920 1080 --frame 20 30 680 320 --media-title "D3 motion" --html-url https://example.org/demo.html --link-frame 20 365 220 26 --output media-batch.json
```

Apply the media batch with a fresh revision and verify the native video or image element, geometry, link target, and accessibility description. Test playback in the presentation when available. A thumbnail can verify placement and visible content at one frame. Keep the editable state slide and the original HTML available when motion is required. [Google Slides media requests](https://developers.google.com/workspace/slides/api/reference/rest/v1/presentations/request#CreateVideoRequest)

## Verify the delivered scope

Check each volume's case order, slide count, image and editable object counts, and exact source links against `coverage.json`. Import each approved volume as native Google Slides and verify readback. Include native thumbnails for challenging paths, layered effects, typography, and media. Present a linked index when a delivery spans several volumes. A converted presentation has a 100 MB Drive import limit. [Google Drive file limits](https://support.google.com/drive/answer/37603)
