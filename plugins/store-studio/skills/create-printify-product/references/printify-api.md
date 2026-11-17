# Printify API Notes

In these examples, `$SkillsDir` is the absolute `skills` folder of the installed `store-studio` plugin. Run commands from the store workspace.

Checked against the official Printify API reference on 2026-05-31:

- `https://developers.printify.com/`

## Credentials

Use environment variables. Do not commit secrets.

```bash
PRINTIFY_API_TOKEN=...
PRINTIFY_SHOP_ID=...
```

Verified token creation route on 2026-06-02:

- Page: `https://printify.com/app/account/api`
- UI section: `Connections`
- Known-good scoped permissions for upload/create/mockup polling:
  - `shops.read`
  - `catalog.read`
  - `products.read`
  - `products.write`
  - `uploads.read`
  - `uploads.write`
  - `print_providers.read`

The scripts in this skill call `https://api.printify.com` and send:

```text
Authorization: Bearer <PRINTIFY_API_TOKEN>
Content-Type: application/json
```

## Catalog Lookup

To create a product through the API, the payload needs catalog IDs:

- `blueprint_id`
- `print_provider_id`
- variant IDs that belong to that blueprint/provider pair

Useful endpoints:

```text
GET /v1/catalog/blueprints.json
GET /v1/catalog/blueprints/{blueprint_id}/print_providers.json
GET /v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json
```

The variants endpoint supports `show-out-of-stock=1` when we need to inspect unavailable variants too.

## Uploads

Upload art before creating a product:

```text
POST /v1/uploads/images.json
```

Printify supports upload by image URL or base64 encoded file contents. Their docs recommend URL upload for files larger than 5 MB.

The response includes an image `id`. Use that value inside `print_areas[].placeholders[].images[]`.

Do not commit upload response IDs for private tests unless there is a specific reason. Prefer sanitized manifests that record the local print asset and downloaded mockup files.

## Product Creation

Create a product in a shop:

```text
POST /v1/shops/{shop_id}/products.json
```

Required product fields include:

- `title`
- `description`
- `blueprint_id`
- `print_provider_id`
- `variants`
- `print_areas`

The product payload shape used by the scripts is:

```json
{
  "title": "Product title",
  "description": "Product description",
  "blueprint_id": 68,
  "print_provider_id": 9,
  "variants": [
    { "id": 33719, "price": 1999, "is_enabled": true }
  ],
  "print_areas": [
    {
      "variant_ids": [33719],
      "placeholders": [
        {
          "position": "front",
          "images": [
            {
              "id": "uploaded-image-id",
              "x": 0.5,
              "y": 0.5,
              "scale": 1,
              "angle": 0
            }
          ]
        }
      ]
    }
  ]
}
```

Creating a product is enough to trigger mockup generation for the tested Gildan 5000 / Printify Choice flow. Publishing was not required and was not tested for mockup generation.

## Mockup Retrieval

Verified on 2026-06-02 with Gildan 5000 / Printify Choice:

1. `POST /v1/uploads/images.json` with a transparent `4500x5400` PNG.
2. `POST /v1/shops/{shop_id}/products.json` using blueprint `6`, print provider `99`, and selected variant IDs.
3. Poll `GET /v1/shops/{shop_id}/products/{product_id}.json`.
4. Wait until `images[]` is non-empty.
5. Download final mockups from `images[].src`.

Important distinctions:

- `product.images[]` contains final generated mockups.
- `print_areas[].placeholders[].images[].src` can point to SVG placement/adjuster assets. Those are not final product mockups.
- In the verified test, `product.images` was initially empty, then populated with 20 mockups per product.
- Front mockups downloaded as `1200x1200` JPEGs from `images-api.printify.com`.
- Save mockups as reviewable artifacts, but sanitize manifests to omit API tokens, shop IDs, private draft product IDs, and upload image IDs.

The Printify public API did not expose a standalone AI Image Generator endpoint in this test. The verified API route is to provide your own artwork, create a draft product, then retrieve generated product mockups from `product.images`.

Second verified run on 2026-06-02: a "define/utilize" Gildan 5000 draft used blueprint `6`, provider `99`, five medium variants, a transparent `4500x5400` front PNG, and placement `{ "x": 0.5, "y": 0.5, "scale": 0.92, "angle": 0 }`. Polling returned 20 generated mockups; five front `1200x1200` JPEGs were downloaded from `images-api.printify.com`.

Verified on 2026-06-04 for existing shop shirts:

1. `GET /v1/shops/{shop_id}/products.json?limit=20&page=1` with Node `fetch`.
2. Filter products by shirt-like titles (`tee`, `t-shirt`, `shirt`, `polera`) or use explicit filters.
3. For each product, download final mockups from `product.images[].src`.
4. Map `product.images[].variant_ids` to variant titles only in memory so the sanitized manifest can store colors and sizes without private variant IDs.
5. Build a contact sheet locally for review and update the manifest with image dimensions.

Reusable commands:

```powershell
node "$SkillsDir/create-printify-product/scripts/download_printify_mockups.js" `
  --output-dir stores\ia-referencias\spikes\YYYY-MM-DD-slug\assets\previews\printify-real `
  --manifest stores\ia-referencias\spikes\YYYY-MM-DD-slug\references\printify-mockups-manifest.json `
  --product-filter shirts

python "$SkillsDir/create-printify-product/scripts/build_mockup_contact_sheet.py" `
  --manifest stores\ia-referencias\spikes\YYYY-MM-DD-slug\references\printify-mockups-manifest.json `
  --output stores\ia-referencias\spikes\YYYY-MM-DD-slug\assets\previews\printify-real\printify-mockups-contact-sheet.jpg
```

If Python `urllib` receives a Cloudflare 1010 response from Printify, retry the same API flow with Node 20+ `fetch` or another standards-compliant HTTP client before changing the payload. Use `scripts/fetch_printify_catalog_node.js` for catalog lookups. The verified "define/utilize" run succeeded with Node `fetch` after Python `urllib` failed; the 2026-06-06 blueprint snapshot also succeeded with the Node script after Python failed.

## Image Positioning

Printify uses normalized placeholder coordinates. Centered artwork uses:

```json
{ "x": 0.5, "y": 0.5, "scale": 1, "angle": 0 }
```

`scale` is relative to the print-area placeholder width. If the artwork width equals the print-area width, `scale: 1` fills the width and keeps the artwork centered at `x: 0.5`, `y: 0.5`.

## Publish Step

Creating a product and publishing it are separate operations. Keep generated payloads and API responses in the product spike, then publish only after checking the mockup in Printify.

```text
POST /v1/shops/{shop_id}/products/{product_id}/publish.json
```
