# Coordination and state

## Choose the ownership model

| Mode | Project root | Branch | Behavior |
| --- | --- | --- | --- |
| Independent | Different per agent/project | Any | Separate database, state and files |
| Alternatives | Same local root | Different per agent/idea | Separate queues and attempt paths; common event inventory |
| Shared work | Same local root | Same branch | Atomic claims divide one queue; explicit shared JSON state |

Branches are logical audio task namespaces, not Git branches. Creating a branch
records lineage without copying queued/running work or automatically merging
artifacts. To adopt an alternative, inspect its verified receipts and submit
an explicit integration task. Shared state namespaces are independently named:
use a branch name for branch-local decisions or `shared` for common decisions.

Pattern ID: `pydub-leased-work`. Trigger: concurrent agents or crash recovery.
Input: project root, branch, stable key and JSON payload. Submit, atomically
claim, render in the token-specific workspace, heartbeat, verify files, then
complete with task/agent/token. Validate that simultaneous claims yield one
owner, an expired owner cannot finish, and a repeated key cannot change payload.

The board uses SQLite `BEGIN IMMEDIATE`, a busy timeout and WAL. File rendering
is outside the transaction. A claim returns a random fencing token; every
owner operation checks token, agent, running status and unexpired lease.
Expired work is reclaimable; old output directories are retained as evidence.
Claims and completions are atomic database transitions. A token cannot stop
arbitrary code from writing files, so stale workers must keep their own attempt
directory and must never overwrite another attempt's output. The board is
cooperative local coordination, not an untrusted-user security boundary.

Pattern ID: `pydub-shared-state`. Trigger: common timing, sample rate, mix
decisions or artifact selection. Input: namespace/key, JSON and expected revision.
Read the current revision; create with 0 or update with the returned revision.
On conflict reread and reconcile. Do not blindly retry the old value. Test that
two writers using the same revision cannot both succeed.

An artifact completion includes a contained regular file, byte length and
SHA-256. It is not a hard link to immutable storage; future file mutations can
invalidate the receipt. Review by comparing the current digest with the receipt.
Paths in task payloads are data, and no shell is evaluated by this coordinator.

Sources checked 2026-11-17:

- [SQLite transactions](https://sqlite.org/lang_transaction.html)
- [SQLite WAL and local filesystem restrictions](https://sqlite.org/wal.html)
- [Python SQLite and backup](https://docs.python.org/3/library/sqlite3.html)
