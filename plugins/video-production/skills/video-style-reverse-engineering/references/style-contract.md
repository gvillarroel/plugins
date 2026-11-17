# Observable style contract

Use a JSON object with the following fields. Extend it when the task needs more
detail; retain the distinction between source evidence and original content.

| Field | Content |
| --- | --- |
| `style_id`, `version` | Stable local recipe name and revision. |
| `output` | Width, height, fps, duration, language and audio requirement. |
| `sources` | Source IDs, local paths or URLs, creator, analysis manifest and access/usage notes. |
| `research` | Optional discovery snapshot, comparable cohort/rank, peer evidence and selection reason; distinguish public reach from outcome evidence. |
| `observations` | Source ID, `start_s`, `end_s`, visible/audible event, evidence frame paths and confidence. |
| `rules` | Reusable rules for typography, layout, palette, motion, pacing, transitions and audio. Each rule names supporting observation IDs or says `proposed`. |
| `mechanisms` | Optional observation-linked viewer-function hypotheses, confounders and a proposed test; do not present correlation as a proven cause. |
| `content` | Original script and timed shots with IDs, start/end, text, visual, motion, assets and audio cues. |
| `limits` | Missing evidence, uncertain measurements, unavailable providers and intentional differences. |

For example, this observation structure records evidence without inventing a
motion curve from one still:

```json
{
  "id": "ref-a-01",
  "source_id": "ref-a",
  "start_s": 0.5,
  "end_s": 1.0,
  "visual": "Headline occupies the upper half; a small figure remains below.",
  "evidence_frames": ["analysis/ref-a/frames/frame-002.jpg"],
  "confidence": "observed layout; entrance easing unverified"
}
```

Measure relative positions and text sizes against the source canvas. Record
approximate colors as estimates unless sampled. Font family guesses are
substitutions until the source font is identified. Describe an entrance with
direction, duration, overshoot/settling and stagger only after checking multiple
frames. Describe camera movement separately from object movement.

Find what repeats across references: word-group size, emphasis location,
background changes, pause/hold length, framing, transition type and sound cues.
Keep one-off story details outside the recipe. With one reference, label a
candidate convention instead of claiming a universal rule. A synthetic fixture
can test the workflow but cannot establish a real creator's editing style.

Translate the new script into beats rather than forcing every reference shot
onto unrelated content. Keep words readable at the delivery resolution. Check
longer strings, accents, line breaks, safe areas and image cropping. With voice,
use measured phrase timings; without voice, allow enough time to read each beat.
Never invent narration alignment from a silent source.

For batches, share the versioned rules while keeping independent item manifests
and outputs. Record requested and completed item IDs, render settings, asset
references and QA results. Reuse assets without regenerating them unnecessarily;
regenerate an item only when its content or validation result calls for it.
