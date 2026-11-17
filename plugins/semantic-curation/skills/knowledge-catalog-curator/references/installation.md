# Installation and migration

## Contents

[GitHub](#install-the-skill-from-github), [runtime](#install-the-runtime),
[engine](#native-open-ontologies), [MCP hosts](#claude-desktop-and-mcp-hosts),
[Claude commands](#claude-code-commands), [existing work](#existing-work-and-removal).

The skill is the distribution unit. Its `assets/runtime/` contains the complete
curator source, ontology, review interfaces, Claude commands, dependency lock,
licenses, and maintenance tests. It does not rely on files outside this bundle.

## Install the skill from GitHub

For Codex or Claude Code, select only this skill:

```sh
npx skills add gvillarroel/skills --skill knowledge-catalog-curator --agent codex --global --copy --yes
npx skills add gvillarroel/skills --skill knowledge-catalog-curator --agent claude-code --global --copy --yes
```

Codex's skill-installer also accepts repository `gvillarroel/skills` and path
`skills/knowledge-catalog-curator`. A checkout works as a local source with
`npx skills add /absolute/path/to/checkout --skill knowledge-catalog-curator`.
The skill becomes available on the next turn after installation.

Pi discovers this skill through the repository's existing package declaration:

```sh
pi install git:github.com/gvillarroel/skills
```

The collection command installs all declared skills. Installing a skill does
not create a Python runtime or register Claude Desktop by itself.

## Install the runtime

Requirements: Python 3.12+ and `uv`; Node is needed only for the Claude Code
plugin launcher or optional host-bridge maintenance. The installer asks uv for
Python 3.12 and permits its normal managed-interpreter download if absent.

Resolve `SKILL_DIR` from the installed skill's actual location. The examples
below use shell variables; use an equivalent absolute path in PowerShell.
Run from the working directory where the project's data and state belong:

```sh
uv run --script "$SKILL_DIR/scripts/curator.py" inspect
uv run --script "$SKILL_DIR/scripts/curator.py" install --destination ./curator-runtime --home ./.kc
uv run --script "$SKILL_DIR/scripts/curator.py" run --installation ./curator-runtime -- status
uv run --script "$SKILL_DIR/scripts/curator.py" run --installation ./curator-runtime -- ui
```

The installer verifies a complete SHA-256 file inventory before copying. It
uses `uv sync --locked --no-dev --no-editable`, then verifies the installed
package import. Source, environment and installation metadata live in the
external destination; saved work lives in the separate `--home`. An identical
rerun is supported. A changed source bundle or state path needs a new destination;
unrelated or modified installations are preserved.

Keep the returned installation path. Subsequent commands use that path through
`run --installation PATH -- COMMAND`. For an isolated maintenance environment,
add `--dev` during installation and run pytest with its returned interpreter.

## Native Open Ontologies

```sh
uv run --script "$SKILL_DIR/scripts/curator.py" install-engine --installation ./curator-runtime
```

This installs the checksum-pinned official 2.1.0 engine under the user's
`.knowledge-catalog-curator/engines/`, outside the skill. Windows x64, Linux x64,
and macOS arm64/x64 assets have recorded pins. Only Windows has execution evidence
in the initial migration. The engine runs bounded, credential-free dry-run
comparisons. Embedding model weights are not downloaded. Without an available
engine, choose **Local comparison** explicitly; no automatic fallback is used.

## Claude Desktop and MCP hosts

The installation JSON includes `mcp_config`: the exact installed Python command,
`-I -m knowledge_catalog.server` arguments and absolute `KC_HOME`. Other local MCP
hosts can register that configuration through their supported settings. MCP Apps
rendering also depends on host support. A skill alone does not establish a public
ChatGPT connector or a signed-in host session.

For Claude Desktop and the Claude Code launcher's runtime registration:

```sh
uv run --script "$SKILL_DIR/scripts/curator.py" register-claude --installation ./curator-runtime
```

Registration preserves other servers and settings and backs up changed files.
An existing different curator registration is rejected before either file is
modified. For a deliberate migration, inspect the selected state path and repeat
with `--replace-existing`. Use `--desktop-config PATH --runtime-dir PATH` for an
isolated verification or another supported configuration location. Restart
Claude Desktop when needed; this helper does not stop running review services.

## Claude Code commands

The repository also exposes the packaged commands through a native marketplace:

```sh
claude plugin marketplace add gvillarroel/skills
claude plugin install kc-curator@personal-skills
```

Install and register the runtime first. The plugin's Node launcher reads the
user's `.knowledge-catalog-curator/runtime.json`; `KC_RUNTIME_CONFIG` can select
an isolated registration. Start a new Claude session or run `/reload-plugins`.
Commands cover status, explore, analyze, ontology, taxonomy, review, history,
lineage, demo, and publication preparation. Human approval remains in the panel.

## Existing work and removal

To retain existing proposals, set `--home` to their existing absolute `.kc`
directory. Installation does not copy private state or datasets into the skill.
Keep original source files where their recorded provenance points. Updating
Claude registration does not restart an already running localhost review service;
complete any review and activate a new service through the normal lifecycle.

Remove the skill using its installing agent's supported removal command. Remove
the `kc-curator` host registration or plugin separately when desired. Runtime
installation folders, downloaded engine and `.kc` are separate local resources;
retain saved state until the user explicitly requests its deletion.
