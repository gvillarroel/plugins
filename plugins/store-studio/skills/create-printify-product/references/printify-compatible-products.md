# Printify-Compatible Product Families

In these examples, `$SkillsDir` is the absolute `skills` folder of the installed `store-studio` plugin. Run commands from the store workspace.

This workspace can prepare prototypes for the full observed Printify catalog, but exact production specs remain product-specific. Do not invent print areas, provider IDs, or variant IDs. Use family rules for concept preparation, then verify the selected blueprint/provider through the Printify catalog, editor, or API before upload.

Primary companion reference:

- `product-family-best-practices.md`

## Current Verification Status

- Public Printify pages checked: 2026-06-06.
- Local authenticated catalog crawl: `shared/references/printify-catalog-2026-05-31/`.
- Local crawl coverage: 38 catalog/category pages, 678 unique product URLs, 18 representative product detail pages.
- Current API blueprint snapshot: `shared/references/printify-catalog-2026-06-06/blueprints.json`, fetched with Node `fetch` on 2026-06-06, 1,409 blueprints.
- Current API orientation summary: `shared/references/printify-catalog-2026-06-06/blueprints-summary.json`.
- Current product-level composition reference: `shared/references/printify-composition-reference-2026-06-06/`, covering 1,409 blueprints, 81,017 variants, and 0 API failures.
- Python `urllib` API fetch attempted 2026-06-06, but `api.printify.com` returned Cloudflare `1010` / browser signature blocked. Use Node `fetch`, the Printify editor, or browser automation when Python is blocked.

Printify public pages currently describe 1,300+ custom products and six main catalog categories. The current API blueprint snapshot confirms 1,409 available blueprints. The local crawl observed these top-level routes:

- Men
- Women
- Kids
- Accessories
- Home and Living
- For-you/promotional collections such as New Arrivals, Bestsellers, Embroidery, Engraving, AOP Clothing, Personalization Picks, Early Access, and Printify Choice

## Family Readiness Matrix

| Family | Ready for concept prototypes | Ready for publish without exact product lookup | Default production route |
| --- | --- | --- | --- |
| DTG tops | Yes | No | Transparent PNG on garment color |
| Hoodies/sweatshirts | Yes | No | Transparent PNG, pocket/hood/zipper-aware |
| Kids/baby apparel | Yes | No | Transparent PNG with larger simpler art |
| AOP apparel | Yes | No | Exact full-bleed panel/template art |
| Mugs/drinkware | Yes | No | Opaque wrap/front PNG |
| Posters/canvas/cards | Yes | No | Opaque full-bleed art with bleed/safe margin |
| Stickers/magnets/buttons | Yes | No | Silhouette/cutline-aware PNG |
| Phone cases/tech accessories | Yes | No | Full-bleed shape-aware art |
| Mouse pads/desk mats | Yes | No | Full-bleed wide art |
| Bags/totes/travel | Yes | No | Transparent placement or full-bleed depending product |
| Hats/embroidery/patches | Yes | No | Simple vector-like art |
| Home textiles | Yes | No | Large full-bleed art or repeat pattern |
| Home decor/kitchen/ornaments | Yes | No | Shape-specific art |
| Pets/baby accessories | Yes | No | Simple safe high-contrast art |
| Jewelry/engraving/pens | Yes | No | One-color line art or personalization template |

## Observed Product Categories

Men:

- T-shirts
- Hoodies
- Sweatshirts
- Long sleeves
- Tank tops
- Sportswear
- Bottoms
- Swimwear
- Shoes
- Outerwear

Women:

- T-shirts
- Hoodies
- Sweatshirts
- Long sleeves
- Tank tops
- Skirts and dresses
- Sportswear
- Bottoms
- Swimwear
- Shoes
- Outerwear

Kids:

- T-shirts
- Long sleeves
- Sweatshirts
- Baby clothing
- Sportswear
- Bottoms
- Other

Accessories:

- Jewelry
- Books
- Phone cases
- Bags
- Socks
- Hats
- Underwear
- Baby accessories
- Mouse pads
- Pets
- Kitchen accessories
- Car accessories
- Tech accessories
- Travel accessories
- Stationery accessories
- Sports and games
- Face masks
- Other

Home and Living:

- Mugs
- Candles
- Ornaments
- Seasonal decorations
- Glassware
- Bottles and tumblers
- Canvas
- Posters
- Postcards
- Journals and notebooks
- Magnets and stickers
- Home decor
- Blankets
- Pillows and covers
- Towels
- Bathroom
- Rugs and mats
- Bedding
- Food, health, and beauty

## Known Workspace Specs

### Tops

Use transparent PNGs unless the design intentionally needs an opaque background. The garment color should usually show through.

Known verified top:

- `tops.gildan_5000`
- Product: `Unisex Heavy Cotton Tee / Gildan 5000`
- Front/back print area: `3951x4919`
- Preferred production canvas: `4500x5400`
- Current reference: `shared/references/printify-unisex-heavy-cotton-tee-gildan-5000.md`

Generic hoodie work is allowed for visual iteration, but do not publish until the exact Printify blueprint, provider, variants, and placement dimensions are extracted.

### Mugs

Use opaque art unless the selected mug/product specifically supports transparency in a useful way. A full white wrap is normal for white sublimation mugs.

Known API example:

- `mugs.mug_11oz`
- Product: `Mug 11oz`
- Print image in official API example: `4350x5850`
- API example IDs: blueprint `68`, print provider `9`, variant `33719`

Treat those IDs as a starting point from the official docs, then verify against the authenticated shop/catalog before publishing.

## Representative Local Product Details

The local crawl includes detail pages and reference images for:

- Gildan 5000 heavy cotton tee
- Gildan 18500 hoodie
- Gildan 18000 crewneck sweatshirt
- AWDIS college hoodie
- 11oz mug
- 11oz/15oz ceramic mug
- matte vertical posters
- rectangle mouse pad
- kiss-cut stickers
- tough phone cases
- organic canvas tote bag
- distressed dad hat embroidery
- velveteen plush blanket
- square pillow
- hardcover journal
- stainless steel travel mug
- sublimation socks
- explorer sling bag embroidery

Use those as representative examples only. They are not substitutes for exact product specs when creating a real product.

## Store Routing

Use `stores/dibujos-infantiles` for children's drawing products and `stores/ia-referencias` for AI, developer, terminal, model, and workflow references. Shared Printify specs and scripts stay in `$SkillsDir/create-printify-product` or `shared/`.
