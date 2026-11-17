#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Rank public video snapshots within explicit comparable cohorts."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import median
import sys
from urllib.parse import parse_qs, urlsplit


UNVERIFIED_LABELS = {"unknown", "unverified", "unspecified", "n-a", "n/a", "na", "none", "null", "unavailable"}


def unverified_fields(row: dict) -> list[str]:
    return [field for field in ("creator", "platform", "format", "metric_definition")
            if row[field].strip().casefold().replace("_", "-") in UNVERIFIED_LABELS]


def timestamp(value: object, label: str, *, date_allowed: bool = False) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO date or timestamp string.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be a valid ISO date or timestamp.") from error
    if parsed.tzinfo is None:
        if not date_allowed or len(value) != 10:
            raise ValueError(f"{label} must include a UTC offset or Z.")
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def count(value: object, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer or null.")
    return value


def video_key(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("url must be an absolute HTTP(S) source URL.")
    if host in {"youtube.com", "m.youtube.com", "youtu.be"}:
        parts = parsed.path.strip("/").split("/")
        video_id = parts[0] if host == "youtu.be" else (
            parts[1] if len(parts) > 1 and parts[0] in {"shorts", "embed"}
            else parse_qs(parsed.query).get("v", [""])[0])
        if video_id:
            return f"youtube:{video_id}"
    return f"{host}{parsed.path.rstrip('/')}?{parsed.query}"


def normalize(row: object, observed: datetime) -> dict:
    if not isinstance(row, dict):
        raise ValueError("Each video record must be an object.")
    result = dict(row)
    for field in ("id", "url", "title", "creator", "platform", "format", "metric_definition"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise ValueError(f"{field} must be a nonempty string.")
        result[field] = row[field].strip()
    result["platform"] = result["platform"].lower()
    result["format"] = result["format"].lower()
    result["_video_key"] = video_key(result["url"])
    published = timestamp(row.get("published_at"), "published_at", date_allowed=True)
    snapshot = timestamp(row.get("observed_at", observed.isoformat()), "observed_at")
    if abs((snapshot - observed).total_seconds()) > 86400:
        raise ValueError("Row observed_at differs from the common snapshot by more than 24 hours.")
    age = (snapshot - published).total_seconds() / 86400
    if age <= 0:
        raise ValueError("published_at must precede the observed snapshot.")
    duration = row.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration_seconds must be finite and positive.")
    for field in ("views", "likes", "comments"):
        result[field] = count(row.get(field), field)
    result.update({"published_at": published.isoformat(), "observed_at": snapshot.isoformat(),
                   "age_days": age, "age_cohort": "fresh" if age < 7 else "legacy" if age > 730 else "mature",
                   "duration_band": "under-60s" if duration < 60 else "60-to-180s" if duration < 180 else "180-to-600s" if duration < 600 else "600s-plus",
                   "_published": published})
    return result


def group_for(row: dict) -> dict:
    return {field: row[field] for field in ("platform", "format", "metric_definition", "duration_band")}


def analyze(data: object) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("candidates"), list) or not data["candidates"]:
        raise ValueError("Input must contain a nonempty candidates array.")
    observed = timestamp(data.get("observed_at"), "observed_at")
    candidates = [normalize(row, observed) for row in data["candidates"]]
    if len({row["id"] for row in candidates}) != len(candidates):
        raise ValueError("Candidate IDs must be unique.")
    if len({row["_video_key"] for row in candidates}) != len(candidates):
        raise ValueError("Candidate source videos must be unique, including URL aliases.")
    candidate_ids = {row["id"] for row in candidates}
    candidate_keys = {row["_video_key"] for row in candidates}
    if not isinstance(data.get("baselines", []), list):
        raise ValueError("baselines must be an array.")
    normalized, excluded = [], []
    for index, row in enumerate(data.get("baselines", [])):
        try:
            normalized.append(normalize(row, observed))
        except ValueError as error:
            excluded.append({"index": index, "id": row.get("id") if isinstance(row, dict) else None, "reason": str(error)})
    ids = Counter(row["id"] for row in normalized)
    keys = Counter(row["_video_key"] for row in normalized)
    baselines = []
    for row in normalized:
        reason = ("candidate-pool video excluded" if row["id"] in candidate_ids or row["_video_key"] in candidate_keys else
                  "duplicate baseline ID or video excluded" if ids[row["id"]] > 1 or keys[row["_video_key"]] > 1 else
                  "baseline views unavailable" if row["views"] is None else None)
        if reason:
            excluded.append({"id": row["id"], "reason": reason})
        else:
            baselines.append(row)
    results = []
    for candidate in candidates:
        group = group_for(candidate)
        peers = [row for row in baselines if row["creator"] == candidate["creator"] and group_for(row) == group
                 and abs((row["_published"] - candidate["_published"]).total_seconds()) <= 180 * 86400
                 and 0.5 <= row["age_days"] / candidate["age_days"] <= 2]
        peer_rates = [row["views"] / row["age_days"] for row in peers]
        peer_median = median(peer_rates) if peers else None
        views = candidate["views"]
        average = views / candidate["age_days"] if views is not None else None
        issues = []
        placeholders = unverified_fields(candidate)
        if placeholders:
            issues.append("Unverified comparison fields: " + ", ".join(placeholders) + "; reach and average rates are descriptive only, with no comparable-winner claim.")
        if views is None:
            issues.append("Public views are unavailable; no reach or rate rank.")
        if len(peers) < 5:
            issues.append("Fewer than five comparable distinct baseline peers; no channel-relative rank.")
        if peer_median == 0:
            issues.append("Median baseline rate is zero; no finite channel-relative ratio.")
        if candidate["age_cohort"] != "mature":
            issues.append("Fresh or legacy evidence is separated from mature recommendations.")
        ratio = (average / peer_median if not placeholders and candidate["age_cohort"] == "mature" and average is not None
                 and len(peers) >= 5 and peer_median and peer_median > 0 else None)
        public = {key: value for key, value in candidate.items() if not key.startswith("_")}
        public.update({"group": group,
                       "comparison_verified": not placeholders,
                       "metrics": {"views": views, "average_views_per_day": average,
                                   "like_per_view": candidate["likes"] / views if views and candidate["likes"] is not None else None,
                                   "comment_per_view": candidate["comments"] / views if views and candidate["comments"] is not None else None,
                                   "channel_outlier_ratio": ratio},
                       "baseline": {"peer_ids": sorted(row["id"] for row in peers), "n": len(peers),
                                    "median_average_views_per_day": peer_median},
                       "confidence": "observational-channel-relative" if ratio is not None else "limited-public-snapshot",
                       "issues": issues})
        results.append(public)
    groups = []
    for signature in sorted({tuple(group_for(row).values()) for row in candidates}):
        matching = [row for row in results if tuple(row["group"].values()) == signature]
        cohorts = {}
        for cohort in ("mature", "fresh", "legacy"):
            rows = [row for row in matching if row["age_cohort"] == cohort]
            def ranking(metric: str) -> list[str]:
                available = [row for row in rows if row["metrics"][metric] is not None]
                return [row["id"] for row in sorted(available, key=lambda row: (-row["metrics"][metric], row["id"]))]
            cohorts[cohort] = {"reach_ranking": ranking("views"), "average_per_day_ranking": ranking("average_views_per_day"),
                               "channel_relative_ranking": ranking("channel_outlier_ratio")}
        verified = all(row["comparison_verified"] for row in matching)
        groups.append({"group": matching[0]["group"], "comparison_verified": verified,
                       "ranking_interpretation": "comparable-public-cohort" if verified else "descriptive-public-snapshot-only",
                       "unverified_candidate_ids": [row["id"] for row in matching if not row["comparison_verified"]],
                       "cohorts": cohorts})
    return {"schema_version": 1, "observed_at": observed.isoformat(), "candidates": results, "groups": groups,
            "excluded_baselines": excluded,
            "formulas": {"average_views_per_day": "public cumulative views / elapsed days at the recorded snapshot; not recent velocity",
                         "duration_bands": "under-60s: d < 60; 60-to-180s: 60 <= d < 180; 180-to-600s: 180 <= d < 600; 600s-plus: d >= 600",
                         "channel_outlier_ratio": "candidate average_views_per_day / median comparable peer average_views_per_day; minimum five peers",
                         "peer_contract": "same creator/platform/format/metric definition/duration band; publication within 180 days; ages within factor two; all candidate and duplicate videos excluded",
                         "comparison_verified": "Nonplaceholder creator/platform/format/metric labels; not external source verification. False labels retain descriptive raw reach/rate ranks only, without channel-relative ratios",
                         "engagement": "likes or comments / public views when both are known and views > 0; not retention, unique reach or conversion"},
            "limitations": ["Observed associations do not establish why a video performed well or prove editing caused performance.",
                            "Public snapshots do not establish CTR, watch-time retention, paid distribution, saves, shares or conversions.",
                            "Do not pool platforms, formats, metric definitions or age cohorts; no universal best-video score is produced.",
                            "Averages since publication are age-adjusted proxies, not time-series growth measurements or matched causal controls."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = analyze(json.loads(args.input.read_text(encoding="utf-8-sig")))
        if args.input.resolve() == args.output.resolve():
            raise ValueError("Input and output must be different paths.")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "candidates": len(result["candidates"]), "groups": len(result["groups"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
