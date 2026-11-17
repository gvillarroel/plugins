# Review and learning from selections

Use an iterative portfolio to learn useful design rules from the current user's choices. This is evidence-led recipe design, not training a model or assigning a universal taste score.

## Keep stable identities

Associate a candidate with the source hash, ordered techniques, effective parameters, seed and output hash. Human-readable filenames help navigation but are insufficient when two source images have identical basenames or local card numbers overlap.

When adding parent IDs and review hypotheses, parse and serialize the existing JSON rather than rebuilding reports as hand-edited text. Preserve the original technical fields. Manifest artifact paths are collection-relative, while a per-image report resolves its paths from its own directory; normalize these bases before comparing records.

For multiple inputs, keep a separate render directory per source and group review material by source before technique. Preserve the original image and immutable render reports. A compact contact sheet provides orientation; users should be able to inspect full-size results before selecting fine marks.

The bundled HTML is a local comparison artifact. Do not claim that it automatically synchronizes ratings with the agent. If a selection UI is added, state where its state is stored and provide an explicit export. Hosting is a separate requested operation, not a requirement for using these techniques.

## Interpret feedback literally

Keep separate states for accepted, explicitly rejected, later and unreviewed. A list of good IDs supplies positive evidence only; absence does not identify a reason for rejection or even establish that the work was reviewed.

When the user requests pruning, retire nonselected work from the active review and keep original renders recoverable unless permanent deletion is explicitly intended. Do not silently erase a parent still needed to explain another accepted construction.

Preserve notes verbatim and distinguish a source-specific comment from a general rule. Retain the original selection file when supplied, with a checksum. For a pasted list, record the received IDs and `received_at`; unknown per-item action timestamps remain unknown. Do not describe a receipt time as the time each rating was made.

If merging with browser-local reviews, preserve later user edits. When exact action times are absent, use missing-only seeding or a declared lower-precedence anchor associated with the earlier release. Do not overwrite a later explicit negative or note simply because an older copied good list was supplied.

## Design the next portfolio

Count selections by technique and source. A technique selected on several different inputs is a useful candidate for transfer; one selected only on a portrait may depend on that composition. These are observations from a small portfolio, not calibrated success probabilities.

Build hypotheses that connect an observed choice to a controllable mechanism:

| Observation | Hypothesis | Next comparison |
| --- | --- | --- |
| Adaptive cells selected across several images | Variable spatial allocation contributes to the appeal. | Compare local hatching, cell cavities and pigment pieces on the same inputs. |
| Pigment regions selected but fine texture is inconsistent | Regional organization may matter more than photographic fidelity. | Hold the regions fixed and compare mark systems or scale. |
| Contour displacement selected on some images | Useful deformation may depend on prominent boundaries. | Compare bounded displacement at two strengths and inspect small features. |
| A combination selected while a constituent is not listed | The interaction deserves testing. | Compare both parents and the combination; do not invent a negative rating for the absent parent. |

Keep a mixture of exploitation and exploration appropriate to the task: deepen supported mechanisms, vary uncertain ones and include a few genuinely different constructions. Do not impose a fixed candidate count or a universal ratio. Stop generating when the requested comparison is complete; do not launch indefinite batches from one selection message.

Store parent candidate IDs and a short hypothesis for each new proposal. New outputs remain unreviewed. Preserve the difference between a parameter variation, a combination and a new algorithm. A different color alone does not make a new technique.

## Provenance of the initial defaults

The four initial recipes were motivated by one user's repeated positive choices in a visual exploration. Adaptive engraving, pigment regions with hatching, alternating ink strata and linked cavities were each selected on three different source compositions. Other methods were image-dependent. Later experiments were technically implemented and reviewed, but that does not mean the user approved them.

This observation justifies a practical starting comparison for this skill. It does not justify carrying private image files, browser drafts, historical IDs or personal ratings into an unrelated user's work. The bundle works without that original project.
