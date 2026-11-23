# First short narrated film

For a 15–20 second narrated explanation, make one local HTML scene and run the
narrated composer. The linked `line_world.py init` starter produces a silent
seven-beat comparison with a minimum duration of 21 seconds. For a runnable
two-scene example with graphics, audio cues and the same composer, see
[Circuito narrado](../assets/examples/narrated-circuit/README.md).

The commands use PowerShell, uv, FFmpeg, FFprobe
and a local Chrome, Edge or Chromium installation. The audio script supports
Python 3.11–3.13. The example selects 3.13. Piper reuses its verified local
model if present and otherwise downloads it on first use. To use an existing
recording, add `file` to the scene in the audio recipe. It can also take
sentence marks. See the [audio recipe](../../media-use/audio/references/scene-audio.md).

Start PowerShell in the installed Line World directory containing `plugin.json` and
`skills/`. Save its location, then select a writable project directory. For example:

```powershell
$plugin = (Get-Location).Path
$project = Join-Path $HOME 'line-world-projects/first-film'
New-Item -ItemType Directory -Force -Path "$project/film" | Out-Null
Set-Location -LiteralPath $project
```

## 1. Write and time the voice

Create `film/voice.json` with a single scene and one idea per sentence. Keep the
scope of the example in the narration and write `Datos sintéticos` beside the
values in the picture. This recipe uses an invented change from 8 s to 6 s.

```json
{
  "voice": "es_MX-claude-high",
  "scenes": [
    {
      "id": "ahorro",
      "text": "En este ejemplo, la carga baja de ocho a seis segundos. La diferencia es de dos segundos: eso es lo que dejamos de esperar. Esos dos segundos son una cuarta parte de los ocho iniciales: un veinticinco por ciento menos."
    }
  ]
}
```

```powershell
uv run --script "$plugin/skills/line-world-video/scripts/narration_review.py" --story film/voice.json --output film/narration-review.json
uv run --python 3.13 --script "$plugin/skills/media-use/audio/scripts/scene_audio.py" film/voice.json --out film/audio
```

The narration review accepts the audio recipe's `scenes[].text` and older
stories' `scenes[].script`. If a scene has both, their values must agree.
Review the spoken text even if the scan flags no lines. Check
`audio/timeline.json` for the actual duration before laying out the visuals.

## 2. Draw the comparison and place the guide

Author `film/scene.html` with a white SVG `#stage` at the intended dimensions.
For this example, show gray bars on a common scale for 8 s and 6 s, then place
`8 s − 6 s = 2 s` and `2 s ÷ 8 s = 25 %` on separate rows. Keep those labels
still. Use a #9e1b32 guide and a short reveal of the difference and proportion
marks as the voice reaches each calculation. Omit a heading unless requested.
The two colors and simple geometry fit [colorset1](color-priority.md).

```powershell
Copy-Item "$plugin/skills/line-world-video/assets/runtime/focus.js" film/focus.js
```

Load `focus.js` in the HTML. Bind the comparison, difference and proportion
groups by `data-focus-id`. Mark the circle `id="guide"`. Use
`LineWorldFocus.port` and `route` with a reserved left lane that clears
every label. Set subsequent cue arrival times from the relevant
`absolute_start_sample / sample_rate` in the measured timeline. Expose an
optional `window.ready` promise to compute geometry after the fonts load.
Implement `window.renderAt(seconds)` to derive the dot and marks from that
argument alone, returning the focus ID and position for repeat-seek checks.
Use the [focus contract](speech-focus.md) for exact helper signatures.

Focus inspection uses a 1920 × 1080 browser viewport. For a small test, give
the SVG its actual width and height in CSS pixels so the inspection still
checks text at delivery size. Listen to the voice and include the cue arrivals,
two mid-travel positions and the final hold in the sample times.

## 3. Bind the edit to the measured clock

Create `film/attention.json` with `fps`, `frames`, `tracks` and `beats`.
Compute `frames = ceil(master.samples × fps / sample_rate)`. Give the guide
and the relation marks distinct normalized `box: [x,y,width,height]` tracks.
Cover frame 0 through `frames` with adjacent half-open beats. Use
`mode: "motion"` with both tracks in `moving` during travel and the mark
reveal. Use `mode: "read"` with an empty `moving` array during the holds.
Each beat names a `focus` and `idea`. Add a cue
`{"scene":"ahorro","sentence":0}` for each phrase that overlaps the beat.
`sentence` is zero-based. Compute that coverage by rounding the start down and
end up from the phrase's absolute sample positions. If a phrase spans two
beats, include it in both.

Create `film/film.json`. The paths in this file are relative to its directory.

```json
{
  "width": 480,
  "height": 270,
  "fps": 12,
  "language": "spa",
  "audioTimeline": "audio/timeline.json",
  "attention": "attention.json",
  "assets": ["focus.js"],
  "scenes": [{"id": "ahorro", "title": "Ahorro de tiempo", "html": "scene.html"}]
}
```

The scene ID must match the audio recipe. Add any local fonts, scripts or
data files needed by the scene to `assets`. See the
[narrated production contract](narrated-production.md) for full score fields.

## 4. Preflight, inspect and export

```powershell
uv run --script "$plugin/skills/line-world-video/scripts/compose_narrated.py" film/film.json --preflight --report film/preflight.json
uv run --script "$plugin/skills/line-world-video/scripts/inspect_focus.py" --html film/scene.html --times 0,4.3,4.46,5,9.16,9.34,15.5 --output film/focus-review.json --screenshot film/preview.png
uv run --script "$plugin/skills/line-world-video/scripts/compose_narrated.py" film/film.json --browser msedge --output film/final.mp4 --report film/export.json
```

The example inspection times come from one measured local voice. Replace them
with the times from your audio. Use `--browser chrome` or `--browser chromium`
if that browser is installed instead of Edge. A failed focus audit gives
the text or mark to move before export. If the encoded movement audit needs a
correction, use its frame and track name to compare the observed motion with
the declared score.

Open the finished MP4 and inspect the first comparison, both cue arrivals
and the final hold. Check that the synthetic-data label and units remain
visible and that the subtitles match the line being heard. The export report
must show `ok: true` and `published: true`. Preserve the HTML, data, voice
recipe, measured timeline, attention score and actual reports with the MP4.
