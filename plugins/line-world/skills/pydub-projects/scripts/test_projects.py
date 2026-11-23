#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Verify concurrency, recovery, state conflicts and artifact ownership."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from projects import Board


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pydub-board-", dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.board = Board(self.root)
        self.board.init()

    def submit(self, key="intro", branch="main", payload=None):
        return self.board.submit(branch, key, payload or {"plan": "intro.json"})["task"]

    def test_processes_cannot_claim_the_same_work(self):
        self.submit()
        script = str(Path(__file__).with_name("projects.py"))
        def claim(index):
            result = subprocess.run([sys.executable, script, "--root", str(self.root), "claim", "--agent", f"agent-{index}"],
                                    capture_output=True, text=True, check=True, timeout=30)
            return json.loads(result.stdout)["task"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            tasks = list(pool.map(claim, range(4)))
        self.assertEqual(sum(t is not None for t in tasks), 1)
        self.assertEqual(self.board.status()["tasks"][0]["attempt"], 1)

    def test_stale_claim_cannot_finish_heartbeat_or_fail(self):
        self.submit()
        with patch("projects.time.time", return_value=100):
            first = self.board.claim("main", "a", 10)["task"]
        with patch("projects.time.time", return_value=111):
            second = self.board.claim("main", "b", 30)["task"]
            self.assertNotEqual(first["token"], second["token"])
            self.assertEqual(second["attempt"], 2)
            with self.assertRaises(ValueError):
                self.board.heartbeat(first["id"], "a", first["token"])
            with self.assertRaises(ValueError):
                self.board.finish(first["id"], "a", first["token"], error="Late")
            self.board.heartbeat(second["id"], "b", second["token"])

    def test_receipts_require_current_attempt_and_survive_restart(self):
        self.submit()
        task = self.board.claim("main", "a")["task"]
        own = self.root / task["workspace"] / "master.wav"
        own.write_bytes(b"synthetic artifact bytes")
        (self.root / "foreign.wav").write_bytes(b"foreign")
        with self.assertRaises(ValueError):
            self.board.finish(task["id"], "a", task["token"], artifacts=["foreign.wav"])
        result = self.board.finish(task["id"], "a", task["token"], artifacts=[own.relative_to(self.root).as_posix()])
        receipt = result["task"]["result"]["artifacts"][0]
        self.assertEqual(len(receipt["sha256"]), 64)
        self.assertEqual(Board(self.root).status()["tasks"][0]["result"]["artifacts"][0], receipt)
        self.assertEqual(self.board.events()["events"][-1]["kind"], "done")

    def test_idempotency_branch_isolation_and_explicit_retry(self):
        task = self.submit()
        again = self.board.submit("main", "intro", {"plan": "intro.json"})
        self.assertFalse(again["created"])
        self.assertEqual(task["id"], again["task"]["id"])
        with self.assertRaises(ValueError): self.submit(payload={"changed": True})
        self.board.branch_create("alternative")
        self.assertIsNone(self.board.claim("alternative", "b")["task"])
        self.submit(branch="alternative")
        alternative = self.board.claim("alternative", "b")["task"]
        self.assertNotEqual(alternative["id"], task["id"])
        self.board.finish(alternative["id"], "b", alternative["token"], error="Decode failed")
        self.board.retry(alternative["id"])
        with self.assertRaises(ValueError): self.board.retry(task["id"])
        self.assertEqual(self.board.claim("alternative", "c")["task"]["attempt"], 2)

    def test_competing_state_writers_observe_revision_conflict(self):
        def write(index):
            try:
                Board(self.root).state_set("shared", "delivery", {"writer": index}, 0)
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(write, range(4)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.board.state_get("shared", "delivery")["revision"], 1)
        self.board.state_set("shared", "delivery", None, 1)
        self.assertIsNone(Board(self.root).state_get("shared", "delivery")["value"])

    def test_uninitialized_reads_and_path_escape_do_not_create_state(self):
        other = Board(self.root / "uninitialized")
        with self.assertRaises(ValueError): other.status()
        self.assertFalse(other.path.exists())
        with self.assertRaises(ValueError): self.board.branch_create("../escape")
        with self.assertRaises(ValueError): self.board.state_set("shared", "key", float("nan"), 0)

    def test_init_is_idempotent_and_concurrent(self):
        def initialize(_): return Board(self.root).init()["ok"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertTrue(all(pool.map(initialize, range(4))))
        self.assertEqual(len(self.board.status()["branches"]), 1)
        connection = sqlite3.connect(self.board.path)
        try:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
