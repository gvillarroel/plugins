# Code-Assistant Problem Types

Generate one purpose-built workflow for the requested recurring problem type. The generated
`solve.mjs` then receives a concrete repository, issue, pull request, diff, or task at runtime. Do not
generate one universal agent loop or embed the answer to one example.

Start with [context preparation](context-first.md). Reuse the current agent when it owns the task;
otherwise use one autonomous execution plus checks. Additional executions need a concrete reason.

## Issue triage

Runtime problem: repository identifier plus optional query, policy, or time window.

1. Collect repository instructions, issue fields, labels, milestones, ownership, and recent related
   issues with deterministic APIs or CLIs.
2. Normalize and batch issue records before an agent sees them. Exclude secrets and unrelated source.
3. Hand the packet to the current assistant or one autonomous producer to classify impact, urgency,
   component, duplication, missing information, and next action against repository policy.
4. Gate the result with a JSON schema, allowed labels, complete issue coverage, stable identifiers,
   and explicit evidence. Sample or independently review high-impact and low-confidence decisions.
5. Produce a report or proposed actions by default. Require explicit authorization and another gate
   before mutating remote labels, assignments, milestones, or issue state.

Triage normally has no repository mutations and does not need a full coding-agent worktree.

## Issue resolution

Runtime problem: issue URL, number, or local issue file for the target repository.

1. Collect the issue, repository rules, manifests, architecture, related code, tests, and prior local
   evidence deterministically. Rank bounded files against the runtime problem.
2. Classify the issue before routing. Select only relevant implementation, testing, security, or
   domain skills; do not inject the whole library.
3. Run the producer code assistant in an isolated Git worktree when it may change unknown paths.
   Otherwise declare and checkpoint every mutable path.
4. Require the smallest complete change, focused regression evidence, and repository-native checks.
5. Gate applicable formatting, types, focused tests, broader tests, mutation scope, and diff invariants.
   Add independent review only for important semantic risks those checks cannot establish.
6. On rejection, repair the same bounded problem with exact diagnostics and reused preparation.
   Promote only the passing patch; leave the original checkout unchanged after terminal failure.

The generated program performs runtime diagnosis and implementation. Authoring must not encode an
expected patch, hidden test, verifier output, or issue-specific helper.

## Code review

Runtime problem: pull request URL or number, commit range, patch path, or diff-producing command input.

1. Collect repository instructions, change metadata, base/head identities, diff, affected tests, and
   relevant owning code deterministically. Preserve stable file and line locations.
2. Keep one review context when it fits. Partition large changes by component or risk only when needed;
   give each reviewer its bounded partition plus applicable acceptance and repository rules.
3. Route specialized skills only when the diff justifies them—for example concurrency, security,
   database migration, accessibility, or API compatibility.
4. Ask a code assistant for actionable correctness findings, not summaries or style preferences.
5. Gate every finding for severity, path, line, concrete failure scenario, and remediation. Reject
   claims outside the supplied diff or without evidence.
6. Use a second independent reviewer for high-risk changes or uncertain findings, then deduplicate and
   sort deterministically. Reviewing is read-only unless the user explicitly requests fixes.

## Custom problem type

Derive the same shape from the requested outcome:

- concrete runtime identifier;
- deterministic evidence acquisition;
- bounded context partitions;
- producer and reviewer responsibilities;
- context-specific skills;
- executable acceptance gates;
- declared mutation and authorization boundary;
- bounded retry and recovery behavior.

Prefer the minimum stages and agents that materially improve acceptance confidence.
