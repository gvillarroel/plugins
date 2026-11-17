import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const API_BASE = "https://api.printify.com/v1";
const DEFAULT_LIMIT = 20;

function parseArgs(argv) {
  const options = {
    outputDir: null,
    manifest: null,
    productFilter: "shirts",
    titleMatch: null,
    productId: null,
    blueprintIds: [],
    positions: [],
    selectedOnly: false,
    visibleOnly: false,
    limit: DEFAULT_LIMIT,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => {
      index += 1;
      if (index >= argv.length) {
        throw new Error(`Missing value for ${arg}`);
      }
      return argv[index];
    };

    if (arg === "--output-dir") options.outputDir = next();
    else if (arg === "--manifest") options.manifest = next();
    else if (arg === "--product-filter") options.productFilter = next();
    else if (arg === "--title-match") options.titleMatch = next();
    else if (arg === "--product-id") options.productId = next();
    else if (arg === "--blueprint-id") options.blueprintIds.push(Number(next()));
    else if (arg === "--positions") {
      options.positions = next()
        .split(",")
        .map((value) => value.trim().toLowerCase())
        .filter(Boolean);
    } else if (arg === "--selected-only") options.selectedOnly = true;
    else if (arg === "--visible-only") options.visibleOnly = true;
    else if (arg === "--limit") options.limit = Number(next());
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!options.outputDir) throw new Error("--output-dir is required.");
  if (!options.manifest) throw new Error("--manifest is required.");
  if (!Number.isInteger(options.limit) || options.limit < 1 || options.limit > 20) {
    throw new Error("--limit must be an integer from 1 to 20.");
  }
  if (!["shirts", "all"].includes(options.productFilter)) {
    throw new Error("--product-filter must be shirts or all.");
  }
  if (options.titleMatch) {
    options.titleRegex = new RegExp(options.titleMatch, "i");
  }

  return options;
}

function printHelp() {
  console.log(`Download final Printify product mockups from product.images[].

Required:
  --output-dir <path>   Directory for downloaded images.
  --manifest <path>     Sanitized JSON manifest path.

Optional:
  --product-filter shirts|all   Product title filter. Default: shirts.
  --title-match <regex>         Additional product title regex.
  --product-id <id>             Download one exact shop product by ID. ID is not written to the manifest.
  --blueprint-id <id>           Restrict to a blueprint. Repeatable.
  --positions front,back,other  Restrict downloaded mockup positions.
  --selected-only               Only images selected for publishing.
  --visible-only                Only visible products.
  --limit <1-20>                API page size. Default: 20.

Environment:
  PRINTIFY_API_TOKEN and PRINTIFY_SHOP_ID must be set.`);
}

function slugify(value) {
  return String(value)
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function variantParts(title) {
  const parts = String(title || "")
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean);
  return {
    color: parts[0] || null,
    size: parts[1] || null,
  };
}

function imageExtension(contentType, fallbackUrl) {
  if (contentType?.includes("png")) return "png";
  if (contentType?.includes("webp")) return "webp";
  if (contentType?.includes("jpeg") || contentType?.includes("jpg")) return "jpg";
  const urlPath = new URL(fallbackUrl).pathname;
  const ext = path.extname(urlPath).replace(".", "").toLowerCase();
  return ext || "jpg";
}

function isShirtProduct(product) {
  const title = String(product.title || "").toLowerCase();
  return (
    title.includes("tee") ||
    title.includes("t-shirt") ||
    title.includes("shirt") ||
    title.includes("polera")
  );
}

function shouldDownloadProduct(product, options) {
  if (options.visibleOnly && !product.visible) return false;
  if (options.productFilter === "shirts" && !isShirtProduct(product)) return false;
  if (options.titleRegex && !options.titleRegex.test(product.title || "")) return false;
  if (options.blueprintIds.length > 0 && !options.blueprintIds.includes(product.blueprint_id)) {
    return false;
  }
  return true;
}

function shouldDownloadImage(image, options) {
  if (options.selectedOnly && !image.is_selected_for_publishing) return false;
  if (options.positions.length === 0) return true;
  return options.positions.includes(String(image.position || "").toLowerCase());
}

