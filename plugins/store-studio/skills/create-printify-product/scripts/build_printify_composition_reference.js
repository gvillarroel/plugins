import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const API_BASE = "https://api.printify.com/v1";
const DEFAULT_BLUEPRINTS = "shared/references/printify-catalog-2026-06-06/blueprints.json";
const DEFAULT_OUTPUT = "shared/references/printify-composition-reference-2026-06-06";

function printHelp() {
  console.log(`Build a Printify composition reference from catalog blueprints/providers/variants.

Usage:
  node scripts/build_printify_composition_reference.js [options]

Options:
  --blueprints <path>     Blueprint JSON. Default: ${DEFAULT_BLUEPRINTS}
  --output-dir <path>     Output directory. Default: ${DEFAULT_OUTPUT}
  --blueprint-id <id>     Restrict to a blueprint. Repeatable.
  --limit <n>             Process first n selected blueprints.
  --concurrency <n>       Concurrent blueprint jobs. Default: 4.
  --delay-ms <n>          Delay after each API request. Default: 0.
  --retries <n>           Retries for 429/rate-limit API responses. Default: 5.
  --retry-base-ms <n>     Base retry delay for rate limits. Default: 3000.
  --force                 Regenerate existing product summaries.
  --help                  Show this help.

Environment:
  PRINTIFY_API_TOKEN must be set.

Outputs:
  index.json
  products/<blueprint-id>-<slug>.json
  failures.json`);
}

function parseArgs(argv) {
  const options = {
    blueprints: DEFAULT_BLUEPRINTS,
    outputDir: DEFAULT_OUTPUT,
    blueprintIds: [],
    limit: null,
    concurrency: 4,
    delayMs: 0,
    retries: 5,
    retryBaseMs: 3000,
    force: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`Missing value for ${arg}`);
      return argv[index];
    };

    if (arg === "--blueprints") options.blueprints = next();
    else if (arg === "--output-dir") options.outputDir = next();
    else if (arg === "--blueprint-id") options.blueprintIds.push(Number(next()));
    else if (arg === "--limit") options.limit = Number(next());
    else if (arg === "--concurrency") options.concurrency = Number(next());
    else if (arg === "--delay-ms") options.delayMs = Number(next());
    else if (arg === "--retries") options.retries = Number(next());
    else if (arg === "--retry-base-ms") options.retryBaseMs = Number(next());
    else if (arg === "--force") options.force = true;
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!Number.isInteger(options.concurrency) || options.concurrency < 1 || options.concurrency > 12) {
    throw new Error("--concurrency must be an integer from 1 to 12.");
  }
  if (options.limit !== null && (!Number.isInteger(options.limit) || options.limit < 1)) {
    throw new Error("--limit must be a positive integer.");
  }
  if (!Number.isInteger(options.delayMs) || options.delayMs < 0) {
    throw new Error("--delay-ms must be a non-negative integer.");
  }
  if (!Number.isInteger(options.retries) || options.retries < 0 || options.retries > 20) {
    throw new Error("--retries must be an integer from 0 to 20.");
  }
  if (!Number.isInteger(options.retryBaseMs) || options.retryBaseMs < 0) {
    throw new Error("--retry-base-ms must be a non-negative integer.");
  }

  return options;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 90) || "product";
}

function uniqueSorted(values) {
  return [...new Set(values.filter((value) => value !== null && value !== undefined).map(String))].sort((a, b) =>
    a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" }),
  );
}

function sortedEntries(map) {
  return [...map.entries()].sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, "utf8"));
}

async function writeJson(filePath, data) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(data, null, 2)}\n`);
}

async function exists(filePath) {
  try {
    await readFile(filePath);
    return true;
  } catch {
    return false;
  }
}

function isRateLimit(status, text) {
  return status === 429 || /rate limit|too many attempts/i.test(text);
}

async function printifyGet(pathname, token, options) {
  for (let attempt = 0; attempt <= options.retries; attempt += 1) {
    const response = await fetch(`${API_BASE}${pathname}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });
    const text = await response.text();
    if (options.delayMs) await sleep(options.delayMs);
    if (response.ok) return JSON.parse(text);

    if (isRateLimit(response.status, text) && attempt < options.retries) {
      const waitMs = options.retryBaseMs * (attempt + 1) * (attempt + 1);
      console.error(`rate limited ${pathname}; retry ${attempt + 1}/${options.retries} after ${waitMs}ms`);
      await sleep(waitMs);
      continue;
    }

    throw new Error(`HTTP ${response.status}: ${text.slice(0, 1000)}`);
  }
  throw new Error(`Printify GET ${pathname} failed after retries.`);
}

