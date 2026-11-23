"""Run Line World's Python and Node regression scripts through their normal local entry points."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory, TemporaryFile
import time
from caption_tracks import write_atomic


SKILLS = Path(__file__).resolve().parents[2]


def scripts(only):
    roots = [path for path in SKILLS.iterdir() if path.is_dir() and (not only or path.name in only)]
    unknown = set(only) - {path.name for path in roots}
    if unknown:
        raise ValueError("Unknown skills: " + ", ".join(sorted(unknown)))
    return sorted(path for root in roots for pattern in ("test_*.py", "*.test.mjs")
                  for path in root.rglob(pattern) if "node_modules" not in path.parts)


def execute(command, directory, environment, timeout):
    # A browser helper may inherit the output handle. Waiting on the test
    # process itself avoids blocking forever on a pipe held by that helper.
    with TemporaryFile(dir=directory) as log, subprocess.Popen(
        command, cwd=directory, env=environment, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=os.name != "nt",
    ) as worker:
        try:
            code = worker.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/pid", str(worker.pid), "/t", "/f"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                try:
                    os.killpg(worker.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if worker.poll() is None:
                worker.kill()
            worker.wait()
            raise
        log.seek(0)
        return subprocess.CompletedProcess(command, code, log.read().decode("utf-8","replace"))


def run(path, environment, timeout=300):
    started = time.monotonic()
    row = {"file": path.relative_to(SKILLS).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def attempt():
        with TemporaryDirectory(prefix="line-world-test-") as directory:
            if path.suffix == ".py":
                command = [sys.executable, "-B", str(path)]
                if path.parent.parent.name in {"hyperframes-explainer", "line-world-hyperframes"} and path.name in {
                    "test_asset_import.py", "test_composition.py", "test_explainer.py"
                }:
                    command.extend(["--work-dir", directory])
            else:
                command = [shutil.which("node") or "node", "--test", str(path)]
            completed = execute(command, directory, environment, timeout)
            if (path.suffix == ".py" and completed.returncode and "ModuleNotFoundError:" in completed.stdout
                    and "# /// script" in path.read_text(encoding="utf-8-sig") and shutil.which("uv")):
                row["environment"] = "uv script dependencies"
                command = [shutil.which("uv"), "run", "--script", str(path), *command[3:]]
                completed = execute(command, directory, environment, timeout)
            return completed

    try:
        try:
            completed = attempt()
        except subprocess.TimeoutExpired:
            row["retriedAfterTimeoutSeconds"] = timeout
            completed = attempt()
    except subprocess.TimeoutExpired:
        return {**row, "ok":False, "error":"The isolated test timed out twice.",
                "seconds":round(time.monotonic()-started,3)}
    except OSError as error:
        return {**row, "ok": False, "error": str(error)}
    output = completed.stdout
    tests = re.search(r"Ran (\d+) tests? in ", output) or re.search(r"(?m)^(?:#|ℹ) tests (\d+)\s*$", output)
    custom = re.search(r"PASS video scene contract tests: (\d+)/(\d+)", output)
    skipped = re.search(r"\bskipped=(\d+)", output) or re.search(r"(?m)^(?:#|ℹ) skipped (\d+)\s*$", output)
    row.update(ok=completed.returncode == 0, exitCode=completed.returncode, seconds=round(time.monotonic()-started, 3),
               tests=int(tests[1]) if tests else (int(custom[2]) if custom else None),
               skipped=int(skipped[1]) if skipped else 0)
    if not row["ok"]:
        row["diagnostic"] = output.strip()[-4000:]
    return row


def save(path, report):
    write_atomic(path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", action="append", default=[], help="Limit to a skill directory. Repeatable.")
    parser.add_argument("--test-timeout",type=float,default=300,
                        help="Seconds allowed per isolated test script, retried once on timeout. Zero disables the limit.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true")
    action.add_argument("--report", type=Path, help="JSON receipt, updated after every completed script.")
    args = parser.parse_args()
    if not math.isfinite(args.test_timeout) or args.test_timeout < 0:
        parser.error("--test-timeout must be finite and nonnegative.")
    selected = scripts(args.skill)
    if args.list:
        for path in selected:
            print(path.relative_to(SKILLS).as_posix())
        return 0
    if not selected:
        parser.error("There are no regression scripts in the selected skills.")
    schema = "line-world-plugin-regressions-v1"
    if args.report.exists():
        previous = json.loads(args.report.read_text(encoding="utf-8-sig"))
        if not isinstance(previous, dict) or previous.get("schema") != schema:
            parser.error("Use a new report path or a previous Line World regression receipt.")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", NO_COLOR="1")
    report = {"schema": schema, "complete": False, "ok": False, "selected": len(selected),
              "python": sys.version.split()[0], "testsReported": 0, "skipped": 0, "results": []}
    save(args.report, report)
    for path in selected:
        row = run(path, env, args.test_timeout or None)
        report["results"].append(row)
        report["testsReported"] += row.get("tests") or 0
        report["skipped"] += row.get("skipped", 0)
        report["complete"] = len(report["results"]) == len(selected)
        report["ok"] = report["complete"] and all(x["ok"] for x in report["results"])
        save(args.report, report)
        print(f"{len(report['results'])}/{len(selected)} {'OK' if row['ok'] else 'FAIL'} {row['file']}", flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
