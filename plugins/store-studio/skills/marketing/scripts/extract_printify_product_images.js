#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
const { URL } = require("node:url");

let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (error) {
  console.error("playwright_not_installed");
  console.error("Install with: npm i -D playwright");
  process.exit(2);
}

function parseArgs(argv) {
  const args = { headless: true, maxImages: 8 };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`Missing value for ${arg}`);
      return argv[index];
    };
    if (arg === "--product-url") args.productUrl = next();
    else if (arg === "--spike-dir") args.spikeDir = next();
    else if (arg === "--output-dir") args.outputDir = next();
    else if (arg === "--manifest") args.manifest = next();
    else if (arg === "--max-images") args.maxImages = Number(next());
    else if (arg === "--headless") args.headless = next() !== "false";
    else if (arg === "--help") {
      printUsage();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!args.productUrl) throw new Error("--product-url is required.");
  if (!args.spikeDir && !args.outputDir) {
    throw new Error("Either --spike-dir or --output-dir is required.");
  }
  if (!args.manifest) {
    if (!args.spikeDir) throw new Error("--manifest requires --spike-dir.");
    args.manifest = path.join(
      args.spikeDir,
      "references",
      "printify-product-media.json",
    );
  }
  if (!args.outputDir) {
    args.outputDir = path.join(args.spikeDir, "assets", "source", "printify");
  }
  if (!Number.isInteger(args.maxImages) || args.maxImages < 1) {
    throw new Error("--max-images must be an integer >= 1.");
  }

  return args;
}

function printUsage() {
  console.log(`Usage:
node scripts/extract_printify_product_images.js --product-url <url> [options]

Required:
  --product-url   Printify product-details URL

Optional:
  --spike-dir     Spike root directory (adds defaults for output + manifest)
  --output-dir    Directory for downloaded images
  --manifest      Output manifest path
  --max-images    Max images to keep (default: 8)
  --headless      true|false (default: true)
`);
}

function parseProductId(url) {
  const parsed = new URL(url);
  const match = parsed.pathname.match(/\/product-details\/([0-9a-f]+)(?:\/|$)/i);
  return match ? match[1] : null;
}

function sanitizeSourceUrl(raw) {
  try {
    const u = new URL(raw);
    u.search = "";
    u.hash = "";
    return u.toString();
  } catch (error) {
    return raw;
  }
}

