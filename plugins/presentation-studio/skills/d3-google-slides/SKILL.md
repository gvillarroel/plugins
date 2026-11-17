---
name: d3-google-slides
description: "Transfers D3 visuals and collections to Google Slides. Preserves editable charts, curves, maps, and frozen animation states, with verified raster layers, original HTML links, and timed media when needed."
---

# D3 to Google Slides

1. Use the supplied settled SVG or trusted local D3 HTML. If D3 is available and the visual needs authoring, use it to build and validate the source. Preserve its data, draw order, labels, colors, and aspect ratio. For motion, use `--selector` and `--wait-ms` to capture each requested settled state.
2. For a new deck with curved paths, use the [editable PPTX route](references/vector-fidelity.md). It preserves supported curves as individual custom shapes, including compound holes. For a gallery, mixed set of artifacts, several animation states, or media links, follow [collection and motion delivery](references/collection-delivery.md).
3. For an in-place edit, run `uv run --script <skill-directory>/scripts/prepare_slides.py --help`. Identify the slide object ID, native page size, and frame in points (12,700 EMU per point). Use a distinct ID prefix. The batch keeps simple marks as individual shapes, lines, or text. Complex paths become grouped native geometry at the requested `--path-tolerance`. Check the [geometry contract](references/vector-fidelity.md) before choosing a fidelity mode.
4. Choose `--mode editable` when native editability is required. It reports unsupported visible features as errors. Use `--mode auto` when the user accepts a whole-visual PNG fallback, or `--mode image` when the user wants a faithful static capture. The `--pptx` flag on `prepare_slides.py` packages an image snapshot. Use `editable_pptx.py` for a vector deck.
5. For an authorized live write, follow [Google Slides delivery](references/slides-delivery.md). Read back the actual object types, text, and order. Inspect a native thumbnail against the browser preview. For a local handoff, return the requested files and the representation used.

Example for a settled SVG on a known widescreen slide:

```sh
uv run --script <skill-directory>/scripts/prepare_slides.py chart.svg --slide-id target_slide --id-prefix quarterly --frame 36 70 648 300 --mode auto --preview out/chart.png --batch out/slide-batch.json --report out/transfer-report.json
```

Google Slides lays out native text with its own font metrics. Check wrapped labels and the smallest marks at the target size. SVG interactions remain in the original HTML. Use an authorized link to that source when viewers need interaction.
