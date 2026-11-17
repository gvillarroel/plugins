# Runtime, state, and invocation

## Contents

- [Requirements and version selection](#requirements-and-version-selection)
- [Choose the graph lifetime](#choose-the-graph-lifetime)
- [A portable CLI batch](#a-portable-cli-batch)
- [A scoped MCP server](#a-scoped-mcp-server)
- [Effects and optional components](#effects-and-optional-components)
- [Primary sources](#primary-sources)

## Requirements and version selection

The core dependency is the `open-ontologies` Rust binary. Existing binaries
need neither a JVM nor a Python service. Obtain a suitable platform binary from
the official release or build the selected source revision when needed. Keep
tool installation inside an allowed tools directory; do not replace an existing
installation or edit a client's configuration just to inspect an ontology.

Baseline: release **v2.0.1**, source commit
`d118719043905132d314611dcee9f0cac5f87868`. The separately reviewed main commit
`fec2b4713bbab52596adbde55decd862e443b020` declares package version **2.1.0**.
Record the installed asset/build identity and hash. Start with `--help`; do not
assume that a binary exposes `--version`, every optional feature, or every tool
described by a newer checkout. Recheck changed commands when upgrading.

A pinned source-install example is:

```text
cargo install --git https://github.com/fabio-rovai/open-ontologies --rev d118719043905132d314611dcee9f0cac5f87868 --locked --root TOOLS_DIR
```

Source builds require the Rust toolchain and native build dependencies. Windows
MSVC builds need Visual Studio C++ Build Tools, a Windows SDK, and
LLVM/libclang. Node/npm is relevant to the optional Studio frontend, not a
requirement for operating an existing engine binary.

## Choose the graph lifetime

| Mode | State lifetime | Appropriate use |
| --- | --- | --- |
| One CLI `batch` process | All commands share one in-memory graph | Reproducible local validation and conversion jobs. |
| One MCP `serve` process | Calls share that server's active graph | Interactive authoring, querying, and reviewed edits. |
| Explicit persistent storage | Graph survives process restarts in `DATA_DIR/triplestore` | Repeated CLI invocations or a durable server. |

Default storage is memory. `load` followed by a separate `query` process loses
the loaded graph unless persistence or a deliberately selected daemon supplies
shared state. File saves, named versions, SQLite metadata, and the compile cache
have their own lifetimes; cache presence is not proof of the active graph.

Inspect dataset boundaries before saving. Turtle and the engine's named-version
N-Triples snapshots flatten graph names and omit its inference graph. For a
dataset whose named, temporal, or inferred graphs must survive, save N-Quads or
TriG and verify restoration into a separate store. A named version is not a
complete dataset or engine-state backup.

For persistence, place this in the selected data directory's `config.toml`:

```toml
[storage]
mode = "persistent"
```

`OPEN_ONTOLOGIES_STORAGE_MODE` can override that choice, including the server's
`--storage-mode` in the released implementation despite its CLI help claiming
the opposite. Inspect and align that environment value with the intended mode,
then verify effective state rather than trusting precedence text. Unknown modes can fall
back to memory with a warning. A persistent store admits one read-write process
at a time. Keep one owner or deliberately use its daemon instead of deleting a
lock to force a second process to open the store.

## A portable CLI batch

Run from the directory containing the supplied inputs. Write `commands.json`:

```json
[
  {"command":"validate","args":["input.ttl"]},
  {"command":"load","args":["input.ttl"]},
  {"command":"stats"},
  {"command":"query","args":["SELECT ?s WHERE { ?s a <https://example.org/Thing> } ORDER BY ?s"]},
  {"command":"save","args":["reviewed.ttl"]}
]
```

```text
open-ontologies --no-connect --data-dir ./run-state --json batch commands.json --bail
```

Use argument arrays. A JSON argument object is converted to flags and is wrong
for positional parameters such as `load`'s path. JSON also avoids shell-dependent
quoting of SPARQL and Windows paths. Use forward slashes or JSON-escaped
backslashes for Windows paths. Relative paths use the process working directory,
not the batch file's directory.

The batch emits one JSON envelope per command. Inspect `result` for errors,
validation outcomes, skipped work, and coverage. `--bail` stops on command errors;
it does not make every negative semantic result a process error. SHACL can
report violations while completing its check successfully. ASK results use the
engine's actual response shape (in v2.0.1, `{"result":true}`), rather than an
assumed `boolean` field from another SPARQL API.

## A scoped MCP server

Choose an explicit data directory and create an explicit configuration file
there. Even with a global `--data-dir`, `serve` otherwise defaults its config
path to the user's home directory. A minimal local configuration is:

```toml
[storage]
mode = "memory"

[cache]
dir = "/ABSOLUTE/run-state/cache"
```

Replace the cache path too: its default is `~/.open-ontologies/cache`, and the
data-directory option does not relocate it. An absolute workspace cache path
keeps parsed graph copies within the selected artifact boundary.

Adapt this fragment to the chosen MCP client's schema when configuration is
part of the task. Replace the absolute paths before using it:

```json
{
  "mcpServers": {
    "open-ontologies": {
      "command": "open-ontologies",
      "env": {"OPEN_ONTOLOGIES_STORAGE_MODE":"memory"},
      "args": ["--data-dir", "/ABSOLUTE/run-state", "serve", "--config", "/ABSOLUTE/run-state/config.toml", "--storage-mode", "memory", "--tools-allow", "onto_status,onto_validate,onto_load,onto_stats,onto_lint,onto_query,onto_save"]
    }
  }
}
```

`serve` speaks stdio JSON-RPC and waits for a client; it is not an interactive
terminal prompt. Discover tools and exact parameter schemas, then call
`onto_status`. Adapt the allowed tool list to the job. Filtering can include
writes, such as save or load; it does not authorize unrelated changes.

The reviewed 2.1.0 source adds named job profiles with `--tool-profile`.
**Release v2.0.1 has no such flag.** Use profiles only if installed help
advertises them; allow/deny filters further narrow a selected profile on builds
that support both. Do not assume that a profile can re-enable a filtered tool.

Native Windows has no usable Unix socket transport; use stdio or deliberately
configured HTTP. HTTP defaults to loopback. Binding beyond localhost requires
the chosen deployment's authentication and TLS arrangement; the engine supplies
no TLS itself.

## Effects and optional components

Core files, queries, ordinary SHACL, and rule reasoning can operate without a
model or remote account. `init` is not a prerequisite for the batch above:
ordinary setup creates its workspace state as needed. An embeddings-enabled
`init` can download a large model and tokenizer, so do not use it as a harmless
universal preflight.

Optional build features include SQL backends (`postgres`, `duckdb`, or `sql`),
`embeddings`, and `plugins`. Embedding tools are MCP operations rather than
invented CLI `embed`/`search` commands. Remote embedding configuration can send
graph text to a provider; local embedding initialization can download assets.
Proof checkers need their separate pinned Lean tools. Enable only components
needed by the task.

The network surface also includes recursive imports, marketplace operations,
SPARQL endpoints, SQL federation/extensions, and configured governance or
monitor webhooks. DuckDB's in-memory database does not make its federation
queries network-free. Keep account values in host credential configuration,
not reusable batch files or skill artifacts.

## Primary sources

- [Release and assets](https://github.com/fabio-rovai/open-ontologies/releases/tag/v2.0.1)
- [Pinned CLI implementation](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/src/main.rs)
- [Pinned batch parser](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/src/batch.rs)
- [Pinned storage configuration](https://github.com/fabio-rovai/open-ontologies/blob/d118719043905132d314611dcee9f0cac5f87868/src/config.rs)
- [Windows build guidance](https://github.com/fabio-rovai/open-ontologies/blob/fec2b4713bbab52596adbde55decd862e443b020/docs/windows.md)
