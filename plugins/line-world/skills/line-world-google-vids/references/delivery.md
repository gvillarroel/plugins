# Verified native and cloud delivery

Use this procedure after native scene placement. Keep live account operations
in the supported connector or computer-use tool. The local utility compiles
evidence; it cannot observe or complete a cloud action.

## Finish a batch project

```text
uv run --script <skill-root>/scripts/vids_batch.py deliver --project film --video native-final.mp4
```

The first call creates `film/handoff/delivery-evidence.json` with false/unobserved
fields and returns status `collect-observations` (exit 2). Fill those fields
from actual observations, then repeat the same command. It writes a compact
`delivery.json`, a link-first `delivery.md` and `delivery-media.json`. Use
`--evidence another-receipt.json` for an existing journal. `next` reports missing
or stale delivery even when the upload queue is empty.

The command refuses delivery while order, speech or uploads remain pending.
It fingerprints the current story, source clip bytes, evidence and downloaded
MP4. Changed bytes or timing invalidate old results. The expensive full decode
is cached by MP4 hash and measured timing; changing cloud evidence alone does
not decode the movie again. Preserve receipts for older revisions.

## Finish an existing non-batch project

Use the actual ordered story with `clip` filenames and measured `clipSeconds`.
Numbered filenames such as `01-method.mp4` can differ from scene ID `method`.
Keep those filenames exact; matching is case-sensitive. Prepare once:

```text
uv run --script <skill-root>/scripts/vids_delivery.py prepare --story story.json --video native-final.mp4 --output delivery-evidence.json
uv run --script <skill-root>/scripts/vids_delivery.py check --story story.json --timing timing.json --evidence delivery-evidence.json --video native-final.mp4 --output delivery.json
```

`prepare` refuses to overwrite evidence. `check` returns exit 2 and specific
pending actions until complete; the report is still written for recovery.
The timing must have `status: measured-native-timing`, measured `duration` and
`fps`, as produced by `vids_plan.py compile`. The utility checks the entire file,
audio and total duration. Native inventory also checks every scene extent.

## Record only observed evidence

The generated template supplies IDs, revision, scene order and downloaded file
hash. Do not change false fields merely to make a check pass.

| Section | Required observations |
| --- | --- |
| `project` | Official Vids `url`, `observed: true`, `saved: true`, concrete `evidence` |
| `inventory` | `observed: true`, actual current `sceneButtonCount`; select each scene and paste its precise English native `announcement`; preserve `id`/`order` and set `visualReviewed: true` only after inspecting its pixels |
| `export` | Native action `source`, matching `projectUrl`, `observed: true`, exact downloaded `localSha256`, concrete `evidence` |
| `cloud` | `observed: true`, metadata for the actual exported MP4, `playbackObserved`, `downloadObserved`, visible `durationSeconds`, `durationResolutionSeconds` (at most 1), concrete `evidence` |
| `review` | `observed: true`, `speechAndJoins`, `contentThroughout`, concrete `evidence` from the actual movie |

Each scene must retain native audio. Inspect the correct replacement pixels,
since the same filename can hide an old version. Review speech endings, joins,
legibility, guide timing and content throughout; a successful decode alone cannot
prove them. Use the owning visual-review workflow for detailed pixel audits.

`export.source` accepts the observed `Google Vids File > Export to Drive` or
`Google Vids File > Download`. Record the actual path. Cloud metadata accepts
official `id`, `mimeType`, `size`, `webViewLink`, or normalized connector keys
`id`, `mime_type`, `size`, `url`. Require MP4, matching local byte size, and an
observed stable Drive URL whose file ID agrees with the metadata.

The player may display a rounded clock. For `3:28`, record `durationSeconds: 208`
and `durationResolutionSeconds: 1`; retain the exact local duration separately.
Do not claim that displayed rounding is an exact speech measurement.

## Find and verify a fresh Drive export efficiently

1. In Vids, use the current observed File > Export to Drive action and wait for
   readiness. The observed export appears under **Vids Exports**. Download the
   complete native MP4 too; record its actual destination.
2. Prefer the connected Drive tool for metadata. Discover only matching tool
   names/descriptions; inspect only the selected tool's full argument schema.
   If a fresh export is absent from one focused connector search, inspect the
   authorized Drive UI rather than repeating near-identical search calls.
3. Search Drive by the exact project name; open the MP4 result, not the Vids
   editor. Observe actual playback, its clock and the enabled Download control.
   Check the file title/type when several exports share a name.
