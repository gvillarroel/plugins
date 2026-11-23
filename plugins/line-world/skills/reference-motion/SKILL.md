---
name: reference-motion
description: Analyze a video or a dated channel corpus with rea-video, connect observed transitions and graphic elements to source timestamps, and reuse their mechanics as editable Line World components.
---

# Reference motion

Use this skill when the brief names reference videos and asks to reuse their editing or graphics in a new film. It contributes a source-linked motion library to `line-world-video`. For editorial reference discovery and channel-relative performance comparisons, use the companion `video-style-reverse-engineering` skill.

## Use the motion library

Generate new assets from a JSON recipe with the bundled [generator](scripts/generate_motion.py). The model supplies text, data, local images and editorial choices. The script owns drawing, timing, palette and export checks. Run from this skill directory. Paths for recipes, exports and reports belong to the production workspace.

```sh
uv run --script scripts/generate_motion.py init data-chart /path/to/film/chart.json
uv run --script scripts/generate_motion.py render /path/to/film/chart.json /path/to/film/chart.png
uv run --script scripts/generate_motion.py render assets/ejemplo.json /path/to/film/comparison.mp4
uv run --script scripts/generate_motion.py verify assets/ejemplo.json /path/to/film/comparison.mp4
```

Use `init` for any of the 23 graphics or 10 transitions in the [gallery](assets/demo.html). For a sequence create one ordered scene list. Assign the handoff to its destination. Hold the data or image long enough to read it. Use exact colorset1 paints, stable identities and a single forward change for each editorial purpose. Preserve a link to the [source observations](references/patterns.json) when reusing a measured mechanism.

For a percentage, `chart-ring` holds the stated value while the arc and its marker trace the corresponding share. A series of bars grows in groups of up to three, separated by a quarter-second pause. Run `python scripts/test_chart_attention.py` after changing the drawing or timing of either chart.

For occasional transitions keep ordinary joins as cuts. In longer edits mark a meaningful destination with `handoff` (`section`, `comparison` or `detail`). Read the exported `transition_audit` for the chosen effect, its reason and source-frame interval. One-scene graphics can develop in place. For a comparison, `data-chart.focusHold` keeps the selected value, bar and category fixed as context appears. For an end card, `detailScale` adjusts the size of the final action. [Recipe fields and pacing](references/usage.md)

When critiquing completed examples, apply rea-video to the encoded MP4s. Match the detected boundaries and motion beats to decoded before, during and after frames, the editorial decision list and the reading size. Record specific defects with timestamps. After changing the generator, repeat the analysis on the revised files and compare the same observable features. [Encoded example review](references/analysis.md#review-an-exported-example)

On export, inspect the actual PNG or MP4 and its adjacent QA report. After editing a component, run `audit-library report.json --sheet sheet.jpg` with the same script, inspect the contact sheet and render the affected sequence. The [usage guide](references/usage.md) covers the input contract, browser dependencies, examples and tests. The [study](references/equifax-study.md) and [inventory](references/equifax-corpus.json) document the original source material.

## Analyze a new reference

1. For a channel, inventory every public video, Short and stream replay in the requested publication interval. Deduplicate by video ID and record unavailable items. For individual source files, record their provenance and duration.
2. Follow the [analysis workflow](references/analysis.md). Use the pinned [rea-video launcher](scripts/rea.py) on source footage. For sampled sources, preserve the source timestamps and label the sampling interval in every finding.
3. Inspect before, during and after each candidate transition. Record the layout, changing elements and persistent elements at each step. When frames support it, measure duration, motion direction, onset, overlap and settle. Record each recurring visual element with its bounding box, layers and relative size.
4. Build an evidence index linking each reusable pattern to its video ID, timestamp or interval, evidence type and measured parameters. Keep configurable design choices explicit, especially when several timing curves fit the observed frames.
5. Implement each component against a seekable clock, with caller-supplied text, colors and media. Use original demo assets. Show the incoming state, midpoint and outgoing state in the demo. Route the chosen components into the Line World scene plan and validate the export at the project's delivery frame rate.

For a corpus, count each video once per pattern. Report the analyzed count alongside the channel inventory, and name the entries or portions for which the requested evidence could not be obtained. Keep the original source links with the library so future editors can verify a behavior before adapting it.
