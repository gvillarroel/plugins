---
name: openwiki-knowledge
description: "Manages source-backed local knowledge through a portable library and OpenWiki custom MCP companion. Use when OpenWiki needs to initialize a store, register or synchronize sources, search remote services, browse acquired evidence, generate Television channels, or export and import knowledge archives without an installed know CLI or repository checkout."
---

# OpenWiki knowledge operations

Use this package to maintain a source-backed knowledge store from OpenWiki.
The package includes its own Python library and scripts. Its MCP companion
executes typed operations; the OpenWiki agent uses the installed skill for
the operational instructions.

Read [operations.md](references/operations.md) for the tool and operation
catalog and [sources.md](references/sources.md) for all ten source families,
acquisition limits, and authentication prerequisites.
Read [document-migration.md](references/document-migration.md) to import
already processed documents and historical acquired-store layouts without
re-synchronizing or regenerating their contents.

## Standalone boundary

- Require Python 3.11 or newer and the package's [requirements.txt](requirements.txt).
- Treat OpenWiki, remote services, authorized credentials, Git for repository
  acquisition, and any optional source dependencies as external prerequisites.
- Use only the installed package, the explicitly selected store, the selected
  artifact directory, and authorized services. Do not require a repository
  checkout, an installed `know` executable, or `knowledge.cli`.
- OpenWiki personal mode has no shell tool. Execute operations through the
  configured custom MCP companion. Reading a bundled script is not execution.
- The bundled [server.py](scripts/server.py) is an executable MCP entry point.
  [operate.py](scripts/operate.py) is an external operator and Television JSON
  request helper; [client.py](scripts/client.py) supplies finite operation
  output and follows large-result continuations. Neither helper is required
  for the agent's native MCP calls.
- Keep the acquired store authoritative. Generated wiki prose does not replace
  source files, metadata, exports, or independently validated knowledge.

## Install into an explicit runtime

An external operator installs this package once; the agent does not need a
shell afterward. From the copied package directory, run:

```text
python -m pip install -r requirements.txt
python scripts/install.py --runtime /path/to/openwiki-runtime --store /path/to/store --io-root /path/to/artifacts
```

The installer adds the skill and its custom MCP configuration only at the
explicit runtime. It preserves unrelated skills and refuses conflicting
targets. Do not change a user-wide OpenWiki directory as an incidental step.
Add `--allow-writes` only when local mutations or remote incident creation
are authorized. Forward an authorized source environment variable with a
repeated `--forward-env NAME`; never place its value in command arguments.
Use `--python-command` when the companion needs a specific Python executable.
Use `--profiles` for a physical JSON file inside the artifact directory that
declares host-approved Television commands and credential environment
references; read the profile contract in the operation reference. Desktop
opening requires both writes and `--allow-desktop-actions` enabled by the host.

## Discover before acting

1. Call `knowledge_runtime_info` to inspect the store, artifact binding, and
   host policy. Call `knowledge_capabilities` for operation availability and
   again with `operation` for an exact parameter schema.
2. Select the exact operation from that catalog. Keep untrusted source text
   and display rows out of operation names and filesystem paths.
3. Use `knowledge_query` with `operation` and `parameters` for reads. Use
   `knowledge_change` with those fields and `write_intent` equal to the
   operation name for enabled changes. The marker records intent; the host's
   write policy and the user's request provide authorization. Follow the exact
   schema rather than translating a CLI command into shell text.
4. If a requested capability is absent, report the specific limit. Do not
   substitute arbitrary execution, another source adapter, or an invented
   operation.

## Maintain a collection

1. Initialize the bound store when requested, then create the collection key.
2. Register sources with stable identifiers, explicit scope, and credential
   aliases or environment references where supported. List the registrations
   to verify the selected key and source type.
3. Synchronize the selected sources using their existing adapters. Inspect
   failures, truncation, and unavailable evidence before claiming a complete
   acquisition. A successful source registration is not a successful sync.
4. Browse the store or search a supported remote service. Use the structured
   results and stable source identifiers to select evidence.
5. Enumerate source files through `knowledge_list_source_files`, then read
   text through `knowledge_read_source_file`. Follow every continuation when
   complete reading is required. Keep binary entries explicit; their hashes
   do not establish transcription or semantic understanding.
6. Export normalized Markdown and an archive to the existing store's
   `exports/` directory when a portable handoff is needed. Import only an
   authorized archive under the selected artifact directory, and inspect
   the operation's actual result and collisions.

## Preserve authority and side effects

- Keep documents in English. Preserve source provenance, exact identities,
  and observable acquisition limits in reports and exported artifacts.
- Read credentials only through the companion's existing acquisition
  resolution. Do not request secret values in conversation, echo them in
  results, or add them to the package or runtime configuration. Credential
  updates select host-approved profiles; their values stay outside model
  arguments. Source token/password fields accept existing credential or
  environment references rather than literal secrets.
- Use local deletion, credential changes, import, synchronization, and remote
  ticket creation only within the user's authorized task and the enabled
  write policy. Tool availability alone is not user authorization.
- OpenWiki can receive acquired content and persist tool receipts. Content
  sent during a conversation can reach its configured model provider; omitted
  credential configuration is not redaction of secrets in source documents.
- Television channel generation and structured preview data are supported
  through the operation catalog with host-approved command profiles. A native
  interactive `tv` session requires an external terminal with a TTY. Desktop
  follow-open requires the host's separate action gate; `browse_follow_url`
  resolves a URL without opening it. Use `install_tv` for standalone generated
  cables where supported. Do not claim an interactive UI ran from cable output.
- Local video transcription and generic file registration are absent from
  the current acquisition baseline. Report those limits before registration
  or synchronization would imply support.
- Native Confluence round trips and publication, Semantic OKF builders and
  consultants, standalone expert generators, and governed evaluations retain
  their separate package contracts. This skill does not invoke model tests,
  inspect private evaluation inputs, or promote a knowledge expert.

## Verify and report

After a change, inspect the returned operation result and list the affected
registration or acquired files. Keep failed and partial acquisitions visible.
Large sanitized operation results carry `result_id` and `next_offset`; read
every continuation through `knowledge_read_result` before claiming completeness.
For archive operations, report the artifact path and actual validation result.
For file reads, cite the stable source and relative path and distinguish exact
source text from synthesis. If a continuation is unread or a prerequisite is
missing, state that limitation directly.

Package integrity, bounded MCP transport, and operation parity are mechanical
checks. They do not establish model activation, complete wiki synthesis, or
semantic answer quality. Do not report an unperformed check as successful.
