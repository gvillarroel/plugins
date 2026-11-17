# Printify Product Family Best Practices

In these examples, `$SkillsDir` is the absolute `skills` folder of the installed `store-studio` plugin. Run commands from the store workspace.

Use this reference when a design may move beyond shirts into any Printify product family. It is intentionally family-based: Printify has many blueprints, and exact print areas, provider support, variant IDs, and mockup behavior must still be verified per blueprint/provider before upload or publishing.

## Source Notes

Current working sources:

- Local authenticated catalog crawl: `shared/references/printify-catalog-2026-05-31/`
- Local reference images: `shared/assets/references/printify-products/`
- Local preview templates: `$SkillsDir/create-printify-product/references/preview-templates.json`
- Printify custom products page, checked 2026-06-06: https://printify.com/custom-products/
- Printify product selection guide, checked 2026-06-06: https://printify.com/blog/how-to-pick-a-product/
- Printify custom printing page, checked 2026-06-06: https://printify.com/custom-printing/
- Current API blueprint snapshot, fetched with Node `fetch` on 2026-06-06: `shared/references/printify-catalog-2026-06-06/blueprints.json`
- Current API orientation summary: `shared/references/printify-catalog-2026-06-06/blueprints-summary.json`
- Product-level composition reference, generated from providers and variants on 2026-06-06: `shared/references/printify-composition-reference-2026-06-06/`

Verification limit:

- A fresh API blueprint fetch was attempted on 2026-06-06 with Python `urllib`, but `api.printify.com` returned Cloudflare `1010` / browser signature blocked. The same endpoint succeeded with Node `fetch` and returned 1,409 blueprints. Use the 2026-06-06 blueprint snapshot for current blueprint availability, and use the 2026-05-31 authenticated crawl for category context, representative detail pages, and reference images.

## Universal Preparation Rules

- Choose product family before art direction. A shirt design, mug wrap, poster, hat embroidery, and phone case need different composition.
- Do not reuse one canvas blindly across families. Preserve the concept, then rebuild layout for each product's aspect ratio and print method.
- Treat product color/material as the background when the product uses transparent DTG or embroidery-style placement.
- Treat the full print area as the artwork when the product uses sublimation, AOP, posters, canvas, mouse pads, desk mats, bedding, or towels.
- Keep separate production files per family and placement. A shared source can exist, but final PNGs should be product-specific.
- Verify exact blueprint, print provider, variants, placements, and print areas before upload. Do not infer them from a similar product.
- Save approximate local previews, but only real Printify editor screenshots or `product.images[].src` mockups count as product proof.
- Prefer product-specific mockup review before campaign images. AI/model promo imagery must not redraw the approved product art.

## Product Family Map

Use this routing table to decide the art contract quickly.

| Family | Observed Printify categories | Default art contract | Key risk |
| --- | --- | --- | --- |
| DTG apparel | T-shirts, hoodies, sweatshirts, long sleeves, tank tops, kids shirts, baby clothing | Transparent PNG; garment color shows through | Low contrast, wrong vertical placement, oversized dense rectangles |
| AOP apparel | Cut-and-sew tees, leggings, dresses, skirts, sportswear, swimwear, shoes, socks | Full-bleed opaque art mapped across panels | Seams, mirrored panels, important details crossing folds/crotch/side seams |
| Embroidery apparel/accessories | Hats, chest/wrist embroidery, bags, blankets/throws with embroidery | Simple solid vector-like art; few colors | Tiny text, gradients, thin lines, too much detail |
| Mugs and drinkware | Mugs, travel mugs, tumblers, bottles, glassware | Opaque wrap or front art; often white/transparent product background | Handle dead zone, wrap seam, cylindrical distortion |
| Wall art and paper | Posters, canvas, framed art, postcards, greeting cards | Opaque full-bleed art with safe margins | Low resolution, no bleed, weak edges, text too close to trim |
| Stickers and magnets | Kiss-cut, die-cut, square stickers, magnets, buttons | Strong silhouette; transparent cutline-style PNG or full-bleed shape | Weak outer contour, tiny type, unclear cut boundary |
| Flat accessories | Mouse pads, desk mats, phone cases, laptop sleeves, AirPod cases, tech accessories | Full-bleed art adapted to object shape | Camera holes, rounded corners, edge loss, hand coverage |
| Bags and travel | Totes, backpacks, drawstring bags, duffels, pouches, sling bags, luggage | Transparent centered print or full-bleed/AOP depending product | Print hidden by handles, seams, zippers, pockets, curves |
| Stationery and books | Journals, notebooks, calendars, bookmarks, cards | Opaque cover/page art with trim-safe margins | Spine/gutter, spiral holes, calendar grid conflict |
| Home textiles | Blankets, pillows, towels, bedding, shower curtains, rugs, mats, tapestries | Large opaque full-bleed art; repeat or hero layout | Detail loss on fabric pile, fold/corner distortion, huge file size |
| Home decor and kitchen | Candles, coasters, ornaments, clocks, cutting boards, banners, wall clocks | Shape-specific opaque or transparent art | Small curved surfaces, holes/hangers, glare, material contrast |
| Pets and baby accessories | Pet bandanas/bowls, baby accessories, bibs | Simple high-contrast art; safe product-specific placement | Safety/compliance context, tiny print area, curved or folded surface |
| Jewelry and engraving | Bracelets, pendants, keychains, pens, leather patches | One-color high-contrast line art; vector-like source preferred | Fine detail loss, illegible micro text, metal/leather glare |
| Seasonal and gifts | Ornaments, cards, candles, stockings, calendars, gift sets | Product-specific; often small, shape-bound, or packaging-aware | Too much copy, seasonal cutoff dates, photo personalization needs |

