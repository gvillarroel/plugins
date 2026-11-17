# Import existing processed documents

Use the package-local [migrate.py](../scripts/migrate.py) from an external
operator to migrate documents already present on disk. This does not require
`know`, a repository checkout, a model, or a new source synchronization.

```text
python scripts/migrate.py --store /path/to/existing-store --library processed=/path/to/processed-library --output /path/to/new-import
python scripts/migrate.py --check --verify-originals --output /path/to/new-import
```

Repeat `--library NAME=PATH` for each explicit library. Choose a new destination:
imports never overwrite an earlier import. The installer creates the native
skill and a read-only MCP companion in the import's `runtime/` directory.
Set `OPENWIKI_CONFIG_DIR` to that directory for a normal personal session.
The companion retains the explicit original store binding; installation
does not mutate that store or copy its credential configuration. Its existing
source acquisition prerequisites remain separate from the document import.

Before visualizing a large corpus, prepare the explicitly selected OpenWiki
0.7.1 package with the package-local
[prepare_openwiki.py](../scripts/prepare_openwiki.py) operator:

```text
python scripts/prepare_openwiki.py --package /path/to/node_modules/openwiki
```

The operator accepts only reviewed exact graph module identities. It preserves
page order and native graph semantics, including the upstream's single URI
decoding of relative Markdown links, while bounding reads to sixteen workers.
It records original and
prepared SHA-256 and recognizes the prepared state idempotently. It does not
alter imported documents, evidence, or model/provider configuration.

The default exact-byte reader is Python. Use `--io-reader native-node` to select
the package-local bounded Node worker explicitly, and optionally
`--node-command /path/to/node` to select its executable. The helper is included
in the runtime integrity manifest and reads only inventory-approved paths.
Original verification performs fresh reads through the selected channel;
cached files cannot stand in for current originals. Neither channel calls a
model, a shell, or the network.

The importer discovers registered source evidence in the current
`<key>/<type>/<source-id>/` layout and the historical
`<key>/raw/<type>/<source-id>/` and `<key>/library/<type>/<source-id>/` layouts.
Each layout retains its own namespace and provenance. Sources without a
registry synchronization timestamp retain their files and are marked as
unverified; their existence does not prove successful acquisition. Missing
and empty registrations remain visible in the inventory. No inferred sync
timestamps or silent deduplication are permitted.

Explicit processed libraries retain Markdown, ledgers, manifests, and assets
as exact bytes. The importer excludes credential and control files, including
`.git`, `.env`, `config.yaml`, `keys.yaml`, and `source-metadata.yaml`, and
rejects linked, special, unsafe, overlapping, or platform-colliding inputs.
Select authorized document roots rather than an evaluation or workspace root.
Do not import sealed tasks, verifier payloads, credentials, or private model
traces as a document collection.

`manifest.json` binds relative paths, original input roots, source identities,
roles, byte counts, text classification, and SHA-256 digests. `evidence/`
retains the immutable source archive. `runtime/wiki/imported/` contains an
initial exact mirror readable through OpenWiki's normal wiki file tools.
Generated navigation pages link to the imported documents and retained assets.
Original Markdown is not normalized, rewritten, translated, or synthesized.
Native OpenWiki graph discovery indexes Markdown; retained PDF and other
binary assets remain evidence without extraction or transcription claims.

Paths containing the literal substring `..` are rejected by the pinned native
file backend, even for valid directory names such as `[[...slug]]`. The importer
retains the original evidence and mirror and adds an exact-byte `.txt` alias
under `runtime/wiki/native-files/`. The manifest's `native_read_path` and
navigation identify this compatible native read path. Aliases are hash-bound
and validated without creating duplicate Markdown graph nodes.

Validation checks evidence membership and bytes independently of the original
inputs. `--verify-originals` additionally checks that the mounted inputs still
have the recorded membership and hashes. The initial wiki mirror is checked
separately: later wiki edits do not change the retained source archive, but an
initial-copy check must report those edits rather than claiming byte parity.
An import proves document retention and native readability. It does not prove
model execution, semantic review, complete synthesis, live credentials, or
source synchronization.
