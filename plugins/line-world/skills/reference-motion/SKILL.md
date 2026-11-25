---
name: reference-motion
description: Choose an explanatory animation for supplied data or a concept, precompose an editable diagram on a shared clock, or study a reference video with rea-video and reuse its source-linked motion in Line World.
---

# Reference motion

Use this skill when choosing explanatory motion, building a reusable diagram, or adapting the graphics in a reference film. For editorial reference discovery and channel-relative performance comparisons, use the companion `video-style-reverse-engineering` skill.

## Choose and precompose a diagram

Start with [the shot decision guide](references/decidir-el-plano.md). Identify a claim the audience can check in the final pose. Map the original data or physical pieces to geometry, name one stable reference and identify the action that makes the relationship visible. Bind script phrases to editorial poses until you have a recording with measured cues.

When the explanation has a voice track, choose which pose belongs to each important mention. Distinguish arrival on screen, complete label, movement, result and renewed attention to an existing entity. Use the [pose and narration study](references/poses-y-menciones.md) and preserve measured word or phrase timing in the production request.

For ordinary new briefs, use the [transfer workflow](references/transferir-composicion.md) before drawing. It binds the viewer's question to the supplied records or concepts, retrieves comparable actions from forty observed passages, and produces editable geometry or a specialist handoff. Use it without waiting for the requester to name a study or a template. Preserve the reference's useful spatial or temporal relationship while using the new entities, quantities, units and reading time.

Start with what the viewer should be able to compare, follow or explain. When the movement is open, use the [animation selector](references/elegir-animacion.md) with the actual brief and available data. Give the proposed representation, what moves, what stays fixed and why that helps the viewer. Respect an animation the user has already selected. If two readings are plausible, describe the distinction and use the surrounding brief to resolve it when possible.

For an unfamiliar domain, identify the moving entity, the relationship and the evidence in the user's own terms. If a free-text query misses a clear relationship, select its explicit `--intent` from `--list-intents` and keep the original brief and data in the call. Distinguish an example that illustrates a mechanism from a drawing driven by the user's measured values.

Use the [precomposition guide](references/precomponer-diagramas.md) to build the selected relation as a timed unit. It includes a runnable example with editable content and a reading hold. Each component takes a local time from its parent. The same instant should restore the same pose after seeking backwards.

## Use the motion library

Generate new assets from a JSON recipe with the bundled [generator](scripts/generate_motion.py). The model supplies text, data, local images and editorial choices. The script owns drawing, timing, palette and export checks. Run from this skill directory. Paths for recipes, exports and reports belong to the production workspace.

```sh
uv run --script scripts/generate_motion.py init data-chart /path/to/film/chart.json
uv run --script scripts/generate_motion.py render /path/to/film/chart.json /path/to/film/chart.png
uv run --script scripts/generate_motion.py render assets/ejemplo.json /path/to/film/comparison.mp4
uv run --script scripts/generate_motion.py verify assets/ejemplo.json /path/to/film/comparison.mp4
```

Use `init` for any graphic or transition in the [gallery](assets/demo.html). For a sequence create one ordered scene list. Assign the handoff to its destination. Hold the data or image long enough to read it. Use exact colorset1 paints, stable identities and a single forward change for each editorial purpose. Preserve a link to the [source observations](references/patterns.json) when reusing a measured mechanism.

For a structural explanation, pick a diagram by the relation the viewer needs to follow. Use `field-packing` for fields and their occupied cells, `layer-preview` to link each layer to a cumulative result, or `isometric-layers` to separate members of a stack towards a side base. Carry a selected module from inventory into use and reveal its named inputs and outputs with `module-transfer`. Follow the same vertices from grid to surface with `vertex-remap`. Use `pass-strip` for the render passes of a single viewport and `command-lanes` for individual calls and their GPU intervals. With `import-footprint`, keep the full import on screen and highlight the cells occupied by each module in turn. Choose `shared-host` for one scene between two hosts or `split-clock` for independent schedules with a common display cadence. Set each diagram's labels in semantic order and use `duration` for the complete move. The diagram starts in its source pose on frame zero. [Diagram recipes and examples](references/usage.md#diagramas-de-estructura-y-ejecución)

For a percentage, `chart-ring` holds the stated value while the arc and its marker trace the corresponding share. A series of bars grows in groups of up to three, separated by a quarter-second pause. Run `python scripts/test_chart_attention.py` after changing the drawing or timing of either chart.

Use the user's entities for system diagrams. Determine whether links represent dependencies, alternatives, membership or recorded transfers before adding arrows or a traveling mark.

For occasional transitions keep ordinary joins as cuts. In longer edits mark a meaningful destination with `handoff` (`section`, `comparison` or `detail`). Read the exported `transition_audit` for the chosen effect, its reason and source-frame interval. One-scene graphics can develop in place. For a comparison, `data-chart.focusHold` keeps the selected value, bar and category fixed as context appears. For an end card, `detailScale` adjusts the size of the final action. [Recipe fields and pacing](references/usage.md)

When critiquing completed examples, apply rea-video to the encoded MP4s. Match the detected boundaries and motion beats to decoded before, during and after frames, the editorial decision list and the reading size. Record specific defects with timestamps. After changing the generator, repeat the analysis on the revised files and compare the same observable features. [Encoded example review](references/analysis.md#review-an-exported-example)

On export, inspect the actual PNG or MP4 and its adjacent QA report. After editing a component, run `audit-library report.json --sheet sheet.jpg` with the same script, inspect the contact sheet and render the affected sequence. The [usage guide](references/usage.md) covers the input contract, browser dependencies, examples and tests.

## Analyze a new reference

1. For a channel, inventory every public video, Short and stream replay in the requested publication interval. Deduplicate by video ID and record unavailable items. For individual source files, record their provenance and duration.
2. Follow the [analysis workflow](references/analysis.md). Use the pinned [rea-video launcher](scripts/rea.py) on source footage. For sampled sources, preserve the source timestamps and label the sampling interval in every finding.
3. Inspect before, during and after each candidate transition. Record the layout, changing elements and persistent elements at each step. When frames support it, measure duration, motion direction, onset, overlap and settle. Record each recurring visual element with its bounding box, layers and relative size.
4. Build an evidence index linking each reusable pattern to its video ID, timestamp or interval, evidence type and measured parameters. Keep configurable design choices explicit, especially when several timing curves fit the observed frames.
5. Implement each component against a seekable clock, with caller-supplied text, colors and media. Use original demo assets. Show the incoming state, midpoint and outgoing state in the demo. Route the chosen components into the Line World scene plan and validate the export at the project's delivery frame rate.

For a corpus, count each video once per pattern. Report the analyzed count alongside the channel inventory, and name the entries or portions for which the requested evidence could not be obtained. Keep the original source links with the library so future editors can verify a behavior before adapting it.
