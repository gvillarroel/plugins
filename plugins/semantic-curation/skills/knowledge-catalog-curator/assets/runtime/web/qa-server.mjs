// No production deployment: loopback, Host/Origin/capability checks, fixed QA home.
import { createServer } from "node:http";
import { randomBytes, timingSafeEqual } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const root = fileURLToPath(new URL("..", import.meta.url));
const port = 8768;
const capability = randomBytes(32).toString("base64url");
const origin = `http://127.0.0.1:${port}`;
const client = new Client({ name: "kc-lineage-qa", version: "0.3.0" });
const transport = new StdioClientTransport({
  command: resolve(root, ".venv/Scripts/python.exe"),
  args: ["-m", "knowledge_catalog.server"],
  cwd: root,
    env: { ...process.env, KC_HOME: resolve(root, ".kc/lineage-host-qa-en") },
  stderr: "pipe",
});
await client.connect(transport);
const allowed = new Set([
  "lineage_list",
  "create_lineage_demo",
  "review_lineage",
  "revise_lineage",
  "lineage_history",
  "lineage_revision",
  "lineage_diff",
  "export_lineage",
  "attach_lineage",
  "open_lineage_panel",
]);
const server = createServer(async (request, response) => {
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("Access-Control-Allow-Origin", origin);
  const send = (code, value, type = "application/json") => {
    response.writeHead(code, { "Content-Type": type });
    response.end(type === "application/json" ? JSON.stringify(value) : value);
  };
  try {
    if (request.headers.host !== `127.0.0.1:${port}`) return send(403, {});
    if (request.url === "/favicon.ico") return send(204, "", "image/x-icon");
    if (request.url === "/" && request.method === "GET")
      return send(
        200,
          '<!doctype html><html lang="en"><meta charset="utf-8"><title>MCP Apps protocol QA</title>' +
          "<style>body{font:16px system-ui;margin:16px}iframe{width:100%;height:1800px;border:1px solid #64748b}button{min-height:44px}body:has(html[data-theme=dark]){background:#111827}</style>" +
          '<h1>Local MCP Apps test host</h1><p id="qa-status" role="status">Connecting SDK…</p>' +
          '<button id="theme">Switch host theme</button><iframe id="app" title="Data lineage explorer" sandbox="allow-scripts allow-downloads"></iframe>' +
          '<script type="module" src="/host.js"></script></html>',
        "text/html; charset=utf-8",
      );
    if (request.url === "/host.js" && request.method === "GET")
      return send(
        200,
        await readFile(resolve(root, "output/lineage-qa-host.js"), "utf8"),
        "text/javascript",
      );
    const auth = Buffer.from(request.headers.authorization || "");
    const expected = Buffer.from("Bearer " + capability);
    if (auth.length !== expected.length || !timingSafeEqual(auth, expected))
      return send(401, {});
    if (request.url === "/resource" && request.method === "GET")
      return send(
        200,
        await client.readResource({ uri: "ui://kc/lineage.html" }),
      );
    if (request.url === "/rpc" && request.method === "POST") {
      if (request.headers.origin !== origin) return send(403, {});
      let data = "";
      for await (const chunk of request) {
        data += chunk;
        if (data.length > 1_000_000) throw Error("Too large");
      }
      const body = JSON.parse(data);
      if (!allowed.has(body.name))
        return send(403, { error: "QA tool not allowed" });
      return send(200, await client.callTool(body));
    }
    send(404, {});
  } catch (error) {
    send(400, { error: error.message });
  }
});
server.listen(port, "127.0.0.1", () => console.log(`${origin}/#${capability}`));
process.on("SIGINT", async () => {
  server.close();
  await client.close();
});
