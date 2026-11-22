const { appendFileSync, readFileSync } = require("node:fs");

const log = process.env.HOOK_PROBE_LOG;
if (log) {
  const event = JSON.parse(readFileSync(0, "utf8"));
  if (event.hook_event_name !== "SessionStart") {
    throw new Error("Expected a SessionStart payload");
  }
  appendFileSync(log, process.argv[2] + "\n");
}