## Apparel: DTG Tops And Kids Clothing

Use this for standard shirts, hoodies, sweatshirts, long sleeves, tank tops, kids tees, and baby garments.

- Use transparent PNG unless an opaque patch is intentional.
- Design for the garment color first; color variants must preserve contrast.
- Keep primary art on the chest or back print zone, not the belly or near seams.
- Hoodies need extra care around pocket, zipper, drawstrings, and hood shadow in mockups.
- Kids and baby garments need simpler, larger marks because the print surface is smaller.
- For sleeve, wrist, and neck-label placements, use compact marks, not full slogans.
- Avoid heavy ink rectangles on fleece or light fabric unless the aesthetic intentionally wants a patch.
- For store concepts based on children's drawings, preserve the drawing's handmade character but clean enough for thumbnail readability.

Read `../../create-shirt-product/references/composition-best-practices.md` conceptually for shirt composition, but verify product-specific print areas through this skill.

## AOP Apparel

Use this for cut-and-sew tees, leggings, dresses, skirts, swimwear, sportswear, shoes, socks, and other panel-mapped products.

- Build full-bleed opaque art at the exact template dimensions.
- Keep important faces, words, logos, and symbols away from panel seams, crotch, heel/toe, side seams, waistbands, and cuffs.
- Prefer seamless patterns, large textures, or repeated motifs over one centered poster composition.
- For leggings and socks, avoid readable text unless it is huge and intentionally placed on a flat visible panel.
- For shoes and swimwear, inspect every panel; a good flat file can fail when wrapped around product geometry.
- Create a seam-risk preview/contact sheet before upload when the product has multiple print panels.

## Mugs, Tumblers, Bottles, And Glassware

Use this for ceramic mugs, black/accent mugs, latte mugs, travel mugs, tumblers, bottles, can holders, and glassware.

- Use opaque wrap art by default. White space can be intentional background, especially on white sublimation products.
- Account for handle/dead zones. A front-only design should face outward from the handle; a wrap design needs left/right balance.
- Avoid placing critical text exactly at the wrap seam.
- Keep type large enough for a curved surface; small lines get harder to read around the cylinder.
- For black or colored drinkware, verify whether white ink/underbase is supported. Do not assume transparent pixels reveal useful product color.
- For glassware, account for translucency and glare; high-contrast single-color marks often work better than subtle gradients.

## Posters, Canvas, Cards, And Paper

Use this for posters, canvas, framed prints, postcards, greeting cards, calendars, bookmarks, and other paper products.

- Use opaque full-bleed art unless the product explicitly expects transparency.
- Keep bleed and trim margins. Important text and faces should sit inside a safe zone.
- Posters and canvas can support more detail than shirts, but product thumbnails still need one clear first read.
- Canvas wraps need edge-aware art; never put critical text or faces near wrapped sides.
- Cards and calendars need front/back/page planning. A pretty front is not enough if the interior/back requires branding, barcode, date grid, or message area.
- Use sRGB exports and high enough pixel dimensions for the selected size.

## Stickers, Magnets, And Buttons

Use this for kiss-cut stickers, die-cut stickers, square stickers, magnets, and pin/button products.

- Build a strong silhouette first. The outer contour is part of the product.
- Avoid fuzzy edges unless the sticker is deliberately rectangular/full-bleed.
- Use fewer words and larger lettering than on posters.
- Leave breathing room between art and implied cut edge.
- For die-cut style work, inspect the alpha edge at high zoom and on a contrasting background.
- For magnets and buttons, avoid important details near curved or crimped edges.

## Phone Cases And Tech Accessories

Use this for phone cases, AirPod cases, laptop sleeves, mouse pads, desk mats, and similar flat accessories.

- Use full-bleed art for cases, mats, sleeves, and desk mats unless the product is clearly a centered logo placement.
- Keep important art away from camera holes, rounded corners, folds, zipper seams, and grip zones.
- Phone cases are tall and narrow; rebuild shirt/poster concepts as vertical compositions.
- Mouse pads and desk mats are wide; horizontal layouts, code snippets, diagrams, and panoramic patterns work well.
- Test both light and dark product mockups when the accessory base color varies.
- For tech accessories, avoid trademarked device UI, protected logos, and screenshots unless they are original or clearly transformed.

## Bags, Pouches, Travel, And Totes

Use this for totes, backpacks, duffels, drawstring bags, pouches, sling bags, luggage, and travel accessories.

