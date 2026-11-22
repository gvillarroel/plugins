# Verified plugin capabilities by harness

These checks ran on Windows with the builds named below. The inventory
checks used disposable profiles and synthetic packages. Skill discovery
was checked without a model turn. Hook runs either used a lifecycle
command or a loopback response server.

## Choose the package format

For a package shared by Copilot CLI and Codex, use the Agent Plugins 1.0
schema and put each skill at `skills/<name>/SKILL.md`. Keep the directories
immediate. Copilot 1.0.114 also found a deeper skill under `skills/`;
Codex portable skipped it. Adding a top-level `skills` field did not
add another root in either portable loader.

| Loader tested | Result when an explicit extra root is declared |
| --- | --- |
| Copilot CLI 1.0.114, Agent Plugins 1.0 and 1.1 | Scans inside `skills/`. Warns and ignores the extra `skills` field. |
| Copilot CLI 1.0.114, legacy | Loads the declared roots. Include `./skills/` to keep it alongside the extras. |
| Claude Code 2.1.302, native | Adds explicit roots to the default `skills/`. |
| Codex CLI 0.171.0, Agent Plugins 1.0 | Uses immediate directories inside `skills/`. Extra roots in the top-level field, OpenAI extension and native overlay all failed to add a skill. |
| Codex CLI 0.171.0, legacy | Loads the declared roots recursively. Include `./skills/` to keep it alongside the extras. |
| OpenCode 1.18.4 and 2.3.2 | Configure skill roots independently from the executable plugin entries. |
| Pi 1.4.0 | An explicit `package.json#pi.skills` array replaces the conventional roots for that package. |