function inferFamilies(blueprint, providerSummaries) {
  const title = String(blueprint.title || "").toLowerCase();
  const methods = new Set(providerSummaries.flatMap((provider) => provider.decoration_methods || []));
  const families = new Set();

  if (methods.has("embroidery") || /\b(embroider|patch|cap|hat|beanie|snapback|trucker)\b/i.test(title)) {
    families.add("embroidery_or_hats");
  }
  if (methods.has("engraving") || /\b(engraving|engraved|pendant|bracelet|necklace|pen|keychain|leather)\b/i.test(title)) {
    families.add("engraving_or_jewelry");
  }
  if (/\b(aop|cut & sew|cut and sew|leggings|dress|skirt|swimsuit|bikini|sneaker|shoe|sock|boxer|brief|apron)\b/i.test(title)) {
    families.add("aop_or_panel_mapped");
  }
  if (/\b(tee|t-shirt|shirt|hoodie|sweatshirt|tank|long sleeve|polo|jersey|crop|bodysuit|youth|kids|infant|toddler)\b/i.test(title)) {
    families.add("dtg_apparel");
  }
  if (/\b(mug|tumbler|bottle|glass|cup|can holder|can cooler|sipper|jar)\b/i.test(title)) {
    families.add("drinkware");
  }
  if (/\b(poster|posters|canvas|canvases|print|prints|postcard|postcards|card|cards|calendar|calendars|bookmark|bookmarks|journal|journals|notebook|notebooks|decal|decals|business card|business cards)\b/i.test(title)) {
    families.add("wall_art_paper_stationery");
  }
  if (/\b(sticker|magnet|button|pin)\b/i.test(title)) {
    families.add("stickers_magnets_buttons");
  }
  if (/\b(phone|case|airpod|laptop|mouse pad|desk mat|watch band|airtag|speaker|earbuds)\b/i.test(title)) {
    families.add("tech_accessory");
  }
  if (/\b(bag|backpack|tote|pouch|duffel|luggage|suitcase|wallet|sling|fanny pack)\b/i.test(title)) {
    families.add("bags_travel");
  }
  if (/\b(blanket|pillow|pillowcase|sham|towel|bedding|comforter|duvet|curtain|rug|mat|tapestry|throw|tablecloth|placemat|scarf)\b/i.test(title)) {
    families.add("home_textiles");
  }
  if (/\b(candle|coaster|ornament|cutting board|clock|banner|tree skirt|stocking|puzzle|tray|mirror|lunch box|bento)\b/i.test(title)) {
    families.add("home_decor_kitchen_seasonal");
  }
  if (/\b(pet|dog|cat|baby|bib|bowl|bandana)\b/i.test(title)) {
    families.add("pets_baby");
  }

  return [...families].sort();
}

