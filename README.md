# Plugins

Gerardo Villarroel's marketplace for Codex, Claude Code and GitHub Copilot CLI. Each plugin bundles the skills, scripts and resources for a particular workflow. A skill can have a different version in each plugin. The [plugin catalog](docs/catalog.md) lists the skills and installation commands for every plugin.

For personal utilities, `agent-utilities` includes `find-skills` and `delegate-map-reduce`. The `workstation-tools` plugin includes Playwright and the Google Workspace CLI workflow.

## Install from GitHub

Sign in with an account that can read the private repository `gvillarroel/plugins`. Register the marketplace once in Codex, Claude Code or Copilot CLI. The examples install `diagram-studio` from `main`. To install another plugin, replace `diagram-studio` with its catalog name and keep the `@plugins` suffix.

### Codex

```sh
codex plugin marketplace add gvillarroel/plugins --ref main
codex plugin add diagram-studio@plugins
```

### Claude Code

```sh
claude plugin marketplace add gvillarroel/plugins
claude plugin install diagram-studio@plugins
```

In Claude Code, `/diagram-studio:mermaid` invokes the plugin's Mermaid skill.

### GitHub Copilot CLI

```sh
copilot plugin marketplace add gvillarroel/plugins
copilot plugin install diagram-studio@plugins
```

`agent-foundry` ships a native Copilot extension. Start `copilot --experimental` to use its `/contract` command.

## Pi

Pi loads individual skill packages from a local clone. Clone the repository once and keep the checkout at the same path.

```sh
gh repo clone gvillarroel/plugins
cd plugins
pi install ./plugins/diagram-studio
pi list
```

Use `/skill:mermaid` in Pi. For another package, run its `pi install` command from the checkout root. Run `git pull --ff-only` there to update the files and `/reload` in an open Pi session. These packages expose skills in Pi. Components such as the Reflex XY MCP renderer require separate host support.

## Use a local checkout with Codex, Claude Code or Copilot

Clone the repository as shown above. From its root, set `$repo = (Get-Location).Path` in PowerShell or `repo="$PWD"` in Bash. Register the absolute path in the client you use, then run the same plugin installation command as above.

| Client | Register the local marketplace |
| --- | --- |
| Codex | `codex plugin marketplace add "$repo"` |
| Claude Code | `claude plugin marketplace add "$repo"` |
| GitHub Copilot CLI | `copilot plugin marketplace add "$repo"` |

If Git reports `Filename too long` on Windows, run `git config --global core.longpaths true` and retry. Some clients clone the marketplace into deeply nested temporary directories.

For a small installation check, install `marketplace-check` and ask its `shared-example-1` skill to read the bundled fixture. Some workflows need additional inputs. For example, `editorial-research` reads the blog's private research corpus, `store-studio` uses the active store's catalog and assets, and `reflex-xy` uses Node.js and `uv` for rendering. Each skill describes its requirements.

[Maintenance, provenance and tests](docs/maintenance.md)
