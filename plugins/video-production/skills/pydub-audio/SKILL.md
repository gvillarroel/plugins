---
name: pydub-audio
description: Creates, edits, mixes, synthesizes, inspects and exports audio with Python PyDub and FFmpeg. Use for audio clips, podcasts, sound beds, format conversion and reproducible audio plans.
---

# PyDub Audio

Produce the requested audio and keep an editable recipe with measured results.
Resolve bundled script paths from this skill directory; write task files in the
caller's workspace. The script works without another skill or this repository.

1. Run `uv run --script scripts/audio.py doctor` to inspect the actual Python,
   PyDub, FFmpeg and ffprobe environment. The script pins PyDub and supplies
   `audioop-lts` on Python 3.13+. WAV and generated tones work without FFmpeg;
   compressed formats need the external executable. See
   [environment and diagnosis](references/environment.md) when setup fails.
2. For repeatable edits, write a JSON plan using the
   [plan contract](references/audio-plans.md), then run:

   ```sh
   uv run --script scripts/audio.py render --root . --plan plan.json --output artifacts/mix.wav --report artifacts/mix.json
   ```

   Paths inside the plan resolve under `--root`, independently of the plan's
   location. Outputs must also stay inside that root. Existing output files are
   preserved; choose a new versioned path for another result.
3. Use sequence mode for ordered clips and crossfades; use timeline mode for
   positioned speech/music/effects and explicit ducking. Set the delivery sample
   rate and channels. The helper supports file clips, silence and sine/square/
   sawtooth/noise generators. For custom PyDub code, follow the
   [editing recipes](references/editing-recipes.md).
4. Inspect the encoded file, duration, channels, rate and sample peak. The report
   records the recipe digest, source digests and decoded output measurements.
   Run `inspect --root . --input artifacts/mix.wav` for a separate check; add
   `--silence-threshold-dbfs -40` only when silence ranges are useful.
   For delivery quality and listening, read
   [verification](references/verification.md).
5. Deliver the exact output paths, plan and report, plus any limitation that
   affects use. Actual listening is a separate check from numerical inspection.

Keep edits in milliseconds and assign transformed immutable `AudioSegment`
results. Decode once, retain a PCM master and encode lossy delivery files once.
Peak normalization is not LUFS normalization; use measured FFmpeg loudness
processing when the user specifies LUFS. PyDub keeps decoded audio in memory;
use streaming FFmpeg or bounded chunks for material that exceeds available RAM.

The project/agent coordinator is an optional companion. This skill can operate
directly on files and plans with no shared state, server or model credentials.