function contractFor(families, placementSummaries, providerSummaries) {
  const methods = new Set(providerSummaries.flatMap((provider) => provider.decoration_methods || []));
  const positions = new Set(placementSummaries.map((placement) => placement.position));
  const notes = [];
  const contracts = [];

  if (families.includes("dtg_apparel") || methods.has("dtg")) {
    contracts.push({
      route: "dtg_apparel",
      art_contract: "transparent garment-placement PNG",
      best_for: "shirts, hoodies, sweatshirts, tanks, long sleeves, kids apparel, and garment placements",
    });
    notes.push("Use garment color as the background; check contrast and chest/back placement on mockups.");
  }
  if (families.includes("embroidery_or_hats") || methods.has("embroidery")) {
    contracts.push({
      route: "embroidery",
      art_contract: "simple vector-like embroidery art",
      best_for: "hats, left chest, center chest, wrist/sleeve embroidery, patches, and small bag marks",
    });
    notes.push("Use bold solid shapes, few colors, no gradients, no tiny text.");
  }
  if (families.includes("engraving_or_jewelry") || methods.has("engraving")) {
    contracts.push({
      route: "engraving",
      art_contract: "one-color engraving line art",
      best_for: "jewelry, pens, keychains, leather patches, and small engraved gifts",
    });
    notes.push("Use monograms, short words, or simple icons; inspect at actual product scale.");
  }
  if (families.includes("aop_or_panel_mapped")) {
    contracts.push({
      route: "aop_panel",
      art_contract: "opaque full-bleed panel/template art",
      best_for: "cut-and-sew apparel, leggings, dresses, shoes, socks, sportswear, and swimwear",
    });
    notes.push("Keep important faces, words, and logos away from seams, cuffs, waistbands, and folds.");
  }
  if (families.includes("drinkware")) {
    contracts.push({
      route: "drinkware",
      art_contract: "opaque wrap/front drinkware art",
      best_for: "mugs, tumblers, bottles, glassware, and can holders",
    });
    notes.push("Avoid the handle/dead zone and keep critical text away from wrap seams.");
  }
  if (families.includes("wall_art_paper_stationery")) {
    contracts.push({
      route: "paper_wall_art",
      art_contract: "opaque full-bleed trim-safe art",
      best_for: "posters, canvas, cards, calendars, journals, notebooks, bookmarks, and paper goods",
    });
    notes.push("Use bleed and safe margins; keep critical text and faces away from trim or canvas wrap edges.");
  }
  if (families.includes("stickers_magnets_buttons")) {
    contracts.push({
      route: "stickers_magnets_buttons",
      art_contract: "silhouette/cutline-aware sticker art",
      best_for: "kiss-cut stickers, die-cut stickers, magnets, buttons, and pins",
    });
    notes.push("Make the outer contour strong and keep text large enough for the smallest selected size.");
  }
  if (families.includes("tech_accessory")) {
    contracts.push({
      route: "tech_accessory",
      art_contract: "full-bleed object-shape-aware art",
      best_for: "phone cases, AirPod cases, laptop sleeves, mouse pads, desk mats, and tech accessories",
    });
    notes.push("Keep important art away from camera holes, rounded corners, folds, and grip zones.");
  }
  if (families.includes("home_textiles")) {
    contracts.push({
      route: "home_textiles",
      art_contract: "large full-bleed textile art or repeat pattern",
      best_for: "blankets, pillows, towels, bedding, rugs, mats, curtains, and tapestries",
    });
    notes.push("Use larger shapes and stronger contrast because fabric pile, folds, and stitching reduce detail.");
  }
  if (families.includes("home_decor_kitchen_seasonal") && contracts.length === 0) {
    contracts.push({
      route: "home_decor_kitchen_seasonal",
      art_contract: "shape-specific product art",
      best_for: "coasters, candles, ornaments, clocks, cutting boards, seasonal decorations, and kitchen products",
    });
    notes.push("Start from the object shape and keep labels readable at small size and across glare.");
  }
  if (families.includes("pets_baby") && contracts.length === 0) {
    contracts.push({
      route: "pets_baby",
      art_contract: "simple safe high-contrast product art",
      best_for: "pet accessories, baby accessories, bibs, bowls, and small folded products",
    });
    notes.push("Keep copy harmless, family-safe, and readable on small or folded surfaces.");
  }
  if (contracts.length === 0) {
    contracts.push({
      route: "product_specific",
      art_contract: "product-specific PNG",
      best_for: "products that require exact blueprint/provider inspection before choosing a composition route",
    });
  }

  if (positions.size > 1) {
    notes.push(`Multiple placements are available: ${[...positions].sort().join(", ")}.`);
  }
  if (placementSummaries.some((placement) => placement.dimension_count > 1)) {
    notes.push("Some placements vary by size/variant; generate or validate against the selected variant dimensions.");
  }

  const artContract =
    contracts.length === 1
      ? contracts[0].art_contract
      : `mixed routes: ${contracts.map((contract) => contract.route).join(", ")}`;

  return { art_contract: artContract, contracts, notes: uniqueSorted(notes) };
}

function summarizeVariants(variants) {
  const optionMaps = new Map();
  const placementGroups = new Map();
  const methods = new Set();
  const variantExamples = [];

  for (const variant of variants) {
    if (variantExamples.length < 8) variantExamples.push(variant.title);
    for (const [name, value] of Object.entries(variant.options || {})) {
      if (!optionMaps.has(name)) optionMaps.set(name, new Set());
      optionMaps.get(name).add(String(value));
    }
    for (const method of variant.decoration_methods || []) {
      methods.add(method);
    }
    for (const placeholder of variant.placeholders || []) {
      const key = `${placeholder.position}|${placeholder.decoration_method}|${placeholder.width}x${placeholder.height}`;
      if (!placementGroups.has(key)) {
        placementGroups.set(key, {
          position: placeholder.position,
          decoration_method: placeholder.decoration_method,
          width: placeholder.width,
          height: placeholder.height,
          variant_count: 0,
          examples: [],
        });
      }
      const group = placementGroups.get(key);
      group.variant_count += 1;
      if (group.examples.length < 5) group.examples.push(variant.title);
    }
  }

  const option_axes = sortedEntries(optionMaps).map(([name, values]) => ({
    name,
    count: values.size,
    values: uniqueSorted([...values]),
  }));
  const placement_dimensions = [...placementGroups.values()].sort(
    (a, b) =>
      String(a.position).localeCompare(String(b.position)) ||
      String(a.decoration_method).localeCompare(String(b.decoration_method)) ||
      a.width * a.height - b.width * b.height,
  );

  return {
    variant_count: variants.length,
    option_axes,
    decoration_methods: uniqueSorted([...methods]),
    placement_dimensions,
    variant_examples: variantExamples,
  };
}

