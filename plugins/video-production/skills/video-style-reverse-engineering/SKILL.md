---
name: video-style-reverse-engineering
description: Discovers strong video references, compares public performance within comparable cohorts, organizes editing styles and explains evidence-backed mechanisms. Applies timestamped style recipes to original scripts, motion graphics, reels or footage. Use for video style research, reference-led recreation, contact-sheet analysis or consistent batches.
---

# Video Style Reverse Engineering

Find useful references with observable performance, organize their editing
styles, then make original videos from the resulting recipes. Preserve the
user's chosen format and tools. A tutorial about editing is process evidence;
use the actual example clips for style evidence.

## Workflow

1. Establish the deliverable: analysis, reusable style recipe, finished video,
   batch, or a packaged style skill. Record exact output paths, script language,
   dimensions, fps, duration, supplied footage, and audio requirements. Infer
   reasonable defaults when optional details are absent; record them.
2. Research before choosing a new style. Search current examples unless the
   task fixes the references or forbids browsing. Use the user's topic/platform;
   otherwise state a useful scope inferred from the task. Read
   [performance research](references/performance-research.md) to build a
   dated shortlist, verify metrics and compare channel-relative performance.
   For supplied or collected metric snapshots, run the bundled ranking helper
   to create `ranked.json`; do not rewrite its arithmetic or peer policy:

   ```sh
   uv run --script <skill-dir>/scripts/rank_references.py research.json --output ranked.json
   ```

   Keep familiar classics and new releases separate. For a new script using an
   established recipe, reuse its research instead of repeating discovery.
   Collect about three comparable clips per promising family when available,
   including typical or weaker controls; fewer clips mean lower confidence.
   Read [reference acquisition](references/acquisition.md) for downloads.
3. Probe each local reference and create a timestamped contact sheet:

   ```sh
   uv run --script <skill-dir>/scripts/inspect_video.py reference.mp4 --output-dir analysis/reference-01 --samples 12
   ```

   Inspect the sheet and selected frames visually. Check short ranges around
   entrances, cuts, emphasis and exits: evenly spaced stills alone cannot prove
   easing, sound timing or shot boundaries. Increase sampling or extract a short
   range with FFmpeg when needed. If visual inspection is unavailable, label
   visual observations unverified and produce a provisional recipe only.
4. Organize the researched clips using [the style library](references/style-library.md):
   keep a source-linked candidate table, comparable rankings and style cards
   explaining visible mechanisms, likely benefits and confounders. Order the
   families by evidence and suitability for the user's task; never imply a
   universal winner across formats. Then write `style.json` for the selected
   family using [the style contract](references/style-contract.md).
   Separate observed facts, inferred rules and proposed additions. Tie rules to
   timestamps and frame paths. Describe typography, layout, palette, pacing,
   motion, transitions, image treatment and audio separately; mark unknowns.
   Public views do not establish retention, conversions or why a video won.
   Label mechanism explanations as hypotheses unless direct evidence supports
   them. Never infer exact fonts from appearance alone.
5. Map the new script into timed shots before rendering. Reuse the editing
   grammar with original words and assets. Fit narration to its measured audio
   duration; reserve reading time and a final hold. For existing footage, keep
   the spoken words, sync and intended cuts coherent with the new overlays.
6. Produce editable source and render the requested video. Prefer HyperFrames
   when it is available or requested; read [production and QA](references/production.md).
   Optional image, voice and sound providers are interchangeable. Existing local
   assets or a graphics-only production remain valid without paid connectors.
   When HyperFrames is unavailable and the task allows it, use the self-contained
   browser renderer and [kinetic starter](assets/templates/kinetic-starter.html):

   ```sh
   uv run --script <skill-dir>/scripts/render_html.py index.html --output output.mp4 --width 1080 --height 1920 --fps 30 --duration 12
   ```

   The starter is a neutral scaffold, not an analyzed style. Adapt it to the
   recipe. The renderer requires FFmpeg, FFprobe and Playwright Chromium; setup
   and the deterministic `renderAt(seconds)` contract are in the production guide.
7. Inspect the actual output, correct visible or audible failures, and deliver
   the editable source, video, style recipe and concise QA evidence. A successful
   encode does not establish style fidelity. For a batch, freeze the shared
   recipe, validate one complete item, then render and check every requested item.

## Reuse and scope

Keep the reusable recipe separate from each episode's script, assets and timing.
For a requested style-specific skill, package compact rules, a parameterized
starter and only necessary runtime resources. Keep downloaded references and
generated videos in the task project. Use an available skill authoring workflow
when appropriate; the recipe and renderer here also work independently.

Use authorized local files, accessible references and permitted assets. Preserve
creator/source/license records for reused media. Public visibility alone does
not establish reuse permission. Do not clone a person's voice without their
authorization. Do not add account connections, paid generation, publishing or
global skill installation unless the user's task authorizes that action.

The method follows [the source tutorial](references/source-method.md). Read that
reference only when explaining its seven steps or checking tool-specific claims.
