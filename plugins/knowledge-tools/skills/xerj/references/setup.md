# Installation and node lifecycle

## Contents

- [Discover or install](#discover-or-install)
- [Start and wait](#start-and-wait)
- [Authentication and embeddings](#authentication-and-embeddings)
- [MCP integration](#mcp-integration)

## Discover or install

Run `xerj --version` and `xerj --help` first. On PowerShell use
`Get-Command xerj -ErrorAction SilentlyContinue`; on POSIX use `command -v xerj`.
Keep an explicit executable path if the desktop host does not inherit PATH.

Official installers:

```sh
curl -fsSL https://xerj.org/get -o get-xerj.sh
# Inspect the downloaded installer; choose a writable task-local destination.
XERJ_INSTALL_DIR="$PWD/tools/xerj" sh get-xerj.sh
```

```powershell
Invoke-WebRequest https://xerj.org/get.ps1 -OutFile get-xerj.ps1
# Inspect the installer before executing it; check supported install parameters.
Get-Content get-xerj.ps1
```

For a workspace-only Windows install, use the manual release route below.
Do not change machine-wide PATH or install a service to complete a local task.

Manual releases are at [GitHub Releases](https://github.com/xerj-org/xerj/releases).
Select a release and the matching `x86_64` or `aarch64` asset:
`pc-windows-msvc.zip`, `apple-darwin.tar.gz`, or
`unknown-linux-musl.tar.gz` (static Linux). A GNU Linux build also exists.
Download the matching `.sha256` alongside the archive. Compute the archive's
SHA-256 locally and require an exact checksum record naming that archive before
extracting or executing it. Do not verify a different file accidentally.

For example, after downloading `archive.zip` and `archive.zip.sha256` from the
same selected release, replace the filenames with their actual asset names:

```powershell
$XerjArchive = Resolve-Path ./archive.zip
$XerjAssetName = Split-Path -Leaf $XerjArchive
$XerjHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $XerjArchive).Hash.ToLowerInvariant()
$XerjExpected = [IO.File]::ReadAllText("$XerjArchive.sha256").Trim()
if ($XerjExpected -notin @("$XerjHash  $XerjAssetName", "$XerjHash *$XerjAssetName")) {
    throw 'XERJ checksum mismatch; archive was not extracted.'
}
Expand-Archive -LiteralPath $XerjArchive -DestinationPath ./tools/xerj
```

Require both downloads to succeed and a 64-character hexadecimal digest.
The published checksum detects corrupted bytes; it is not an independent
signature over the release. Run the extracted executable's `--version`.

## Start and wait

First query `GET /_cluster/health` on the intended endpoint. Reuse an appropriate
node rather than racing its ports. `--port 19320` moves the ES API to 19320,
native REST to 19321, and gRPC to 19322; all three must be available. Without
`--port`, the defaults are 9200, 8080, and 8081 respectively.

Keep `node-data`, journals, and server logs outside the folder being indexed.
An example layout is `work/source`, `work/node-data`, and `work/journal`.

```sh
xerj --insecure --bind 127.0.0.1 --port 19320 --data-dir ./node-data >node.log 2>&1 &
xerj_pid=$!
uv run --script <skill-dir>/scripts/xerj_api.py --url http://127.0.0.1:19320 wait --seconds 30
```

```powershell
$XerjExe = (Get-Command xerj).Source
$XerjProcess = Start-Process -FilePath $XerjExe `
    -ArgumentList @('--insecure','--bind','127.0.0.1','--port','19320','--data-dir','./node-data') `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput ./node.stdout.log -RedirectStandardError ./node.stderr.log
uv run --script <skill-dir>/scripts/xerj_api.py --url http://127.0.0.1:19320 wait --seconds 30
```

PowerShell's `Start-Process -ArgumentList` joins strings. If a path contains
spaces, quote that argument explicitly or use an available process tool with
an argument array. Keep startup logs local; they may contain Console setup
tokens. Do not reproduce those tokens in a final answer.

Stop a POSIX node with `kill -TERM "$xerj_pid"`, or the owned Windows process
with `Stop-Process -Id $XerjProcess.Id` once it is no longer needed. If the host
provides a managed process session, use that session's stop mechanism instead.
Do not stop an existing shared node. Restarting with the same data directory
preserves its indices; deleting storage is a separate operation.

## Authentication and embeddings

Without `--insecure`, authentication is normally enabled and the first start
writes `<data-dir>/admin.key`. Read it into the process environment rather than
printing it. Clients such as `autoindex` use their own `--url` and `XERJ_API_KEY`;
they do not read server connection settings from `xerj.toml`.

```powershell
$env:XERJ_API_KEY = [IO.File]::ReadAllText('./node-data/admin.key').Trim()
```

The HTTP header is `Authorization: ApiKey <token>`. Preserve TLS verification;
the helper's defaults use normal CA verification. Production exposure and
certificate management require the operator's configuration, not a blanket
`--insecure` workaround.

For neural embeddings, add `--embed-mode neural` at server start before indexing.
The initial model download is about 90 MB from Hugging Face; this is distinct
from sending document text to a proxy. An offline deployment can stage
`config.json`, `tokenizer.json`, and `model.safetensors` and set
`embedding.local_model_dir` in TOML. Check the selected release's config for
provider endpoints or WAL taps before describing a node's privacy behavior.

## MCP integration

Check `xerj mcp --help` on the installed binary. MCP is a stdio client of an
already-running node; it does not start the server. Prefer an absolute executable
path in the host's native configuration:

```json
{
  "mcpServers": {
    "xerj": {
      "command": "/absolute/path/to/xerj",
      "args": ["mcp", "--url", "http://127.0.0.1:9200"]
    }
  }
}
```

This illustrates the common `mcpServers` JSON shape; adapt it to the target
host's schema. For authenticated nodes, provide `XERJ_AUTH` containing the full
`ApiKey ...` header through the host's secret/environment mechanism. Discover
actual tools with `tools/list`; tool inventories can vary by release. If MCP
is unavailable, use the CLI and HTTP workflows. Folder discovery remains
CLI-only; there is no HTTP `/_autoindex` endpoint.

Sources: [install](https://xerj.org/docs/install),
[CLI](https://xerj.org/docs/cli), [config](https://xerj.org/docs/config),
[security](https://xerj.org/docs/security).