function filenameFromUrl(index, sourceUrl, width, height, contentType) {
  const extFromType = String(contentType || "")
    .toLowerCase()
    .includes("png")
    ? ".png"
    : String(contentType || "").toLowerCase().includes("webp")
      ? ".webp"
      : ".jpg";
  const safeName = sanitizeSourceUrl(sourceUrl)
    .replace(/^https?:\/\//, "")
    .replace(/[^a-z0-9.-]/gi, "-")
    .replace(/-+/g, "-")
    .slice(0, 70);
  const sizeSuffix = width && height ? `-${width}x${height}` : "";
  return `printify-${String(index + 1).padStart(2, "0")}${sizeSuffix}-${safeName}${extFromType}`;
}

function selectImageUrl(candidates) {
  return candidates.find((src) => {
    if (!src || !/^https?:\/\//i.test(src)) return false;
    return /images\.printify\.com|cdn-cgi\/image|printify\.com\/cdn/i.test(src);
  }) || candidates.find((src) => /^https?:\/\//i.test(src));
}

function parseSrcSet(srcset) {
  return String(srcset || "")
    .split(",")
    .map((part) => part.trim().split(/\s+/)[0])
    .filter(Boolean)
    .filter((value) => /^https?:\/\//i.test(value));
}

async function collectProductMetadata(page) {
  return page.evaluate(() => {
    const parseSrcSet = (value) =>
      String(value || "")
        .split(",")
        .map((part) => part.trim().split(/\s+/)[0])
        .filter(Boolean)
        .filter((entry) => /^https?:\/\//i.test(entry));

    const title =
      document.querySelector("h1")?.innerText.trim() ||
      document.title ||
      "Printify product";
    const paragraphs = Array.from(document.querySelectorAll("p"))
      .map((node) => node.innerText)
      .filter(Boolean);
    const description = paragraphs.find((text) => text.length > 40) || null;

    const images = Array.from(document.querySelectorAll("img")).map((img) => {
      const candidates = [];
      if (img.src) candidates.push(img.src);
      if (img.currentSrc) candidates.push(img.currentSrc);
      candidates.push(...parseSrcSet(img.getAttribute("srcset") || ""));
      const unique = [...new Set(candidates)];
      return {
        srcs: unique,
        alt: img.getAttribute("alt") || "",
        width: img.naturalWidth || img.width || 0,
        height: img.naturalHeight || img.height || 0,
      };
    });

    return {
      title,
      description,
      images,
      bodyText: document.body?.innerText?.slice(0, 2000) || "",
    };
  });
}

async function extractImageCandidates(page) {
  await page.waitForTimeout(2000);
  for (let i = 1; i <= 8; i += 1) {
    await page.evaluate((step) => {
      window.scrollTo(0, window.innerHeight * step * 0.85);
    }, i);
    await page.waitForTimeout(250);
  }
  return collectProductMetadata(page);
}

async function downloadImage(sourceUrl, dest, timeoutMs = 120000) {
  const response = await fetch(sourceUrl, { method: "GET", redirect: "follow" });
  if (!response.ok) {
    throw new Error(`Download failed: ${response.status}`);
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  await fs.promises.writeFile(dest, bytes);
  return {
    bytes: bytes.length,
    contentType: response.headers.get("content-type") || "",
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const productId = parseProductId(args.productUrl);
  if (!productId) throw new Error("Cannot parse product id from URL.");

  const outputDir = path.resolve(args.outputDir);
  const manifestPath = path.resolve(args.manifest);
  await fs.promises.mkdir(outputDir, { recursive: true });
  await fs.promises.mkdir(path.dirname(manifestPath), { recursive: true });

  const browser = await chromium.launch({ headless: args.headless });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1100 },
  });
  const page = await context.newPage();
  try {
    await page.goto(args.productUrl, { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForTimeout(3000);

    const metadata = await extractImageCandidates(page);
    const filtered = metadata.images
      .map((image) => {
        const selected = selectImageUrl(image.srcs);
        return selected
          ? {
              source_url: sanitizeSourceUrl(selected),
              alt: image.alt,
              width: image.width,
              height: image.height,
            }
          : null;
      })
      .filter(Boolean);

    const priority = filtered.filter((item) =>
      /images\.printify\.com|cdn-cgi\/image|printify\.com\/cdn/i.test(item.source_url)
    );
    const others = filtered.filter((item) =>
      !/images\.printify\.com|cdn-cgi\/image|printify\.com\/cdn/i.test(item.source_url)
    );
    const ordered = [...priority, ...others]
      .filter((item, index, list) => list.findIndex((entry) => entry.source_url === item.source_url) === index)
      .filter((item) => item.source_url.includes("http"))
      .filter((item) => (item.width || 0) >= 200 && (item.height || 0) >= 200)
      .slice(0, args.maxImages);

    const savedImages = [];
    const warnings = [];

    for (let index = 0; index < ordered.length; index += 1) {
      const item = ordered[index];
      const fileName = filenameFromUrl(index, item.source_url, item.width, item.height, null);
      const safePath = path.join(outputDir, fileName);
      try {
        const download = await downloadImage(item.source_url, safePath);
        savedImages.push({
          index: index + 1,
          file: path.relative(process.cwd(), safePath).replace(/\\/g, "/"),
          source_url: item.source_url,
          alt: item.alt,
          width: item.width || null,
          height: item.height || null,
          bytes: download.bytes,
          content_type: download.contentType,
        });
      } catch (error) {
        warnings.push(`Skipped ${item.source_url}: ${error.message}`);
      }
    }

    const manifest = {
      generated_at: new Date().toISOString(),
      source: {
        product_url: args.productUrl,
        product_id: productId,
        mode: args.headless ? "playwright_headless" : "playwright_visible",
      },
      extraction_status: savedImages.length ? "success" : "failed",
      product_title: metadata.title,
      product_description_preview: metadata.description,
      output_dir: path.relative(process.cwd(), outputDir).replace(/\\/g, "/"),
      requested_images: args.maxImages,
      extracted_images: savedImages,
      warnings,
      body_text_excerpt: metadata.bodyText.slice(0, 600),
    };

    await fs.promises.writeFile(
      manifestPath,
      `${JSON.stringify(manifest, null, 2)}\n`,
      "utf-8",
    );
    console.log(
      JSON.stringify(
        {
          manifest: path.relative(process.cwd(), manifestPath).replace(/\\/g, "/"),
          image_count: savedImages.length,
          status: manifest.extraction_status,
        },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
