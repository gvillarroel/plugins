# Narrated production with a second-by-second review

Time the edit to a recorded phrase. While the viewer listens, keep the name and
number readable. Couple a visible change in the subject to one consequence,
such as a guide following a newly exposed line. A pan, an independently animated
object and a moving video surface each use one of the three available movements.
Individual bars with separate trajectories each count. A label that stays
attached to its object under the same transform follows that object.

1. Prepare data and images and [build the audio master](../../media-use/audio/references/scene-audio.md).
   The audio timeline includes numbered sentences, exact sample boundaries and
   the master digest. Place a sound when the depicted event occurs.
2. Give each visual scene a local HTML document with a seekable
   `window.renderAt(localSeconds, absoluteFrame, scene)`. The script may return
   a promise while it loads or decodes a frame. Its clock is the argument.
   `scene.voice` includes the measured phrases and effects. A native-size
   canvas with `data-export-surface` offers direct image capture. Ordinary
   HTML and SVG scenes use browser screenshots.
3. Declare the intended focus for each beat. In a motion beat name two or three
   distinct moving elements, including the focus. In a reading beat name the
   focus, its idea and any background movement that continues. Keep the whole
   reading passage visible for the duration of the corresponding sentence.
4. Run the pre-render hook, render and inspect the post-export report. The
   composer calls both hooks automatically and checks the candidate MP4 before
   replacing the delivery. A failing pixel review includes timestamps and the
   element that moved unexpectedly or stayed still.

```sh
uv run --script scripts/compose_narrated.py film.json --preflight --report preflight.json
uv run --script scripts/compose_narrated.py film.json --output film.mp4 --report review.json
uv run --script scripts/review_attention.py post-export attention.json --video film.mp4 --audio-timeline audio/timeline.json --report second-by-second.json
```

A browser frame that stays unresolved for 90 seconds triggers one retry in a
fresh tab on the same frame. The scene's paint receipt records the stalled
frame and the recovered frame. A second stall returns a diagnostic while
the last approved MP4 remains available. For unusually slow source imagery,
set `--frame-timeout` to a longer interval in seconds. Zero disables this
limit. The timeout measures a single browser operation, irrespective of the
duration of the film.

Run the commands from the skill directory or use absolute script paths.
`film.json` specifies `width`, `height`, `fps`, `audioTimeline`, `attention`,
the subtitle language, and ordered `scenes` with matching audio IDs, `title`
and `html`. File paths are relative to the film specification. By default the
composer uses the subtitle file beside the audio timeline.

The narration pipeline writes PCM WAV by default. For a long edit with
limited disk space, the composer also accepts a lossless FLAC master. Set
`master.file` and its file `sha256` in the audio timeline, retain the original
PCM sample rate and sample count, and use that clock for every cue. The
composer reads the exact number of samples from FLAC or counts the decoded
samples when a streaming encoder leaves the total unset. Export checks the
delivered audio against the original channels and scheduled effects.

For a bilingual film, set `audioLanguage` and `subtitleLanguage` to the three-letter MP4
language codes, for example `"spa"` for Spanish speech and `"eng"` for English text.
The existing `language` value supplies either track that has no explicit override.
The preflight reads every subtitle block and verifies its clock against the measured
duration. The delivery report checks both track labels and records the time available
to read the longest and fastest cues. Inspect the wording against the recorded voice.

Set `"captionMode":"verbatim"` for a transcription of the measured narration.
Preflight compares the ordered words, signs, quantities and units, then verifies
the first and last subtitle against each recorded phrase (100 ms tolerance).
Line breaks can change within a phrase. The report identifies the first changed
word or the interval that needs attention. The default `authored` mode also
accepts reviewed translations, condensed subtitles and sound descriptions.

The composer uses PyAV to open the SubRip decoder and pass its style header to
the MP4 subtitle encoder before encoding the first cue. It copies each cue's
timing from the SubRip packet and keeps authored line breaks, bold, italics and underline.
`uv run --script` installs PyAV with the composer's other Python dependencies.

