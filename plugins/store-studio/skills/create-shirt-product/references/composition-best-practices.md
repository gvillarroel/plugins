# Shirt Composition Best Practices

Use this reference before judging whether a shirt design is good enough to continue into Printify setup, product mockups, or campaign assets. The goal is a wearable graphic that reads quickly, sits naturally on the garment, and survives real print constraints.

## Source Notes

These notes synthesize current placement and design guidance from:

- Printify placement guide: https://printify.com/blog/t-shirt-design-placement-guide/
- Printful placement guide: https://www.printful.com/ca/blog/t-shirt-design-placement-guide
- Accent T-Shirts print size guide: https://accenttshirts.com/knowledge-item/knowledge-base-print-placement-size-guide/
- Bolt Printing detail/readability guide: https://www.boltprinting.com/blog/shirt-design-tip-avoid-tiny-details
- Merch Titans typography guide: https://merchtitans.com/blog/typography-t-shirt-design-guide
- T-Shirt Elephant apparel design guide: https://www.tshirtelephant.com/resource-guide/how-to-design-custom-apparel

Treat exact inch measurements as starting points. Always check the specific Printify product, provider, print area, and mockup before final acceptance.

## First Read

A strong shirt usually has one obvious first read:

- One primary hook: a word, face, object, symbol, or silhouette that is understood first.
- One secondary support: small text, texture, decoration, or context that helps the hook.
- One clear tone: funny, severe, retro, academic, terminal, handmade, childish, etc.

If the viewer cannot describe the shirt in one short phrase after a 2-second glance, simplify the concept before adding polish.

## Placement And Scale

For standard adult full-front shirts:

- Keep the design centered on the garment unless the concept intentionally needs asymmetry.
- Common full-front width is about 10-12 inches; 11 inches is a reliable default.
- Common full-front height is about 12-15 inches; avoid pushing artwork near the hem.
- Center-chest designs usually sit about 3-3.5 inches below the collar.
- Full-front designs usually start about 2.5-4 inches below the collar, depending on garment and provider.
- Complex artwork needs more space than a logo or short text lockup.

For the default `4500x5400` transparent production asset:

- Use the outer 8-12 percent as a practical safety margin unless the design is intentionally oversized.
- Keep the primary mass chest-high, not vertically centered so low that it reads like a belly print.
- Avoid filling the full rectangular print canvas. The shirt should not look like a pasted poster unless that is the intentional style.
- Define an anchor point before Printify placement. For symmetrical art this is usually the centerline; for asymmetrical art, choose the optical center of visual weight.
- Preview on the smallest target shirt size when possible. A design that only works on XL is not ready for a general product.

## Layout Patterns That Work

Use one of these as the default structure unless the concept demands another layout:

- Centered stack: top text, central figure or symbol, bottom text. Best for quote, thinker, meme, and statement shirts.
- Typographic block: short phrase arranged with clear hierarchy. Best when words are the product.
- Emblem or badge: compact centered mark with contained lettering. Best for logos, clubs, faux institutions, and retro marks.
- Illustration plus caption: illustration dominates; caption supports without competing.
- Reference UI crop: preserve the recognizable proportions of the source UI while removing accidental screenshot background.
- Oversized art: large visual mass with simple edges and minimal copy. Use only when mockups prove it does not crowd seams, collar, or hem.

## Typography

Text-led shirts fail fastest when type is decorative but unreadable.

- Limit to 1-2 fonts in most designs; use 3 only when there is a clear hierarchy reason.
- Make the primary word or phrase the largest and boldest element.
- Use line breaks as composition, not as leftovers from fitting text.
- For adult full-front typography, make the main headline roughly 2 inches tall or larger on the garment when text is the hook.
- Keep subtext short. If it cannot be read in a product thumbnail or at arm's length, remove it or make it part of the source notes instead of the artwork.
- Avoid thin scripts, condensed novelty fonts, and tiny serifs for critical text.
- Adjust kerning/tracking manually for all-caps words, curved text, and large display type.
- Do not let top and bottom text overpower a figure unless the concept is a typographic shirt with an illustration accent.
- For vertical phrase stacks, make the smallest final line feel intentionally separate from the headline above it. If a divider sits between them, place it from the rendered alpha bounding box, not font metrics, and leave visible air above and below the rule.

## Contrast And Color

Pick the garment color before final color decisions.

- Use the shirt color as the background. Do not bake garment color into the production PNG unless explicitly requested.
- Prefer high-contrast ink/fabric combinations: light ink on dark shirts, dark ink on light shirts.
- Avoid low-contrast combinations such as dark gray on black, navy on purple, pale ink on heather, or red/green pairings that collapse on fabric.
- Keep most shirt graphics to 1-3 ink colors unless color complexity is the point.
- Make text and figure share an ink logic. A black-ink figure with unrelated bright text usually looks assembled rather than designed.
- Use negative space as part of the composition. It improves readability and helps the design feel printed on fabric instead of pasted onto fabric.

## Detail And Print Survival

Shirt art is viewed from several feet away and printed on fabric texture.

- Avoid critical fine lines, tiny symbols, and small internal facial details.
- Use bold shapes, clean silhouettes, and deliberate spacing.
- If details disappear in a 300 px wide preview, they are decoration, not information.
- Do not solve overcrowding by shrinking every element. Remove secondary elements first.
- Large dense rectangles can feel heavy and reduce breathability. Break them with transparent space, texture, or open shape when possible.
- Distress effects should support the style, not destroy letterforms or faces.

## Visual Hierarchy Checks

Before calling a composition final, inspect:

- Squint test: the main shape still reads when blurred or zoomed out.
- Thumbnail test: at about 300 px wide, the hook is still readable or recognizable.
- Arm's-length test: text and focal figure read without leaning in.
- Black/white test: a flattened value preview still has a clear focal point.
- Crop test: no important text, face, or symbol sits near the print-area edge.
- Mockup test: the design sits on the chest, not too high like a tag and not too low like an accident.
- Close-crop test: when a user flags one element as too close, inspect a cropped real mockup around that exact area before accepting a fix. A contact sheet can hide cramped spacing or near-cropping in small subtext.

## Common Failure Modes

Reject or revise when you see:

- No single focal point.
- Too many fonts, colors, slogans, textures, or ornaments fighting.
- Text that only reads at full-size canvas zoom.
- A figure that is technically detailed but has a weak silhouette.
- A full rectangular image with transparent corners only, creating a poster-on-shirt effect.
- Top and bottom text with different weights, styles, or spacing that look unrelated.
- A small subline, date, day marker, price, or punchline that visually touches the preceding headline or divider.
- Art placed too low in the preview.
- Complex artwork squeezed into left chest or tiny center chest placement.
- Contrast that works on a white editor background but fails on the garment.
- A generated mockup where the shirt art has been redrawn or distorted.

## Composition Review Protocol

Run this before accepting a serious spike:

1. Make the transparent print PNG.
2. Make at least one preview on the actual target garment color.
3. Check the alpha bounding box and outer margins.
4. Review the design at full size, 600 px wide, and 300 px wide.
5. Confirm one primary hook, one secondary support, and enough breathing room.
6. Confirm typography hierarchy, line breaks, contrast, and garment placement.
7. If using Printify, validate against the product's exact print area and inspect a real Printify mockup or editor screenshot before product acceptance.

Do not advance to Printify upload or campaign images when the composition still fails readability, hierarchy, contrast, or garment placement.