function aggregateProvider(provider, variantsData) {
  const variants = variantsData.variants || variantsData || [];
  const summary = summarizeVariants(variants);
  return {
    id: provider.id,
    title: provider.title,
    decoration_methods: uniqueSorted([...(provider.decoration_methods || []), ...summary.decoration_methods]),
    ...summary,
  };
}

function aggregatePlacements(providerSummaries) {
  const groups = new Map();
  for (const provider of providerSummaries) {
    for (const dimension of provider.placement_dimensions || []) {
      const key = `${dimension.position}|${dimension.decoration_method}`;
      if (!groups.has(key)) {
        groups.set(key, {
          position: dimension.position,
          decoration_method: dimension.decoration_method,
          dimension_count: 0,
          variant_count: 0,
          widths: new Set(),
          heights: new Set(),
          dimensions: new Map(),
          providers: new Set(),
        });
      }
      const group = groups.get(key);
      group.dimension_count += 1;
      group.variant_count += dimension.variant_count;
      group.widths.add(dimension.width);
      group.heights.add(dimension.height);
      group.providers.add(provider.title);
      const sizeKey = `${dimension.width}x${dimension.height}`;
      group.dimensions.set(sizeKey, (group.dimensions.get(sizeKey) || 0) + dimension.variant_count);
    }
  }

  return [...groups.values()]
    .map((group) => {
      const widths = [...group.widths].sort((a, b) => a - b);
      const heights = [...group.heights].sort((a, b) => a - b);
      return {
        position: group.position,
        decoration_method: group.decoration_method,
        provider_count: group.providers.size,
        variant_count: group.variant_count,
        dimension_count: group.dimensions.size,
        min_width: widths[0] || null,
        max_width: widths.at(-1) || null,
        min_height: heights[0] || null,
        max_height: heights.at(-1) || null,
        recommended_canvas: {
          width: widths.at(-1) || null,
          height: heights.at(-1) || null,
          note:
            group.dimensions.size > 1
              ? "Use exact selected variant dimensions when possible; max canvas is only a broad safe starting point."
              : "Single observed dimension for this position/method.",
        },
        dimensions: [...group.dimensions.entries()]
          .map(([size, variant_count]) => {
            const [width, height] = size.split("x").map(Number);
            return { width, height, variant_count };
          })
          .sort((a, b) => a.width * a.height - b.width * b.height),
      };
    })
    .sort((a, b) => String(a.position).localeCompare(String(b.position)) || String(a.decoration_method).localeCompare(String(b.decoration_method)));
}

function aggregateOptions(providerSummaries) {
  const axes = new Map();
  for (const provider of providerSummaries) {
    for (const axis of provider.option_axes || []) {
      if (!axes.has(axis.name)) axes.set(axis.name, new Set());
      for (const value of axis.values || []) axes.get(axis.name).add(value);
    }
  }
  return sortedEntries(axes).map(([name, values]) => ({
    name,
    count: values.size,
    values: uniqueSorted([...values]),
  }));
}

function summarizeProduct(blueprint, providerSummaries, failures) {
  const placement_summary = aggregatePlacements(providerSummaries);
  const family_tags = inferFamilies(blueprint, providerSummaries);
  const composition = contractFor(family_tags, placement_summary, providerSummaries);
  const totalVariants = providerSummaries.reduce((sum, provider) => sum + (provider.variant_count || 0), 0);

  return {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    source: "Printify catalog API",
    blueprint: {
      id: blueprint.id,
      title: blueprint.title,
      brand: blueprint.brand || null,
      model: blueprint.model || null,
    },
    family_tags,
    composition,
    provider_count: providerSummaries.length,
    total_variant_count: totalVariants,
    option_summary: aggregateOptions(providerSummaries),
    placement_summary,
    providers: providerSummaries,
    failures,
  };
}

function productIndexEntry(product, file) {
  return {
    blueprint_id: product.blueprint.id,
    title: product.blueprint.title,
    brand: product.blueprint.brand,
    model: product.blueprint.model,
    file,
    family_tags: product.family_tags,
    art_contract: product.composition.art_contract,
    provider_count: product.provider_count,
    total_variant_count: product.total_variant_count,
    option_axes: product.option_summary.map((axis) => ({ name: axis.name, count: axis.count })),
    placements: product.placement_summary.map((placement) => ({
      position: placement.position,
      decoration_method: placement.decoration_method,
      dimension_count: placement.dimension_count,
      min_width: placement.min_width,
      max_width: placement.max_width,
      min_height: placement.min_height,
      max_height: placement.max_height,
    })),
    failure_count: product.failures.length,
  };
}

