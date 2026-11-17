---
name: optimize-printify-product
description: Optimize existing or draft Printify products for IA-Referencias and similar merch stores. Use when Codex needs to improve Printify titles, descriptions, bullets, tags, variant/color strategy, price, Etsy/POD fee margins, draft/product metadata, product positioning, or sanitized documentation before publishing or comparing product candidates.
---

# Optimize Printify Product

Run bundled helpers by their absolute paths from the root of the store workspace. Resolve `scripts/` and `references/` next to this `SKILL.md`. Set `SKILL_DIR` to that skill directory in the shell examples below.

## Overview

Use this skill after a product exists as a concept, local mockup, or Printify draft. The goal is to turn a technically valid product into a sharper, more sellable product while preserving the store idea, product truth, fee math, and reproducible documentation.

## Required Context

1. Read store identity and product context first:
   - `AGENTS.md`
   - `stores/ia-referencias/IDENTITY.md`
   - `stores/ia-referencias/DESIGN_STYLES.md`, when present
   - the spike `README.md` and `RESOURCES.md`
   - relevant Printify manifests or product URLs
2. For detailed IA-Referencias copy and optimization rules, read `references/ia-referencias-product-optimization.md`.
3. If pricing or Etsy is involved, verify current official marketplace fee sources before changing prices. Fees are temporally unstable.
4. If editing Printify through API, use `PRINTIFY_API_TOKEN` and `PRINTIFY_SHOP_ID` from environment only. Never print or commit secrets.

## Workflow

1. **Product Truth**
   - Use real Printify mockups or the existing Printify product as truth.
   - Do not optimize from local previews when real mockups exist.
   - Identify whether the product is accepted, candidate-only, or comparison-only.

2. **Positioning**
   - Reduce the concept to one sentence: what contradiction is the product selling?
   - For IA-Referencias, prefer AI/dev/workflow satire, self-aware capitalism, anti-AI jokes, terminal/model culture, or automation sarcasm.
   - Avoid claims about real vendors, compliance, safety, earnings, legal outcomes, or factual incidents unless sourced and intentionally used.

3. **Title**
   - Make the first 40-70 characters scan well in search and listings.
   - Include the phrase customers will remember.
   - Add a category or audience cue only when useful: `AI`, `Developer`, `Groundhog`, `Workflow`, `Programmer`, `Tech Satire`.
   - Use `- Light`, `- Dark`, `- Black Ink`, or `- White Ink` only when variants are split across products and the distinction prevents confusion.

4. **Description**
   - Lead with the joke, not the blank.
   - Include product family, material/fulfillment route, print method, and color/ink strategy.
   - Keep the tone sharp but defensible: satire is fine; invented measurable claims are not.
   - Add one short "no claims" sentence when the concept could imply compliance, safety, income, medical, legal, or performance promises.

5. **Bullets And Tags**
   - Bullets should answer: what is it, who gets the joke, what is printed, what variants exist, and what product quality route was chosen.
   - Tags should mix exact phrase, audience, concept, and product category. Avoid stuffing irrelevant trend tags.
   - For Etsy-style tags, prefer short natural search phrases when possible.

6. **Variants And Mockups**
   - Keep color sets small enough to look intentional.
   - Split dark/light products when one-color art needs different ink files.
   - Disable weak colors where contrast or mockup clarity fails.
   - Choose default mockups from real Printify images, not local render sheets.

7. **Pricing**
   - Do not price from Printify gross cost alone.
   - Hard floor for IA-Referencias: every enabled variant must clear at least `55%` standard item-only profit margin after Printify product cost, Etsy listing allowance, Etsy transaction fee, and Etsy Payments fee.
   - Standard item-only profit margin formula: `(item_price - printify_cost - listing_fee - transaction_fee - payments_fee) / item_price`.
   - Use the highest enabled Printify cost for each advertised size/variant group when several colors share a size.
   - Do not keep 2XL/3XL or expensive variants below the 55% margin by averaging their cost into smaller sizes; increase those variants or disable them.
   - Model at least:
     - Printify product cost by size
     - Etsy listing/renewal allowance
     - Etsy transaction fee
     - Etsy Payments fee for the seller's market
     - Offsite Ads downside when relevant
   - Use `scripts/etsy_pod_price_matrix.py` for quick item-only pricing math. Its default target is `--target-standard-margin 55%`. Pass current prices with `--price SIZE=AMOUNT` when auditing an existing draft.
   - Treat Offsite Ads as a downside scenario unless the user explicitly asks to optimize for it; requiring 55% after a 15% Offsite Ads fee can make POD apparel prices uncompetitive.
   - State what is excluded: shipping subsidy, taxes, VAT, currency conversion, Etsy Ads, returns, samples, discounts.

8. **Printify Update**
   - Prefer a safe `GET -> build full payload -> PUT -> GET` flow.
   - Preserve `blueprint_id`, `print_provider_id`, enabled variants, `print_areas`, image IDs, placement, and disabled/enabled state unless intentionally changing them.
   - Write sanitized manifests. Do not commit upload IDs, shop IDs, tokens, private order/customer data, or raw secret-bearing responses.

9. **Validation**
   - Confirm Printify accepted the update with a GET.
   - Re-check title, description, tags, enabled colors/sizes, and prices.
   - Inspect real mockups if variant/color strategy changed.
   - Run a secret scan over text artifacts before final response.

10. **Documentation**
   - Update the spike `RESOURCES.md` with:
     - old vs new titles
     - final descriptions or manifest path
     - pricing assumptions and source URLs
     - product URLs
     - commands/scripts used
     - tradeoffs

## Pricing Script

Use:

```bash
python "$SKILL_DIR/scripts/etsy_pod_price_matrix.py" \
  --cost S=11.29 --cost M=11.29 --cost L=11.29 --cost XL=11.29 --cost 2XL=13.82 --cost 3XL=16.12 \
  --price S=33.99 --price M=33.99 --price L=33.99 --price XL=33.99 --price 2XL=40.99 --price 3XL=46.99 \
  --target-standard-margin 55%
```

The script is item-price-only. Add shipping/free-shipping strategy separately before publication. If the user asks for a fixed-dollar floor too, pass `--target-standard-profit AMOUNT` in addition to the 55% margin.

## Output Shape

When finishing an optimization, report:

- Product URLs updated.
- New titles.
- Final price table.
- Fee assumptions with source dates.
- Files/manifests updated.
- Residual tradeoffs and excluded costs.
