# Caching, affinity and waiting

Choose controls the host supports and whose cost is justified by expected reuse. Complete local results and provider-cached prefixes have separate identities, metrics and lifetimes.

## Reuse completed results

Check the result cache before acquiring a worker or coordinating a shared prefix. The cache key describes the semantic task. Include the stage, question or applicable objective, source contents and versions, instructions, output contract, resolved backend and model, and parameters that affect the response. Canonicalize objects while preserving meaningful array order.

An output directory, timestamp, PID or question position is a poor cache key. Changing an objective should invalidate the stages it affects. Administrative relabeling can reuse an otherwise identical task. Reuse results across configurations only when the relevant model and settings are known.

Validate each hit against the current contract and sources. Treat parseable JSON containing nonexistent quotes as a miss. Keep the semantic result separate from its administrative metadata. The coordinator can associate a valid result with the current `task_id` while preserving its original claims, evidence and provenance. Store reusable responses separately from run-specific artifacts. Content-based validity is independent of the provider's prefix TTL.

For identical in-flight requests, let one owner compute while followers wait. A multi-process runner needs exclusive locks with owner identification, complete atomic publication, and a cache recheck before and after acquiring the lock. A wait timeout alone is insufficient grounds to duplicate inference or remove another owner's lock. Cancelling a follower leaves the owner running. With subagents alone, the parent can avoid duplicate dispatch within its own run. Inter-process locking requires separate coordination.

## Reuse provider prefixes

Place instructions, contracts and shared context first. Put questions, feedback and other variable data later. Inspect the actual request. A random working directory, an injected date or a new session key can break affinity even when templates look identical.

Use affinity keys or cache breakpoints on the reusable block when the active transport supports them. Verify the SDK, gateway and API that will send the request. A model name alone cannot establish which fields the gateway accepts.

Group work by provider, model, system instructions and actual shared prefix.

1. The first useful task leads the group. Avoid empty requests just to warm the cache.
2. Followers wait for a valid result and, where appropriate, a configurable propagation delay. Give them a common deadline.
3. Release waiters on success, failure or cancellation. If the leader fails, another worker may take over within budget.
4. Wait outside inference slots for capacity or prefix readiness so other groups can make progress.
5. When rate-limiting, check and record the actual start immediately before calling the backend. A reservation made before a long queue can expire and cause a burst. Return the worker before waiting again.

Affinity and scheduling can be used independently. A reducer can receive a stable key for its common instructions without delaying all reducers for a short prefix. Keep prompts relevant when considering a provider's cache threshold.

The proof of concept tried a default propagation delay of 250 ms, a 1,000 ms delay in one run, an estimated 240-second warm window and 12 starts per group every 60 seconds. These are experimental settings. A scheduler's warm estimate cannot establish whether a provider cached an entry or control other processes without distributed coordination.

Check the provider's current terms and the installed SDK and transport before applying TTLs, token minimums or provider-specific controls. With opaque subagents, report only the local reuse you can verify. [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) · [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

## Measure reuse

Record logical requests, reused responses, new calls, retries, waits and coverage per run. Where the runner exposes them, distinguish disk hits, shared in-flight results and inter-process waits.

Attribute usage to the call that emitted it. A shared backend needs per-request callbacks or correlation. Reading global history can assign another batch's tokens to a follower that made no calls.

In the tested Pi normalization, `input` counts ordinary input tokens. The total is `input + cacheRead + cacheWrite`, and the cache read rate is `cacheRead / total_input`. Other SDKs may already include cached tokens in `input`. Check the definition before adding counts. Use complete records, report how many calls they cover and treat missing usage as unknown. A local replay without inference does not remeasure provider caching.

One local replay reused all 33 of 33 results and made zero calls. A previous live batch read 3,584 cached tokens out of 84,365 total input tokens. Other probes reported zero. Those observations describe the tested environment. Attributing an improvement to waiting would require a comparable controlled experiment.
