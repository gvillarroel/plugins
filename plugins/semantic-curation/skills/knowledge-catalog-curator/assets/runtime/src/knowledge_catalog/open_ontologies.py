"""Checksum-pinned, dry-run Open Ontologies comparisons with local eligibility gates."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SKOS

from .analysis import CONCEPTS, _words
from .taxonomy import _load_vocabulary, suggest_concepts

VERSION = "2.1.0"
BINARY_SHA256 = "1d81ff3933868bfed001b63d8bdd6f9cb3c0807389d4e3064a51a41d7d60f480"
PINNED_ASSETS = {
    ("Windows", "AMD64"): ("open-ontologies-x86_64-pc-windows-msvc.exe", BINARY_SHA256),
    ("Linux", "x86_64"): (
        "open-ontologies-x86_64-unknown-linux-gnu",
        "ead03c7148a66ea0fe01cbdaa289d47361c2a4d54619a60f805a72a2c57e81bb",
    ),
    ("Darwin", "arm64"): (
        "open-ontologies-aarch64-apple-darwin",
        "493f6db51550112528d19f3ca88caf133b46c2a9054a195a98bc588b57ba07b6",
    ),
    ("Darwin", "x86_64"): (
        "open-ontologies-x86_64-apple-darwin",
        "d2aacac75b2301eb3ce8f49000a8cc0bc7dd7edbf01fa36ac422ffdf4aaf11ee",
    ),
}
POLICY = "open-ontologies-pairwise-dry-run-v1"
MAX_OUTPUT = 2 * 1024 * 1024
TIMEOUT = 30.0
SIGNALS = {
    "label_similarity",
    "property_overlap",
    "parent_overlap",
    "instance_overlap",
    "restriction_similarity",
    "neighborhood_similarity",
    "embedding_similarity",
}


class OpenOntologiesError(ValueError):
    """The verified engine could not provide a bounded, read-only comparison."""


def _asset() -> tuple[str, str]:
    identity = (platform.system(), platform.machine())
    if identity not in PINNED_ASSETS:
        raise OpenOntologiesError("No pinned Open Ontologies release asset is registered for this platform.")
    return PINNED_ASSETS[identity]


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime() -> dict:
    manifest = Path(
        os.environ.get(
            "KC_OPEN_ONTOLOGIES_RUNTIME",
            str(Path.home() / ".knowledge-catalog-curator/engines/open-ontologies/runtime.json"),
        )
    )
    try:
        _, expected_sha256 = _asset()
        if not manifest.is_file() or manifest.stat().st_size > 16_384:
            raise OpenOntologiesError(
                "Install the verified Open Ontologies runtime before using this provider."
            )
        value = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("version") != VERSION:
            raise OpenOntologiesError("The Open Ontologies runtime must be the pinned 2.1.0 release.")
        binary = value.get("binary")
        if not isinstance(binary, str) or not Path(binary).is_absolute():
            raise OpenOntologiesError("The Open Ontologies manifest must name an absolute executable path.")
        executable = Path(binary).resolve(strict=True)
        if not executable.is_file() or value.get("binary_sha256") != expected_sha256:
            raise OpenOntologiesError(
                "The Open Ontologies executable is not the pinned official release asset."
            )
        if _sha(executable) != expected_sha256:
            raise OpenOntologiesError(
                "Open Ontologies executable integrity failed; reinstall the verified runtime."
            )
        return {**value, "binary": str(executable), "binary_sha256": expected_sha256}
    except OpenOntologiesError:
        raise
    except (OSError, ValueError, TypeError) as error:
        raise OpenOntologiesError(
            "The Open Ontologies runtime manifest or executable is unavailable."
        ) from error


def runtime_status() -> dict:
    """Inspect installation integrity without starting an engine or downloading anything."""
    try:
        runtime = _runtime()
    except OpenOntologiesError as error:
        return {
            "id": "open-ontologies",
            "label": "Open Ontologies",
            "available": False,
            "error": str(error),
            "invoked": False,
        }
    return {
        "id": "open-ontologies",
        "label": "Open Ontologies",
        "available": True,
        "version": runtime["version"],
        "binary_sha256": runtime["binary_sha256"],
        "release_url": runtime.get("release_url"),
        "source_commit": runtime.get("source_commit"),
        "mode": "dry-run",
        "invoked": False,
    }


def _canonical(graph: Graph) -> bytes:
    # Sorted N-Triples is a deterministic Turtle subset; no remote context is parsed.
    return (
        "\n".join(sorted(line for line in graph.serialize(format="nt").splitlines() if line)) + "\n"
    ).encode("utf-8")


def _source(metadata: dict, column_name: str | None, query: str) -> tuple[str, bytes]:
    columns = [
        column
        for column in metadata.get("columns", [])
        if isinstance(column, dict) and isinstance(column.get("name"), str)
    ]
    names = [column_name] if column_name is not None else [column["name"] for column in columns]
    label = " ".join(name[:500] for name in names)[:4000] or query
    identity = json.dumps({"column": column_name, "names": names, "query": query}, sort_keys=True).encode()
    iri = "urn:knowledge-catalog:observed:" + hashlib.sha256(identity).hexdigest()
    node = URIRef(iri)
    graph = Graph()
    graph.add((node, RDF.type, SKOS.Concept))
    graph.add((node, SKOS.prefLabel, Literal(label)))
    for alias in sorted({_words(label), query.strip()} - {"", label}):
        graph.add((node, SKOS.altLabel, Literal(alias)))
    return iri, _canonical(graph)


def _target(candidate: dict, terms: list[dict], scheme: str) -> bytes:
    registered = {term["concept"]: term for term in terms}
    pending, visited = [candidate["concept"]], set()
    graph = Graph()
    while pending:
        iri = pending.pop()
        if iri in visited or iri not in registered:
            continue
        visited.add(iri)
        term = registered[iri]
        node = URIRef(iri)
        graph.add((node, RDF.type, SKOS.Concept))
        graph.add((node, SKOS.inScheme, URIRef(scheme)))
        graph.add((node, SKOS.prefLabel, Literal(term["label"], lang="en")))
        graph.add((node, SKOS.definition, Literal(term["definition"], lang="en")))
        aliases = {*term["aliases"], *CONCEPTS[term["label"]].split()}
        for alias in sorted(aliases - {term["label"]}):
            graph.add((node, SKOS.altLabel, Literal(alias)))
        for parent in term["parents"]:
            if parent in registered:
                graph.add((node, SKOS.broader, URIRef(parent)))
                pending.append(parent)
    return _canonical(graph)


def _environment(workspace: Path) -> dict:
    env = {name: os.environ[name] for name in ("PATH", "SystemRoot", "WINDIR") if name in os.environ}
    profile, temporary = workspace / "profile", workspace / "tmp"
    profile.mkdir(exist_ok=True)
    temporary.mkdir(exist_ok=True)
    env.update(
        HOME=str(profile),
        USERPROFILE=str(profile),
        APPDATA=str(profile),
        LOCALAPPDATA=str(profile),
        TEMP=str(temporary),
        TMP=str(temporary),
    )
    return env


def _run(command: list[str], workspace: Path, timeout: float) -> bytes:
    """Keep output on disk until its size and process exit have been checked."""
    if timeout <= 0:
        raise OpenOntologiesError("Open Ontologies comparison exceeded its time budget.")
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            with subprocess.Popen(
                command,
                cwd=workspace,
                env=_environment(workspace),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            ) as process:
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    if (
                        os.fstat(stdout.fileno()).st_size > MAX_OUTPUT
                        or os.fstat(stderr.fileno()).st_size > MAX_OUTPUT
                    ):
                        process.kill()
                        process.wait()
                        raise OpenOntologiesError("Open Ontologies exceeded the bounded output limit.")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        process.kill()
                        process.wait()
                        raise OpenOntologiesError("Open Ontologies comparison timed out.")
                    try:
                        process.wait(timeout=min(0.05, remaining))
                    except subprocess.TimeoutExpired:
                        pass
                if process.returncode:
                    raise OpenOntologiesError("Open Ontologies could not complete the dry-run comparison.")
        except OpenOntologiesError:
            raise
        except OSError as error:
            raise OpenOntologiesError("The verified Open Ontologies executable could not start.") from error
        if os.fstat(stdout.fileno()).st_size > MAX_OUTPUT or os.fstat(stderr.fileno()).st_size > MAX_OUTPUT:
            raise OpenOntologiesError("Open Ontologies exceeded the bounded output limit.")
        stdout.seek(0)
        return stdout.read(MAX_OUTPUT + 1)


def _number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _assessment(body: bytes, source_iri: str, target_iri: str, allowed: set[str]) -> dict | None:
    try:
        if len(body) > MAX_OUTPUT:
            raise ValueError("size")
        value = json.loads(body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        if not isinstance(value, dict) or "error" in value:
            raise ValueError("shape")
        if type(value.get("applied_count")) is not int or value["applied_count"] != 0:
            raise ValueError("writes")
        if value.get("scoring") != "informative_renormalised" or value.get("cardinality") != "many_to_one":
            raise ValueError("mode")
        rows = value.get("candidates")
        if not isinstance(rows, list) or len(rows) > 64:
            raise ValueError("rows")
        for key in ("candidates", "auto_applied", "borderline"):
            bucket = value.get(key, [])
            if (
                not isinstance(bucket, list)
                or len(bucket) > 64
                or any(not isinstance(row, dict) or row.get("applied") is True for row in bucket)
            ):
                raise ValueError("writes")
        found = []
        for row in rows:
            if row.get("source_iri") != source_iri or row.get("target_iri") != target_iri:
                continue
            if type(row.get("ambiguous", False)) is not bool or type(row.get("requires_review")) is not bool:
                raise ValueError("review flags")
            confidence, coverage, signals = (
                row.get("confidence"),
                row.get("evidence_coverage"),
                row.get("informative_signals"),
            )
            if (
                not _number(confidence)
                or not _number(coverage)
                or not isinstance(signals, list)
                or not signals
                or len(signals) > len(SIGNALS)
                or any(signal not in SIGNALS for signal in signals)
            ):
                raise ValueError("evidence")
            tied = row.get("tied_with", [])
            if not isinstance(tied, list) or len(tied) > 32:
                raise ValueError("ties")
            ties = []
            for other in tied:
                if not isinstance(other, dict) or not _number(other.get("confidence")):
                    raise ValueError("ties")
                if other.get("source_iri") == source_iri and other.get("target_iri") in allowed:
                    ties.append({"target_iri": other["target_iri"], "confidence": other["confidence"]})
            found.append(
                {
                    "confidence": confidence,
                    "evidence_coverage": coverage,
                    "informative_signals": sorted(set(signals)),
                    "ambiguous": bool(row.get("ambiguous")) or bool(ties),
                    "requires_review": row["requires_review"],
                    "tied_with": ties,
                }
            )
        if len(found) > 1:
            raise ValueError("duplicate")
        return found[0] if found else None
    except (ValueError, TypeError, UnicodeError) as error:
        raise OpenOntologiesError(
            "Open Ontologies returned invalid or non-read-only comparison evidence."
        ) from error


def compare_concepts(metadata: dict, *, column_name: str | None, query: str = "", limit: int = 3) -> dict:
    """Compare eligible candidates using the real engine; no silent local fallback."""
    if type(limit) is not int or not 1 <= limit <= 3:
        raise OpenOntologiesError("Engine alternatives must request between one and three results.")
    local = suggest_concepts(metadata, column_name=column_name, query=query, limit=5)
    runtime = _runtime()
    vocabulary, terms, _ = _load_vocabulary()
    if vocabulary["version"] != local["vocabulary"]["version"]:
        raise OpenOntologiesError("The installed vocabulary changed; retry against one saved snapshot.")
    source_iri, source = _source(metadata, column_name, query)
    provider = {
        "id": "open-ontologies",
        "label": "Open Ontologies",
        "version": VERSION,
        "binary_sha256": runtime["binary_sha256"],
        "invoked": False,
        "mode": "dry-run",
        "scoring": "informative_renormalised",
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "target_sha256": {},
        "comparison_count": 0,
    }
    result = copy.deepcopy(local)
    result["provider"] = provider
    result["method"] = {
        "name": "Open Ontologies informative alignment with local eligibility gates",
        "score_is_probability": False,
        "policy_version": POLICY,
        "version": hashlib.sha256(
            json.dumps(
                {
                    "policy": POLICY,
                    "binary": runtime["binary_sha256"],
                    "local_method": local["method"]["version"],
                    "vocabulary": vocabulary["version"],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest(),
    }
    if not local["candidates"]:
        result["message"] += (
            " Local eligibility filters left no supported target; the engine was not invoked."
        )
        return result
    assessed = []
    deadline = time.monotonic() + TIMEOUT
    with tempfile.TemporaryDirectory(prefix="kc-open-ontologies-") as directory:
        workspace = Path(directory)
        data = workspace / "data"
        data.mkdir()
        (data / "config.toml").write_text(
            '[storage]\nmode = "memory"\n[embeddings]\nprovider = "local"\n', encoding="utf-8"
        )
        source_path = workspace / "source.ttl"
        source_path.write_bytes(source)
        allowed = {term["concept"] for term in terms}
        for index, candidate in enumerate(local["candidates"]):
            target = _target(candidate, terms, vocabulary["id"])
            provider["target_sha256"][candidate["concept"]] = hashlib.sha256(target).hexdigest()
            target_path = workspace / f"target-{index}.ttl"
            target_path.write_bytes(target)
            command = [
                runtime["binary"],
                "--data-dir",
                str(data),
                "--no-connect",
                "--json",
                "align",
                str(source_path),
                str(target_path),
                "--dry-run",
                "--scoring",
                "informative",
                "--cardinality",
                "many-to-one",
                "--min-confidence",
                "0.4",
            ]
            body = _run(command, workspace, deadline - time.monotonic())
            provider["invoked"] = True
            provider["comparison_count"] += 1
            evidence = _assessment(body, source_iri, candidate["concept"], allowed)
            if evidence is None:
                continue
            item = copy.deepcopy(candidate)
            item["score"] = evidence["confidence"]
            item["engine_evidence"] = evidence
            item["requires_human_review"] = True
            item["evidence"].append(
                "Open Ontologies compared this observed-field proposal with the registered concept in a dry run."
            )
            if evidence["informative_signals"] == ["label_similarity"]:
                item["warnings"].append(
                    "The engine has label-only evidence for this alignment; its score does not verify business meaning."
                )
            assessed.append(item)
    assessed.sort(
        key=lambda item: (-item["score"], -item["engine_evidence"]["evidence_coverage"], item["concept"])
    )
    ambiguous = any(item["engine_evidence"]["ambiguous"] for item in assessed)
    if len(assessed) > 1 and assessed[0]["score"] - assessed[1]["score"] <= 0.001:
        ambiguous = True
    result["candidates"] = assessed[:limit]
    result["filter_summary"]["engine_below_threshold_or_unmatched"] = len(local["candidates"]) - len(assessed)
    result["filter_summary"]["engine_outside_limit"] = max(0, len(assessed) - limit)
    result["status"] = "ambiguous" if ambiguous else "suggested" if assessed else "no_reliable_match"
    result["message"] = (
        "The real Open Ontologies engine found similarly supported alignments. Compare the evidence and choose deliberately."
        if ambiguous
        else "Review these real Open Ontologies dry-run comparisons. No mapping was applied and human review is required."
        if assessed
        else "No eligible target met the real Open Ontologies comparison threshold. Keep the meaning unresolved."
    )
    return result
