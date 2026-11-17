#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["harbor==0.18.0", "gepa==0.1.2"]
# ///
"""Evolve one SKILL.md with Harbor, validate a frozen winner, then gate holdout."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import math
import os
import re
import shutil
import sys
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from gepa.optimize_anything import (
    EngineConfig,
    GEPAConfig,
    ReflectionConfig,
    optimize_anything,
)
from harbor import TrialQueue
from harbor.models.task.task import Task
from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    TrialConfig,
    VerifierConfig,
)
from harbor.skills import compute_skill_digest

# Resolve only this copied bundle, including when loaded by an offline harness.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_authoring import validate_bundle, validate_skill_text


PORTABLE_SKILL_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
RESERVED_SKILL_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


REFLECTION_PROMPT = """I am evolving a complete SKILL.md file for an agent.
The current SKILL.md is:
<curr_param>

The following Harbor trial evidence contains rewards, verifier diagnostics,
agent trajectories, and execution errors from development tasks:
<side_info>

Propose a drop-in replacement for the complete SKILL.md. Preserve its YAML
frontmatter name exactly. Keep a non-empty description within 1024 characters,
a body under 500 lines, and working direct links to the existing references.
Use portable resource paths. Generalize from recurring evidence, preserve behavior
that passed, avoid task-specific answers, and do not refer to hidden validation
or holdout cases. Return only the complete SKILL.md inside one fenced block.
"""


@dataclass(frozen=True)
class HarborTaskExample:
    task_id: str
    task_name: str
    path: Path
    digest: str


@dataclass
class Runtime:
    source_skill: Path
    source_digest: str
    baseline_skill: Path
    baseline_digest: str
    skill_name: str
    output_directory: Path
    agent_name: str
    model_name: str
    environment_type: str
    agent_kwargs: dict[str, Any]
    reward_key: str
    concurrency: int
    queue: TrialQueue
    counter: Any


_RUNTIME: Runtime | None = None


def require_mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a mapping.")
    return value


def require_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string.")
    return value.strip()


def resolve_path(base: Path, value: Any, location: str) -> Path:
    raw = Path(require_string(value, location)).expanduser()
    return raw.resolve() if raw.is_absolute() else (base / raw).resolve()


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Evolution config does not exist: {path}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in evolution config {path}: {error}") from error
    return require_mapping(value, "config")


def directory_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative = path.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def text_digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_portable_skill_name(value: Any, location: str) -> str:
    name = require_string(value, location)
    if (
        value != name
        or not PORTABLE_SKILL_NAME.fullmatch(name)
        or name in RESERVED_SKILL_NAMES
    ):
        raise ValueError(
            f"{location} must be an exact portable skill basename "
            "(1-64 lowercase letters, digits, or interior hyphens). "
            "No fallback name is used because that would change the identity "
            f"installed by Harbor: {value!r}."
        )
    return name


def installed_skill_path(container: Path, logical_name: str) -> Path:
    """Return an isolated path whose physical basename is the skill identity."""

    require_portable_skill_name(logical_name, "logical skill name")
    skills_directory = container / "skills"
    destination = skills_directory / logical_name
    if destination.parent != skills_directory or destination.name != logical_name:
        raise ValueError(
            f"Logical skill name escapes its staging directory: {logical_name!r}"
        )
    return destination


def parse_skill_frontmatter(text: str) -> dict[str, Any]:
    return validate_skill_text(text)


def validate_candidate(text: str, expected_name: str) -> None:
    frontmatter = parse_skill_frontmatter(text)
    if frontmatter["name"] != expected_name:
        raise ValueError(
            f"Candidate changed skill name from '{expected_name}' to '{frontmatter['name']}'."
        )


def discover_task_directories(path: Path) -> list[Path]:
    if (path / "task.toml").is_file():
        return [path]
    if not path.is_dir():
        raise ValueError(f"Harbor task or dataset path does not exist: {path}")
    tasks = sorted(
        child.resolve()
        for child in path.iterdir()
        if child.is_dir() and (child / "task.toml").is_file()
    )
    if not tasks:
        raise ValueError(f"No Harbor tasks found directly under dataset path: {path}")
    return tasks


def load_split(
    config_directory: Path, values: Any, location: str
) -> list[HarborTaskExample]:
    if not isinstance(values, list) or not values:
        raise ValueError(
            f"{location} must be a non-empty list of task or dataset paths."
        )
    directories: list[Path] = []
    for index, value in enumerate(values):
        path = resolve_path(config_directory, value, f"{location}[{index}]")
        directories.extend(discover_task_directories(path))
    unique_directories = list(dict.fromkeys(directories))
    examples = []
    for directory in unique_directories:
        if not Task.is_valid_dir(directory):
            raise ValueError(f"Invalid Harbor task directory: {directory}")
        task = Task(directory)
        examples.append(
            HarborTaskExample(
                task_id=directory.name,
                task_name=task.name,
                path=directory,
                digest=directory_digest(directory),
            )
        )
    names = [example.task_name for example in examples]
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate Harbor task names inside {location}: {names}")
    return examples


def validate_disjoint_splits(splits: dict[str, list[HarborTaskExample]]) -> None:
    seen_names: dict[str, str] = {}
    seen_digests: dict[str, str] = {}
    for split_name, examples in splits.items():
        for example in examples:
            prior_name = seen_names.get(example.task_name)
            if prior_name:
                raise ValueError(
                    f"Task '{example.task_name}' occurs in both {prior_name} and {split_name}."
                )
            prior_digest = seen_digests.get(example.digest)
            if prior_digest:
                raise ValueError(
                    f"Identical task content occurs in both {prior_digest} and {split_name}: "
                    f"{example.path}"
                )
            seen_names[example.task_name] = split_name
            seen_digests[example.digest] = split_name


def normalize_config(
    config_path: Path, output_override: Path | None = None
) -> dict[str, Any]:
    raw = load_yaml(config_path)
    if raw.get("schemaVersion") != 2:
        raise ValueError(
            "schemaVersion must be 2 so independent validation cannot be "
            "silently used by the optimizer."
        )
    directory = config_path.resolve().parent
    evolution = require_mapping(raw.get("evolution"), "evolution")
    harbor = require_mapping(raw.get("harbor"), "harbor")
    agent = require_mapping(harbor.get("agent"), "harbor.agent")
    splits_raw = require_mapping(raw.get("splits"), "splits")
    gepa = require_mapping(raw.get("gepa", {}), "gepa")
    validation_gate = require_mapping(
        raw.get("validationGate", {}), "validationGate"
    )
    promotion = require_mapping(raw.get("promotion", {}), "promotion")

    baseline_skill = resolve_path(
        directory,
        evolution.get("baselineSkill"),
        "evolution.baselineSkill",
    )
    skill_path = baseline_skill / "SKILL.md"
    if not skill_path.is_file():
        raise ValueError(f"Baseline skill has no SKILL.md: {baseline_skill}")
    validate_bundle(baseline_skill)
    baseline_text = skill_path.read_text(encoding="utf-8")
    frontmatter = parse_skill_frontmatter(baseline_text)

    splits = {
        name: load_split(directory, splits_raw.get(name), f"splits.{name}")
        for name in ("evolution", "validation", "holdout")
    }
    validate_disjoint_splits(splits)

    output_directory = (
        output_override.resolve()
        if output_override
        else resolve_path(directory, evolution.get("outputDir"), "evolution.outputDir")
    )
    required_env = harbor.get("requiredEnv", [])
    if not isinstance(required_env, list) or any(
        not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
        for name in required_env
    ):
        raise ValueError(
            "harbor.requiredEnv must contain portable environment variable names."
        )
    agent_kwargs = agent.get("kwargs", {})
    require_mapping(agent_kwargs, "harbor.agent.kwargs")

    normalized = {
        "id": require_string(evolution.get("id"), "evolution.id"),
        "objective": require_string(evolution.get("objective"), "evolution.objective"),
        "background": str(evolution.get("background", "")).strip(),
        "baselineSkill": baseline_skill,
        "baselineText": baseline_text,
        "skillName": frontmatter["name"],
        "outputDirectory": output_directory,
        "splits": splits,
        "harbor": {
            "agentName": require_string(agent.get("name"), "harbor.agent.name"),
            "modelName": require_string(agent.get("model"), "harbor.agent.model"),
            "agentKwargs": agent_kwargs,
            "environment": require_string(
                harbor.get("environment", "docker"), "harbor.environment"
            ),
            "concurrency": int(harbor.get("concurrency", 4)),
            "rewardKey": require_string(
                harbor.get("rewardKey", "reward"), "harbor.rewardKey"
            ),
            "requiredEnv": required_env,
            "validationAttempts": int(harbor.get("validationAttempts", 2)),
            "holdoutAttempts": int(harbor.get("holdoutAttempts", 2)),
        },
        "gepa": {
            "maxMetricCalls": int(gepa.get("maxMetricCalls", 100)),
            "maxCandidateProposals": (
                int(gepa["maxCandidateProposals"])
                if gepa.get("maxCandidateProposals") is not None
                else None
            ),
            "reflectionMinibatchSize": int(gepa.get("reflectionMinibatchSize", 3)),
            "reflectionModel": require_string(
                gepa.get("reflectionModel", "openai/gpt-5.1"),
                "gepa.reflectionModel",
            ),
            "seed": int(gepa.get("seed", 0)),
        },
        "validationGate": {
            "minimumMeanGain": float(validation_gate.get("minimumMeanGain", 0)),
            "allowTaskRegressions": bool(
                validation_gate.get("allowTaskRegressions", False)
            ),
            "requireNoErrors": bool(validation_gate.get("requireNoErrors", True)),
        },
        "promotion": {
            "minimumMeanGain": float(promotion.get("minimumMeanGain", 0)),
            "allowTaskRegressions": bool(promotion.get("allowTaskRegressions", False)),
            "requireNoErrors": bool(promotion.get("requireNoErrors", True)),
        },
    }
    if normalized["harbor"]["concurrency"] < 1:
        raise ValueError("harbor.concurrency must be at least 1.")
    if normalized["harbor"]["validationAttempts"] < 1:
        raise ValueError("harbor.validationAttempts must be at least 1.")
    if normalized["harbor"]["holdoutAttempts"] < 1:
        raise ValueError("harbor.holdoutAttempts must be at least 1.")
    if normalized["gepa"]["maxMetricCalls"] < 1:
        raise ValueError("gepa.maxMetricCalls must be at least 1.")
    for location, rules in (
        ("validationGate", normalized["validationGate"]),
        ("promotion", normalized["promotion"]),
    ):
        if not math.isfinite(rules["minimumMeanGain"]):
            raise ValueError(f"{location}.minimumMeanGain must be finite.")
    if output_directory == baseline_skill or output_directory.is_relative_to(
        baseline_skill
    ):
        raise ValueError("evolution.outputDir must not be inside the baseline skill.")
    for examples in splits.values():
        for example in examples:
            if output_directory == example.path or output_directory.is_relative_to(
                example.path
            ):
                raise ValueError(
                    "evolution.outputDir must not be inside a Harbor task input."
                )
    return normalized


def public_plan(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 2,
        "evolutionId": config["id"],
        "baselineSkill": str(config["baselineSkill"]),
        "baselineDigest": compute_skill_digest(config["baselineSkill"]),
        "baselineSourceBasename": config["baselineSkill"].name,
        "skillName": config["skillName"],
        "outputDirectory": str(config["outputDirectory"]),
        "harborVersion": version("harbor"),
        "gepaVersion": version("gepa"),
        "agent": config["harbor"]["agentName"],
        "model": config["harbor"]["modelName"],
        "environment": config["harbor"]["environment"],
        "rewardKey": config["harbor"]["rewardKey"],
        "requiredEnv": config["harbor"]["requiredEnv"],
        "missingRequiredEnv": [
            name for name in config["harbor"]["requiredEnv"] if not os.environ.get(name)
        ],
        "splits": {
            name: [
                {
                    "taskName": example.task_name,
                    "path": str(example.path),
                    "digest": example.digest,
                }
                for example in examples
            ]
            for name, examples in config["splits"].items()
        },
        "evaluationBoundary": {
            "evolutionDatasetSplit": "evolution",
            "validationDatasetSplit": "validation",
            "validationOptimizerVisible": False,
            "candidateFreezeBeforeValidation": True,
            "holdoutRequiresValidationPass": True,
        },
        "budget": {
            "maxMetricCalls": config["gepa"]["maxMetricCalls"],
            "maxCandidateProposals": config["gepa"]["maxCandidateProposals"],
            "validationAttemptsPerCandidatePerTask": config["harbor"][
                "validationAttempts"
            ],
            "holdoutAttemptsPerCandidatePerTask": config["harbor"]["holdoutAttempts"],
        },
    }


def doctor(config: dict[str, Any]) -> dict[str, Any]:
    plan = public_plan(config)
    missing = plan["missingRequiredEnv"]
    if missing:
        raise ValueError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    checks: dict[str, Any] = {"credentials": "declared variables present"}
    if config["harbor"]["environment"] == "docker":
        checks["docker"] = run_check(
            ["docker", "info", "--format", "server={{.ServerVersion}}"]
        )
        checks["dockerCompose"] = run_check(["docker", "compose", "version", "--short"])
    else:
        checks["docker"] = "not required for selected environment"
        checks["dockerCompose"] = "not required for selected environment"
    plan["checks"] = checks
    return plan


def run_check(command: list[str]) -> str:
    if shutil.which(command[0]) is None:
        raise ValueError(f"Required executable is not on PATH: {command[0]}")
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=20, check=False
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ValueError(f"Preflight failed for {' '.join(command)}: {detail}")
    return completed.stdout.strip() or "ready"


def preserve_skill_copy(source: Path, destination: Path, label: str) -> dict[str, Any]:
    """Copy a skill once and prove that the source and copy stayed identical."""

    validate_bundle(source)
    source_digest = compute_skill_digest(source)
    if destination.exists():
        raise RuntimeError(f"{label} destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    validate_bundle(destination, require_directory_name=True)
    source_digest_after_copy = compute_skill_digest(source)
    copied_digest = compute_skill_digest(destination)
    if source_digest_after_copy != source_digest:
        raise RuntimeError(f"{label} source changed while it was being copied: {source}")
    if copied_digest != source_digest:
        raise RuntimeError(
            f"{label} digest changed while staging {source} at {destination}: "
            f"{source_digest} != {copied_digest}"
        )
    return {
        "logicalName": parse_skill_frontmatter(
            (destination / "SKILL.md").read_text(encoding="utf-8")
        )["name"],
        "sourceSkill": str(source),
        "sourceBasename": source.name,
        "sourceDigest": source_digest,
        "sourceDigestAfterCopy": source_digest_after_copy,
        "copiedSkill": str(destination),
        "copiedBasename": destination.name,
        "copiedDigest": copied_digest,
        "sourceUnchanged": True,
    }


def verify_frozen_baseline(runtime: Runtime, context: str) -> str:
    observed = compute_skill_digest(runtime.baseline_skill)
    if observed != runtime.baseline_digest:
        raise RuntimeError(
            f"Frozen baseline digest changed {context}: {runtime.baseline_skill}: "
            f"{runtime.baseline_digest} != {observed}"
        )
    return observed


def create_candidate_bundle(
    candidate: str, destination: Path, runtime: Runtime
) -> dict[str, Any]:
    """Create one attributable candidate without writing to the source skill."""

    validate_candidate(candidate, runtime.skill_name)
    source_digest_before = verify_frozen_baseline(runtime, "before candidate staging")
    if destination.exists():
        raise RuntimeError(f"Candidate destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(runtime.baseline_skill, destination)
    skill_path = destination / "SKILL.md"
    if skill_path.read_text(encoding="utf-8") != candidate:
        skill_path.write_text(candidate, encoding="utf-8")
    validate_bundle(destination, runtime.skill_name, require_directory_name=True)
    source_digest_after = verify_frozen_baseline(runtime, "after candidate staging")
    staged_text = (destination / "SKILL.md").read_text(encoding="utf-8")
    if staged_text != candidate:
        raise RuntimeError(f"Candidate SKILL.md changed while staging: {destination}")
    staged_digest = compute_skill_digest(destination)
    return {
        "logicalName": runtime.skill_name,
        "sourceSkill": str(runtime.baseline_skill),
        "sourceBasename": runtime.baseline_skill.name,
        "sourceDigest": source_digest_before,
        "sourceDigestAfterStaging": source_digest_after,
        "stagedSkill": str(destination),
        "stagedBasename": destination.name,
        "stagedDigest": staged_digest,
        "candidateSkillMdDigest": text_digest(candidate),
        "canonicalStaging": (
            destination.name == runtime.skill_name
            and destination.parent.name == "skills"
        ),
        "sourceUnchanged": True,
    }


def stage_candidate_bundle(
    candidate: str, evaluation_directory: Path, runtime: Runtime
) -> tuple[Path, dict[str, Any]]:
    destination = installed_skill_path(evaluation_directory, runtime.skill_name)
    provenance = create_candidate_bundle(candidate, destination, runtime)
    if not provenance["canonicalStaging"]:
        raise RuntimeError(
            f"Candidate was not staged under its exact logical name: {destination}"
        )
    return destination, provenance


def read_json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} is invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must contain an object: {path}")
    return value


def normalized_skill_source(value: str) -> str:
    normalized = value.strip().replace("\\", "/").rstrip("/")
    wsl_match = re.fullmatch(r"/mnt/([A-Za-z])/(.*)", normalized)
    if wsl_match:
        normalized = f"{wsl_match.group(1)}:/{wsl_match.group(2)}"
    if re.match(r"^[A-Za-z]:/", normalized):
        normalized = normalized.casefold()
    return normalized


def configured_skill_source(payload: dict[str, Any], label: str) -> str:
    agent = require_mapping(payload.get("agent"), f"{label}.agent")
    skills = agent.get("skills")
    if (
        not isinstance(skills, list)
        or len(skills) != 1
        or not isinstance(skills[0], str)
        or not skills[0].strip()
    ):
        raise RuntimeError(f"{label}.agent.skills must contain exactly one path.")
    return skills[0]


def verify_trial_skill_provenance(
    trials_directory: Path,
    staged_skill: Path,
    staged_provenance: dict[str, Any],
) -> dict[str, Any]:
    """Bind a completed Harbor trial to the exact staged name, source, and digest."""

    trial_directories = sorted(
        path for path in trials_directory.iterdir() if path.is_dir()
    )
    if len(trial_directories) != 1:
        raise RuntimeError(
            "A candidate evaluation must produce exactly one Harbor trial directory; "
            f"found {len(trial_directories)} under {trials_directory}."
        )
    trial = trial_directories[0]
    config_payload = read_json_mapping(trial / "config.json", "Trial config")
    lock_payload = read_json_mapping(trial / "lock.json", "Trial lock")
    result_payload = read_json_mapping(trial / "result.json", "Trial result")
    result_config = require_mapping(result_payload.get("config"), "Trial result.config")
    configured_sources = [
        configured_skill_source(config_payload, "Trial config"),
        configured_skill_source(lock_payload, "Trial lock"),
        configured_skill_source(result_config, "Trial result.config"),
    ]
    locked_skills = lock_payload.get("skills")
    if not isinstance(locked_skills, list) or len(locked_skills) != 1:
        raise RuntimeError("Trial lock.skills must contain exactly one skill record.")
    locked_skill = require_mapping(locked_skills[0], "Trial lock.skills[0]")
    locked_name = require_string(locked_skill.get("name"), "Trial lock.skills[0].name")
    locked_source = require_string(
        locked_skill.get("source"), "Trial lock.skills[0].source"
    )
    locked_digest = require_string(
        locked_skill.get("digest"), "Trial lock.skills[0].digest"
    )
    logical_name = staged_provenance["logicalName"]
    expected_source = normalized_skill_source(str(staged_skill.resolve()))
    observed_sources = [*configured_sources, locked_source]
    source_matches = all(
        normalized_skill_source(source) == expected_source
        for source in observed_sources
    )
    name_matches = (
        locked_name == logical_name
        and staged_skill.name == logical_name
        and all(
            normalized_skill_source(source).rsplit("/", 1)[-1] == logical_name
            for source in observed_sources
        )
    )
    observed_staged_digest = compute_skill_digest(staged_skill)
    digest_matches = (
        locked_digest == staged_provenance["stagedDigest"]
        and observed_staged_digest == staged_provenance["stagedDigest"]
    )
    if not name_matches:
        raise RuntimeError(
            "Harbor trial locked or configured the candidate under a different "
            f"skill name: expected {logical_name!r}, locked {locked_name!r}."
        )
    if not source_matches:
        raise RuntimeError(
            "Harbor trial skill source does not match the canonical staged path: "
            f"expected {staged_skill}, observed {observed_sources}."
        )
    if not digest_matches:
        raise RuntimeError(
            "Harbor trial skill digest does not match the staged candidate: "
            f"expected {staged_provenance['stagedDigest']}, locked {locked_digest}, "
            f"observed {observed_staged_digest}."
        )
    return {
        **staged_provenance,
        "status": "verified",
        "verified": True,
        "trialDirectory": str(trial),
        "configuredSources": configured_sources,
        "lockedName": locked_name,
        "lockedSource": locked_source,
        "lockedDigest": locked_digest,
        "stagedDigestAfterTrial": observed_staged_digest,
        "nameMatches": True,
        "sourceMatches": True,
        "digestMatches": True,
        "contentStableAfterTrial": True,
    }


def read_first(paths: list[Path], limit: int = 6000) -> str:
    for path in paths:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            return (
                text
                if len(text) <= limit
                else text[:limit] + f"\n... truncated ({len(text)} chars)"
            )
    return ""


def collect_trial_evidence(trials_directory: Path, agent_name: str) -> dict[str, str]:
    if not trials_directory.is_dir():
        return {"agentTrajectory": "", "agentOutput": "", "verifierOutput": ""}
    trial_directories = sorted(
        path for path in trials_directory.iterdir() if path.is_dir()
    )
    if not trial_directories:
        return {"agentTrajectory": "", "agentOutput": "", "verifierOutput": ""}
    trial = trial_directories[0]
    return {
        "agentTrajectory": read_first(
            [
                trial / "agent" / "trajectory.json",
                trial / "agent" / agent_name / "trajectory.json",
            ]
        ),
        "agentOutput": read_first(
            [
                trial / "agent" / f"{agent_name}.txt",
                trial / "agent" / "output.txt",
            ]
        ),
        "verifierOutput": read_first(
            [
                trial / "verifier" / "test-output.txt",
                trial / "verifier" / "test-stdout.txt",
                trial / "verifier" / "test-stderr.txt",
            ]
        ),
    }


def is_finite_reward(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def trial_evaluation_failure(
    trial_directory: Path, result: dict[str, Any], reward_key: str
) -> dict[str, Any] | None:
    """Check native outcome metadata without collecting private feedback text."""

    verifier_directories = [trial_directory / "verifier"]
    verifier_directories.extend(sorted(trial_directory.glob("steps/*/verifier")))
    for directory in verifier_directories:
        for path in sorted(directory.rglob("diagnostics.json")):
            diagnostic = read_json_mapping(path, "Verifier diagnostics")
            for field in ("failure_domain", "status", "terminal_outcome", "error_code"):
                value = diagnostic.get(field)
                if value is not None and not isinstance(value, str):
                    return {"reason": "malformed-diagnostic", "failureDomain": "evaluator"}
                signal = re.sub(r"[^a-z0-9]+", "-", (value or "").casefold()).strip("-")
                if field != "failure_domain" and signal.rsplit("-", 1)[-1] in {
                    "success", "succeeded", "passed", "complete", "completed", "ok",
                }:
                    continue
                for domain, prefixes in (
                    ("authentication", ("authentication", "auth", "credential", "unauthorized", "invalid-api-key")),
                    ("environment", ("environment", "container", "docker", "runtime-environment")),
                    ("evaluator", ("evaluator", "evaluation", "verifier-error")),
                    ("infrastructure", ("infrastructure", "infra", "platform")),
                    ("provider", ("provider", "context-length", "context-limit", "context-window", "rate-limit", "quota", "insufficient-quota", "api-overloaded", "api-unavailable", "service-unavailable", "model-not-found")),
                ):
                    if any(signal == prefix or signal.startswith(prefix + "-") for prefix in prefixes):
                        return {
                            "reason": "classified-diagnostic",
                            "failureDomain": domain,
                            "diagnosticsPath": str(path),
                        }
    exceptions = [result.get("exception_info")]
    exceptions.extend(step.get("exception_info") for step in result.get("step_results") or [])
    for exception in exceptions:
        if exception and is_infrastructure_error(
            f"{exception.get('exception_type', '')}: {exception.get('exception_message', '')}"
        ):
            return {"reason": "external-execution-error", "failureDomain": "external"}
    if not result.get("finished_at"):
        return {"reason": "incomplete-trial", "failureDomain": "evaluator"}
    try:
        datetime.fromisoformat(result["finished_at"])
    except (TypeError, ValueError):
        return {"reason": "invalid-terminal-timestamp", "failureDomain": "evaluator"}
    # Harbor can coerce JSON strings and booleans into numbers. Inspect the
    # preserved reward JSON too; leave multi-step aggregation to Harbor.
    for directory in verifier_directories:
        path = directory / "reward.json"
        if path.is_file():
            rewards = read_json_mapping(path, "Verifier reward")
            if any(not is_finite_reward(value) for value in rewards.values()):
                return {"reason": "malformed-verifier-reward", "failureDomain": "evaluator"}
    verifier = result.get("verifier_result")
    rewards = verifier.get("rewards") if isinstance(verifier, dict) else None
    if rewards is None or (isinstance(rewards, dict) and reward_key not in rewards):
        exception = result.get("exception_info") or {}
        if exception.get("exception_type") == "AgentTimeoutError":
            return None
        return {"reason": "missing-primary-reward", "failureDomain": "evaluator"}
    if not isinstance(rewards, dict) or not is_finite_reward(rewards.get(reward_key)):
        return {"reason": "invalid-primary-reward", "failureDomain": "evaluator"}
    return None


async def run_candidate_trial(
    candidate: str,
    example: HarborTaskExample,
    *,
    phase: str,
) -> dict[str, Any]:
    runtime = _RUNTIME
    if runtime is None:
        raise RuntimeError("Harbor evolution runtime is not initialized.")
    if phase not in {
        "development", "validation-baseline", "validation-candidate",
        "holdout-baseline", "holdout-candidate",
    }:
        raise ValueError(f"Unknown Harbor evaluation phase: {phase}")
    sequence = next(runtime.counter)
    candidate_digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:12]
    evaluation_directory = (
        runtime.output_directory
        / "harbor-trials"
        / phase
        / f"{sequence:05d}-{candidate_digest}-{example.task_id}-{uuid4().hex[:8]}"
    )
    evaluation_directory.mkdir(parents=True)
    candidate_directory = installed_skill_path(
        evaluation_directory, runtime.skill_name
    )
    trials_directory = evaluation_directory / "trials"
    staged_provenance: dict[str, Any] = {
        "status": "not-staged",
        "verified": False,
        "logicalName": runtime.skill_name,
        "sourceSkill": str(runtime.baseline_skill),
        "sourceDigest": runtime.baseline_digest,
        "stagedSkill": str(candidate_directory),
        "candidateSkillMdDigest": text_digest(candidate),
    }
    try:
        candidate_directory, staged_provenance = stage_candidate_bundle(
            candidate, evaluation_directory, runtime
        )
    except ValueError as error:
        evidence = {
            "taskId": example.task_id,
            "taskName": example.task_name,
            "reward": 0.0,
            "evaluable": True,
            "error": str(error),
            "agentTrajectory": "",
            "agentOutput": "",
            "verifierOutput": "",
            "artifactDirectory": str(evaluation_directory),
            "skillProvenance": {
                **staged_provenance,
                "status": "candidate-rejected",
                "reason": str(error),
            },
        }
        (evaluation_directory / "evaluation.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        return evidence
    except Exception as error:
        evidence = {
            "taskId": example.task_id,
            "taskName": example.task_name,
            "reward": None,
            "evaluable": False,
            "error": f"{type(error).__name__}: {error}",
            "agentTrajectory": "",
            "agentOutput": "",
            "verifierOutput": "",
            "artifactDirectory": str(evaluation_directory),
            "skillProvenance": {
                **staged_provenance,
                "status": "staging-failed",
                "reason": str(error),
            },
        }
        (evaluation_directory / "evaluation.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        raise RuntimeError(
            f"Could not stage an attributable candidate for {example.task_name}: "
            f"{type(error).__name__}: {error}"
        ) from error

    config = TrialConfig(
        task=TaskConfig(path=example.path),
        trials_dir=trials_directory,
        agent=AgentConfig(
            name=runtime.agent_name,
            model_name=runtime.model_name,
            skills=[candidate_directory],
            kwargs=runtime.agent_kwargs,
        ),
        environment=EnvironmentConfig(type=runtime.environment_type),
        verifier=VerifierConfig(),
    )
    fatal_error: RuntimeError | None = None
    trial_provenance = staged_provenance
    try:
        await runtime.queue.submit(config)
        trial_provenance = verify_trial_skill_provenance(
            trials_directory, candidate_directory, staged_provenance
        )
        verify_frozen_baseline(runtime, "after Harbor trial execution")
        result = read_json_mapping(
            Path(trial_provenance["trialDirectory"]) / "result.json", "Trial result"
        )
        evaluation_failure = trial_evaluation_failure(
            Path(trial_provenance["trialDirectory"]), result, runtime.reward_key
        )
        verifier = result.get("verifier_result")
        rewards = verifier.get("rewards") if isinstance(verifier, dict) else None
        raw_reward = rewards.get(runtime.reward_key) if isinstance(rewards, dict) else None
        reported_reward = float(raw_reward) if is_finite_reward(raw_reward) else None
        exception = result.get("exception_info")
        error = (
            f"{exception['exception_type']}: {exception['exception_message']}"
            if exception and phase == "development"
            else ("Harbor execution error; details remain in the native trial." if exception else None)
        )
        reward = (
            None if evaluation_failure else (0.0 if exception else reported_reward)
        )
        feedback = (
            collect_trial_evidence(trials_directory, runtime.agent_name)
            if phase == "development" and evaluation_failure is None
            else {"agentTrajectory": "", "agentOutput": "", "verifierOutput": ""}
        )
        evidence = {
            "taskId": example.task_id,
            "taskName": example.task_name,
            "reward": reward,
            "reportedReward": reported_reward,
            "evaluable": evaluation_failure is None,
            "evaluationFailure": evaluation_failure,
            "error": error,
            **feedback,
            "artifactDirectory": str(evaluation_directory),
            "skillProvenance": trial_provenance,
        }
    except Exception as error:
        evidence = {
            "taskId": example.task_id,
            "taskName": example.task_name,
            "reward": None,
            "evaluable": False,
            "error": f"{type(error).__name__}: {error}",
            "agentTrajectory": "",
            "agentOutput": "",
            "verifierOutput": "",
            "artifactDirectory": str(evaluation_directory),
            "skillProvenance": {
                **trial_provenance,
                "status": "verification-failed",
                "verified": False,
                "reason": f"{type(error).__name__}: {error}",
            },
        }
        fatal_error = RuntimeError(
            f"Harbor could not execute {example.task_name}: {type(error).__name__}: {error}"
        )
    (evaluation_directory / "evaluation.json").write_text(
        json.dumps(evidence, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    if fatal_error is not None:
        raise fatal_error
    return evidence


def is_infrastructure_error(message: str) -> bool:
    normalized = re.sub(r"([a-z])([A-Z])", r"\1 \2", message).casefold()
    normalized = re.sub(r"[_-]+", " ", normalized)
    indicators = (
        "authentication",
        "credential",
        "unauthorized",
        "invalid api key",
        "docker",
        "environment setup",
        "image build",
        "rate limit",
        "model not found",
        "unsupported model",
        "context length",
        "context limit",
        "context window",
        "quota",
        "api connection",
        "apiconnection",
        "api timeout",
        "apitimeout",
        "service unavailable",
        "internal server error",
        "reward file",
        "verifier output parse",
        "verifier timeout",
        "add tests dir",
        "download verifier dir",
    )
    return any(indicator in normalized for indicator in indicators)


async def gepa_evaluator(candidate: str, example: HarborTaskExample):
    evidence = await run_candidate_trial(candidate, example, phase="development")
    if not evidence.get("evaluable", False) or not is_finite_reward(evidence["reward"]):
        raise RuntimeError(
            "Harbor evaluation is not evaluable; no fitness or feedback may reach GEPA. "
            f"Inspect preserved artifacts: {evidence['artifactDirectory']}"
        )
    return evidence["reward"], {
        "Task": evidence["taskName"],
        "Verifier": evidence["verifierOutput"],
        "Agent Trajectory": evidence["agentTrajectory"],
        "Agent Output": evidence["agentOutput"],
        "Error": evidence["error"] or "",
    }


async def evaluate_frozen_candidate_gate(
    candidate: str,
    examples: list[HarborTaskExample],
    attempts: int,
    phase: str,
) -> list[dict[str, Any]]:
    coroutines = [
        run_candidate_trial(candidate, example, phase=phase)
        for example in examples
        for _ in range(attempts)
    ]
    return list(await asyncio.gather(*coroutines))


def mean(values: list[float | None]) -> float | None:
    if not values or any(not is_finite_reward(value) for value in values):
        return None
    value = math.fsum(float(value) / len(values) for value in values)
    return value if is_finite_reward(value) else None


def mean_gain(baseline: float | None, candidate: float | None) -> float | None:
    delta = candidate - baseline if baseline is not None and candidate is not None else None
    return delta if is_finite_reward(delta) else None


def trial_reward(item: dict[str, Any]) -> float | None:
    if not item.get("evaluable", False) or not item.get("skillProvenance", {}).get("verified", False):
        return None
    return item.get("reward")


def summarize_comparison(
    baseline: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    rules: dict[str, Any],
) -> dict[str, Any]:
    baseline_by_task: dict[str, list[float | None]] = {}
    candidate_by_task: dict[str, list[float | None]] = {}
    for task_name in sorted({item["taskName"] for item in baseline + candidate}):
        baseline_by_task[task_name] = [
            trial_reward(item) for item in baseline if item["taskName"] == task_name
        ]
        candidate_by_task[task_name] = [
            trial_reward(item) for item in candidate if item["taskName"] == task_name
        ]
    per_task = []
    regressions = []
    for task_name in baseline_by_task:
        baseline_mean = mean(baseline_by_task[task_name])
        candidate_mean = mean(candidate_by_task[task_name])
        matched = len(baseline_by_task[task_name]) == len(candidate_by_task[task_name])
        delta = mean_gain(baseline_mean, candidate_mean) if matched else None
        if delta is not None and delta < 0:
            regressions.append(task_name)
        per_task.append(
            {
                "taskName": task_name,
                "baselineMeanReward": baseline_mean,
                "candidateMeanReward": candidate_mean,
                "delta": delta,
            }
        )
    baseline_mean = mean([trial_reward(item) for item in baseline])
    candidate_mean = mean([trial_reward(item) for item in candidate])
    gain = mean_gain(baseline_mean, candidate_mean)
    candidate_errors = sum(1 for item in candidate if item["error"])
    provenance_failures = sum(
        1
        for item in baseline + candidate
        if not item.get("skillProvenance", {}).get("verified", False)
    )
    matched_attempts = bool(baseline_by_task) and all(
        len(baseline_by_task[task]) == len(candidate_by_task[task])
        and bool(baseline_by_task[task])
        for task in baseline_by_task
    )
    non_evaluable_trials = sum(
        not is_finite_reward(trial_reward(item)) for item in baseline + candidate
    )
    baseline_digests = {item.get("skillProvenance", {}).get("stagedDigest") for item in baseline}
    candidate_digests = {item.get("skillProvenance", {}).get("stagedDigest") for item in candidate}
    unchanged = (
        len(baseline_digests) == 1 and None not in baseline_digests
        and baseline_digests == candidate_digests
    )
    evaluable = gain is not None and matched_attempts and provenance_failures == 0
    passed = (
        evaluable and not unchanged
        and gain >= rules["minimumMeanGain"]
        and (rules["allowTaskRegressions"] or not regressions)
        and (not rules["requireNoErrors"] or candidate_errors == 0)
        and provenance_failures == 0
    )
    return {
        "baselineMeanReward": baseline_mean,
        "candidateMeanReward": candidate_mean,
        "meanGain": gain if matched_attempts else None,
        "evaluable": evaluable,
        "nonEvaluableTrials": non_evaluable_trials,
        "matchedAttempts": matched_attempts,
        "candidateChanged": not unchanged,
        "candidateErrors": candidate_errors,
        "provenanceFailures": provenance_failures,
        "provenanceVerified": provenance_failures == 0,
        "regressedTasks": regressions,
        "perTask": per_task,
        "rules": rules,
        "passed": passed,
    }


def summarize_validation(
    baseline: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    comparison = summarize_comparison(baseline, candidate, config["validationGate"])
    return {
        "status": "complete" if comparison["evaluable"] else "not-evaluable",
        "optimizerVisible": False,
        **comparison,
    }


def summarize_holdout(
    baseline: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    comparison = summarize_comparison(baseline, candidate, config["promotion"])
    return {
        "status": "complete" if comparison["evaluable"] else "not-evaluable",
        "opened": True,
        **comparison,
        "promotionRules": comparison["rules"],
        "promoted": comparison["passed"],
    }


def sealed_holdout() -> dict[str, Any]:
    return {
        "status": "sealed",
        "opened": False,
        "reason": "independent-validation-failed",
        "promoted": False,
    }


def summarize_preserved_provenance(output_directory: Path) -> dict[str, Any]:
    phases: dict[str, dict[str, int | bool]] = {}
    trials_root = output_directory / "harbor-trials"
    for phase in (
        "development",
        "validation-baseline",
        "validation-candidate",
        "holdout-baseline",
        "holdout-candidate",
    ):
        evidence_files = (
            sorted((trials_root / phase).glob("*/evaluation.json"))
            if (trials_root / phase).is_dir()
            else []
        )
        rows = [read_json_mapping(path, "Trial evaluation") for path in evidence_files]
        provenance_rows = [row.get("skillProvenance", {}) for row in rows]
        staged_rows = [row for row in provenance_rows if row.get("stagedDigest")]
        verified = sum(1 for row in staged_rows if row.get("verified", False))
        rejected = sum(
            1 for row in provenance_rows if row.get("status") == "candidate-rejected"
        )
        phases[phase] = {
            "verified": verified,
            "total": len(staged_rows),
            "rejectedCandidates": rejected,
            "allVerified": bool(staged_rows) and verified == len(staged_rows),
        }
    total = sum(int(row["total"]) for row in phases.values())
    verified = sum(int(row["verified"]) for row in phases.values())
    return {
        "policy": "exact-logical-name-source-digest",
        "required": True,
        "phases": phases,
        "verifiedTrials": verified,
        "totalTrials": total,
        "allTrialsVerified": total > 0 and verified == total,
    }


def format_reward(value: float | None, *, signed: bool = False) -> str:
    if not is_finite_reward(value):
        return "unavailable"
    return format(value, "+.3f" if signed else ".3f")


def render_report(run: dict[str, Any]) -> str:
    validation = run["validation"]
    holdout = run["holdout"]
    decision = "PROMOTE" if holdout["promoted"] else "KEEP BASELINE"
    lines = [
        f"# Harbor Skill Evolution: {run['evolutionId']}",
        "",
        f"Decision: **{decision}**",
        "",
        "## Evidence",
        "",
        f"- Baseline skill: `{run['baselineSkill']}`",
        f"- Candidate skill: `{run['candidateSkill']}`",
        f"- Logical skill name: `{run['skillProvenance']['logicalName']}`",
        f"- Frozen baseline: `{run['baselineSnapshot']}`",
        f"- Baseline digest: `{run['baselineDigest']}`",
        f"- Candidate digest: `{run['candidateDigest']}`",
        "- Verified staged identities: "
        f"{run['skillProvenance']['verifiedTrials']}/"
        f"{run['skillProvenance']['totalTrials']}",
        f"- Harbor: `{run['harborVersion']}`",
        f"- GEPA: `{run['gepaVersion']}`",
        f"- Agent/model: `{run['agent']}` / `{run['model']}`",
        f"- GEPA candidates: {run['gepa']['candidateCount']}",
        f"- GEPA metric calls: {run['gepa']['metricCalls']}",
        f"- Best evolution score: {run['gepa']['bestEvolutionScore']:.3f}",
        "",
        "## Independent validation gate",
        "",
        "| Task | Baseline mean | Candidate mean | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in validation["perTask"]:
        lines.append(
            f"| {row['taskName']} | {format_reward(row['baselineMeanReward'])} | "
            f"{format_reward(row['candidateMeanReward'])} | {format_reward(row['delta'], signed=True)} |"
        )
    lines.extend(
        [
            "",
            f"Validation decision: {'PASS' if validation['passed'] else validation['status'].upper() if validation['status'] != 'complete' else 'FAIL'}",
            f"Overall baseline: {format_reward(validation['baselineMeanReward'])}",
            f"Overall candidate: {format_reward(validation['candidateMeanReward'])}",
            f"Mean gain: {format_reward(validation['meanGain'], signed=True)}",
            f"Non-evaluable trials: {validation['nonEvaluableTrials']}",
            f"Candidate errors: {validation['candidateErrors']}",
            f"Provenance failures: {validation['provenanceFailures']}",
            f"Regressed tasks: {', '.join(validation['regressedTasks']) or 'none'}",
            "",
            "## Holdout gate",
            "",
        ]
    )
    if not holdout["opened"]:
        lines.extend(
            [
                "Private gates remained sealed because the selected candidate is unchanged."
                if validation.get("reason") == "selected-candidate-unchanged"
                else "Holdout remained sealed because independent validation did not pass.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "| Task | Baseline mean | Candidate mean | Delta |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for row in holdout["perTask"]:
            lines.append(
                f"| {row['taskName']} | {format_reward(row['baselineMeanReward'])} | "
                f"{format_reward(row['candidateMeanReward'])} | {format_reward(row['delta'], signed=True)} |"
            )
        lines.extend(
            [
                "",
                f"Overall baseline: {format_reward(holdout['baselineMeanReward'])}",
                f"Overall candidate: {format_reward(holdout['candidateMeanReward'])}",
                f"Mean gain: {format_reward(holdout['meanGain'], signed=True)}",
                f"Non-evaluable trials: {holdout['nonEvaluableTrials']}",
                f"Candidate errors: {holdout['candidateErrors']}",
                f"Provenance failures: {holdout['provenanceFailures']}",
                f"Regressed tasks: {', '.join(holdout['regressedTasks']) or 'none'}",
                "",
            ]
        )
    lines.extend(
        [
            "The source skill was not modified. Promote the candidate bundle only after reviewing this report and its preserved Harbor trial artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def initialize_runtime(
    config: dict[str, Any], baseline_snapshot: Path, source_digest: str
) -> Runtime:
    return Runtime(
        source_skill=config["baselineSkill"],
        source_digest=source_digest,
        baseline_skill=baseline_snapshot,
        baseline_digest=compute_skill_digest(baseline_snapshot),
        skill_name=config["skillName"],
        output_directory=config["outputDirectory"],
        agent_name=config["harbor"]["agentName"],
        model_name=config["harbor"]["modelName"],
        environment_type=config["harbor"]["environment"],
        agent_kwargs=config["harbor"]["agentKwargs"],
        reward_key=config["harbor"]["rewardKey"],
        concurrency=config["harbor"]["concurrency"],
        queue=TrialQueue(n_concurrent=config["harbor"]["concurrency"]),
        counter=itertools.count(1),
    )


def run_evolution(config: dict[str, Any]) -> dict[str, Any]:
    global _RUNTIME
    missing = [
        name for name in config["harbor"]["requiredEnv"] if not os.environ.get(name)
    ]
    if missing:
        raise ValueError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    output = config["outputDirectory"]
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    baseline_snapshot = installed_skill_path(
        output / "baseline-snapshot", config["skillName"]
    )
    baseline_snapshot_provenance = preserve_skill_copy(
        config["baselineSkill"], baseline_snapshot, "Baseline snapshot"
    )
    _RUNTIME = initialize_runtime(
        config, baseline_snapshot, baseline_snapshot_provenance["sourceDigest"]
    )

    gepa_directory = output / "gepa"
    result = optimize_anything(
        seed_candidate=config["baselineText"],
        evaluator=gepa_evaluator,
        dataset=config["splits"]["evolution"],
        valset=config["splits"]["evolution"],
        objective=config["objective"],
        background=config["background"],
        config=GEPAConfig(
            engine=EngineConfig(
                run_dir=str(gepa_directory),
                seed=config["gepa"]["seed"],
                max_metric_calls=config["gepa"]["maxMetricCalls"],
                max_candidate_proposals=config["gepa"]["maxCandidateProposals"],
                candidate_selection_strategy="pareto",
                acceptance_criterion="strict_improvement",
                max_workers=config["harbor"]["concurrency"],
                parallel=True,
                cache_evaluation=False,
                raise_on_exception=True,
                display_progress_bar=False,
            ),
            reflection=ReflectionConfig(
                reflection_lm=config["gepa"]["reflectionModel"],
                reflection_minibatch_size=config["gepa"]["reflectionMinibatchSize"],
                reflection_prompt_template=REFLECTION_PROMPT,
            ),
        ),
    )
    candidate = result.best_candidate
    if not isinstance(candidate, str):
        raise ValueError("GEPA returned a non-text candidate for a text SKILL.md seed.")
    validate_candidate(candidate, config["skillName"])
    candidate_directory = installed_skill_path(output / "candidate-skill", config["skillName"])
    candidate_artifact_provenance = create_candidate_bundle(
        candidate, candidate_directory, _RUNTIME
    )
    frozen_candidate_digest = compute_skill_digest(candidate_directory)

    _RUNTIME.queue = TrialQueue(n_concurrent=config["harbor"]["concurrency"])
    candidate_changed = frozen_candidate_digest != _RUNTIME.baseline_digest
    validation = config["splits"]["validation"] if candidate_changed else []
    validation_attempts = config["harbor"]["validationAttempts"]
    validation_baseline_results = asyncio.run(
        evaluate_frozen_candidate_gate(
            config["baselineText"],
            validation,
            validation_attempts,
            "validation-baseline",
        )
    )
    _RUNTIME.queue = TrialQueue(n_concurrent=config["harbor"]["concurrency"])
    validation_candidate_results = asyncio.run(
        evaluate_frozen_candidate_gate(
            candidate,
            validation,
            validation_attempts,
            "validation-candidate",
        )
    )
    validation_summary = summarize_validation(
        validation_baseline_results, validation_candidate_results, config
    )
    if not candidate_changed:
        validation_summary.update(
            status="not-run", reason="selected-candidate-unchanged", candidateChanged=False
        )

    holdout_baseline_results: list[dict[str, Any]] = []
    holdout_candidate_results: list[dict[str, Any]] = []
    if validation_summary["passed"]:
        holdout = config["splits"]["holdout"]
        holdout_attempts = config["harbor"]["holdoutAttempts"]
        _RUNTIME.queue = TrialQueue(n_concurrent=config["harbor"]["concurrency"])
        holdout_baseline_results = asyncio.run(
            evaluate_frozen_candidate_gate(
                config["baselineText"],
                holdout,
                holdout_attempts,
                "holdout-baseline",
            )
        )
        _RUNTIME.queue = TrialQueue(n_concurrent=config["harbor"]["concurrency"])
        holdout_candidate_results = asyncio.run(
            evaluate_frozen_candidate_gate(
                candidate,
                holdout,
                holdout_attempts,
                "holdout-candidate",
            )
        )
        holdout_summary = summarize_holdout(
            holdout_baseline_results, holdout_candidate_results, config
        )
    else:
        holdout_summary = sealed_holdout()
        if not candidate_changed:
            holdout_summary["reason"] = "selected-candidate-unchanged"
    source_digest_at_completion = compute_skill_digest(_RUNTIME.source_skill)
    if source_digest_at_completion != _RUNTIME.source_digest:
        raise RuntimeError(
            "Source skill changed after the frozen baseline snapshot was created: "
            f"{_RUNTIME.source_skill}: {_RUNTIME.source_digest} != "
            f"{source_digest_at_completion}. Refusing to finalize promotion evidence."
        )
    verify_frozen_baseline(_RUNTIME, "before finalizing the run")
    candidate_digest_at_completion = compute_skill_digest(candidate_directory)
    if candidate_digest_at_completion != frozen_candidate_digest:
        raise RuntimeError(
            "Selected candidate changed after it was frozen and before validation "
            f"completed: {frozen_candidate_digest} != {candidate_digest_at_completion}."
        )
    provenance_summary = summarize_preserved_provenance(output)
    generated_at = datetime.now(timezone.utc).isoformat()
    run = {
        "schemaVersion": 2,
        "source": "harbor-gepa",
        "evolutionId": config["id"],
        "generatedAt": generated_at,
        "baselineSkill": str(_RUNTIME.source_skill),
        "baselineDigest": _RUNTIME.source_digest,
        "baselineSnapshot": str(baseline_snapshot),
        "baselineSnapshotDigest": _RUNTIME.baseline_digest,
        "baselineSnapshotProvenance": baseline_snapshot_provenance,
        "candidateSkill": str(candidate_directory),
        "candidateDigest": frozen_candidate_digest,
        "candidateArtifactProvenance": candidate_artifact_provenance,
        "skillProvenance": {
            **provenance_summary,
            "logicalName": config["skillName"],
            "sourceSkill": str(_RUNTIME.source_skill),
            "sourceBasename": _RUNTIME.source_skill.name,
            "sourceDigest": _RUNTIME.source_digest,
            "sourceDigestAtCompletion": source_digest_at_completion,
            "sourceUnchanged": True,
            "baselineSnapshot": str(baseline_snapshot),
            "baselineSnapshotDigest": _RUNTIME.baseline_digest,
        },
        "harborVersion": version("harbor"),
        "gepaVersion": version("gepa"),
        "agent": config["harbor"]["agentName"],
        "model": config["harbor"]["modelName"],
        "splits": {
            name: [example.task_name for example in examples]
            for name, examples in config["splits"].items()
        },
        "gepa": {
            "candidateCount": result.num_candidates,
            "metricCalls": result.total_metric_calls,
            "bestIndex": result.best_idx,
            "bestEvolutionScore": result.val_aggregate_scores[result.best_idx],
            "runDirectory": result.run_dir,
        },
        "evaluationBoundary": {
            "evolutionDatasetSplit": "evolution",
            "validationDatasetSplit": "validation",
            "validationOptimizerVisible": False,
            "candidateDigestFrozenBeforeValidation": frozen_candidate_digest,
            "candidateDigestAfterValidation": candidate_digest_at_completion,
            "holdoutOpened": validation_summary["passed"],
        },
        "validation": validation_summary,
        "validationTrials": {
            "baseline": validation_baseline_results,
            "candidate": validation_candidate_results,
        },
        "holdout": holdout_summary,
        "holdoutTrials": {
            "baseline": holdout_baseline_results,
            "candidate": holdout_candidate_results,
        },
    }
    (output / "run.json").write_text(
        json.dumps(run, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (output / "report.md").write_text(render_report(run), encoding="utf-8")
    return run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output-dir", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--doctor", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        config = normalize_config(args.config.resolve(), args.output_dir)
        if args.dry_run:
            result = {"mode": "dry-run", **public_plan(config)}
        elif args.doctor:
            result = {"mode": "doctor", **doctor(config)}
        else:
            run = run_evolution(config)
            result = {
                "mode": "live",
                "decision": (
                    "promote"
                    if run["holdout"]["promoted"]
                    else (
                        "validation-rejected"
                        if not run["validation"]["passed"]
                        and run["validation"].get("reason") != "selected-candidate-unchanged"
                        else "keep-baseline"
                    )
                ),
                "candidateSkill": run["candidateSkill"],
                "runJson": str(config["outputDirectory"] / "run.json"),
                "reportMarkdown": str(config["outputDirectory"] / "report.md"),
            }
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
