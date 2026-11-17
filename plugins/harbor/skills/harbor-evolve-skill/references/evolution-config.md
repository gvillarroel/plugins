# Harbor Skill Evolution Config

## Contents

- [Configuration](#configuration)
- [Split meaning](#split-meaning)
- [Harbor task requirements](#harbor-task-requirements)
- [Candidate boundary](#candidate-boundary)
- [Trial identity and provenance](#trial-identity-and-provenance)
- [Independent validation and promotion gates](#independent-validation-and-promotion-gates)
- [Method provenance](#method-provenance)
- [Skill authoring gate](#skill-authoring-gate)

Read this reference before authoring or changing an evolution run.

## Configuration

Paths resolve from the YAML directory. A split entry may point to one Harbor
task directory or to a dataset directory whose direct children are tasks.

~~~yaml
schemaVersion: 2

evolution:
  id: example-skill-harbor-evolution
  baselineSkill: ../../skills/example-skill
  outputDir: ../../.tmp/harbor-evolution/example-run
  objective: >-
    Improve the skill's reliability across the declared Harbor tasks while
    preserving concise, transferable instructions.
  background: >-
    The skill guides a coding agent. Do not add task answers or holdout facts.

harbor:
  agent:
    name: codex
    model: openai/gpt-5.1-codex-mini
    kwargs: {}
  environment: docker
  concurrency: 4
  rewardKey: reward
  validationAttempts: 2
  holdoutAttempts: 2
  requiredEnv:
    - OPENAI_API_KEY

gepa:
  reflectionModel: openai/gpt-5.1
  reflectionMinibatchSize: 3
  maxMetricCalls: 100
  maxCandidateProposals: 12
  seed: 0

splits:
  evolution:
    - tasks/evolution
  validation:
    - tasks/validation
  holdout:
    - tasks/holdout

validationGate:
  minimumMeanGain: 0
  allowTaskRegressions: false
  requireNoErrors: true

promotion:
  minimumMeanGain: 0
  allowTaskRegressions: false
  requireNoErrors: true
~~~

## Split meaning

- evolution: the only optimizer-visible dataset. GEPA samples it for
  feedback-guided proposals and evaluates candidates on it for selection.
- validation: invisible to GEPA; evaluated only after selection against both
  the unchanged baseline and the digest-frozen candidate.
- holdout: invisible to GEPA and validation; opened only when the frozen
  candidate passes independent validation.

The validator rejects repeated task names and identical task content across
splits. This is a byte-level control, so also review for semantic duplicates.
Keep enough task-family diversity in the evolution dataset to avoid choosing a
candidate from one narrow behavior, and keep validation representative enough
to detect evolution-dataset overfitting.

Schema 2 is mandatory. Schema 1 used `validation` as GEPA's selection set and
is rejected so an older optimizer-visible boundary cannot be mistaken for
independent validation.

## Harbor task requirements

Every task must satisfy Harbor's current task model:

- task.toml uses a supported schema and org/name task identity
- instruction.md contains only agent-visible intent
- environment defines a reproducible sandbox
- tests write a numeric reward
- verifier output provides actionable diagnostics without printing canonical
  answers that can be copied into the skill

Multi-reward tasks may choose another rewardKey, but the selected value must be
finite numeric for every completed evolution, validation, and holdout trial.
Booleans, numeric strings, nulls, NaN, and infinity are not valid rewards. The
runner checks preserved `result.json` and available raw `reward.json` files so
Harbor's model coercion cannot silently turn a malformed JSON reward into
fitness. Harbor remains responsible for multi-step reward aggregation.

A terminal `finished_at` timestamp is required. Missing primary rewards without
an attributable native `AgentTimeoutError`, malformed rewards, and classified
provider, infrastructure, environment, authentication, or evaluator failures
are non-evaluable. The runner checks diagnostic metadata in root and step
verifier directories before reward availability; a provider failure that emits
no reward retains its external cause. Explicit success/completion diagnostic
statuses do not establish a failure.

Rejected candidate text and genuine agent execution failures remain visible as
zero-quality outcomes, including `AgentTimeoutError` without a verifier reward.
An accompanying external diagnostic overrides that treatment. A non-evaluable
development trial stops GEPA without returning fitness or reflection feedback.
Its original native artifacts remain unchanged, and `evaluation.json` records
`reward: null`, `evaluable: false`, and the failure reason. A finite emitted
score may remain in `reportedReward` for audit, but is ineligible for selection.

## Candidate boundary

The seed is the complete baseline SKILL.md. Before GEPA starts, the runner
copies the source skill once to
`<output>/baseline-snapshot/skills/<frontmatter.name>` and verifies the copy
with Harbor's skill digest. The original source remains read-only, and every
candidate is derived from the frozen snapshot rather than from a potentially
changing workspace directory.

The frontmatter name is the installed identity, not a display label. It must be
an exact portable basename containing 1-64 lowercase letters, digits, or
interior hyphens and must not be a Windows-reserved name such as `con`, `nul`,
`com1`, or `lpt1`. The source directory may have a different physical basename;
the runner never adopts that alias or sanitizes an unsafe name.

Other bundle files are copied unchanged into every candidate trial at:

~~~text
<evaluation>/skills/<frontmatter.name>/
~~~

GEPA may change any text inside SKILL.md but the runner rejects:

- invalid YAML frontmatter
- missing name or description
- a changed skill name
- more than 500 lines

This boundary keeps each trial attributable. If evidence points to a broken
script or reference, stop this run, repair and validate the baseline resource,
then freeze a new benchmarked baseline.

## Trial identity and provenance

After `TrialQueue` completes, the runner requires exactly one terminal trial
directory and reads its `config.json`, `result.json`, and `lock.json`. All three
configured skill sources plus the locked source must resolve to the canonical
staged path. The staged basename and locked name must equal the frontmatter
name, and the locked digest must equal Harbor's digest of the staged bundle
both before and after execution.

Missing artifacts, aliases, source mismatches, digest mismatches, or multiple
terminal trial directories fail closed before the reward reaches GEPA. There is
no legacy/exploratory identity mode because this workflow creates new live
trials. Each `evaluation.json` preserves the candidate text digest and complete
identity evidence for audit.

## Independent validation and promotion gates

GEPA receives the evolution examples as both its feedback dataset and its
internal selection set. After GEPA returns one winner, the runner validates its
text, copies the complete candidate bundle, and freezes its digest before
opening validation. It runs the unchanged baseline and that one candidate for
`validationAttempts` on every validation task. The validation gate uses its own
minimum gain, task-regression, error, and provenance rules.
If the selected bundle digest equals the frozen baseline digest, the runner
keeps the baseline without running validation or holdout. This is a no-change
outcome, not an improvement claim; changed candidates still use the declared
minimum gain, including zero when explicitly configured.

Validation evidence cannot trigger a mutation, candidate reranking, or
reselection in the same run. On failure the runner writes the candidate and
validation evidence, leaves holdout unopened, and returns
`validation-rejected`. Reusing that validation feedback for a later evolution
consumes its independence; a later unbiased gate requires a fresh validation
dataset.

Only after validation passes does Harbor run the unchanged baseline and frozen
candidate for the same number of attempts on every holdout task.

Promotion requires:

- candidate mean minus baseline mean is at least minimumMeanGain
- no task-level mean regression unless allowTaskRegressions is true
- no candidate execution errors when requireNoErrors is true
- verified canonical name/source/digest provenance for every baseline and
  candidate holdout trial
- non-empty, matched per-task attempt counts with evaluable rewards throughout
- a changed candidate bundle

Non-evaluable gate trials block acceptance even when `requireNoErrors` is false
or task regressions are allowed. An affected side's mean and every dependent
gain are null, shown as `unavailable` in the report; no failing attempt is
discarded or replaced with zero. Validation failure or non-evaluability keeps
holdout sealed. The same rules protect baseline failures from creating an
artificial apparent gain.

Only development trials collect verifier feedback, agent output, and
trajectories for reflection. Private gate trials retain those detailed files in
their native locations; `evaluation.json` and `run.json` contain only scores,
identity evidence, and outcome metadata. Private exception messages and
unbounded diagnostic detail are not copied into the gate report.

The gate does not automatically install or replace the skill. Review the
candidate, preserved trials, and normal skill tests before copying it.

## Method provenance

This workflow adapts the official
[Harbor + GEPA cookbook](https://github.com/harbor-framework/harbor-cookbook/tree/main/harbor_cookbook/gepa):
Harbor supplies isolated trials, rewards, and rich side information; GEPA uses
reflective candidate mutation and Pareto-aware selection. The local adaptation
evolves a complete SKILL.md rather than a prompt template, adds an independent
baseline-versus-frozen-candidate validation gate, and defers the final holdout
until that gate passes.

## Skill authoring gate

The final selected bundle is published at `candidate-skill/skills/<name>/`,
using the same canonical identity as baseline snapshots and per-trial staging.

Before evaluating or sealing a new candidate, the runner checks its complete
bundle with the bundled [skill authoring validator](../scripts/skill_authoring.py).
The gate checks YAML metadata, entrypoint size, direct reference discovery,
resource links, and Python syntax without executing candidate code. A failed
check stops staging or publication; it never changes frozen source bytes.
Structural acceptance does not establish task performance, semantic independence,
or model transfer. Keep those claims in native Harbor evaluations.
