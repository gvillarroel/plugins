---
name: find-skills
description: Find a skill for a requested task, identify the plugin that provides it, and install that plugin when the user requests installation.
---

# Find a skill

Identify the user's task and active client. Look in the personal marketplace `gvillarroel-plugins` from `gvillarroel/plugins` when it is registered. Browse other registered marketplaces if the capability is missing. Search plugin descriptions and their `skills/*/SKILL.md` manifests for the capability. Skills can have independent variants in different plugins, so choose the plugin that fits the task.

| Client | Browse | Install when requested |
| --- | --- | --- |
| Codex | `codex plugin list --available --marketplace gvillarroel-plugins --json` | `codex plugin add NAME@MARKETPLACE` |
| Claude Code | `claude plugin list --available --json` | `claude plugin install NAME@MARKETPLACE` |
| GitHub Copilot CLI | `copilot plugin marketplace browse gvillarroel-plugins --json` | `copilot plugin install NAME@MARKETPLACE` |
| Pi | `pi list` and the source package's skills directory | `pi install /absolute/path/to/plugin` |

To search beyond the registered marketplaces, use the host's available plugin discovery or `npx skills find <keywords>`. Check the actual source, maintainer, required tools, and installable plugin manifest. Report the skill name, provider, and installation command. When only a standalone skill exists, identify its source and describe how to package it in a plugin. After installing a plugin, verify discovery through the target client.
