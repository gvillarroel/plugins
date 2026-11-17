# Higgsfield provider route

In these examples, `$SkillsDir` is the absolute `skills` folder of the installed `store-studio` plugin. Run commands from the store workspace.

Use Higgsfield as an optional reference-capable provider inside the existing marketing skill. It complements the default Codex/OpenAI image route; it does not replace Printify product truth, campaign review, disclosure, or publication controls.

## Route by task

| Need | Higgsfield route | Guardrail |
| --- | --- | --- |
| Add restrained motion to an approved social/product scene | `seedance1_5` through `$SkillsDir/higgsfield-generate/` | Start from the selected Printify-approved image; freeze garment artwork and reject text/icon drift. |
| Preflight a finished Reel | `brain_activity` when the active CLI/MCP supports text jobs | Analysis only. Do not treat a predicted score as observed performance. |
| Build a reference-led product still | `$SkillsDir/higgsfield-product-photoshoot/` | Use direct Printify `product.images[]`; for model/lifestyle campaigns, keep the required 2M/2F cast and distinct person references. |
| Explore a structured product prompt without spending credits | `higgsfield product-photoshoot create ... --enhance-only` | The enhanced prompt is a draft, not a finished campaign asset. |
| Generate paid-ad variants | Marketing Studio | Wait for reconciled margins and organic signal; never launch or publish without explicit authorization. |

## Mandatory rules

- Run `higgsfield model list --json` and `higgsfield model get <job_type> --json` before relying on remembered parameters.
- Run the cost command first. Set a per-run credit ceiling and record estimated and actual credits in a sanitized manifest.
- Do not store account email, OAuth credentials, cloud result URLs, upload IDs, workspace IDs, or job IDs in the repository.
- Use a direct Printify mockup as product truth. For Instagram motion, a locally mirrored model/scene image is acceptable only when it is already selected in Printify `product.images[]`.
- Preserve the garment/product print, typography, icon, color, and geometry. If any of those drift, reject and regenerate; never paste artwork over a worn garment to repair it.
- Keep `AI Generated Image` fully visible throughout every generated store-facing image or video. Add the disclosure deterministically after generation when framing clips the source label.
- Keep raw/rejected generations under `assets/work/` or another ignored workspace. Promote only reviewed finals to `assets/marketing/` or `assets/upload-ready/`.
- Do not publish, schedule, upload to Printify, start ads, or purchase credits without the authority required by the repository rules.

## Reusable command

Estimate first; generation requires an explicit switch:

```powershell
./shared/scripts/invoke_higgsfield_seedance_pilot.ps1 `
  -InputImage "stores/ia-referencias/social/instagram/assets/approved-product-images/<product>/01-product-image.png" `
  -Prompt "Restrained product-preserving motion..." `
  -MaxCredits 3

./shared/scripts/invoke_higgsfield_seedance_pilot.ps1 `
  -InputImage "stores/ia-referencias/social/instagram/assets/approved-product-images/<product>/01-product-image.png" `
  -Prompt "Restrained product-preserving motion..." `
  -OutputDirectory "stores/ia-referencias/spikes/YYYY-MM-DD-slug/assets/work" `
  -MaxCredits 3 `
  -Generate
```

The wrapper prints sanitized JSON and never persists private Higgsfield identifiers or URLs.

## Current compatibility note

On 2026-07-19, CLI `1.1.13` could discover `brain_activity` but could not submit text-type jobs (`Model type "text" is not supported by generate create yet`). Recheck after a CLI/MCP update; do not build automation around that route until an actual submission succeeds.

See `docs/operations/higgsfield-marketing-workflow.md` and the accepted pilot at `stores/ia-referencias/spikes/2026-07-19-higgsfield-marketing-pilot/`.
