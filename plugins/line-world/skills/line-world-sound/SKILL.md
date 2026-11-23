---
name: line-world-sound
description: Generate narrated film soundtracks with Piper, timed Earshot effects and optional recorded foley. Choose cues from picture, preserve voice timing, measure the final mix and verify it against the encoded Line World video.
---

# Line World sound

Choose sound from the visible event. For an explainer, start with the narration.
Add a cue where hearing the action improves understanding, such as the instant a
switch closes. Use the first frame of contact and measure the onset in the final
AAC. One effect may carry a whole transition.

- For new narration or an imported voice with timed effects, use the [scene audio generator](../media-use/audio/references/scene-audio.md). It writes a 48 kHz WAV, phrase and effect sample positions, a subtitle file and a measured timeline for the video composer.
- With existing narration, enter each event's frame, Earshot design, seed, sound anchor, protected phrase and silent alternative in a short [picture score](references/picture-score.md). The [producer](scripts/score_picture.py) renders both the edit and voice alone. A supplied MP4 enables adjacent-frame comparison and a second sync check after encoding the new audio to AAC.
- For a new effect, use the Earshot CLI or MCP to generate and measure a take. Keep the chosen sound ID, seed, effect WAV and placement. For selection or perceptual critique use Earshot on the individual stimulus and on the relevant few seconds of the mix. The [editable Earshot guide](references/earshot.md) includes the sound catalogue workflow and command options.
- For a field recording or a real event whose sound is identifiable, select a recording with a source and reuse terms. The [recorded-sound reference](references/recorded-sound.md) covers planning layers, readable levels and cuts to picture. Measure an imported file with the bundled [recording analyzer](scripts/analyze.py).
- For final delivery, use the [narrated composer](../line-world-video/references/narrated-production.md). It compares the encoded speech scene by scene with the measured master, verifies word and subtitle timing and checks the chapter boundaries.
- For a consequential number, sign or unit, [check the spoken facts](../media-use/audio/references/spoken-facts.md) in the final MP4 or WAV. Compare independent word timestamps with the editorial windows and listen to any interval marked `revisar`.

The Earshot and real-sound resources are editable copies within this plugin.
Their upstream revision and original digests are recorded in [upstream.json](upstream.json).
Changes to the project copy can be tested with the local audio examples.

```sh
uv run --python 3.12 --script scripts/analyze.py path/to/effect.wav --out measurements.json
```

The analyzer requires FFmpeg and FFprobe. Run it from this skill directory or
pass its full path. Earshot's basic effect generator runs separately from the
optional listening models.
