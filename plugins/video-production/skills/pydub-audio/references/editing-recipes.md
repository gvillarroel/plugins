# Editing recipes

Use the plan helper for its supported contract. Use custom Python when a request
needs PyDub operations beyond that contract. Keep the same root/output policy,
close export handles, and inspect the encoded file.

## Cut and assemble

Load each source once with `AudioSegment.from_file(path)`. Slice in milliseconds
with `source[start_ms:end_ms]`, then assign transformations. `a + b` concatenates;
`a.overlay(b, position=...)` mixes and keeps the base length. Extend the base
with silence first when an overlay should extend the total duration.
`a.append(b, crossfade=250)` shortens the total by 250 ms; validate this against
the intended edit duration. Frame-exact work needs sample indices and a PCM
workflow, because millisecond slicing rounds boundaries.

## Silence and dynamics

Use `detect_nonsilent` with an explicit threshold and minimum silence duration
for speech cleanup. `split_on_silence` can split long pauses within speech;
retain the original timing map if captions or other media depend on it. An
all-silent segment has nonfinite dBFS; do not derive thresholds or gains from it.
Distinguish silence detection from denoising. PyDub does not supply speech
recognition, source separation or a general noise-removal model.

`effects.normalize` adjusts sample peak, `compress_dynamic_range` changes
dynamics, and `overlay(..., gain_during_overlay=-12)` ducks the existing base
under the incoming clip. Check the combined peak after mixing; two safe
individual tracks can clip when summed. `set_frame_rate` resamples; overriding
frame-rate metadata changes pitch and timing and is a different operation.

## Reproducible work

Pattern ID: `pydub-plan-render`. Trigger: repeated editing/mixing or agent
handoff. Input contract: the JSON plan described in `audio-plans.md`. Keep
source hashes, clip IDs and milliseconds, render to a new output, decode it,
and compare intended duration/rate/channels/peak. Validate with the helper's
`render` followed by `inspect`. Known pitfalls: implicit crossfade duration,
truncated overlays, clipping, nonfinite silence levels and repeated lossy edits.
Noise generators are stochastic; save and hash a generated noise source when
exact sample reproducibility matters.

Source: [PyDub API and immutable segments](https://github.com/jiaaro/pydub/blob/master/API.markdown).
