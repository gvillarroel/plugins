---
name: pydub-projects
description: Coordinates PyDub audio projects and agent work with independent branches or a shared SQLite task board, leased claims, artifact receipts and versioned shared state. Use for multi-agent audio pipelines, handoffs, recovery and concurrent project administration.
---

# PyDub Projects

Use independent project roots when agents should have separate work. Use one
local project root with named branches when agents need isolated alternatives
and a shared inventory. Use the same branch when they should divide one queue.
This coordinator does not launch models; agents can use any authorized host.

Read [coordination and state](references/coordination.md) for branch semantics,
lease recovery and compare-and-set state. Read the
[command contract](references/commands.md) for exact JSON CLI arguments.

1. Resolve the user's writable workspace, branch and agent identity. Initialize
   the project using this skill's `scripts/projects.py`, never inside the
   installed skill:

   ```sh
   uv run --script scripts/projects.py --root <workspace> init
   ```

2. Submit a JSON payload using a stable task key. The key is idempotent within
   its branch; a changed payload under the same key is rejected. Reference audio
   inputs, edit plans and delivery checks in that payload. The helper does not
   execute payload contents.
3. Claim work with the agent ID. Retain the returned task ID, claim token,
   lease expiry and workspace path. Each attempt has a different directory.
   Keep audio generation outside database transactions. Extend the lease with
   `heartbeat` during long work; stop publishing if the lease has expired or a
   heartbeat fails.
4. Render and verify the requested audio with available tools. This skill is
   standalone and does not require another skill: PyDub can be installed in a
   task-local `uv` script, or any existing authorized audio worker can produce
   the files. Store outputs in the claimed attempt directory. Complete with the
   current token and verified artifact paths; the board records SHA-256 receipts.
5. Use `fail` for an unsuccessful attempt and an explicit `retry` when desired.
   Expired claims may be reclaimed with a new token. A stale worker cannot
   complete, fail or renew the new owner's claim. Inspect `status` and `events`
   to distinguish unfinished, failed and completed work.
6. Use `state-get` and `state-set --expected-revision` for actual shared JSON
   decisions. Read before updating and resolve conflicts against the new state.
   Shared state uses an explicit namespace; it never exposes a model's private
   memory or merges conversations automatically.

Use one local filesystem for the SQLite board; do not put it on an NFS/SMB
share or synchronize a live database using cloud-drive tools. Agents on other
machines need a separately deployed single-owner service/API. Back up with
SQLite's backup API or after closing writers. Artifact receipts verify bytes,
not subjective audio quality or exactly-once external effects.
