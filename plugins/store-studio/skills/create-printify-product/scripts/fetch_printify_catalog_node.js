import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const API_BASE = "https://api.printify.com/v1";

function printHelp() {
  console.log(`Fetch Printify catalog data using Node fetch.

Usage:
  node scripts/fetch_printify_catalog_node.js blueprints [--output <path>]
  node scripts/fetch_printify_catalog_node.js providers --blueprint-id <id> [--output <path>]
  node scripts/fetch_printify_catalog_node.js variants --blueprint-id <id> --print-provider-id <id> [--show-out-of-stock] [--output <path>]

Environment:
  PRINTIFY_API_TOKEN must be set.`);
}

function parseArgs(argv) {
  const [command, ...rest] = argv;
  const options = {
    command,
    output: null,
    blueprintId: null,
    printProviderId: null,
    showOutOfStock: false,
  };

  if (!command || command === "--help" || command === "-h") {
    printHelp();
    process.exit(0);
  }

  for (let index = 0; index < rest.length; index += 1) {
    const arg = rest[index];
    const next = () => {
      index += 1;
      if (index >= rest.length) throw new Error(`Missing value for ${arg}`);
      return rest[index];
    };

    if (arg === "--output") options.output = next();
    else if (arg === "--blueprint-id") options.blueprintId = Number(next());
    else if (arg === "--print-provider-id") options.printProviderId = Number(next());
    else if (arg === "--show-out-of-stock") options.showOutOfStock = true;
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!["blueprints", "providers", "variants"].includes(command)) {
    throw new Error("Command must be blueprints, providers, or variants.");
  }
  if ((command === "providers" || command === "variants") && !Number.isInteger(options.blueprintId)) {
    throw new Error("--blueprint-id is required.");
  }
  if (command === "variants" && !Number.isInteger(options.printProviderId)) {
    throw new Error("--print-provider-id is required.");
  }

  return options;
}

function endpoint(options) {
  if (options.command === "blueprints") return "/catalog/blueprints.json";
  if (options.command === "providers") {
    return `/catalog/blueprints/${options.blueprintId}/print_providers.json`;
  }

  const query = options.showOutOfStock ? "?show-out-of-stock=1" : "";
  return `/catalog/blueprints/${options.blueprintId}/print_providers/${options.printProviderId}/variants.json${query}`;
}

async function printifyGet(pathname, token) {
  const response = await fetch(`${API_BASE}${pathname}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Printify GET ${pathname} failed: HTTP ${response.status}\n${text.slice(0, 1200)}`);
  }
  return JSON.parse(text);
}

async function writeOrPrint(data, output) {
  const text = `${JSON.stringify(data, null, 2)}\n`;
  if (!output) {
    process.stdout.write(text);
    return;
  }

  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, text);
  console.log(JSON.stringify({ output }, null, 2));
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const token = process.env.PRINTIFY_API_TOKEN;
  if (!token) throw new Error("PRINTIFY_API_TOKEN is required.");

  const data = await printifyGet(endpoint(options), token);
  await writeOrPrint(data, options.output);
}

main().catch((error) => {
  console.error(error.message || error);
  process.exitCode = 1;
});
