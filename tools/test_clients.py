#!/usr/bin/env python3
"""Install marketplace plugins with the native CLIs using temporary user profiles."""

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = {
    "claude": ".claude-plugin/marketplace.json",
    "codex": ".agents/plugins/marketplace.json",
    "copilot": ".github/plugin/marketplace.json",
}


def check_payload(source, installed):
    expected = {f.relative_to(source) for f in source.rglob("*") if f.is_file()}
    actual = {f.relative_to(installed) for f in installed.rglob("*") if f.is_file()}
    if missing := expected - actual:
        raise RuntimeError(f"{installed} is missing {sorted(missing)[0]}")
    if source.resolve() != installed.resolve():
        for path in expected:
            if not filecmp.cmp(source / path, installed / path, shallow=False):
                raise RuntimeError(f"Installed content differs: {installed / path}")


def verify_pi(only, checkout):
    executable = shutil.which("pi")
    if not executable:
        raise SystemExit("Pi is required for this test")
    root = Path(checkout).resolve()
    manifest = root / "marketplace.toml"
    if not manifest.is_file():
        raise SystemExit("Pi installs packages from a local clone. Pass its path with --source.")
    overrides = tomllib.loads(manifest.read_text(encoding="utf-8")).get("clients", {})
    available = sorted(p for p in (root / "plugins").iterdir() if p.is_dir()
                       and "pi" in overrides.get(p.name, ("pi",)))
    selection = [p for p in available if only is None or p.name == only]
    if not selection:
        raise SystemExit(f"{only} is not offered by Pi")
    total = 0
    with tempfile.TemporaryDirectory(prefix="pi-plugin-qa-") as tmp:
        for plugin in selection:
            # Isolate each package so that copies with the same skill name can be tested independently.
            profile = Path(tmp) / plugin.name
            profile.mkdir()
            env = dict(os.environ, PI_CODING_AGENT_DIR=str(profile), PI_SKIP_VERSION_CHECK="1", NO_COLOR="1")
            options = dict(env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=90)
            install = subprocess.run([executable, "install", f"./plugins/{plugin.name}"],
                                     cwd=root, stdin=subprocess.DEVNULL, **options)
            if install.returncode:
                raise RuntimeError(f"Pi could not install {plugin.name}\n{install.stdout}\n{install.stderr}")
            commands = subprocess.run([executable, "--mode", "rpc", "--no-session", "--no-extensions"],
                                      cwd=tmp, input='{"id":"catalog","type":"get_commands"}\n', **options)
            replies = (json.loads(line) for line in commands.stdout.splitlines() if line.startswith("{"))
            reply = next((r for r in replies if r.get("id") == "catalog"), {})
            if commands.returncode or not reply.get("success"):
                raise RuntimeError(f"Pi skill discovery failed for {plugin.name}\n{reply}\n{commands.stderr}")
            found = {r["name"]: Path(r["sourceInfo"]["path"]).resolve() for r in reply["data"]["commands"]
                     if r.get("source") == "skill" and r["sourceInfo"].get("origin") == "package"}
            expected = {f"skill:{p.parent.name}": p.resolve() for p in (plugin / "skills").glob("*/SKILL.md")}
            if found != expected:
                raise RuntimeError(f"Pi discovery mismatch for {plugin.name}: {expected.items() ^ found.items()}")
            total += len(found)
    print(f"pi: {len(available)} available, {len(selection)} installed, {total} skill commands verified.")


def verify(client, only, marketplace_source):
    executable = shutil.which(client)
    if not executable:
        raise SystemExit(f"{client} is required for this test")
    marketplace = json.loads((ROOT / CATALOGS[client]).read_bytes())
    market = marketplace["name"]
    all_names = {p["name"] for p in marketplace["plugins"]}
    selection = sorted(all_names if only is None else all_names & {only})
    if not selection:
        raise SystemExit(f"{only} is not offered by {client}")
    with tempfile.TemporaryDirectory(prefix="plugin-qa-") as tmp:
        work = Path(tmp)
        profile = work / "profile"
        profile.mkdir()
        env = dict(os.environ, CODEX_HOME=str(profile), CLAUDE_CONFIG_DIR=str(profile),
                   COPILOT_HOME=str(profile), COPILOT_CACHE_HOME=str(work / "cache"),
                   CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1", DISABLE_AUTOUPDATER="1",
                   NO_COLOR="1", PYTHONDONTWRITEBYTECODE="1")

        def run(*args, timeout=180):
            result = subprocess.run([executable, *args], cwd=work, env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
            if result.returncode:
                raise RuntimeError(f"{client} {' '.join(args)}\n{result.stdout}\n{result.stderr}")
            return result.stdout.strip()

        def read(*args):
            return json.loads(run(*args))

        print(run("--version").splitlines()[0], flush=True)
        # A remote registration may fetch every plugin before the client returns.
        run("plugin", "marketplace", "add", marketplace_source, timeout=600)
        if client == "claude":
            read("plugin", "validate", str(ROOT / CATALOGS[client]), "--strict", "--json")
            listed = read("plugin", "list", "--available", "--json")["available"]
            found = {row["name"] for row in listed if row["marketplaceName"] == market}
        elif client == "codex":
            listed = read("plugin", "list", "--available", "--marketplace", market, "--json")
            found = {row["name"] for row in listed["available"] + listed["installed"]}
        else:
            found = {p["name"] for p in read("plugin", "marketplace", "browse", market, "--json")}
        if found != all_names:
            raise RuntimeError(f"{client} catalog mismatch: {sorted(all_names ^ found)}")

        total = 0
        for name in selection:
            selector = f"{name}@{market}"
            source = ROOT / "plugins" / name
            skills = {p.parent.name for p in (source / "skills").glob("*/SKILL.md")}
            if client == "codex":
                result = read("plugin", "add", selector, "--json")
                if result["pluginId"] != selector:
                    raise RuntimeError(f"Unexpected installed ID: {result['pluginId']}")
                installed = Path(result["installedPath"])
            elif client == "claude":
                result = read("plugin", "install", selector, "--json")
                if result.get("outcome") != "ok":
                    raise RuntimeError(str(result))
                details = run("plugin", "details", name)
                match = re.search(r"(?m)^\s*Skills \((\d+)\)\s*([^\r\n]*)", details)
                if not match or int(match[1]) != len(skills):
                    raise RuntimeError(f"{selector}: unexpected component inventory\n{details}")
                installed = next(Path(row["installPath"]) for row in read("plugin", "list", "--json")
                                 if row["id"] == selector and row["enabled"])
            else:
                run("plugin", "install", selector)
                row = next(p for p in read("plugin", "list", "--json") if p.get("name") == name and
                           p.get("marketplace") == market and p.get("enabled"))
                if row.get("source") == "live":
                    installed = Path(row["installedFrom"]) / "plugins" / name
                else:
                    installed = profile / "installed-plugins" / market / name
            if not installed.is_dir():
                raise RuntimeError(f"Missing installed folder: {installed}")
            check_payload(source, installed)
            total += len(skills)
            print(f"  {selector} ({len(skills)} skills)", flush=True)
        print(f"{client}: {len(found)} listed, {len(selection)} installed, {total} skills verified.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client", choices=sorted([*CATALOGS, "pi"]))
    parser.add_argument("--plugin", help="Install only this plugin after checking the full catalog.")
    parser.add_argument("--source", default=str(ROOT), help="Marketplace to register, for example gvillarroel/plugins. Defaults to this checkout.")
    args = parser.parse_args()
    if args.client == "pi":
        verify_pi(args.plugin, args.source)
    else:
        verify(args.client, args.plugin, args.source)
