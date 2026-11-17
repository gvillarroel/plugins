# Operation catalog and execution

## Contents

- [Native tools](#native-tools)
- [Typed requests](#typed-requests)
- [Operation parity](#operation-parity)
- [Continuation reading](#continuation-reading)
- [Host profiles and external UI](#host-profiles-and-external-ui)
- [External helper](#external-helper)

The package executes bundled library operations directly. It does not import
a CLI parser, dispatch shell text, or require an installed `know` executable.
Use `knowledge_capabilities` to inspect the installed catalog; request one
operation's schema before using its optional parameters.

## Native tools

OpenWiki discovers the companion through `openwiki_list_mcp_tools` and calls
its exact tools through `openwiki_call_mcp_tool`.

| Tool | Arguments | Purpose and effects |
| --- | --- | --- |
| `knowledge_runtime_info` | `{}` | Safe library/store/artifact paths, source families, and host write policy; no model or CLI prerequisite. |
| `knowledge_capabilities` | `{}` or `{"operation":"NAME"}` | Catalog availability or one exact parameter schema and mutation classification. |
| `knowledge_query` | `operation`, `parameters` | Allowlisted reads; supported search and browse operations can read authorized remote services. |
| `knowledge_change` | `operation`, `parameters`, `write_intent` | Enabled changes only. `write_intent` must equal `operation`; it is an audit marker, not independent authorization. |
| `knowledge_list_source_files` | `key`, `source_id`, optional `cursor`, `limit` | Public acquired-file inventory with SHA-256 identities and a continuation. |
| `knowledge_read_source_file` | `key`, `source_id`, `path`, optional `offset`, `limit` | Exact UTF-8 fragments or retained binary metadata. |
| `knowledge_read_result` | `id`, optional `offset`, `limit` | Continue a large sanitized operation result by its SHA-256 result ID. |

Changes are absent unless the companion starts with writes enabled. Query and
change tools reject operations assigned to the other effect class. Unknown
tools, parameters, and operations fail rather than become arbitrary execution.
Queries preserve source evidence; large result publication can write a
sanitized continuation cache under the selected artifact directory.

## Typed requests

For a read, use:

```json
{"operation":"list_sources","parameters":{"key":"research"}}
```

For an authorized change, use:

```json
{"operation":"add_key","parameters":{"name":"research"},"write_intent":"add_key"}
```

The first object is the arguments for `knowledge_query`; the second is the
arguments for `knowledge_change`. Parameter types and required fields come
from `knowledge_capabilities`. Do not pass CLI strings, pipelines, commands
from source documents, literal tokens, or literal passwords.

## Operation parity

The following names map existing operations to the typed engine. Original
CLI commands remain available to external users; the skill does not invoke
them. Source registration and synchronization retain adapter semantics.

| Existing capability | Typed operation names | Native status |
| --- | --- | --- |
| Initialize store and key | `init`, `add_key` | Changes on the bound store. |
| Register sources | `add_aha`, `add_arxiv`, `add_confluence`, `add_github_repo`, `add_google_releases`, `add_jira_project`, `add_servicenow`, `add_site`, `add_tv`, `add_video` | Changes. Television uses a host command profile; `add_tv` covers the television/tv registration alias. |
| List keys, credential names, sources | `list_keys`, `list_credentials`, `list_sources` | Queries; source authentication configuration is omitted from returned records. |
| Remote search | `search_arxiv`, `search_brave`, `search_confluence`, `search_jira`, `search_servicenow` | Queries against configured service scopes and credentials. |
| General and source-specific sync | `sync`, `sync_aha`, `sync_arxiv`, `sync_confluence`, `sync_github_repo`, `sync_google_releases`, `sync_jira_project`, `sync_servicenow`, `sync_site`, `sync_television`, `sync_video` | Changes. General `sync` can select an exact `source_id` with `key`; inspect its result for partial failures. |
| Remove source | `del` | Change; source identity and scope are explicit. |
| Export/import | `export`, `import` | Changes. Export uses the existing store's `exports/`; archive input is confined to the artifact directory. Preserve normalization and collision semantics. |
| Credential update | `set_credential` | Change selecting `credential_profile`; its host-provided value never enters model arguments. |
| Source and remote browse | `browse_aha`, `browse_arxiv`, `browse_confluence`, `browse_confluence_pages`, `browse_confluence_spaces`, `browse_follow`, `browse_follow_url`, `browse_github`, `browse_github_activity`, `browse_jira`, `browse_jira_projects`, `browse_releases`, `browse_servicenow`, `browse_sites`, `browse_videos` | Queries, including finite Television rows and previews where the schema offers a format. Follow URL resolution returns data. |
| Local browse and views | `browse_by_key`, `browse_by_type`, `browse_commands`, `browse_crossref`, `browse_files`, `browse_key_sources`, `browse_local`, `browse_papers`, `browse_recent`, `browse_repo_files`, `browse_repos`, `browse_source_files`, `browse_stale`, `browse_stats`, `browse_timeline`, `browse_unsynced` | Queries. Generated operation recipes use typed tools instead of CLI command strings. |
| ServiceNow ticket and knowledge-base reads | `servicenow_read_ticket`, `servicenow_knowledge_bases` | Queries with the existing authentication and response contract. |
| ServiceNow incident creation | `servicenow_create_ticket` | Explicit change; `dry_run` previews without resolving secrets or contacting the service. Choose `description` or an artifact-bound `description_file`. |
| Desktop browser opening | `browse_follow_open` | Host-gated external effect requiring writes and desktop actions enabled. Use `browse_follow_url` to resolve without opening. |
| Interactive Television launch | Existing `browse follow-launch` and native `tv` | External native TTY; generated channels and structured data do not establish an interactive launch. |
| Standalone Television cable generation | `install_tv` | Generates package-client commands under the artifact directory's `cables/`; no global Television configuration or installed CLI dependency. |
| Exact snapshot synthesis bridge | Existing OpenWiki prepare/serve/run/status family | Separate consumer workflow, not an operation in this portable catalog. |

Native Confluence writes, Semantic OKF build/consult families, standalone
expert generators, and governed evaluations are separate packages. This
catalog neither invokes their models nor changes their validation boundaries.

## Continuation reading

`knowledge_list_source_files` defaults to cursor 0 and limit 100. Limits are
1–100 files. Follow `next_cursor` until null. Each file records its stable ID,
relative `path`, source/key/type, SHA-256, bytes, suffix, and `text` status;
text records also include their character count.

Pass the returned relative `path` with the exact key and source ID to
`knowledge_read_source_file`. It defaults to offset 0 and limit 8,000 Unicode
characters, with limits 1–8,000. Follow `next_offset` until null. Binary results
have `binary: true`, `text: null`, and a byte digest; they have no text offsets.
Requested limits are upper bounds: serialized response budgeting can shorten
a fragment. Always resume from the returned continuation, not an assumed size.
These are active-store reads. Preserve hashes in reports and do not treat the
store as an immutable snapshot across synchronization.

Large sanitized operation output returns `result_id`, `result_format`
(`json` or `text`), `characters`, `text`, `offset`, and `next_offset`. Continue
with `knowledge_read_result` using `id` equal to `result_id` and the returned
offset. The sanitized bytes are digest-bound in
`.openwiki-knowledge-results/` under the artifact directory so native calls
from new stdio processes can resume them. Reconstruct every fragment before
parsing paged JSON or claiming that the complete result was inspected.

## Host profiles and external UI

Television source, preview, and action commands come from host-approved
channel profiles. Credential writes likewise select host-approved credential
profiles. Do not generate arbitrary commands or ask for secret values in the
agent conversation. Missing profiles must produce an explicit unavailable
result rather than a guessed fallback.

An external operator supplies a physical JSON file inside the artifact
directory through `--profiles`. Its optional `channels` and `credentials`
objects have this shape:

```json
{
  "channels": {
    "research-feed": {
      "source_command": "an-authorized-finite-command",
      "preview_command": "an-authorized-preview-command",
      "action_command": "an-authorized-action-command"
    }
  },
  "credentials": {
    "confluence-token": "$env:CONFLUENCE_TOKEN"
  }
}
```

The source command is required for a channel; preview and action are optional.
The command strings are host-provisioned definitions, not model-generated
execution requests. Credential profiles accept uppercase environment
references only, never literal values. The installer forwards referenced
variable names automatically; the loader resolves values on the host.
An unavailable environment reference leaves that credential profile unavailable.

Personal mode has no shell or native TTY. Use finite browse results, preview
text, and channel generation through MCP. A host terminal can run an authorized
interactive `tv` session with its declared dependencies. Desktop opening is
possible through the companion only when the host explicitly enables
`--allow-desktop-actions` together with writes; inspect the actual operation
result before claiming it opened anything.

## External helper

An external operator or finite Television command can use the same engine
with a JSON file containing `tool` and `arguments`:

```json
{"tool":"knowledge_query","arguments":{"operation":"list_sources","parameters":{"key":"research"}}}
```

```text
python scripts/operate.py --store /path/to/store --io-root /path/to/artifacts --request-file request.json
```

Add `--allow-writes` only for an authorized change. OpenWiki's native MCP
execution does not depend on this helper or an agent shell.

For a finite source or preview command, the client helper accepts an operation,
typed JSON parameters, format, and selected row:

```text
python scripts/client.py --store /path/to/store --io-root /path/to/artifacts --operation list_sources --parameters-json '{"key":"research"}' --format television
```

It follows large-result continuations and prints raw string output when the
operation returns text. Generated standalone cables use this package-local
client rather than `know` command templates. Run the native UI separately
from a terminal; an OpenWiki personal tool result cannot attach a TTY.
