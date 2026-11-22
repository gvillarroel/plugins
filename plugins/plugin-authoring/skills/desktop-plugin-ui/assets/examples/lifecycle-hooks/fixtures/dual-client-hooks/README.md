# Separate Claude Code and Codex hooks

This package has two native manifests. Each manifest points to its own
`SessionStart` hook file.

| Client | Manifest | `hooks` value |
| --- | --- | --- |
| Claude Code | `.claude-plugin/plugin.json` | `"./hooks/claude.json"` |
| Codex | `.codex-plugin/plugin.json` | `"./hooks/codex.json"` |

The commands validate the actual event payload on stdin and append a
client-specific marker to the file named by `HOOK_PROBE_LOG`. The
fixture has neither a root `plugin.json` nor a shared
`hooks/hooks.json`.

## Run the check

With Python, Node.js, Claude Code and Codex on PATH, run this from
`assets/examples/lifecycle-hooks` inside the installed skill.

```powershell
python -B test_dual_client_hooks.py
```

The runner installs copies of one package through local catalogs in
disposable profiles. Claude reports the hook count with
`plugin details` and logs the loaded path and execution with
`--init-only`. Codex reports the hook source and trust state through
`hooks/list`. The runner approves the fixture hook by hash in the
temporary profile and executes a normal turn against a loopback model
stub.

| Case | Registered hook | Marker |
| --- | --- | --- |
| Claude Code, both manifests | `./hooks/claude.json` | `claude:SessionStart` |
| Codex, both manifests | `hooks/codex.json` | `codex:SessionStart` |
| Either client, its own `hooks` value removed | None | None |
| Codex, whole Codex manifest removed | `hooks/claude.json` | `claude:SessionStart` |

The negative control keeps the other client's hook declaration and
both JSON files. Keep both native manifests to isolate their hooks.
Use `--claude-executable` or `--codex-executable` to select a build.

Tested on Windows with Claude Code 2.1.302, Codex CLI 0.167.0 and
0.171.0, and the Desktop-bundled core 0.171.0-alpha.13 through CLI
and app-server.