The portable layout and MCP file name are defined in the specification.
[Agent Plugins 1.0](https://agent-plugins.org/specification)

Keep marketplace registration, the marketplace entry's `source`, and
the component paths in the package manifest separate. Verify registration,
installation, and the installed inventory. The Copilot and Codex tests
below include successful installs with an empty runtime inventory.

## GitHub Copilot CLI

These cases used CLI 1.0.114. Run `copilot --no-auto-update --version`
when the test uses the same flag. The Windows launcher otherwise
selected a different build than the bundled 1.0.73 in this environment.

### Skills

- To add a directory in legacy mode, set `skills` in the package's own
  manifest. A string selected one root and an array selected multiple
  roots. Nested skill directories worked. A directory containing a
  direct `SKILL.md` also worked. A path to the file, an empty array,
  and absolute or relative paths outside the package yielded no skills.
- A root `SKILL.md` worked as the legacy fallback when `skills/` was
  absent. In portable mode it was skipped. Placing `SKILL.md` directly
  inside `skills/` caused this build to load that file as one skill
  and omit the other skills in that directory. Use one directory per
  skill for a shared package.
- `plugins[].skills` did not add a root in either a directory-registered
  or a Git-registered marketplace. This also held with a manifestless
  source and `strict: false`.
- For independent skills, `copilot skill add <directory>` registered a
  custom source. `copilot skill add <SKILL.md>` copied a personal skill
  into the temporary profile. `COPILOT_SKILLS_DIRS` also added a
  directory as a custom source. A plain HTTP file URL was refused.
- Check `copilot skill list --json` after installation. The fixture
  checked both the names and the `source: "plugin"` entries. A personal
  skill of the same name hid the plugin entry, and a project skill of
  the same name then hid the personal one. A root Agent Plugins 2.0
  manifest registered as installed but contributed no skills. The
  bundled 1.0.73 treated the tested 1.0 and 1.1 manifests as legacy,
  so it honored their explicit `skills` fields.

[Manifest component paths](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference#component-path-fields) ·
[Independent skill commands](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#skills-reference)

### Other components

- The portable plugin registered its namespaced command from
  `com.github.copilot/commands/`. The legacy plugin registered a command
  from an explicit `commands` path and kept both declared skill roots.
  The CLI exposed the plugin-qualified agent name in each format.
  Selecting the qualified portable agent with `--agent` sent that
  agent's marker to the loopback model.
- The portable MCP inventory listed the server from a versioned
  root `mcp.json` and a real session completed its stdio handshake and
  tool listing. The legacy inline MCP entry also exposed its tool.
  The LSP inventory listed the server from
  `com.github.copilot/lsp.json` with the
  `{"lspServers":{"<name>":{...}}}` envelope. The legacy LSP inventory
  read the inline server from its manifest. These LSP checks measured
  discovery.

[Agent Plugins component locations](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference#components)

### Marketplace sources

- Use a path string relative to the marketplace root in
  `.github/plugin/marketplace.json`. Both `./p/sample` and `p/sample`
  worked. A bare name resolved under `metadata.pluginRoot`. An
  absolute path inside a directory-registered catalog also worked in
  this build. Absolute and relative paths outside the catalog root
  failed. Typed `local` and `file` objects were rejected at registration.
- For a plugin in a separate Git repository, use an entry with
  `{"source":"url","url":"<Git URL>","path":"p/sample","sha":"<full SHA>"}`
  as its `source` and test with the marketplace itself registered
  from Git. On a loopback smart-HTTP Git server, the installed skill
  came from the pinned commit even though the repository had a newer
  HEAD. A plain Git URL string in the entry was interpreted as a path.
- Recheck the inventory in a new process. The same typed Git entry
  reported a successful install when the marketplace was registered
  as a directory. The following invocation dropped its cached copy
  and the plugin was absent from the inventory. A directory-registered
  catalog with an in-root path entry loaded that package live.
- A `SKILL.md` file as an entry's `source` failed. Its containing
  directory with a root `SKILL.md` worked as a legacy source.

[Marketplace entry source types](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference#plugin-source-types)

## Claude Code

These cases used Claude Code 2.1.302 with `.claude-plugin/plugin.json`.
Use paths relative to the plugin root and inspect
`claude plugin details <name>` after installation.
`claude plugin validate <plugin> --strict --json` also identified
invalid paths before installation.

- `skills: ["./extra-a", "./extra-b"]` added both roots alongside
  default `skills/`. A directly listed folder containing `SKILL.md`
  and an explicit `"."` root also worked. A nested grouping directory
  inside the default root was skipped. A manifestless root with just
  `SKILL.md` registered one skill. Absolute and escaping paths did not
  add a skill.
- For an in-catalog package, put a contained `./plugins/name` in the
  entry's `source`. It resolves from the marketplace root above
  `.claude-plugin/`. A bare name worked with `metadata.pluginRoot`.
  Absolute and escaping entry paths failed at install after the
  marketplace had registered.
- An external Git source installed from a fixture repository with a
  full pinned SHA. An object of type `url` selected its root and
  `git-subdir` selected its `packages/reviewer` subdirectory. Each
  registered exactly the expected skill. An `npm` source also
  installed the expected skill from an integrity-checked tarball on
  the temporary profile's synthetic default registry.
- An ordinary entry with default `strict` added its `skills` to the
  manifest's roots. The same fields with `strict: false` and a native
  manifest installed but left the plugin absent from runtime details.
  When the entry used the marketplace root and listed particular
  skill folders, only those categories loaded.
- A reviewed `command` entry in copy mode delivered a package outside
  the marketplace directory. `plugin install --json` returned
  `shownCommand.sha256` before executing the producer. Retrying with
  `--accept-command <sha256>` ran the producer and installed its skill.
- An explicit `commands` path selected the alternate command and
  skipped default `commands/`. Default `agents/` appeared in
  `plugin details`. An explicit `agents` value pointing to an
  individual Markdown file loaded the alternate agent and skipped
  the default. Verify this case with `--init-only --debug-file <path>`,
  since `plugin details` counted zero agents even though the startup
  log confirmed the load. An agent directory failed strict validation.
- The MCP and LSP inventories showed both a default file entry and
  an inline entry from the manifest. These checks verified discovery.
  Both default and native-manifest `SessionStart` hooks executed.
  A catalog-level hook for the same event replaced both in the test.

[Claude manifest path rules](https://code.claude.com/docs/en/plugins-reference#path-rules) ·
[Marketplace entry and manifest composition](https://code.claude.com/docs/en/plugins-reference#marketplace-entries-and-the-manifest) ·
[Command-source contract](https://code.claude.com/docs/en/plugins/marketplace-reference#command-plugin-source)

## Codex

The layout matrix used Codex CLI 0.171.0 and verified both `plugin/read`
and the installed `skills/list` inventory. Codex CLI 0.167.0 also
reproduced the portable immediate-child and default legacy cases.

- In legacy format, set the contained directories in
  `.codex-plugin/plugin.json`. A single extra replaced the default.
  A list with both extras and `./skills/` discovered those roots
  and nested skills. If no valid paths remained, the loader fell back
  to recursive `skills/`. Root `SKILL.md` alone registered nothing.
- A root `plugin.json` without the portable schema and alongside the
  native overlay used the overlay's skill paths. A portable 1.1 root
  prevented installation in 0.171.0 even with a valid legacy overlay.
  Use 1.0 with this build for portable skills.
- Portable identity and version came from the root manifest.
  When `extensions.com.openai` was absent, `plugin/read` exposed
  the native overlay's display name and short description. An inline
  extension object replaced the overlay as a unit. An empty object
  also suppressed its settings in the tested build.
- In `.agents/plugins/marketplace.json`, local entries installed with a
  contained `"./plugins/name"` or
  `{"source":"local","path":"./plugins/name"}`. Bare names, absolute
  paths and escaping paths did not install. Entry `skills` supplied
  paths for a manifestless source and did not override a real native
  manifest in the tests.
- To install from Git, use typed `url` for a repository root or
  `git-subdir` for a path inside it. Both returned the marker skill
  from a pinned `sha` against a loopback smart-HTTP Git server.
  A typed `npm` source with an exact package version and an HTTPS
  registry also installed and registered the marker skill from an
  isolated test registry.
- Legacy Markdown commands with a description became generated skills
  during installation. A custom `commands` directory replaced the
  default one. The portable test did not migrate either. Use installed
  `skills/list` to check the generated skills, which were absent from
  source `plugin/read`.
- With both MCP files in one package, `plugin/read` discovered only
  the server from `.mcp.json` in legacy and `mcp.json` in portable.
  Both servers later returned the exact marker from a real
  `mcpServer/tool/call` in an ephemeral thread. The portable
  configuration used `type: "stdio"`, a bare `python` command and
  a `${PLUGIN_ROOT}/mcp_fixture.py` argument. The legacy one used
  `python`, package-relative arguments and `cwd: "./"`. An
  absolute executable path in the portable fixture was rejected.
  Use `mcpServerStatus/list` to locate the server before calling it.

[Codex 0.171.0 skill loader](https://github.com/openai/codex/blob/rust-v0.171.0/codex-rs/core-plugins/src/loader.rs#L975-L1037) ·
[Codex 0.171.0 marketplace resolver](https://github.com/openai/codex/blob/rust-v0.171.0/codex-rs/core-plugins/src/marketplace.rs#L622-L662) ·
[Codex 0.171.0 command migration](https://github.com/openai/codex/blob/rust-v0.171.0/codex-rs/core-plugins/src/command_migration/plugin.rs#L14-L48)

## OpenCode

- In V1 1.18.4, the native `plugin` list loaded a local JS module.
  In V2 2.3.2, `plugins` loaded a local package directory relative to
  the config file. A direct JS file in the V2 `plugins` list did
  not activate. The same style of file was auto-discovered under
  `.opencode/plugins/`. A root Agent Plugins manifest on its own
  did not register the example in either version.
- Use `skills.paths` and `skills.urls` in V1, and a `skills` array
  with paths and HTTP catalog base URLs in V2. Both versions found
  multiple additional roots, an absolute sibling directory, and a
  skill plus supporting file from a loopback HTTP catalog. Relative
  skill paths resolved from the project working directory even when
  the config file was under `.opencode/`.
- Both versions scanned the project `.opencode/skills`,
  `.claude/skills` and `.agents/skills` locations. Both found grouped
  `SKILL.md` files. V2 found a standalone Markdown file that V1 skipped.
- In V2, an active addon contributed a command and skill through
  `ctx.command.transform` and `ctx.skill.transform`. Its private
  `skills/` fixture did not register by convention. Wait for the addon
  in `GET /api/plugin` before checking `GET /api/skill` or
  `GET /api/command`. Startup inventory was initially empty in testing.
  V1 exposes a skill inventory through `opencode debug skill`.

[OpenCode V1 config loader](https://github.com/anomalyco/opencode/blob/v1.18.4/packages/opencode/src/config/plugin.ts) ·
[OpenCode skill sources](https://opencode.ai/docs/skills/#sources) ·
[OpenCode V2 server extension API](https://opencode.ai/docs/build/plugins/server/#skills)

## Pi

These cases used Pi 1.4.0.

- `pi install <local directory>` loaded conventional `skills/`,
  including nested `SKILL.md`. The root Agent Plugins manifest did
  not redirect it. `package.json#pi.skills` supported multiple extra
  directory paths and replaced the default. Include `./skills` to
  expose it alongside the extras.
- A sibling `../` skill path worked in the live local install. Keep
  files within the package when distributing that layout.
- The same local package registered an explicit JS extension, a globbed
  prompt, and a command. Its `session_start` event handler fired. A
  settings-level package filter selected one of its declared skills
  while retaining its extension and prompt.
- `pi install git:<repository URL>` and
  `pi install npm:<package>@<version>` each loaded the expected skill
  from a synthetic loopback source. A packaged theme was discovered
  by the Pi loader, and a TypeScript extension registered a command
  and tool.
- `pi mcp add <name> -- node <server.cjs>` registered a local stdio
  server. `pi mcp list --json` reported its discovered tool. A
  packaged extension calling `pi.registerMcpServer` with
  `exposure: "direct"` also completed MCP initialization and tool
  listing. Keep the RPC session open long enough for asynchronous
  server startup when verifying an extension.
- Project-local package resources appeared after approving project
  trust. The denied test returned no package skills, prompt or command.
  With a configured package, `pi --mode rpc --no-session` and
  `get_commands` exposed the inventory without running a prompt.

[Pi 1.4.0 packages](https://github.com/earendil-works/pi/blob/v1.4.0/packages/coding-agent/docs/packages.md) ·
[Pi 1.4.0 MCP](https://github.com/earendil-works/pi/blob/v1.4.0/packages/coding-agent/docs/mcp.md) ·
[Pi RPC](https://docs.pi.dev/latest/rpc)

## Lifecycle hook isolation

- For Claude Code and Codex, give each native manifest its own hook
  file. The dual-client package has both native manifests, no portable
  root manifest and no shared `hooks/hooks.json`. Each client
  registered one hook and wrote only its own marker. Removing only
  that client's `hooks` field gave zero hooks in both control runs.
  Removing the whole Codex manifest caused Codex to load the Claude
  hook instead. [Dual-client example and verification](../assets/examples/lifecycle-hooks/fixtures/dual-client-hooks/README.md)
- The four-client package uses a legacy root hook pointer for Copilot,
  the native Claude and Codex overlays, and explicit OpenCode config.
  Portable Copilot 1.0.103 and 1.0.114 also loaded the namespaced hook
  from `com.github.copilot/hooks/hooks.json`. Copilot 1.0.73 loaded the
  hook through the legacy path. Changing Codex to an Agent Plugins
  1.0 root produced zero hooks in `hooks/list` even when both the
  OpenAI extension and native overlay specified one. Codex legacy
  registered and ran after review. [Four-client example and verification](../assets/examples/lifecycle-hooks/fixtures/multi-client-hooks/README.md) ·
  [Codex hook loader](https://github.com/openai/codex/blob/rust-v0.171.0/codex-rs/core-plugins/src/loader.rs#L889)

## Replay and extend the checks

Use distinct names and valid frontmatter for the initial layout probe.

```text
layout-probe/
  skills/primary/SKILL.md
  skills/group/nested/SKILL.md
  extra-skills/secondary/SKILL.md
```

Install the same fixture with an Agent Plugins 1.0 root and again with
the appropriate native manifest. Add only `./extra-skills/` in a control
to distinguish adding from replacing the default. To test a catalog
source, leave the package unchanged and vary only the entry or the
marketplace registration. Check the inventory in a new process using the
commands for that client.

For Codex, initialize app-server, send `initialized`, then call
`plugin/read` with `pluginName` and an absolute `marketplacePath`.
Use `skills/list` with `cwds` and `forceReload: true` for the installed
inventory. Check `hooks/list` before judging hook execution.
[Codex app-server](https://learn.chatgpt.com/docs/app-server)

When adding a recommendation, record the harness build, package format,
source form, exact inventory and adjacent control. Record a tool call or
an execution marker if the recommendation depends on runtime behavior.