async function processBlueprint(blueprint, options, token, productDir) {
  const slug = `${String(blueprint.id).padStart(5, "0")}-${slugify(`${blueprint.brand || "generic"}-${blueprint.title}`)}.json`;
  const productPath = path.join(productDir, slug);
  if (!options.force && (await exists(productPath))) {
    const product = await readJson(productPath);
    if (!product.failures || product.failures.length === 0) {
      return { product, file: productPath.replaceAll("\\", "/"), skipped: true };
    }
  }

  const failures = [];
  let providers = [];
  try {
    providers = await printifyGet(`/catalog/blueprints/${blueprint.id}/print_providers.json`, token, options);
  } catch (error) {
    failures.push({ scope: "providers", message: error.message });
  }

  const providerSummaries = [];
  for (const provider of providers || []) {
    try {
      const variants = await printifyGet(
        `/catalog/blueprints/${blueprint.id}/print_providers/${provider.id}/variants.json?show-out-of-stock=1`,
        token,
        options,
      );
      providerSummaries.push(aggregateProvider(provider, variants));
    } catch (error) {
      failures.push({ scope: "variants", provider_id: provider.id, provider_title: provider.title, message: error.message });
    }
  }

  const product = summarizeProduct(blueprint, providerSummaries, failures);
  await writeJson(productPath, product);
  return { product, file: productPath.replaceAll("\\", "/"), skipped: false };
}

async function runPool(items, concurrency, worker) {
  const results = [];
  let index = 0;

  async function runWorker() {
    while (index < items.length) {
      const current = items[index];
      index += 1;
      results.push(await worker(current, index, items.length));
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, runWorker));
  return results;
}

function buildIndex(entries, options) {
  const familyCounts = new Map();
  const methodCounts = new Map();
  let totalVariants = 0;
  let productsWithFailures = 0;

  for (const entry of entries) {
    totalVariants += entry.total_variant_count || 0;
    if (entry.failure_count) productsWithFailures += 1;
    for (const family of entry.family_tags || []) {
      familyCounts.set(family, (familyCounts.get(family) || 0) + 1);
    }
    for (const placement of entry.placements || []) {
      methodCounts.set(placement.decoration_method, (methodCounts.get(placement.decoration_method) || 0) + 1);
    }
  }

  return {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    source_blueprints: options.blueprints,
    product_count: entries.length,
    total_variant_count: totalVariants,
    products_with_failures: productsWithFailures,
    family_counts: Object.fromEntries([...familyCounts.entries()].sort()),
    decoration_method_counts: Object.fromEntries([...methodCounts.entries()].sort()),
    products: entries.sort((a, b) => a.blueprint_id - b.blueprint_id),
  };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const token = process.env.PRINTIFY_API_TOKEN;
  if (!token) throw new Error("PRINTIFY_API_TOKEN is required.");

  const blueprintsRaw = await readJson(options.blueprints);
  let blueprints = Array.isArray(blueprintsRaw) ? blueprintsRaw : blueprintsRaw.data || [];
  if (options.blueprintIds.length) {
    const selected = new Set(options.blueprintIds);
    blueprints = blueprints.filter((blueprint) => selected.has(blueprint.id));
  }
  if (options.limit) blueprints = blueprints.slice(0, options.limit);

  const productDir = path.join(options.outputDir, "products");
  await mkdir(productDir, { recursive: true });

  let completed = 0;
  const results = await runPool(blueprints, options.concurrency, async (blueprint) => {
    const result = await processBlueprint(blueprint, options, token, productDir);
    completed += 1;
    const action = result.skipped ? "skipped" : "wrote";
    console.log(`${completed}/${blueprints.length} ${action} ${blueprint.id} ${blueprint.title}`);
    return result;
  });

  const entries = results.map((result) => productIndexEntry(result.product, result.file));
  const failures = entries.filter((entry) => entry.failure_count > 0);
  await writeJson(path.join(options.outputDir, "index.json"), buildIndex(entries, options));
  await writeJson(path.join(options.outputDir, "failures.json"), failures);
  console.log(JSON.stringify({ output_dir: options.outputDir, product_count: entries.length, failures: failures.length }, null, 2));
}

main().catch((error) => {
  console.error(error.message || error);
  process.exitCode = 1;
});
