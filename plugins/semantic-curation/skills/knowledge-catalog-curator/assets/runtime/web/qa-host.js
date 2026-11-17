// Development-only host: the official AppBridge communicates with the bundled
// view in an opaque-origin sandbox. Tool calls reach the real Python stdio MCP.
import {
  AppBridge,
  PostMessageTransport,
} from "@modelcontextprotocol/ext-apps/app-bridge";

const token =
  location.hash.slice(1) || sessionStorage.getItem("kc-qa-host-token") || "";
if (token) sessionStorage.setItem("kc-qa-host-token", token);
history.replaceState(null, "", location.pathname);
const status = document.getElementById("qa-status");
const frame = document.getElementById("app");
async function request(path, body) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) throw new Error("QA transport failed: " + response.status);
  return response.json();
}
const resource = await request("/resource");
const bridge = new AppBridge(
  null,
  { name: "KC local protocol QA", version: "0.3.0" },
  { serverTools: {} },
  {
    hostContext: {
      theme: "light",
      displayMode: "inline",
      availableDisplayModes: ["inline"],
    },
  },
);
bridge.oncalltool = (params) => request("/rpc", params);
bridge.oninitialized = async () => {
  status.textContent = "SDK handshake complete · real stdio MCP";
  await bridge.sendToolInput({ arguments: { seed: 49 } });
  const result = await request("/rpc", {
    name: "create_lineage_demo",
    arguments: { seed: 49 },
  });
  await bridge.sendToolResult(result);
};
bridge.onerror = (error) => {
  status.textContent = "Host error: " + error.message;
};
await bridge.connect(
  new PostMessageTransport(frame.contentWindow, frame.contentWindow),
);
frame.srcdoc = resource.contents[0].text;
document.getElementById("theme").addEventListener("click", () => {
  const theme =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  bridge.setHostContext({ theme });
});