To extract a WebVTT sidecar from the actual delivery, run
`python scripts/caption_tracks.py film.mp4 film.vtt --language spa`. Use the
[frame review page](frame-notes.md) to jump to a spoken phrase at its original
time and check the chart while the text stays below the picture. WebVTT stores
the cue times in milliseconds and can be loaded as a browser text track.
[W3C WebVTT format](https://www.w3.org/TR/webvtt1/)

To independently check the text in a delivered file, add
`--compare-voice audio/timeline.json --require-verbatim --report lectura.json`.
This compares the subtitles with the supplied transcript and measured sample
boundaries. Listen back to confirm that the recording itself says the intended
words and pronounces the figures correctly.

When a headline changes inside a sentence, check the words against the encoded
headline. In one market edit the picture switched from a weekly loss to the
closing price before the voice had finished saying the percentage. The sound
and subtitle tracks both passed their own checks. The
[spoken headline check](spoken-headlines.md) compares the reviewed number
against every displayed frame that overlaps its spoken words.

List local footage, images, fonts, CSS, and data needed for a scene in the
optional project-level `assets` array. Preflight records a SHA-256 fingerprint
for each. During export the composer also fingerprints local resources requested
by Chromium and records the origins of network requests. The published MP4
has passed the picture, audio, and subtitle checks. If a later edit fails,
the previous MP4 stays available and the new JSON report identifies the
failing stage. Read its `published` field before treating a run as a delivery.

The sound check compares each channel at the master's original sample rate.
For each scheduled effect it also compares that exact interval in the mix.
This can expose a stereo swap or a missing high-pitched effect during a
scene whose voice remains intelligible. The report keeps source and delivered
channel counts, correlation and level difference for each channel.

The attention score declares `fps`, `frames`, `tracks` and `beats`. Give each
track a normalized `box: [x,y,width,height]` that covers its actual motion.
Use half-open global `start` and `end` frames per beat. Include `mode`,
`focus`, `moving`, `idea` and sentence references such as
`"cues": [{"scene":"coil","sentence":0}]`. For a change of composition,
`visible` selects tracks in its new layout. Use `cut: true` only on the actual
cut frame. A beat spanning several sentences lists them in speaking order.

The encoded review measures independent changes inside the exclusive part
of each visible element's region. For each second it reports the primary
focus, the phrase, the number of frames in which each part moves and the
maximum observed together. It checks the whole film for rapid alternation.
A second check looks for a repeated highlight inside each visible subject,
including when footage or another region continues to move. Its report names
the affected subject and the four frames that best show the alternation. The two middle visits may have unequal durations. For imported footage with variable frame durations, run `scripts/content_scan.py --video input.mp4 --output content.json`. It reads every presentation timestamp, preserves portrait proportions, and reports the first switch on the playback clock. Inspect a flagged passage to identify whether the same two objects traded attention.

To test the detector after a change, run `python scripts/audit_cadence.py --fps 30000/1001 --cases 30 --report cadence.json`. The script encodes H.264 cards with unequal holds and one-way controls. It checks whether the four frames identified in each positive case contain the alternating authored states. Small changes confined to a single sampled color boundary require stronger contrast than a two-dimensional patch, so codec shimmer at a held edge can be distinguished from a flashing label.

Preflight also checks the order of the primary focus. A repeated A–B–A–B
handoff with both intermediate visits at or below 0.45 seconds needs a
longer reading hold or a single subject for the action. This test works even
when each visit uses a different drawing. If multiple tracks depict the
same physical subject across cuts, give them the same `subject` ID.
A region should describe one identifiable surface. Assign one track to each
independently moving object. Two marks that translate, change size or turn
separately inside one track will be counted as one moving region. When subjects overlap,
inspect their independent geometry in the producer as well. The reviewer
records whether the imagery conveys the narrated idea and whether faces,
axes and labels remain clear at the intended viewing size.

For a fixed, fully opaque text plate placed over moving footage, declare
`"occludes":["footage"]` on the foreground track. Its box must delimit the
opaque rectangle throughout its visible interval. The checker measures the
foreground inside the plate and the footage in its exposed area. Use ordinary
exclusive regions for transparent lettering, round portraits and objects
that travel across a background. Record both surfaces in `visible` while they
are on screen.

The narrated composer compares the original pixels in each full native track
rectangle throughout capture. A rectangle that is byte-identical in every
frame may still flicker slightly after compression. The checker measures
those decoded RGB pixels against the first and preceding frames. It discounts
the change as residual only when every comparison stays within all three
limits. The largest channel change may be 48/255, the mean absolute channel
change may be 0.12/255, and at most 0.2% of pixels (rounded down, at least
one and at most 16) may change by 7/255 or more. Other changes retain the
usual motion review. The report keeps the native measurements. Reuse them
with `review_attention.py post-export … --source-report composicion.json`
for the same movie and score. A movie supplied without a source report
receives the ordinary decoded-picture check. Rapid alternation is always
measured in the delivered frames.

### Check flat fills against the delivered pixels

The composer inspects authored paint operations on each frame and records
the surface type and first affected element. The [solid-paint inspector](solid-paints.md)
describes the coverage for Canvas 2D, SVG, HTML and original imagery.
To check a finished rail, digit, bar or background against the actual
compressed picture, add the path to a JSON palette plan as `solidRegions`
in the film specification. A plan can also appear inline.

```json
{"colorset":"colorset1","regions":[
  {"id":"white-plate","role":"surface","box":[0.02,0.02,0.05,0.04]},
  {"id":"settled-bar","role":"primary","box":[0.39,0.49,0.04,0.02],"start":48,"end":84}
]}
```

Select the interior in the editable original, away from letters, corners
and antialiased outlines. The checker measures each selected frame on a
grid of up to 64 × 64 native RGB samples. The 95th-percentile color error
and the spread between the 5th and 95th percentiles must each stay within
eight RGB levels per channel. A report records the worst frame and every
failing interval. To run it against an existing delivery use
`python scripts/review_solid_regions.py film.mp4 paints.json --report paint-review.json`.

## Open-caption MP4

Use this delivery when selectable subtitles in a receiving player can cover dates, labels or credits. Run the command with Python, Pillow, FFmpeg and ffprobe. Use a fresh output filename.

```sh
python scripts/open_captions.py film.mp4 film-open.mp4 --language spa
```

The exporter uses the selected text track and its clock, scales the entire picture inside the original frame dimensions, and prints up to two caption lines in a dark bottom band. It copies each audio stream and the chapter timings. A receiving player can display the finished H.264 pixels directly. The original file remains the larger-picture, selectable-caption edition. At 1280 × 720 the image occupies 1088 × 612. At 390 × 844 it occupies 340 × 736. Weigh the reduced size of chart lettering against the benefit of captions that stay clear of it. For local review, the frame-note viewer can show captions beneath the video on demand.

Omit `--language` to use the default text track. Use `--font path/to/font.ttf` for characters outside the bundled typeface. The exporter supports square-pixel, unrotated, constant-frame-rate 8-bit SDR YUV 4:2:0 video with presentation time starting at zero. It keeps each cue's wording, punctuation and times. It can adjust line breaks and type size to fit. Spanish written-out numeric groups and numeric strings are kept together. Split a cue upstream if its text cannot fit in two lines at the minimum size. The output contains open captions and no selectable subtitle track.
