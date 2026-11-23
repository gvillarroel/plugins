# Keep the headline on screen while the number is spoken

Use this check for a price, percentage, name or unit held in a fixed panel.
Pick the approved appearance of the value at delivery size and inspect its
sign, separators and unit. Export that rectangle as an opaque PNG. A reviewer
can take it from the editable design or a previously approved film frame.
Keep the chosen reference fixed while comparing cuts. A moving number,
dissolving plate or perspective shot needs a separate visual review.

1. Run the [spoken fact check](../../media-use/audio/references/spoken-facts.md)
   on the recording. It identifies the words and their measured intervals.
2. Set the matching fact ID, pixel rectangle and SHA-256 of the reference PNG
   in a plan for this delivery size. For example, the closing percentage
   occupies a different rectangle in the portrait and landscape edits.

```json
{
  "version": 1,
  "plates": [
    {
      "fact": "weekly-change",
      "reference": "weekly-change.png",
      "sha256": "<SHA-256 of the approved PNG>",
      "box": [16, 113, 354, 66]
    }
  ]
}
```

3. Review the H.264. The command reports frame intervals as
   `[first, stop)`. A result of `revisar` identifies the affected fact.

```sh
uv run --script scripts/review_spoken_visuals.py film.mp4 plates.json --speech-report heard.json --report visible.json
```

If the same recording accompanies a different picture, supply
`--speech-media original-film.mp4`. The check verifies the listening report's
original file hash and compares channel format, sample rate and every
decoded PCM sample before reusing the word times. Audio and video can start
at different times. A picture held between two variable-rate timestamps
counts for the entire time it remains visible.

The checker compares native RGB samples. A change over 32 levels in any
channel counts towards the changed area. More than 2% of the reference ink
(with a three-pixel allowance), or eight changed pixels in any 6 × 6 window,
flags that frame. The local check catches small missing minus signs or
decimal marks. The report retains the reference hash, full word interval
and worst pixel count. An unrecognized spoken expression stays open for
listening review. The reference image still needs editorial verification
against the source number and its unit.
