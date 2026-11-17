# Adapting delegation to the host

Check which tools, credentials, permissions, caching and scheduling the host actually provides. Keep the same work contract when the executor changes.

## Codex with collaboration tools

If the environment exposes tools such as `spawn_agent`, `send_message`, `followup_task` and `wait_agent`, use their available names and schemas for authorized delegation. A subtask belongs to the current run. Starting a separate chat or contacting people or unrelated tasks requires its own authorization.

- Give each worker a self-contained objective, units, sources, contract and limits. Reuse a worker session only if its context is compatible.
- Dispatch batches that fit the available slots. The parent maintains the ledger and works on independent tasks while waiting.
- For an independent review, send the sources and question without revealing the expected answer. The reviewer should reach its own conclusion.
- Collect terminal results, validate them and pass concrete artifacts to reducers. Use event-based waits or reasonable intervals. The parent delivers coverage and the conclusion.
- Agents may share context and a filesystem. Assign files to individual owners and reserve an integration stage for edits.

These tools may hide payloads, affinity keys and usage. Report prompt-cache control or token savings only with supporting measurements. Timestamps and stable prompts alone cannot establish a hit.

## Pi with the documentation proof of concept

If the session registers `analyze_product_docs`, read its active schema. The documented runner supports a documentation manifest, questions, map tasks and a reduction with citations. Use the parameters exposed by the installed version.

The proof of concept exposed `manifest`, `output_dir`, `backend`, `workers`, `question`, `cache_dir`, `cache_wait_ms`, `cache_warmup_delay_ms` and `prompt_cache`. The `demo` backend verifies deterministic orchestration. Semantic analysis requires a model-backed run.

The runner executes inside Pi and returns artifact paths. Read the report, coverage and metrics before drawing conclusions. Share the same `cache_dir` across output directories where results are reusable. Check that the extension is loaded before calling it.

A compatible checkout containing `src/cli.ts`, `package.json` and the expected manifest can access the same runner through Node. Inspect `node src/cli.ts --help` and use real paths. The proof-of-concept checkout supports the following example.

```sh
node src/cli.ts run examples/product.json --backend pi --workers 4 --cache-dir .cache/docbatch --cache-warmup-delay-ms 1000 --output runs/analysis
```

The runner lives in that separate checkout. This skill package provides the instructions. The runner requires Pi installed and authenticated through the user's usual mechanism.

## Pi with another delegation extension or without a runner

If a subagent extension is available, use its verified tools and preserve contracts, budget and coverage. Check the current configuration. Installing or reconfiguring an extension is a separate task from performing the analysis.

If only Pi subprocesses are available and the user authorized inference, a Node runner can execute bounded tasks in isolated processes using stdin and argv without a shell, timeouts, cancellation and parsing of terminal results. Verify the protocol for the installed version and reuse an existing runner when possible. Count every call and nested worker. If delegation is unavailable, process units sequentially with the same ledger and report that mode.

## Invoke the skill

In Codex, use the `$` skill picker to select `agent-utilities:delegate-map-reduce`. In Pi, use `/skill:delegate-map-reduce` after discovery with skill commands enabled. Load or reload the host's resources to make a new installation visible in an open session.
