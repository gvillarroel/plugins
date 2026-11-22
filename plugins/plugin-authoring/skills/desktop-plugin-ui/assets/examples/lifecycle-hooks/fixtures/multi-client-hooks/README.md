# Client-specific hooks in one plugin directory

Each client writes its own marker to `HOOK_PROBE_LOG`. The same
directory was tested with these registrations on Windows.

| Client | Hook registration | Marker |
| --- | --- | --- |
| Copilot CLI | Legacy root `plugin.json` points to `com.github.copilot/hooks/hooks.json`. Portable builds that support it find that path automatically. | `copilot:sessionStart` |
| Claude Code | `.claude-plugin/plugin.json` points to `./hooks/claude.json`. | `claude:SessionStart` |
| Codex | `.codex-plugin/plugin.json` points to `./hooks/codex.json` with a legacy root. | `codex:SessionStart` |
| OpenCode V1 | The project config's `plugin` list points to `hooks/opencode-v1.mjs`. | `opencode:session.created` |
| OpenCode V2 | The project config's `plugins` list points to `hooks/opencode-v2/`. | `opencode-v2:session.created` |

## Use the verified layout

Keep the legacy root manifest and both native overlays for the
four-client example. The root hook declaration reuses the Copilot
namespace file.

```json
{
  "name": "multi-client-hooks",
  "version": "0.1.0",
  "description": "Probe lifecycle hooks from one plugin directory.",
  "hooks": "./com.github.copilot/hooks/hooks.json"
}
```

Add the matching entry to the OpenCode project config. These paths
assume `opencode.json` is in the package directory. Resolve them from
the config that declares the plugin.

```json
{ "plugin": ["./hooks/opencode-v1.mjs"] }
```

```json
{ "plugins": ["./hooks/opencode-v2"] }
```

## Compare a portable root

The runner creates the Agent Plugins 1.0 variant in a temporary copy.
It replaces the legacy root `hooks` field with
`extensions.com.openai.hooks` and selects the portable schema.

| Build | Agent Plugins root | Legacy root |
| --- | --- | --- |
| Copilot CLI 1.0.73 | No marker | Copilot marker |
| Copilot CLI 1.0.103 and 1.0.114 | Copilot marker | Copilot marker |
| Claude Code 2.1.302 | Claude marker | Claude marker |
| Codex CLI 0.167.0 and 0.171.0, Desktop-bundled core 0.171.0-alpha.13 | Zero hooks in `hooks/list`, no marker | Codex marker after approval |

The Codex turn completed in both formats. The portable root skipped
hook discovery even with the native overlay present. The
Desktop-bundled binary was exercised through CLI and app-server.
[Codex 0.171.0 hook loader](https://github.com/openai/codex/blob/rust-v0.171.0/codex-rs/core-plugins/src/loader.rs#L889)

OpenCode 1.18.4 and 2.3.2 both created a session without a marker when
only the package manifests were present. Each emitted its own marker
with the native project config in either package variant.

## Run the checks

Run the matching command from `assets/examples/lifecycle-hooks` inside
the installed skill, with Python, Node.js and the client on PATH.
Use `--executable` to select a specific binary.

```powershell
python -B test_plugin_hooks.py copilot
python -B test_plugin_hooks.py claude
python -B test_plugin_hooks.py codex
python -B test_plugin_hooks.py opencode
```

The runner uses isolated profiles. Copilot and Codex complete a turn
against a loopback stub. Claude uses `--init-only`. OpenCode creates
a session over local HTTP. OpenCode V1 can install its SDK dependency
when it first starts the local plugin.

For the regular Codex trust flow, the
[dual-client check](../dual-client-hooks/README.md) approves the
discovered fixture hook by hash and executes without a trust override.
The four-client comparison uses a trust override in its disposable
Codex profile to test both manifest formats.
