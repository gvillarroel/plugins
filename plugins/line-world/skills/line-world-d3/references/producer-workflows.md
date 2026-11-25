# D3 video operations

Use real D3 for the geometry that needs it. The copied runtime includes original
builders/exporters and their assets, but a synchronized SVG group is the normal
video output. Do not invoke a full dashboard or logo studio to get a simple mark.

## Signed comparisons and dated series

For two to eight categories, use the existing `records` array and a shared unit.
Each nonzero bar grows to the right or left of a common zero. A zero has a dot
on the baseline. An explicit null has a missing-value label and an empty mark.
Set `signed` to show plus signs, or `focus` to keep one entity selected.

```json
{"title":"Weekly change","unit":"Price change (%)","duration":8,"signed":true,
 "records":[{"id":"equity","label":"Equities","value":-3.2},
            {"id":"bonds","label":"Bonds","value":1.6},
            {"id":"cash","label":"Cash","value":0},
            {"id":"other","label":"Other","value":null}]}
```

For a trend, supply one series with two or more distinct, increasing ISO dates.
Values are spaced by elapsed UTC days. A null breaks the line and adds a mark
on the missing-data rail. Include an explicit null when a scheduled observation
is missing. An irregular interval between two supplied values simply joins those
observations. The headline shows the value on the final calendar date, including
its missing status. Supply `locale` for the numeric and date labels.

Use `"revealObservations": true` to tell the story chronologically. The axes and positions are fixed from frame zero. Each point or missing mark appears when the cursor reaches its date, and the value and date above the plot follow the latest revealed record. The complete series stays visible through the last 35 percent of the clip. The ordinary `line_world.py from-brief` route uses this mode for a time-series binding.

```json
{"kind":"time-series","id":"air","title":"Temperatura exterior","unit":"°C",
 "duration":8,"locale":"es-ES","observations":[
  {"date":"2026-01-01","value":-2.5},{"date":"2026-01-02","value":1.1},
  {"date":"2026-01-06","value":null},{"date":"2026-01-10","value":3.4}]}
```

```text
uv run --script <skill-root>/scripts/video_chart.py build --data data.json --project film
uv run --script <skill-root>/scripts/video_chart.py export --project film --svg film/asset.svg --screenshot review/frame.png --receipt review/receipt.json
uv run --script <skill-root>/scripts/video_chart.py export --project film --width 390 --height 844 --at 4 --svg review/mobile.svg --screenshot review/mobile.png --receipt review/mobile.json --mp4 review/mobile.mp4
uv run --script <skill-root>/scripts/test_video_chart.py -v
```

Build in a new directory. The project ships its own D3 runtime and opens from
disk. `--at` selects the SVG and PNG reading pose. Optional MP4 export needs
FFmpeg and renders the whole scene from clock zero at 24 fps by default.
Builds keep the 1920×1080 default for existing callers. Mobile viewports stack
labels and values above each quantitative mark and keep the unit visible.
The full plugin embeds its OFL-licensed Space Grotesk in the HTML and exported SVG for numeric values and labels. Headings retain their serif family. A standalone copy of the D3 skill can also run with system fonts. The date below the last value is positioned from actual text bounds with at least six SVG pixels of clearance.

The comparison moves one emphasis stroke and one marker over a complete,
stationary value bar. Each focus window has a reveal followed by a still hold.
The time series draws the line, advances a date guide and moves the date cursor.
Across a missing interval only the two date cues advance. The export records
the focus ID, screen coordinates, phase and active elements every second and
compares rendered track geometry every eighth of a second. It also measures
font size, label clearance, source values, visible numbers, solid paint, signed
scales, calendar positions, line gaps and repeated seeking in a real browser.
An export with a failed check returns a nonzero status and writes the receipt.

## Data and geometry

Use `d3.select(...).selectAll(...).data(records, d => d.id).join(...)` with stable
IDs. Use `scaleLinear` for measured positions and lengths, `scaleBand` for
discrete slots, `line`/`area` for ordered observations, `hierarchy` plus `tree`,
`pack`, `treemap` or `partition` for nested records. Use `Delaunay.from` for
neighbor/cell views and `geoPath` with a declared projection for geographic data.

Seed `randomLcg`; stop and pre-tick force simulations. Preserve one canonical
dataset, equal units and shared domains across linked representations. Keep
source record IDs on marks and expose sensible focus ports above labels.

The runtime inventory is available in `assets/vendor/` and the exact palette
in `assets/palettes/video-colors.json`. Both selectors start with primary red
and light and medium neutrals. Extended colors follow them in `colorset2`.
Locate actual filenames before wiring the
project; copy only the runtime files needed by the output. Keep all output
outside the copied skill bundle.

## Time contract

Build settled geometry once. Let `renderAt(t)` update reveal, selected paint,
markers or camera state from project timing. Use the parent's pure clock when
embedded. Keep controls in a separate preview. Export an SVG from the rendered
state after flattening computed presentation and local font dependencies.

## Useful pairings

Use table + bars/dumbbells for precise comparison, timeline + lines for events
and change, hierarchy + treemap/pack for membership and magnitude, Sankey +
matrix for direction and exact transfers. Do not add all possible chart types
to a production scene merely because the library supports them.

## Checks

Measure text and native bounds after fitting. Check zero values, shared scales,
missing data, direct labels, focus linkage, meaningful transitions and repeated
seeking. Check exact palette on actual computed paint, not source declarations.

Primary API references: [D3 API](https://d3js.org/api),
[hierarchy](https://d3js.org/d3-hierarchy),
[Delaunay](https://d3js.org/d3-delaunay).
