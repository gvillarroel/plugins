#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Exercise comparable-cohort ranking, evidence exclusions and missing metrics."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("rank_references.py")
SPEC = importlib.util.spec_from_file_location("rank_references", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
OBSERVED = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


def row(identifier: str, views: int | None = 3000, age: float = 30, creator: str = "small", **extra) -> dict:
    record = {"id": identifier, "url": f"https://www.youtube.com/watch?v={identifier}", "title": identifier,
              "creator": creator, "platform": "youtube", "format": "long", "metric_definition": "public-view-count",
              "published_at": (OBSERVED - timedelta(days=age)).isoformat(), "duration_seconds": 45, "views": views}
    record.update(extra)
    return record


def fixture() -> dict:
    return {"observed_at": OBSERVED.isoformat(), "candidates": [row("alpha", 30000), row("big", 900000, creator="large")],
            "baselines": [row(f"s{i}", 3000) for i in range(5)] + [row(f"b{i}", 1200000, creator="large") for i in range(5)]}


class RankingTests(unittest.TestCase):
    def test_separate_reach_and_channel_relative_order(self):
        result = MODULE.analyze(fixture())
        mature = result["groups"][0]["cohorts"]["mature"]
        self.assertEqual(mature["reach_ranking"], ["big", "alpha"])
        self.assertEqual(mature["channel_relative_ranking"], ["alpha", "big"])
        self.assertEqual(result["candidates"][0]["metrics"]["channel_outlier_ratio"], 10)
        self.assertEqual(result["candidates"][1]["metrics"]["channel_outlier_ratio"], .75)

    def test_comparison_groups_are_not_pooled(self):
        data = fixture()
        data["candidates"] += [row("short", format="short"), row("platform", platform="vimeo"),
                               row("metric", metric_definition="starts-and-replays"), row("duration", duration_seconds=60)]
        result = MODULE.analyze(data)
        self.assertEqual(len(result["groups"]), 5)
        self.assertTrue(all(item["baseline"]["n"] == 0 for item in result["candidates"][2:]))

    def test_target_and_duplicate_baseline_videos_do_not_leak(self):
        data = fixture()
        data["baselines"] += [deepcopy(data["candidates"][0]), row("s0"), row("alias", url="https://youtu.be/s1?si=tracking")]
        result = MODULE.analyze(data)
        alpha = result["candidates"][0]
        self.assertEqual(alpha["baseline"]["n"], 3)
        self.assertIsNone(alpha["metrics"]["channel_outlier_ratio"])
        self.assertEqual(len(result["excluded_baselines"]), 5)

    def test_duration_boundaries_are_explicit(self):
        data = {"observed_at": OBSERVED.isoformat(), "candidates": [row(f"x{i}", duration_seconds=duration)
                for i, duration in enumerate([59.9, 60, 179.9, 180, 599.9, 600])]}
        result = MODULE.analyze(data)
        self.assertEqual([item["duration_band"] for item in result["candidates"]],
                         ["under-60s", "60-to-180s", "60-to-180s", "180-to-600s", "180-to-600s", "600s-plus"])

    def test_placeholder_comparison_fields_never_create_relative_winners(self):
        for field, placeholder in [("platform", "unknown"), ("format", "unknown"), ("metric_definition", "unverified"),
                                   ("creator", "unspecified"), ("format", "n/a"), ("metric_definition", "n-a")]:
            data = {"observed_at": OBSERVED.isoformat(), "candidates": [row("target", 30000, **{field: placeholder})],
                    "baselines": [row(f"peer{i}", **{field: placeholder}) for i in range(5)]}
            with self.subTest(field=field, placeholder=placeholder):
                result = MODULE.analyze(data)
                target, group = result["candidates"][0], result["groups"][0]
                self.assertEqual(target["baseline"]["n"], 5)
                self.assertFalse(target["comparison_verified"])
                self.assertIsNone(target["metrics"]["channel_outlier_ratio"])
                self.assertIn(field, " ".join(target["issues"]))
                self.assertFalse(group["comparison_verified"])
                self.assertEqual(group["ranking_interpretation"], "descriptive-public-snapshot-only")
                self.assertEqual(group["cohorts"]["mature"]["reach_ranking"], ["target"])
                self.assertEqual(group["cohorts"]["mature"]["channel_relative_ranking"], [])

    def test_explicit_custom_metric_definition_remains_eligible(self):
        data = fixture()
        for item in data["candidates"] + data["baselines"]:
            item["metric_definition"] = "creator-export-qualified-plays-v2"
        result = MODULE.analyze(data)
        self.assertTrue(result["candidates"][0]["comparison_verified"])
        self.assertEqual(result["candidates"][0]["metrics"]["channel_outlier_ratio"], 10)

    def test_missing_metrics_remain_unknown_and_zero_is_known(self):
        data = {"observed_at": OBSERVED.isoformat(), "candidates": [row("hidden", None), row("zero", 0, likes=0)]}
        result = MODULE.analyze(data)
        hidden, zero = result["candidates"]
        self.assertIsNone(hidden["metrics"]["views"])
        self.assertIsNone(hidden["metrics"]["average_views_per_day"])
        self.assertEqual(zero["metrics"]["average_views_per_day"], 0)
        self.assertIsNone(zero["metrics"]["like_per_view"])
        self.assertEqual(result["groups"][0]["cohorts"]["mature"]["reach_ranking"], ["zero"])

    def test_fresh_and_legacy_are_separate(self):
        data = {"observed_at": OBSERVED.isoformat(), "candidates": [row("fresh", age=1), row("mature", age=7), row("edge", age=730), row("legacy", age=731)]}
        result = MODULE.analyze(data)
        cohorts = result["groups"][0]["cohorts"]
        self.assertEqual(cohorts["fresh"]["reach_ranking"], ["fresh"])
        self.assertEqual(cohorts["legacy"]["reach_ranking"], ["legacy"])
        self.assertEqual(set(cohorts["mature"]["reach_ranking"]), {"edge", "mature"})

    def test_peer_age_publication_and_snapshot_bounds(self):
        data = fixture()
        data["baselines"] = [row("young", age=14), row("old", age=61), row("far", age=240),
                             row("stale", observed_at=(OBSERVED - timedelta(days=2)).isoformat()), row("future", age=-1)]
        result = MODULE.analyze(data)
        self.assertEqual(result["candidates"][0]["baseline"]["n"], 0)
        self.assertEqual(len(result["excluded_baselines"]), 2)

    def test_zero_median_never_yields_infinite_ratio(self):
        data = fixture()
        for peer in data["baselines"]:
            peer["views"] = 0
        result = MODULE.analyze(data)
        self.assertIsNone(result["candidates"][0]["metrics"]["channel_outlier_ratio"])
        self.assertIn("zero", " ".join(result["candidates"][0]["issues"]))

    def test_bad_candidate_records_fail_explicitly(self):
        for change in [{"views": -1}, {"likes": True}, {"comments": "2"}, {"duration_seconds": float("inf")},
                       {"published_at": "not-a-date"}, {"published_at": OBSERVED.isoformat()}, {"format": ""}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                MODULE.analyze({"observed_at": OBSERVED.isoformat(), "candidates": [row("x", **change)]})
        data = fixture()
        data["candidates"].append(deepcopy(data["candidates"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            MODULE.analyze(data)

    def test_bad_baseline_records_are_auditable_exclusions(self):
        data = fixture()
        data["baselines"] += [row("missing", None), row("negative", -2), None]
        result = MODULE.analyze(data)
        self.assertEqual(len(result["excluded_baselines"]), 3)
        self.assertEqual(result["candidates"][0]["baseline"]["n"], 5)

    def test_cli_exact_path_and_failure_preserves_existing_output(self):
        with tempfile.TemporaryDirectory(prefix="rank-test-", dir=Path.cwd()) as temporary:
            folder = Path(temporary)
            source, output = folder / "input with spaces.json", folder / "nested" / "rank.json"
            source.write_text(json.dumps(fixture()), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            previous = output.read_bytes()
            source.write_text("{}", encoding="utf-8")
            failed = subprocess.run([sys.executable, str(SCRIPT), str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(output.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
