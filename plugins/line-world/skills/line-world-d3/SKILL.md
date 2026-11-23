---
name: line-world-d3
description: Creates data-driven SVG charts, linked views and seeded geometric layouts specifically for Line World videos. Use inside the video plugin when D3 geometry must fit full-frame sections, share entity focus and follow the parent clock with sparse line styling.
---

# Line World D3

Create the data geometry for the film. Read the bundled
[video contract](references/video-contract.md) before choosing marks or styling.

1. Identify the viewer question, exact records, units, stable entity IDs and
   shared domains. Prefer one precise view and a complementary representation.
2. Use the real bundled D3 runtime for joins, scales, shapes, hierarchy, force,
   geography or spatial layouts. Keep the generated project offline. Seed
   random layouts and settle forces before beginning the film clock.
   For signed comparisons or dated observations, start with the bundled
   `uv run --script <skill-root>/scripts/video_chart.py --help`, then use its
   `build` and `export` commands with `uv run --script`, including help calls.
   It reflows labels and marks for portrait and landscape. Supply the records
   and units, then export at the actual viewing dimensions. For example, use
   `--width 390 --height 844` for a portrait clip. Dated observations preserve
   elapsed calendar time and explicit gaps. See the [input formats and export commands](references/producer-workflows.md).
3. Author the chart as a semantic SVG group in the parent composition, or as an
   editable standalone SVG/HTML with native bounds and focus ports. Use thin
   structural strokes on a white field. Give small objects borderless gray
   bodies, with primary-red active bodies and readable white internal text.
   Keep large grouping shells white with discreet outlines.
   Avoid importing a logo studio, catalog chrome, dashboard cards or a title
   banner into the movie.
4. Bind marks with `data-entity-id`. Show essential axes, units, values and
   compact legends. Keep a common zero and domain when comparisons require it.
   Preserve missing observations and do not animate a misleading interim scale.
5. Expose pure `renderAt(seconds)` updates. In moving passages, choreograph two
   or three related elements and keep the reading pose still. The bundled
   export checks the geometry of each movement and records focus every second.
   Let the parent own reveal, camera,
   duration, pause and seeking. When the parent is unavailable, provide a small
   local preview with transport controls outside the SVG.
6. Inspect rendered bounds, pairwise labels and repeatable seeking. Export the
   settled geometry and a receipt with data, units, palette and producer version.

The copied [producer workflows](references/producer-workflows.md) and their
references remain available for a specific API, builder or exporter. Their
standalone logo studios, default titles and gallery presentation are not
the video art direction. Use custom D3 groups for synchronized video geometry;
do not carry a supported standalone document's UI into the film.

Read [gentle motion](references/gentle-motion.md) for static image/group motion.
Keep quantitative geometry fixed and move connected groups as one assembly.
