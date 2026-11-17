# Memory and reference corpora

## Contents

- [Store and recall memory](#store-and-recall-memory)
- [Reference coding](#reference-coding)

## Store and recall memory

Select a stable namespace for the requested project or agent. Store useful facts
with provenance metadata and an explicit ID when updates should replace a known
memory. Do not persist secrets or inferred preferences as established facts.
Namespace separation prevents accidental mixed queries; it does not give
independent authorization to callers of an unauthenticated node.

Write the following bodies as UTF-8 JSON in the workspace, then use the HTTP
helper from this skill. Set `XERJ_URL` or pass `--url` for a custom node.

`memory.json`:

```json
{
  "id": "build-runtime",
  "text": "This project uses Python 3.12 for its build scripts.",
  "metadata": {"kind": "project-fact", "source": "pyproject.toml"}
}
```

```sh
uv run --script <skill-dir>/scripts/xerj_api.py --output stored.json request POST _memory/projectx --body-file memory.json
uv run --script <skill-dir>/scripts/xerj_api.py --output recent.json request GET _memory/projectx
```

`recall.json`:

```json
{
  "query": "Python build scripts",
  "k": 3,
  "filter": {"term": {"metadata.kind": "project-fact"}}
}
```

```sh
uv run --script <skill-dir>/scripts/xerj_api.py --output recalled.json request POST _memory/projectx/_recall --body-file recall.json
```

Expect a top-level `hits` array containing `id`, `text`, `metadata`, and `score`.
Adding `"semantic": true` embeds the query on the server; without it a text
query uses lexical BM25. A supplied `vector` uses vector recall. Never mix
embedding dimensions or models. Text without a supplied vector is embedded
automatically; the node's default feature hashing remains lexical.

Only forget requested entries: `DELETE /_memory/projectx/build-runtime` removes
one; `DELETE /_memory/projectx` removes the whole namespace. Use an exact
namespace and ID, percent-encoding path components if needed. Verify a requested
deletion by recalling or listing afterward. Do not drop all memory to repair
an unrelated query failure.

## Reference coding

Use reference corpora when the task needs mechanisms from unfamiliar or pinned
upstream code. Keep the selected sources and revisions explicit, and check the
source license before adapting code. Do not clone a broad library collection
when a focused local source or one selected repository answers the task.

For peer repositories already present locally, ordinary `autoindex` with
different `--prefix` and `--state-dir` values is sufficient. Query each prefix
with `xerj search` or `xerj def` and cite `repository/path:line`. Pin a commit
when reproducibility matters.

For the managed corpus lifecycle, check `xerj corpus --help` and
`xerj code --help` before using a release-specific option:

```sh
xerj corpus add peerlib https://github.com/OWNER/REPOSITORY.git
xerj corpus index peerlib --url http://127.0.0.1:9200
xerj corpus list --url http://127.0.0.1:9200
xerj code peerlib "how does it bound the retry budget"
```

Set `XERJ_URL` for commands whose help advertises it; do not assume a server's
TOML config selects the CLI client endpoint. `autoindex` requires its explicit
`--url` for a custom node. Managed corpus data defaults to `~/.xerj-code` in
the checked release; set `XERJ_CODE_HOME` to an absolute task-local directory
before `corpus add` or `index` when writes must stay in the workspace. Use
`XERJ_CODE_HOME="$PWD/reference-cache"` on POSIX or
`$env:XERJ_CODE_HOME = Join-Path (Get-Location) 'reference-cache'` on PowerShell.
Keep this cache outside any local tree being indexed.

The [Corpus Hub catalog](https://hub.xerj.org/llms.txt) lists manifests. When a
specific hub corpus is requested, download its manifest to a local JSON file
and inspect its sources, commit pins, and licensing. The checked `corpus add
--from` contract accepts a local manifest or pack; do not pass a URL where a
local path is required:

```sh
xerj corpus add --from ./selected-corpus.json
xerj corpus index selected-slug --url http://127.0.0.1:9200
xerj code selected-slug "the mechanism required for this task"
```

Pack imports may support `--verify-sig <public-key-file>`; verify checksums and
the appropriate trusted signature instead of disabling verification after a
failure. Availability of signed hub packs, `hub`, and `ask` varies with release
and build features. The checked Windows release advertises `ask` as unavailable
without a compiled hub signing key. Fall back to supported manifest/local
indexing, not an invented command.

Verify that indexing actually produced searchable records and retrieval returns
relevant passages. Report source revision, license boundary, paths/lines, and
the query used. Empty retrieval is not evidence for a remembered upstream claim.

Sources: [agent quickstart](https://xerj.org/docs/agents/quickstart),
[memory API](https://xerj.org/docs/recipes/agentic-memory),
[reference coding](https://xerj.org/case-studies/reference-coding),
[corpus hub](https://xerj.org/docs/corpus-hub), and installed command help.
