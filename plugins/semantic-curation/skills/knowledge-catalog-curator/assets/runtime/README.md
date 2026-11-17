# Knowledge Catalog Curator runtime

This is the self-contained source of Knowledge Catalog Curator 0.3.0, distributed
inside the `knowledge-catalog-curator` skill. Its runtime and interface assets are
packaged together; no previous development checkout is required.

Use the owning skill's installer to copy this source into a separate runtime
directory, install the locked Python dependencies as a wheel, and choose a
separate `.kc` state directory. The installer returns a portable MCP configuration.
It does not register or overwrite an existing Claude installation automatically.

The runtime includes CSV/JSON/document profiling, RDF/SKOS/SHACL validation,
filtered local or native Open Ontologies comparisons, metadata review,
synthetic lineage, the English Colorset 1 interfaces, and Claude plugin commands.
The official Open Ontologies 2.1.0 executable is downloaded separately and
verified against pinned SHA-256 hashes; no native executable or model weights
are included in this source bundle.

For runtime maintenance after installation:

```sh
uv sync --locked --extra dev
uv run pytest
uv run ruff check .
```

Build the bundled MCP Apps bridge, when changing its source, with
`npm ci --ignore-scripts` followed by `npm run build` in `web/`. Preserve the
adjacent third-party license notices. The core Python package includes the
compiled bridge, so normal installation requires no npm build.

See [SECURITY.md](SECURITY.md) for local-state, credential, human-approval,
publication, document, and lineage limits. Writes are disabled by default.
