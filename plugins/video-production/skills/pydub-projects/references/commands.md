# Command contract

Resolve `scripts/projects.py` against this skill's directory. The helper uses
only Python's standard library. All successful commands emit a JSON object to
stdout. Errors emit `{"ok": false, "error": "..."}` and exit 2.
`--root` is required before the subcommand; it identifies the writable project.

```sh
uv run --script <skill>/scripts/projects.py --root studio init
uv run --script <skill>/scripts/projects.py --root studio branch-create --branch alternative --parent main
uv run --script <skill>/scripts/projects.py --root studio submit --branch main --key intro --payload-file task.json
uv run --script <skill>/scripts/projects.py --root studio claim --branch main --agent editor-a --lease-seconds 300
```

Payload paths resolve from the project root. Example `task.json`:

```json
{"plan": "plans/intro.json", "delivery": {"duration_ms": 3000, "channels": 2}}
```

`claim` returns `task: null` when no eligible task exists. Otherwise `task`
contains `id`, `branch`, `task_key` (the submitted `--key`), `payload`, `agent`,
`token`, `lease_until`, `attempt`, and
`workspace` (a project-relative directory). Store artifacts there.
Use `task_key` to name an artifact from the submitted key; the returned task
object has no `key` field.

Task `status` uses exactly `queued`, `running`, `done`, or `failed`.
Successful `complete` sets `status: "done"`; compare against that value when
checking completion. The CLI command name is not the stored status string.

```sh
uv run --script <skill>/scripts/projects.py --root studio heartbeat --task <id> --agent editor-a --token <token> --lease-seconds 300
uv run --script <skill>/scripts/projects.py --root studio complete --task <id> --agent editor-a --token <token> --artifact work/main/editor-a/<id>/<token>/mix.wav --artifact work/main/editor-a/<id>/<token>/report.json
uv run --script <skill>/scripts/projects.py --root studio fail --task <id> --agent editor-a --token <token> --error "Decode failed; source is corrupt."
uv run --script <skill>/scripts/projects.py --root studio retry --task <id>
uv run --script <skill>/scripts/projects.py --root studio status --branch main
uv run --script <skill>/scripts/projects.py --root studio events --after 0 --limit 100
```

Completion requires at least one nonempty artifact under the current attempt
workspace. Return `ok`/`task` and retain the receipts. Repeating a completed
token is rejected so callers inspect status after an uncertain response.
`retry` only changes failed tasks to queued and retains previous events.

```sh
uv run --script <skill>/scripts/projects.py --root studio state-get --namespace shared --key delivery
uv run --script <skill>/scripts/projects.py --root studio state-set --namespace shared --key delivery --value-file delivery.json --expected-revision 0
```

Missing state returns revision 0 and value `null`. State values may be any JSON
value. Keys, branches, namespaces and agent IDs use lowercase letters, digits,
hyphens and underscores, up to 64 characters. Task keys use the same grammar.
The board is `<root>/.pydub/state.sqlite3`; runtime data belongs in the project,
not in installed plugin or skill directories. Read-only status commands refuse
an uninitialized board and do not create it.
