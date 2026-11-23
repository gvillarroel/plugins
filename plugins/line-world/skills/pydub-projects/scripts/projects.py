#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Coordinate local audio work using atomic claims and explicit JSON state."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value):
        raise ValueError("Use a lowercase identifier of at most 64 letters, digits, hyphens or underscores.")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def contained(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Path must stay inside the project root.")
    return path


def file_receipt(root, workspace, value):
    path = contained(root, value)
    if not path.is_relative_to(workspace) or not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Artifacts must be nonempty regular files inside this claim's workspace.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size,
            "sha256": digest.hexdigest()}


SCHEMA = """
CREATE TABLE meta(version INTEGER NOT NULL);
INSERT INTO meta VALUES(1);
CREATE TABLE branches(id TEXT PRIMARY KEY, parent TEXT REFERENCES branches(id), created REAL NOT NULL);
CREATE TABLE tasks(
 id TEXT PRIMARY KEY, branch TEXT NOT NULL REFERENCES branches(id), task_key TEXT NOT NULL,
 payload TEXT NOT NULL, status TEXT NOT NULL, agent TEXT, token TEXT, lease_until REAL,
 attempt INTEGER NOT NULL DEFAULT 0, workspace TEXT, result TEXT,
 created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(branch, task_key));
CREATE TABLE state(namespace TEXT NOT NULL, key TEXT NOT NULL, revision INTEGER NOT NULL,
 value TEXT NOT NULL, PRIMARY KEY(namespace, key));
CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, time REAL NOT NULL,
 kind TEXT NOT NULL, task TEXT, detail TEXT NOT NULL);
"""


