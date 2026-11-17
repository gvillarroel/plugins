import {
  App,
  applyDocumentTheme,
  applyHostStyleVariables,
} from "@modelcontextprotocol/ext-apps";

// The official SDK owns postMessage validation, request correlation and teardown.
// No tokens, localhost calls, CDN scripts or model-facing approval tool are used.
const app = new App(
  { name: "Knowledge Catalog Lineage", version: "0.3.0" },
  {},
);
const ready = [];
window.kcHost = {
  result: null,
  onResult(callback) {
    ready.push(callback);
    if (this.result) callback(this.result);
  },
  async call(action, args) {
    const names = {
      list: "lineage_list",
      get: "review_lineage",
      demo: "create_lineage_demo",
      revise: "revise_lineage",
      history: "lineage_history",
      revision: "lineage_revision",
      diff: "lineage_diff",
      export: "export_lineage",
      attach: "attach_lineage",
    };
    if (!names[action])
      throw new Error("This decision requires the local human review panel.");
    const result = await app.callServerTool({
      name: names[action],
      arguments: args,
    });
    if (result.isError)
      throw new Error(
        result.content?.find((c) => c.type === "text")?.text ||
          "The operation could not be completed.",
      );
    return (
      result.structuredContent ||
      JSON.parse(result.content.find((c) => c.type === "text").text)
    );
  },
  async openReview() {
    const result = await app.callServerTool({
      name: "open_lineage_panel",
      arguments: {},
    });
    if (result.isError)
      throw new Error(
        result.content?.find((c) => c.type === "text")?.text ||
          "The review panel could not be opened.",
      );
    return result;
  },
};
app.ontoolresult = (result) => {
  if (result.isError) return;
  const value =
    result.structuredContent ||
    JSON.parse(result.content.find((c) => c.type === "text").text);
  window.kcHost.result = value;
  ready.forEach((callback) => callback(value));
};
function theme(context) {
  if (context?.theme) applyDocumentTheme(context.theme);
  if (context?.styles?.variables)
    applyHostStyleVariables(context.styles.variables);
}
app.onhostcontextchanged = theme;
app
  .connect()
  .then(() => theme(app.getHostContext()))
  .catch((error) => {
    window.dispatchEvent(
      new CustomEvent("kc-host-error", { detail: error.message }),
    );
  });
