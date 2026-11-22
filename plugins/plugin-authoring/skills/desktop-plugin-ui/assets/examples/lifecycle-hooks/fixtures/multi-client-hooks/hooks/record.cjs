const { appendFileSync } = require("node:fs");

function record(marker) {
  const path = process.env.HOOK_PROBE_LOG;
  if (path) {
    appendFileSync(path, marker + "\n");
  }
}

if (require.main === module) {
  record(process.argv[2]);
}

module.exports = { record };
