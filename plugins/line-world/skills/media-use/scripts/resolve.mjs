#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveNpxInvocation } from "./lib/npx-sync.mjs";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const dist = join(root, "packages/cli/dist/cli.js");
const source = join(root, "packages/cli/src/cli.ts");
// The standalone Line World bundle uses the release paired with this skill.
const pluginVersion = process.env.HYPERFRAMES_PLUGIN_VERSION;
if (pluginVersion || (!existsSync(dist) && !existsSync(source))) {
  const invocation = resolveNpxInvocation(
    ["--yes", `hyperframes@${pluginVersion || "0.8.199"}`, "media-use", "resolve", ...process.argv.slice(2)],
    { stdio: "inherit" },
  );
  const result = spawnSync(invocation.cmd, invocation.args, invocation.opts);
  if (result.error) console.error(result.error.message);
  process.exit(result.status ?? 1);
}
const result = existsSync(dist)
  ? spawnSync(process.execPath, [dist, "media-use", "resolve", ...process.argv.slice(2)], {
      stdio: "inherit",
    })
  : spawnSync(
      "bun",
      [source, "media-use", "resolve", ...process.argv.slice(2)],
      { stdio: "inherit" },
    );
process.exit(result.status ?? 1);
