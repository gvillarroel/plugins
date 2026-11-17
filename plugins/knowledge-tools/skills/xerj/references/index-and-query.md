# Index and retrieve evidence

## Contents

- [Index a folder](#index-a-folder)
- [Retrieve code first](#retrieve-code-first)
- [Discover real fields](#discover-real-fields)
- [Compact HTTP search](#compact-http-search)
- [Diagnose absent or stale results](#diagnose-absent-or-stale-results)

## Index a folder

Use a narrow source directory. Give unrelated corpora different prefixes and
journals; avoid indexing the server's storage or generated search outputs.
`autoindex` must run on the machine that can read the files, even if `--url`
points to another node. A remote URL sends extracted content to that node.

Inspect `xerj autoindex --help`. Preview a substantial run with `--dry-run`,
relay the measured plan, then proceed within the user's authorized scope:

```sh
xerj autoindex ./source --url http://127.0.0.1:19320 --prefix projectx --state-dir ./journal --no-graph --workers 2 --dry-run --json
xerj autoindex ./source --url http://127.0.0.1:19320 --prefix projectx --state-dir ./journal --no-graph --workers 2 --json
xerj autoindex map --url http://127.0.0.1:19320 --json
```

`--no-graph` selects the generated-journal reconciliation route in the checked
release. Normal reruns against the same folder, prefix, and journal reconcile
add/change/delete/rename. Keep graph mode for tasks that need relationships:
its frozen-plan resume has different addition/deletion limits. Do not treat
`--fresh` as removal of stale records; for an independent rebuild choose a new
prefix and state directory, verify it, then switch readers.

Defaults respect ignore files and skip hidden files. `--no-ignore` still skips
hidden files and removes useful exclusions; do not add it just to raise counts.
Unpack an explicitly selected archive before indexing its contents.
`--no-semantic` makes text retrieval lexical-only. `--code-analyzer code` affects
new code datasets and costs more indexing work; use it when identifier splitting
matters. For code watch mode, inspect the release's `--watch --no-graph` support.

Interpret completion before reporting success:

| Exit | Meaning and response |
| --- | --- |
| 0 | Complete, or explicitly cancelled by an approval response; inspect the summary. |
| 3 | Completed with junk or another qualified result. Read reasons and `datasets_refused` / `files_refused`; verify the intended dataset. |
| 4 | Decision gate. Read the JSON payload; do not blindly retry. Narrow scope or supply `--approve proceed` / `fast` when existing user authorization covers it. `fast` disables semantic and graph work. |
| 2 | Usage error. Check installed help. |
| 1 | Read the error: transport, journal, removal, or unsafe transition failure. |

The time gate defaults to ten minutes. Do not disable it reflexively. No extra
approval is necessary for a run already covered by the user's scope and budget.
On a refused mapping, address the cause and rebuild separately; repeating a
committed refusal does not repair it. For transient back pressure, autoindex
already retries rejected items; avoid running a competing ingestion process.
Relay actual `xerj-progress` phase and percentages. `unknown` is not an ETA.

## Retrieve code first

```sh
xerj search --url http://127.0.0.1:19320 --prefix projectx -k 5 "retry failed requests with exponential backoff"
xerj def --url http://127.0.0.1:19320 --prefix projectx --kind function --lang python "retry_request"
```

`search` returns passages with file/line provenance; `def` targets definitions.
Use `--json` to retain raw evidence. Verify that a result answers the question,
then open only the small source range needed to confirm behavior. Cite the
returned path and line, and distinguish local observations from inferences.
Create a destination's parent directory before redirecting CLI output to a file;
the HTTP helper creates output parents itself.

## Discover real fields

Query the catalog or mappings before writing DSL. Set `XERJ_URL` or pass the
helper's `--url` for a custom node:

```sh
uv run --script <skill-dir>/scripts/xerj_api.py --output catalog.json request POST autoindex-catalog/_search --body-file catalog-query.json
uv run --script <skill-dir>/scripts/xerj_api.py --output mappings.json request GET 'projectx-*/_mapping'
```

A minimal `catalog-query.json` is `{"size":10,"query":{"match_all":{}}}`.
Do not assume every format uses `body`, or every code record has the same
symbol field. Restrict a query to indices with compatible fields. Wrong fields
can return a strict 400 on autoindex indices or hints/zero hits elsewhere.
Read `_xerj.hints` rather than interpreting a typo as absent evidence.

## Compact HTTP search

After verifying that `body`, `title`, and `ax_path` exist, write `query.json`:

```json
{
  "size": 5,
  "query": {"match": {"body": "retry exponential backoff"}},
  "_source": ["title", "ax_path"],
  "fields": ["_passage"]
}
```

```sh
uv run --script <skill-dir>/scripts/xerj_api.py --output hits.json request POST 'projectx-*/_search' --body-file query.json
```

`_passage` is requested through `fields`; it is not a mapped source field. It
returns matching text and offsets, sometimes a page. Limit `_source` to needed
provenance so a few hits do not return entire long documents. Inspect the actual
response shape; line provenance may come from code metadata rather than offsets.

For semantic search, require a `semantic_text` mapping and an embedding mode
chosen at ingest. A query body can be:

```json
{
  "size": 5,
  "query": {"semantic": {"field": "body", "query": "retry exponential backoff", "k": 5}},
  "_source": ["title", "ax_path"],
  "fields": ["_passage"]
}
```

Default lexical embeddings still reward token/subword overlap. Do not label
such results neural or promise synonym recall. For a manually created index,
declare `body` as `semantic_text` and use `PUT /index/_doc/id` for an explicit
ID, `POST /index/_doc` for an automatic ID, then `POST /index/_refresh` before
testing immediate visibility.

For custom `dense_vector` or hybrid queries, fetch the current endpoint
contract. Match dimensions and embedding model at ingest and query. Hybrid
fusion accepts `rrf` or `linear`; `learned` is unsupported. `_passage` is not
accepted with hybrid or multi-kNN fusion; use an allowed source projection.
Do not silently add external `rerank` to local retrieval.

## Diagnose absent or stale results

1. Check readiness, authentication, the explicit URL, and the selected prefix.
2. Check catalog/mappings and a bounded `match_all` before changing a query.
3. Inspect skips, refused datasets, and autoindex's final summary.
4. Refresh newly written manual indices. Rerun a generated journal for changed
   files; respect graph-mode limitations. A new embedding mode needs reindexing.
5. If no relevant passage exists, say so and continue from available source
   evidence. Scores are ranking signals, not factual confidence.

Sources: installed `autoindex`, `search`, and `def` help;
[zero-config indexing](https://xerj.org/docs/recipes/zero-config-autoindex),
[exit codes](https://xerj.org/answers/autoindex-exit-codes),
[passage retrieval](https://xerj.org/docs/recipes/passage-retrieval),
[agent endpoints](https://xerj.org/docs/agents/endpoints).
