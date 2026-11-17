# Audio plan contract

Use `schema_version: 1`, `mode: "sequence"` or `"timeline"`, `sample_rate`
(default 48000), `channels` (1 or 2, default 2), and a nonempty `clips` array.
Every clip has a unique `id` and exactly one source:

- `file`: path to an existing audio file under the explicit workspace root.
- `tone`: object with `kind` (`sine`, `square`, `sawtooth`, `noise`),
  `duration_ms`, optional `frequency_hz` (default 440), and `gain_db` (default -18).
- `silence_ms`: positive integer duration.

Optional clip edits: `start_ms`, `end_ms` (exclusive source end), `gain_db`,
`fade_in_ms`, `fade_out_ms`, `reverse`, `repeat`, `pan` (-1 to 1),
`high_pass_hz`, `low_pass_hz`. Edits apply after source trimming; fades apply
after repeat. Negative times, empty trims, excessive crossfades, unknown keys,
nonfinite values and invalid types fail before publishing outputs.

In sequence mode each clip after the first may have `crossfade_ms`; the first
must omit it or set zero. The crossfade cannot exceed either adjacent segment.
Sequence duration equals the sum of edited clip durations minus crossfades.

In timeline mode each clip has optional `position_ms` (default 0) and
`duck_db` (default 0). Clips are overlaid in array order on a silent canvas.
`duck_db: -12` attenuates the already mixed material beneath the incoming clip
for that clip's interval, so put a music bed before speech. `duration_ms`
optionally sets canvas length; a clip extending past it is rejected. Otherwise
the canvas grows to the latest clip end. Do not use crossfade in timeline mode.

Optional top-level `peak_dbfs` applies one final sample-peak gain adjustment.
Silence remains silence. This is not integrated loudness or true peak.
Optional `bitrate` controls compressed export. Output extensions supported by
the helper: `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a` (AAC). WAV is 16-bit PCM.
No user-supplied FFmpeg arguments or shell text are evaluated.

Example: a three-second bed with one second of foreground audio:

```json
{
  "schema_version": 1,
  "mode": "timeline",
  "sample_rate": 48000,
  "channels": 2,
  "duration_ms": 3000,
  "peak_dbfs": -1,
  "clips": [
    {"id": "bed", "tone": {"kind": "sine", "frequency_hz": 220, "duration_ms": 3000, "gain_db": -24}},
    {"id": "cue", "tone": {"kind": "sine", "frequency_hz": 660, "duration_ms": 1000, "gain_db": -12}, "position_ms": 1000, "duck_db": -12, "fade_in_ms": 20, "fade_out_ms": 80}
  ]
}
```

Run from the workspace, resolving `<skill>` to this skill's installed path:

```sh
uv run --script <skill>/scripts/audio.py render --root . --plan plan.json --output mix.wav --report mix.json
uv run --script <skill>/scripts/audio.py inspect --root . --input mix.wav --output inspection.json
```

The helper preserves existing outputs. A report contains source and plan
SHA-256 values, encoded output SHA-256, duration, rate, channels, sample width,
RMS dBFS and sample peak. JSON represents silent dBFS as `null`.