4. Read the stable file ID from the observed URL or share dialog. If Copy link
   returns an empty clipboard, reobserve that UI; do not guess an ID. With a
   known ID, request only `id,name,mimeType,size,webViewLink` from metadata.
5. Keep the existing authorized identity and sharing restrictions. Stable Drive
   view URLs are suitable for delivery. Raw connector `file_uri` values may be
   structured objects; signed `download_url` values are temporary credentials.
   Do not print them or store them in documentation. Do not make a file public
   to work around an account mismatch.

Lead the user handoff with the verified cloud movie link and editable Vids link.
Include a local MP4 as an additional artifact when useful. The tool's `ready`
status means supplied observations and local checks agree; it does not prove
another account can access a private file, nor does it publish or share it.

## Check the exported subtitles

Inspect each fresh native download for subtitle streams, their language and
default/forced flags. Google Vids can include automatic captions with missing
scenes and mistranscribed prices even when the scene graphics and voice are
correct. A player can select that stream by default. Read every cue against the
spoken script, with particular attention to decimals, thousands, names, units,
negation and scene boundaries. Compare the full set of cues to the full set of
narrated scenes. Inspect timecodes against the actual speech.

For a project with an authored SRT, verify which track a player will select
even when the automatic and reviewed tracks share the same language. Run
this from your project directory using the installed plugin path. The receipt
lists candidate stream indices, default flags and any cue differences. A
changed line break or a one-millisecond discrepancy produces exit code 2.
The extracted WebVTT is available for reviewing the difference.

```text
python <plugin-root>/skills/line-world-video/scripts/caption_tracks.py native.mp4 extracted.vtt --language spa --compare-srt reviewed.srt --require-default --report captions-check.json
```

```text
ffprobe -v error -select_streams s -show_streams -of json native.mp4
ffmpeg -v error -i native.mp4 -map 0:s:0 -f srt extracted.srt
```

Repeat extraction for each reported subtitle index. Preserve the original
download and the editable Vids link. When delivering a reviewed local version
with one replacement Spanish track, keep separate file names. The command
below assumes a single video and a single voice mix. Map each intended stream
explicitly when the source has additional tracks.

```text
ffmpeg -n -i native.mp4 -i reviewed.srt -map 0:v:0 -map 0:a:0 -map 1:s:0 -c copy -c:s mov_text -metadata:s:s:0 language=spa -disposition:s:0 default -movflags +faststart delivery-es.mp4
ffmpeg -v error -i native.mp4 -map 0:v:0 -map 0:a:0 -c copy -f streamhash -hash sha256 -
ffmpeg -v error -i delivery-es.mp4 -map 0:v:0 -map 0:a:0 -c copy -f streamhash -hash sha256 -
```

Confirm identical hashes per compressed audio/video stream, probe the new
track, re-extract it and compare the full timed text to the reviewed SRT. Label
the local correction in the handoff so a future native download is checked again.

For a reviewed MP4 with subtitles and navigation chapters on the same timeline,
first compare scene cuts and voice timing with the native download. Then run
the verified restoration command with a new output filename.

```text
uv run --script <skill-root>/scripts/vids_delivery.py restore-tracks --video native.mp4 --reference reviewed.mp4 --language spa --output delivery-es.mp4
```

This command replaces subtitles tagged with the chosen language. It copies
every native audio and video stream, retains subtitles in other languages and
selects the reviewed track by default. The reference MP4 supplies its chapter
titles and times. With a reviewed SRT, WebVTT or a reference without chapters,
the copy retains the native chapters. The JSON receipt records input and output
hashes, cue count, chapters and packet fingerprints. The tool re-extracts all
reviewed cue text and times and checks the exact clocks, codec parameters and
payload of each copied stream before publishing the local file. A new native
download may still contain the editor's automatic captions.

For a constant delay measured across the exported voice, `--caption-offset-ms 82`
places every reviewed cue 82 milliseconds later. Signed integer offsets also
allow an advance. The default is zero. The command preserves cue text, line
breaks and durations, verifies both ends after remuxing, and rejects a requested
shift that would put any part of a cue outside the native movie. Chapter times,
other languages and audio/video clocks stay on the original timeline. Measure
several phrases including the opening and closing scenes. If the lag grows
over time or changes at a cut, align the affected sections to the native voice
and supply the individually retimed SRT or WebVTT.
