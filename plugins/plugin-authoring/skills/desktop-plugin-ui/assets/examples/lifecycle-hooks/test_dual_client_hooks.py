#!/usr/bin/env python3
"""Verify hook discovery and execution for the same Claude Code and Codex plugin."""

import argparse
import json
from pathlib import Path
from queue import Queue
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread

from test_plugin_hooks import (
    ANSWER, MARKET, base_environment, codex_profile, install, json_file, model_stub, read_markers, run,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dual-client-hooks"
PLUGIN = FIXTURE.name


def expect(actual, expected, context):
    if actual != expected:
        raise RuntimeError(f"{context}: expected {expected!r}, found {actual!r}")


def verify_claude(command, project, env, markers, has_hook):
    details = run(command, project, env, "plugin", "details", PLUGIN)
    section = re.search(r"^\s*Hooks \((\d+)\)[ \t]*([^\r\n]*)", details, re.MULTILINE)
    if not section:
        raise RuntimeError(f"Missing hooks inventory in Claude Code plugin details: {details}")
    expect(int(section[1]), int(has_hook), "Claude Code inventory count")
    if has_hook and not section[2].startswith("SessionStart"):
        raise RuntimeError(f"Expected SessionStart in Claude Code inventory: {details}")

    log = project / "claude.log"
    run(command, project, env, "--init-only", "--debug-file", str(log))
    reads = re.findall(
        rf"Read manifest hooks for plugin {PLUGIN} \(enabled=true\): (.+)",
        log.read_text(encoding="utf-8"),
    )
    expect(reads, ["./hooks/claude.json"] if has_hook else [], "Claude Code runtime manifest hook paths")
    marks = read_markers(markers)
    expect(marks, ["claude:SessionStart"] if has_hook else [], "Claude Code execution")
    return {"registered": reads, "markers": marks}


def inspect_and_trust_codex(command, project, env, source):
    """Approve only the fixture's discovered hook in the temporary Codex profile."""
    with subprocess.Popen(
        [*command, "app-server", "--stdio"], cwd=project, env=env, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
    ) as process:
        replies = Queue()

        def read_replies():
            for line in process.stdout:
                replies.put(json.loads(line))
            replies.put(None)

        reader = Thread(target=read_replies, daemon=True)
        reader.start()

        def request(method, params=None, request_id=None):
            message = {"method": method}
            if request_id is not None:
                message.update(id=request_id, params=params)
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            if request_id is not None:
                while (reply := replies.get(timeout=20)) is not None:
                    if reply.get("id") == request_id:
                        if "error" in reply:
                            raise RuntimeError(f"{method}: {reply['error']}")
                        return reply["result"]
                raise RuntimeError(f"Codex closed the stream during {method}")

        def list_hooks(request_id):
            result = request("hooks/list", {"cwds": [str(project)]}, request_id)
            return [hook for location in result["data"] for hook in location["hooks"]]

        try:
            request("initialize", {"clientInfo": {"name": "dual-hook-probe", "version": "1.0.0"}}, 1)
            request("initialized")
            hooks = list_hooks(2)
            observed = [
                (Path(hook["sourcePath"]).name, hook["eventName"], hook["source"], hook["trustStatus"],
                 hook["pluginId"])
                for hook in hooks
            ]
            expectation = [(f"{source}.json", "sessionStart", "plugin", "untrusted", f"{PLUGIN}@{MARKET}")]
            expect(observed, expectation if source else [], "Codex inventory before approving the fixture")
            if source:
                hook = hooks[0]
                request("config/batchWrite", {
                    "edits": [{
                        "keyPath": "hooks.state", "mergeStrategy": "upsert",
                        "value": {hook["key"]: {"trusted_hash": hook["currentHash"]}},
                    }],
                    "filePath": str(Path(env["CODEX_HOME"]) / "config.toml"),
                    "reloadUserConfig": True,
                }, 3)
                expect([(item["key"], item["trustStatus"]) for item in list_hooks(4)],
                       [(hook["key"], "trusted")], "Codex inventory after approving the fixture")
            return [row[0] for row in observed]
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            reader.join(timeout=5)


def verify_codex(command, project, env, markers, source):
    args = ("exec", "--skip-git-repo-check", "--ephemeral", "--json", f"Reply {ANSWER} without using tools.")

    def turn():
        response = run(command, project, env, *args)
        if ANSWER not in response:
            raise RuntimeError(f"Missing loopback model response: {response}")
        return read_markers(markers)

    expect(turn(), [], "Codex execution before approving the fixture")
    inventory = inspect_and_trust_codex(command, project, env, source)
    marks = turn()
    expect(marks, [f"{source}:SessionStart"] if source else [], "Codex execution after hook review")
    return {"registered": inventory, "markers": marks}


def probe(client, command, model_url, case):
    with TemporaryDirectory(prefix=f"{client} dedicated hooks ") as tmp:
        root = Path(tmp)
        market = root / "market"
        plugin = market / PLUGIN
        profile = root / "profile"
        project = root / "project"
        markers = root / "markers.log"
        profile.mkdir()
        project.mkdir()
        shutil.copytree(FIXTURE, plugin)
        manifest = plugin / f".{client}-plugin" / "plugin.json"
        if case == "without own hook":
            settings = json.loads(manifest.read_bytes())
            del settings["hooks"]
            json_file(manifest, settings)
        elif case == "without Codex manifest":
            manifest.unlink()
        env = dict(
            base_environment(), HOOK_PROBE_LOG=str(markers), NO_COLOR="1", DISABLE_AUTOUPDATER="1",
            CLAUDE_CONFIG_DIR=str(profile), CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
            CODEX_HOME=str(profile), HOOK_PROBE_TOKEN="fixture-token",
        )
        version = run(command, project, env, "--version").splitlines()[0]
        if client == "codex":
            codex_profile(profile, model_url)
        else:
            run(command, project, env, "plugin", "validate", str(plugin), "--strict", "--json")
        install(command, client, market, project, env, PLUGIN)
        if client == "claude":
            evidence = verify_claude(command, project, env, markers, case == "both hooks")
        else:
            sources = {"both hooks": "codex", "without own hook": None, "without Codex manifest": "claude"}
            evidence = verify_codex(command, project, env, markers, sources[case])
        print(json.dumps({"client": client, "version": version, "case": case, **evidence}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-executable", default="claude")
    parser.add_argument("--codex-executable", default="codex")
    args = parser.parse_args()
    commands = {client: shutil.which(getattr(args, f"{client}_executable")) for client in ("claude", "codex")}
    for client, command in commands.items():
        if not command:
            parser.error(f"{client} executable not found")
    with model_stub() as model_url:
        for client, command in commands.items():
            for case in ("both hooks", "without own hook"):
                probe(client, (command,), model_url, case)
        probe("codex", (commands["codex"],), model_url, "without Codex manifest")


if __name__ == "__main__":
    main()
