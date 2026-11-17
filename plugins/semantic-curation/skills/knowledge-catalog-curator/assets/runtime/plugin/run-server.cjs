// No protocol rewriting: Python owns the MCP transport. Never log on stdout.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
try {
  const configPath =
    process.env.KC_RUNTIME_CONFIG ||
    path.join(os.homedir(), ".knowledge-catalog-curator", "runtime.json");
  const runtime = JSON.parse(fs.readFileSync(configPath, "utf8"));
  if (!path.isAbsolute(runtime.python) || !path.isAbsolute(runtime.home))
    throw new Error("Runtime paths must be absolute");
  const child = spawn(runtime.python, ["-I", "-m", "knowledge_catalog.server"], {
    stdio: "inherit",
    windowsHide: true,
    cwd: path.dirname(runtime.home),
    env: { ...process.env, KC_HOME: runtime.home, PYTHONUNBUFFERED: "1" },
  });
  child.on("error", (error) => {
    process.stderr.write(error.message + "\n");
    process.exit(1);
  });
  child.on("exit", (code) => process.exit(code ?? 1));
  for (const signal of ["SIGINT", "SIGTERM"])
    process.on(signal, () => child.kill(signal));
} catch (error) {
  process.stderr.write(
    "Install the skill runtime and run register-claude first: " + error.message + "\n",
  );
  process.exit(1);
}