- Decide whether the product is a centered print product or an AOP/full-bleed product before composing.
- Keep art clear of handles, straps, pockets, zippers, seams, and curved corners.
- Totes work well with shirt-like centered graphics, but need slightly simpler edges because fabric wrinkles.
- Backpacks and sling bags often have smaller practical print zones; use logo, emblem, or short phrase designs.
- Luggage and large bags can take patterns or large motifs, but need mockup review from multiple angles.

## Hats, Patches, And Embroidery

Use this for caps, beanies, embroidered apparel placements, embroidered bags, and patches.

- Use simple, bold, vector-like art. Think emblem, initials, icon, short wordmark.
- Avoid gradients, photographs, distressed textures, tiny text, and thin strokes.
- Limit colors; thread changes and small stitches reduce clarity.
- Curved hat fronts distort horizontal text. Use compact marks and inspect real mockups.
- For left-chest or wrist embroidery, keep the design much smaller and cleaner than DTG art.
- For faux leather patches or engraved patches, design as high-contrast line art and verify material/color contrast.

## Home Textiles

Use this for blankets, throws, pillows, pillowcases, towels, bedding, rugs, mats, shower curtains, and tapestries.

- Use full-bleed opaque art by default.
- Large items benefit from either a repeated pattern or one hero composition with generous edge margins.
- Fabric pile, folds, and stitching reduce fine detail. Use larger shapes and stronger contrast than a poster.
- Pillows need safe zones away from seams and corners; square art should still read when the pillow bulges.
- Towels and blankets may be viewed folded. Keep the main hook visible in a central or repeated position.
- Bedding and rugs often need room-scale thinking: avoid tiny centered graphics floating in a large empty field unless minimalism is intentional.

## Home Decor, Kitchen, Candles, And Ornaments

Use this for coasters, candles, cutting boards, ornaments, clocks, banners, wall decor, and kitchen accessories.

- Start from the object shape: round, square, vertical label, hanging ornament, or handled tool.
- Keep labels readable at small size and across glare.
- For candles, plan both label design and product scent/theme fit.
- For coasters and cutting boards, expect edge wear and object use; keep art bold and away from the rim.
- For ornaments, avoid thin text and place the hook below any hanger hole or top cap.
- For clocks, do not let art obscure hands/numbers unless the product is intentionally decorative.

## Pets, Baby Accessories, And Safety-Sensitive Products

Use this for pet bandanas, bowls, baby accessories, bibs, and related products.

- Keep copy harmless, family-safe, and product-appropriate.
- Use simple high-contrast art that survives folds and small print areas.
- Avoid designs that imply unsafe use, choking hazards, medical claims, or inappropriate content for baby/kids products.
- For bowls and curved objects, favor icons or short names over long slogans.

## Jewelry, Engraving, Pens, And Small Gifts

Use this for engraved bracelets, pendants, pens, keychains, patches, and small personalized gifts.

- Build one-color art first; vector-style source is preferred even if final upload is PNG.
- Use initials, monograms, coordinates, short words, or simple icons.
- Avoid portraits and complex scenes unless the product is explicitly a photo pendant.
- Inspect at actual product scale. If the design only reads on a zoomed editor screen, it will fail in hand.
- For personalization, create a clear text-length limit before generating variants.

## Product Selection Checklist

Before starting a product spike:

1. Choose the target store: `dibujos-infantiles` or `ia-referencias`.
2. Choose the product family and whether it is DTG, sublimation/AOP, embroidery, engraving, or paper print.
3. Look up the candidate in `shared/references/printify-composition-reference-2026-06-06/index.json`.
4. Open the product file listed there and review `composition`, `option_summary`, `placement_summary`, and provider-level `placement_dimensions`.
5. Choose the exact Printify blueprint and print provider when possible.
6. Fetch or read exact placements, variants, colors, sizes, and print areas.
7. Pick the art contract: transparent placement, opaque full-bleed, wrap, panel map, vector-like embroidery, or engraving.
8. Generate product-specific production files and previews.
9. Validate PNG size, alpha/opacity, edges, and color contrast.
10. Upload only after the exact production file passes family-specific review.
11. Use real Printify mockups before final acceptance or campaign imagery.

## Fast Reuse Patterns

- Shirt concept to mug: keep the phrase/icon, rebuild as front-and-back wrap or single front mark; do not paste the shirt rectangle.
- Shirt concept to poster: add richer detail and stronger border/bleed control; keep one first read.
- Shirt concept to sticker: simplify to silhouette and large type; remove secondary text.
- Shirt concept to hat: reduce to one emblem or wordmark; remove gradients and tiny detail.
- Shirt concept to phone case: make it vertical; keep critical art away from camera holes.
- Shirt concept to blanket: turn it into a repeated motif or large central art with enough edge breathing room.
- Shirt concept to journal: build a cover system with title area, spine awareness, and back cover optionality.
- Drawing concept to products: keep the original drawing as the hero on shirts, mugs, stickers, posters, and journals; use patterns or cropped motifs for AOP/textiles.