async function printifyGet(pathname, token, shopId) {
  const response = await fetch(`${API_BASE}${pathname}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const redactedPath = pathname.replace(shopId, "{shop_id}");
    throw new Error(`Printify GET ${redactedPath} failed: ${response.status}`);
  }
  return response.json();
}

async function fetchProducts(token, shopId, limit) {
  const products = [];
  let page = 1;

  while (true) {
    const response = await printifyGet(
      `/shops/${shopId}/products.json?limit=${limit}&page=${page}`,
      token,
      shopId,
    );
    products.push(...(response.data || []));

    if (!response.next_page_url || page >= Number(response.last_page || page)) {
      break;
    }
    page += 1;
  }

  return products;
}

async function fetchProduct(token, shopId, productId) {
  return printifyGet(`/shops/${shopId}/products/${productId}.json`, token, shopId);
}

async function downloadImage(image, filePath) {
  const response = await fetch(image.src);
  if (!response.ok) {
    throw new Error(`Image download failed: ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  const bytes = Buffer.from(await response.arrayBuffer());
  await writeFile(filePath, bytes);

  return {
    content_type: contentType,
    bytes: bytes.length,
  };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const token = process.env.PRINTIFY_API_TOKEN;
  const shopId = process.env.PRINTIFY_SHOP_ID;

  if (!token || !shopId) {
    throw new Error("PRINTIFY_API_TOKEN and PRINTIFY_SHOP_ID must be set.");
  }

  await mkdir(options.outputDir, { recursive: true });
  await mkdir(path.dirname(options.manifest), { recursive: true });

  const products = options.productId
    ? [await fetchProduct(token, shopId, options.productId)].filter((product) =>
        shouldDownloadProduct(product, { ...options, productFilter: "all" }),
      )
    : (await fetchProducts(token, shopId, options.limit)).filter((product) =>
        shouldDownloadProduct(product, options),
      );
  const manifest = {
    generated_at: new Date().toISOString(),
    source: "Printify API product.images[] final mockups",
    safety:
      "API token, shop ID, product IDs, mockup IDs, upload image IDs, variant IDs, and source URLs are intentionally omitted.",
    filters: {
      product_filter: options.productFilter,
      product_id: options.productId ? "provided-redacted" : null,
      title_match: options.titleMatch,
      blueprint_ids: options.blueprintIds,
      positions: options.positions,
      selected_only: options.selectedOnly,
      visible_only: options.visibleOnly,
    },
    products: [],
  };

  for (const product of products) {
    const productSlug = `${product.blueprint_id}-${slugify(product.title)}`;
    const variantTitles = new Map(
      (product.variants || []).map((variant) => [variant.id, variant.title]),
    );
    const images = (product.images || []).filter((image) =>
      shouldDownloadImage(image, options),
    );
    const productEntry = {
      title: product.title,
      blueprint_id: product.blueprint_id,
      print_provider_id: product.print_provider_id,
      visible: Boolean(product.visible),
      image_count: images.length,
      images: [],
    };

    for (const [index, image] of images.entries()) {
      const parts = (image.variant_ids || [])
        .map((variantId) => variantParts(variantTitles.get(variantId)))
        .filter((part) => part.color || part.size);
      const colors = unique(parts.map((part) => part.color));
      const sizes = unique(parts.map((part) => part.size));
      const colorSlug = slugify(colors.join("-") || "all-colors");
      const position = slugify(image.position || "mockup");
      const order = String(image.order ?? index + 1).padStart(2, "0");

      const extension = imageExtension("", image.src);
      const fileName = `${productSlug}-${order}-${position}-${colorSlug}.${extension}`;
      const filePath = path.join(options.outputDir, fileName);
      const downloadMeta = await downloadImage(image, filePath);

      productEntry.images.push({
        file: filePath.replaceAll("\\", "/"),
        position: image.position || null,
        order: image.order ?? index + 1,
        is_default: Boolean(image.is_default),
        is_selected_for_publishing: Boolean(image.is_selected_for_publishing),
        colors,
        sizes,
        ...downloadMeta,
      });

      console.log(`downloaded ${fileName}`);
    }

    manifest.products.push(productEntry);
  }

  await writeFile(options.manifest, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`manifest ${options.manifest}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
