# Production and QA

## HyperFrames path

Use the project's pinned HyperFrames CLI. For a Line World composition, follow
the `line-world-hyperframes` skill and its project runner. The official
[quickstart](https://hyperframes.heygen.com/quickstart) and
[render contract](https://github.com/heygen-com/hyperframes/blob/main/skills/hyperframes/SKILL.md)
are the authority for version-specific behavior.

Typical sequence:

```sh
npx hyperframes init my-video --skip-skills
npx hyperframes check --json
npx hyperframes preview
npx hyperframes render --output output.mp4
```

Run project checks in the generated project directory. Check the installed CLI
help before assuming a flag exists. Preserve user dimensions rather than taking
framework defaults. Use timed clips, a paused registered timeline, local assets
and deterministic time. Expose editable text and source media. Keep voice, music
and effects on distinct identified audio tracks. Requesting the finished file
authorizes rendering after review; follow the user's existing permission scope.

## Self-contained browser path

Use this path for small graphics productions when HyperFrames is unavailable
or the user chooses a plain browser renderer. Requirements: `uv`, FFmpeg and
FFprobe on PATH; Playwright Chromium installed for the declared Playwright
package. Install the browser only in an authorized environment:

```sh
uv run --with playwright python -m playwright install chromium
```

Copy `assets/templates/kinetic-starter.html` from this skill into the task
workspace and replace its content, layout and motion with the analyzed rules.
It uses system fonts and no remote assets. Set all visible properties from
`window.renderAt(seconds)` so seeking backward produces the same frame. Avoid
timers, unseeded randomness, autonomous CSS animation and wall-clock state.
Use the supplied viewport for the exact requested dimensions; keep media local.
Await fonts and images before capture. If using video/canvas, explicitly finish
seeking and drawing before the async `renderAt` resolves.

```sh
uv run --script <skill-dir>/scripts/render_html.py index.html --output output.mp4 --width 1080 --height 1920 --fps 30 --duration 12
uv run --script <skill-dir>/scripts/render_html.py index.html --output voiced.mp4 --width 1080 --height 1920 --fps 30 --duration 12 --audio mix.wav
```

Use even pixel dimensions for H.264/yuv420p. Choose duration and fps whose
product is an integer frame count; the renderer samples `0..(N-1)/fps`.
Keep a visible final hold before the endpoint. HTML audio is not recorded;
provide a finished local mix through `--audio`. The script pads/trims that mix
to the output. For dialogue, measure the track first and make the shot plan fit,
so automatic trimming does not remove words. The renderer produces an MP4 and
validates its media properties; it does not judge storytelling or similarity.

For images, use an already connected image generator or existing local assets.
For voice, use supplied recordings or an authorized provider such as Fish Audio.
For music/effects, use local or licensed assets and time cues to visible actions.
Do not invent MCP endpoints or claim an unconnected provider ran. The public
[Pixabay API documentation](https://pixabay.com/api/docs/) describes image and
video search; do not assume it exposes a music/sound download API.

## Delivery checks

1. Probe the actual MP4: width, height, frame rate, frame count/duration and audio
   stream presence must match the brief. Compare duration within one frame.
2. Make a contact sheet from the final output with `inspect_video.py`. Inspect
   opening, each distinct shot, transition midpoints and the last visible hold.
3. Seek the editable HTML at those times in a browser when text is dense. Check
   clipping, contrast, safe areas, missing images/fonts and overlapping text at
   final output size. A layout intentionally cropped during a transition should
   settle into a readable state.
4. Compare output frames with the source observations. State which measured
   rules transfer and which differ. Do not call a generic scaffold a style match.
5. Watch motion or inspect denser adjacent frames. For audio, listen for cut-off
   words, clicks, unintelligible mixing and cue drift; use FFmpeg peak/loudness
   measurements as additional evidence. Report unperformed listening honestly.
6. Write concise QA notes with commands, observed results, evidence paths and
   limitations. Deliver the source, recipe, asset records and final file. A
   provider outage may justify a provisional silent draft only when the user
   accepts silence; otherwise report the missing deliverable explicitly.