class Board:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = contained(self.root, ".pydub/state.sqlite3")

    def init(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            # Executescript must not implicitly commit a partially initialized
            # schema. Its explicit transaction serializes concurrent initializers.
            try:
                connection.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "\nCOMMIT;")
            except sqlite3.OperationalError:
                if connection.in_transaction:
                    connection.rollback()
                if connection.execute("SELECT version FROM meta").fetchone() != (1,):
                    raise ValueError("Unsupported or incomplete board schema.")
            connection.execute("INSERT OR IGNORE INTO branches VALUES(?,?,?)", ("main", None, time.time()))
        finally:
            connection.close()
        return {"ok": True, "root": str(self.root), "schema_version": 1}

    @contextmanager
    def transaction(self):
        if not self.path.is_file():
            raise ValueError("Project is uninitialized; run init first.")
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            if tuple(connection.execute("SELECT version FROM meta").fetchone()) != (1,):
                raise ValueError("Unsupported board schema.")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def event(db, kind, task=None, **detail):
        db.execute("INSERT INTO events(time,kind,task,detail) VALUES(?,?,?,?)",
                   (time.time(), kind, task, canonical(detail)))

    @staticmethod
    def task(row):
        if row is None:
            return None
        value = dict(row)
        value["payload"] = json.loads(value["payload"])
        value["result"] = json.loads(value["result"]) if value["result"] is not None else None
        return value

    def branch_create(self, branch, parent="main"):
        identifier(branch)
        identifier(parent)
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM branches WHERE id=?", (parent,)).fetchone():
                raise ValueError("Parent branch does not exist.")
            old = db.execute("SELECT parent FROM branches WHERE id=?", (branch,)).fetchone()
            if old:
                if old[0] != parent:
                    raise ValueError("Branch exists with different lineage.")
            else:
                db.execute("INSERT INTO branches VALUES(?,?,?)", (branch, parent, time.time()))
                self.event(db, "branch-created", branch=branch, parent=parent)
        return {"ok": True, "branch": branch, "parent": parent}

    def submit(self, branch, key, payload):
        identifier(branch)
        identifier(key)
        encoded = canonical(payload)
        with self.transaction() as db:
            old = db.execute("SELECT * FROM tasks WHERE branch=? AND task_key=?", (branch, key)).fetchone()
            if old:
                if old["payload"] != encoded:
                    raise ValueError("The task key already has a different payload.")
                return {"ok": True, "created": False, "task": self.task(old)}
            task_id = uuid.uuid4().hex
            now = time.time()
            db.execute("INSERT INTO tasks(id,branch,task_key,payload,status,created,updated) VALUES(?,?,?,?,?,?,?)",
                       (task_id, branch, key, encoded, "queued", now, now))
            self.event(db, "submitted", task_id, branch=branch, key=key)
            task = self.task(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())
        return {"ok": True, "created": True, "task": task}

    @staticmethod
    def lease(seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 86400:
            raise ValueError("Lease seconds must be an integer from 1 through 86400.")
        return seconds

    def claim(self, branch, agent, lease_seconds=300):
        identifier(branch)
        identifier(agent)
        self.lease(lease_seconds)
        with self.transaction() as db:
            now = time.time()
            old = db.execute("SELECT * FROM tasks WHERE branch=? AND (status='queued' OR (status='running' AND lease_until<=?)) ORDER BY created,id LIMIT 1",
                             (branch, now)).fetchone()
            if old is None:
                return {"ok": True, "task": None}
            token = uuid.uuid4().hex
            workspace = f"work/{branch}/{agent}/{old['id']}/{token}"
            contained(self.root, workspace).mkdir(parents=True, exist_ok=False)
            db.execute("UPDATE tasks SET status='running',agent=?,token=?,lease_until=?,attempt=attempt+1,workspace=?,result=NULL,updated=? WHERE id=?",
                       (agent, token, now + lease_seconds, workspace, now, old["id"]))
            self.event(db, "claimed", old["id"], agent=agent, token=token, previous_status=old["status"])
            task = self.task(db.execute("SELECT * FROM tasks WHERE id=?", (old["id"],)).fetchone())
        return {"ok": True, "task": task}

    @staticmethod
    def owned(db, task_id, agent, token):
        task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if (task is None or task["status"] != "running" or task["agent"] != agent
                or task["token"] != token or task["lease_until"] <= time.time()):
            raise ValueError("Claim is stale, expired, finished or owned by another agent.")
        return task

    def heartbeat(self, task_id, agent, token, lease_seconds=300):
        self.lease(lease_seconds)
        with self.transaction() as db:
            self.owned(db, task_id, agent, token)
            until = time.time() + lease_seconds
            db.execute("UPDATE tasks SET lease_until=?,updated=? WHERE id=?", (until, time.time(), task_id))
        return {"ok": True, "lease_until": until}

    def finish(self, task_id, agent, token, artifacts=None, error=None):
        with self.transaction() as db:
            task = self.owned(db, task_id, agent, token)
            if error is None:
                if not artifacts:
                    raise ValueError("Completion needs at least one verified artifact.")
                workspace = contained(self.root, task["workspace"])
                receipts = [file_receipt(self.root, workspace, name) for name in artifacts]
                if len({r["path"] for r in receipts}) != len(receipts):
                    raise ValueError("Artifact paths must be unique.")
                outcome = {"artifacts": receipts}
                status = "done"
            else:
                if not isinstance(error, str) or not error.strip():
                    raise ValueError("Failure needs a nonempty error.")
                outcome = {"error": error}
                status = "failed"
            # Hashing can take time; recheck the fence before committing.
            self.owned(db, task_id, agent, token)
            db.execute("UPDATE tasks SET status=?,result=?,lease_until=NULL,updated=? WHERE id=?",
                       (status, canonical(outcome), time.time(), task_id))
            self.event(db, status, task_id, agent=agent, token=token, result=outcome)
            task = self.task(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())
        return {"ok": True, "task": task}

    def retry(self, task_id):
        with self.transaction() as db:
            changed = db.execute("UPDATE tasks SET status='queued',agent=NULL,token=NULL,lease_until=NULL,updated=? WHERE id=? AND status='failed'",
                                 (time.time(), task_id)).rowcount
            if not changed:
                raise ValueError("Only a failed task can be retried.")
            self.event(db, "retried", task_id)
        return {"ok": True, "task_id": task_id}

    def state_get(self, namespace, key):
        identifier(namespace)
        identifier(key)
        with self.transaction() as db:
            row = db.execute("SELECT revision,value FROM state WHERE namespace=? AND key=?", (namespace, key)).fetchone()
        return {"ok": True, "namespace": namespace, "key": key,
                "revision": row[0] if row else 0, "value": json.loads(row[1]) if row else None}

    def state_set(self, namespace, key, value, expected_revision):
        identifier(namespace)
        identifier(key)
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ValueError("Expected revision must be a nonnegative integer.")
        encoded = canonical(value)
        with self.transaction() as db:
            old = db.execute("SELECT revision FROM state WHERE namespace=? AND key=?", (namespace, key)).fetchone()
            if (old[0] if old else 0) != expected_revision:
                raise ValueError("Shared state revision conflict; reread before reconciling.")
            revision = expected_revision + 1
            db.execute("INSERT INTO state VALUES(?,?,?,?) ON CONFLICT(namespace,key) DO UPDATE SET revision=excluded.revision,value=excluded.value",
                       (namespace, key, revision, encoded))
            self.event(db, "state-updated", namespace=namespace, key=key, revision=revision)
        return {"ok": True, "revision": revision, "value": value}

    def status(self, branch=None):
        if branch is not None:
            identifier(branch)
        with self.transaction() as db:
            tasks = db.execute("SELECT * FROM tasks" + (" WHERE branch=?" if branch else "") + " ORDER BY created,id",
                               (branch,) if branch else ()).fetchall()
            branches = [dict(r) for r in db.execute("SELECT * FROM branches ORDER BY id")]
        return {"ok": True, "branches": branches, "tasks": [self.task(r) for r in tasks]}

    def events(self, after=0, limit=100):
        if not isinstance(after, int) or isinstance(after, bool) or after < 0:
            raise ValueError("after must be a nonnegative event sequence.")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit must be from 1 through 1000.")
        with self.transaction() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?", (after, limit))]
        for row in rows:
            row["detail"] = json.loads(row["detail"])
        return {"ok": True, "events": rows, "next_after": rows[-1]["seq"] if rows else after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    p = sub.add_parser("branch-create"); p.add_argument("--branch", required=True); p.add_argument("--parent", default="main")
    p = sub.add_parser("submit"); p.add_argument("--branch", default="main"); p.add_argument("--key", required=True); p.add_argument("--payload-file", required=True)
    p = sub.add_parser("claim"); p.add_argument("--branch", default="main"); p.add_argument("--agent", required=True); p.add_argument("--lease-seconds", type=int, default=300)
    for command in ("heartbeat", "complete", "fail"):
        p = sub.add_parser(command)
        p.add_argument("--task", required=True); p.add_argument("--agent", required=True); p.add_argument("--token", required=True)
        if command == "heartbeat": p.add_argument("--lease-seconds", type=int, default=300)
        if command == "complete": p.add_argument("--artifact", action="append", required=True)
        if command == "fail": p.add_argument("--error", required=True)
    p = sub.add_parser("retry"); p.add_argument("--task", required=True)
    p = sub.add_parser("status"); p.add_argument("--branch")
    p = sub.add_parser("events"); p.add_argument("--after", type=int, default=0); p.add_argument("--limit", type=int, default=100)
    for command in ("state-get", "state-set"):
        p = sub.add_parser(command); p.add_argument("--namespace", required=True); p.add_argument("--key", required=True)
        if command == "state-set":
            p.add_argument("--value-file", required=True); p.add_argument("--expected-revision", type=int, required=True)
    args = parser.parse_args()
    try:
        board = Board(args.root)
        def load(value): return json.loads(contained(board.root, value).read_text(encoding="utf-8-sig"))
        if args.command == "init": result = board.init()
        elif args.command == "branch-create": result = board.branch_create(args.branch, args.parent)
        elif args.command == "submit": result = board.submit(args.branch, args.key, load(args.payload_file))
        elif args.command == "claim": result = board.claim(args.branch, args.agent, args.lease_seconds)
        elif args.command == "heartbeat": result = board.heartbeat(args.task, args.agent, args.token, args.lease_seconds)
        elif args.command == "complete": result = board.finish(args.task, args.agent, args.token, artifacts=args.artifact)
        elif args.command == "fail": result = board.finish(args.task, args.agent, args.token, error=args.error)
        elif args.command == "retry": result = board.retry(args.task)
        elif args.command == "state-get": result = board.state_get(args.namespace, args.key)
        elif args.command == "state-set": result = board.state_set(args.namespace, args.key, load(args.value_file), args.expected_revision)
        elif args.command == "status": result = board.status(args.branch)
        else: result = board.events(args.after, args.limit)
        print(json.dumps(result, allow_nan=False)); return 0
    except (ValueError, OSError, TypeError, sqlite3.Error) as error:
        print(json.dumps({"ok": False, "error": str(error)})); return 2


if __name__ == "__main__":
    raise SystemExit(main())
