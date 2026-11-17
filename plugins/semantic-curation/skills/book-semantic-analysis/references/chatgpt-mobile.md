# ChatGPT delivery and mobile testing

Capability notes checked against official documentation on 2026-10-31. Recheck the linked documentation before giving later installation instructions; product surfaces and account availability can change.

## Choose the smallest delivery

For a first analysis, use the book-reading workflow and the existing ChatGPT visualization capability when available. A skill supplies instructions and resources; it does not itself enable a rendering surface. The bundled fragment provides a visible semantic graph and linked evidence, is data-local, and needs no MCP server, login, or hosted application. Keep node/edge selection, alternatives, and paragraph disclosures local so inspecting an existing interpretation does not consume a model turn.

Use the supplied standalone file or an anchored text report if the inline renderer is unavailable. Browser testing at phone width checks responsive layout, not whether a particular ChatGPT mobile account renders the content. Official documentation describes visualizations as supported on web, in desktop preview, and rolling out to eligible mobile accounts. Check whether `@Visualize` is offered and test the actual device before claiming mobile visual acceptance. See [Visualizations](https://learn.chatgpt.com/docs/visualizations).

## Package a reusable skill

Standalone filesystem skills are not the portable phone-install path. Official documentation describes plugin-bundled skills across Chat and Work on web, desktop, and mobile; availability and workspace policy still apply. See [Skills](https://learn.chatgpt.com/docs/enterprise/skills), [Build skills](https://learn.chatgpt.com/docs/build-skills), and [Plugins](https://learn.chatgpt.com/docs/plugins).

Use a skills-only portable plugin with this structure:

```text
plugin.json
skills/book-semantic-analysis/SKILL.md
skills/book-semantic-analysis/agents/openai.yaml
skills/book-semantic-analysis/references/...
skills/book-semantic-analysis/scripts/...
skills/book-semantic-analysis/assets/templates/...
```

Use the root `plugin.json` portable format and its official schema; the conventional `skills/` directory is discovered automatically. Do not copy a desktop compatibility manifest with different fields into this format. No local stdio server, localhost URL, desktop daemon, or API key is needed for the reading instructions and supplied-data explorer. See [Plugin structure](https://developers.openai.com/plugins/build/plugins).

Prepare a concrete ZIP, verify its inventory and schema, and explain the account-specific next step. If private ZIP upload is exposed by the user's ChatGPT workspace, use that supported flow. Otherwise, when `@Plugin Creator` and workspace creation permissions are available, use the documented web creation route: provide the skill folder and resources, create a private skills-only plugin, review its preview, and install it for the appropriate workspace. Bundled Python helpers still require an execution tool in that Chat or Work environment; phone access alone does not establish it. Use the anchored manual fallback when execution is unavailable. See [Build plugins](https://learn.chatgpt.com/docs/build-plugins) and [Apps and connectors](https://learn.chatgpt.com/docs/enterprise/apps-and-connectors).

Do not confuse the public submission wizard at `platform.openai.com/plugins` with private installation. Do not submit or publish the user's plugin without authorization. Do not invent a phone-side ZIP upload button or promise that a private plugin appears in a different account/workspace.

## Device acceptance

After installation, open a new chat in the same account and workspace, invoke the installed plugin, and supply the book file or an excerpt. Ask for a scoped analysis with exact evidence and an interactive explorer if supported. Verify:

- The requested source is actually read and scope is explicit.
- Selecting a graph node changes the selected claim, theme and evidence consistently; the graph is visible, not replaced by selectors alone.
- Selecting a typed connection exposes its direction, rationale and exact evidence, while theme grouping remains visibly distinct.
- Supporting and complicating quotations open readable paragraph context.
- Alternatives and limitations remain accessible without hover.
- Narrow layout, text selection, disclosures, and controls work with touch.
- The fallback report is useful when inline rendering or helper execution is unavailable.

Report installation, invocation, semantic quality, and actual device rendering as separate outcomes. A correct ZIP and a responsive browser screenshot do not establish phone installation or rendering.
