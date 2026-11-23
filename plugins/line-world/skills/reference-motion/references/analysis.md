# Analyze reference motion with rea-video

The launcher resolves the exact Git revision recorded in its [script metadata](../scripts/rea.py). Install Git, uv, FFmpeg and FFprobe on the analysis machine. Use Python 3.13 for the commands below. The CLI's report languages are English and Chinese. Write the accompanying analysis in the user's language.

## Full footage

Set the working directory to this skill's root. Give each video its own output directory. These commands provide a local visual breakdown with the upstream survey, review and VIDEO.md tools.

```sh
uv run --python 3.13 --script scripts/rea.py survey reference.mp4 -o analysis/source-id --no-vlm
uv run --python 3.13 --script scripts/rea.py decompose reference.mp4 -o analysis/source-id --lang en --no-vlm --no-asr --no-ocr --no-stems --no-speakers
uv run --python 3.13 --script scripts/rea.py summary analysis/source-id/breakdown.json
uv run --python 3.13 --script scripts/rea.py review analysis/source-id
```

The survey is interactive through files. Inspect the returned images, answer the requested questions in the listed files, and rerun the same survey command until it reports `done`. Its gap and keyframe answers improve the boundaries used by `decompose`. When a batch uses automatic boundaries, label them candidate cuts and visually check the spans used as evidence. The command above skips transcription, OCR and audio stem separation because its purpose is visual transition analysis. Enable those stages and their optional upstream dependencies if the brief also asks for subtitle text, speech timing or audio.

Read the card in `VIDEO.md` and the shot and rhythm tables in `video/`. For a transition, inspect the actual source frames immediately before, during and after it. For a reusable graphic, inspect a stable frame and its entrance or exit. Fill in the review answers for the shots inspected and run the following commands to merge that review and check the resulting package.

```sh
uv run --python 3.13 --script scripts/rea.py apply-review analysis/source-id --by line-world
uvx --from videomd==1.2.0 videomd check analysis/source-id
```

For longer material that exceeds the resources available to `decompose`, extract multiple contiguous clips with FFmpeg and record each clip's exact offset on the source timeline. Map reviewed shot times back to source seconds using that offset. Link to the original upload at those seconds. Track which ranges have been examined.

## Sampled material

YouTube storyboard tiles represent sampled frames. Record the sample interval from the manifest, the tile index and its mapped source time. A pair of tiles can bracket a compositional change; the elapsed time between them includes any holds. Model a candidate effect only as precisely as the evidence allows. For static graphics, supply a representative tile time. For wipes, easing or short overlaps, confirm with source footage or record timing as a design parameter to be adjusted during production. If a proxy made of storyboard tiles is passed through the shot detector, its still-frame cuts belong to the proxy timeline.

## Evidence for implementation

### Review an exported example

Keep the input recipe and SHA-256 for each version. Run the pinned detector on the actual MP4 at its presentation cadence. Compare the proposed shot intervals and in-shot beats with both the planned handoffs and a strip of decoded frames. A moving bar and a scene replacement can both produce a motion peak. In white-background graphics a brief push can remain inside a single detected segment.

Use the [export reviewer](../scripts/review_export.py) with timestamps from the production, in seconds. Its optional QA receipt must match the MP4's SHA-256 and frame clock. The resulting `rea.json` preserves the source shots, the authored cuts and animated handoffs, and the internal beats that fall outside those joins. `frames.png` shows the chosen images at a 390 px viewing width.

```sh
uv run --python 3.13 --script scripts/review_export.py /path/to/film/comparison.mp4 --receipt /path/to/film/comparison.qa.json --out /path/to/film/review --at 0 3 4.5 8
```

For each proposed revision, name the viewer's reading task. Inspect the first image, the instant of the handoff and the settled result at delivery size and at the intended mobile width. For a number that persists, check that its unit and category remain legible. For a closing action, measure its readable hold after the move. Repeat the same measurements on the new export and retain the two hashes. A rendering receipt records which joins the generator selected and whether decoded frames match the recipe. Record the editorial decision separately.

Record a stable source URL, the input kind, the source interval, any time offset, and the component ID. Keep observed geometry and motion separate from implementation choices in the data. For example, a title moving left across two sampled states supplies direction. A cubic easing curve selected to connect those states is a design choice. A complete run of frames can additionally support a duration or fitted curve. Compare multiple examples before describing a behavior as recurring. Keep artwork, text and footage supplied by the new production as caller inputs.

The [upstream workflow](https://github.com/JuneYaooo/rea-video/blob/a124acd4a02b3a9b72b9e7dedca5d1bfcda2a7b8/skills/rea-video/SKILL.md) describes the survey and correction process. The [visual review guide](https://github.com/JuneYaooo/rea-video/blob/a124acd4a02b3a9b72b9e7dedca5d1bfcda2a7b8/skills/rea-video/references/review.md) explains the limits of shot classification.
