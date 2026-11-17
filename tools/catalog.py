#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Build or check the three catalogs from the plugin folders in this checkout."""

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CLIENTS = ("codex", "claude", "copilot", "pi")
LOCATIONS = {
    "codex": ".agents/plugins/marketplace.json",
    "copilot": ".github/plugin/marketplace.json",
    "claude": ".claude-plugin/marketplace.json",
}
ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def json_text(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def skill_names(folder):
    skills = folder / "skills"
    names = []
    for child in sorted(skills.iterdir()):
        if child.name.startswith(".") or child.is_file():
            continue
        entry = child / "SKILL.md"
        text = entry.read_text(encoding="utf-8-sig")
        match = re.match(r"\A---\n(.+?)\n---(?:\n|$)", text, re.S)
        if not match:
            raise ValueError(f"No YAML frontmatter in {entry.relative_to(ROOT)}")
        header = yaml.safe_load(match[1])
        if not isinstance(header, dict):
            raise ValueError(f"Invalid skill header in {entry.relative_to(ROOT)}")
        name, description = header.get("name"), header.get("description")
        if name != child.name or not ID.fullmatch(name) or len(name) > 64:
            raise ValueError(f"Invalid skill name in {entry.relative_to(ROOT)}")
        if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
            raise ValueError(f"Invalid skill description in {entry.relative_to(ROOT)}")
        if child.is_symlink() or not entry.resolve().is_relative_to(folder):
            raise ValueError(f"Expected an independent skill copy at {entry.relative_to(ROOT)}")
        names.append(name)
    if not names:
        raise ValueError(f"No skills in {folder.relative_to(ROOT)}")
    return names


def build():
    config = tomllib.loads((ROOT / "marketplace.toml").read_text(encoding="utf-8"))
    name = config["name"]
    common = {"name": name, "owner": {"name": config["owner"]}}
    catalogs = {
        "codex": {"name": name, "interface": {"displayName": config["display_name"]}, "plugins": []},
        "copilot": {**common, "metadata": {"description": config["description"]}, "plugins": []},
        "claude": {**common, "description": config["description"], "plugins": []},
    }
    outputs = {}
    docs = ["# Plugin catalog", "",
            "Register the marketplace once in your client using the [installation guide](../README.md#install-from-github). "
            "Run Pi commands from the root of a local clone. Each skill link opens the version shipped by that plugin.", ""]
    folders = sorted(p for p in (ROOT / "plugins").iterdir() if p.is_dir())
    overrides = config.get("clients", {})
    if unknown := set(overrides) - {p.name for p in folders}:
        raise ValueError(f"Unknown plugin in marketplace.toml: {sorted(unknown)}")
    for folder in folders:
        plugin = json.loads((folder / "plugin.json").read_bytes())
        key, version, desc = plugin["name"], plugin["version"], plugin["description"]
        if key != folder.name or not ID.fullmatch(key) or not desc.strip() or not version:
            raise ValueError(f"Invalid manifest in {folder.relative_to(ROOT)}")
        clients = overrides.get(key, CLIENTS)
        if not clients or set(clients) - set(CLIENTS) or len(set(clients)) != len(clients):
            raise ValueError(f"Invalid client list for {key}: {clients}")
        if "codex" in clients and plugin.get("$schema") != SCHEMA:
            raise ValueError(f"Missing portable manifest in {key}")
        names = skill_names(folder)
        source = "./plugins/" + key
        openai = plugin.get("extensions", {}).get("com.openai", {})
        interface = openai.get("interface", {})
        entry = {"name": key, "source": source, "description": desc, "version": version}
        # Claude and the Codex compatibility manifest use common metadata at the top level.
        metadata = {k: plugin[k] for k in ("name", "version", "description", "author", "homepage",
                                            "repository", "license", "keywords") if k in plugin}
        if "codex" in clients:
            catalog_entry = {
                "name": key, "source": {"source": "local", "path": source},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": interface.get("category", "Productivity"),
            }
            catalogs["codex"]["plugins"].append(catalog_entry)
            adapter = {**metadata, **openai, "skills": "./skills/"}
            if (folder / "mcp.json").is_file():
                adapter["mcpServers"] = "./mcp.json"
            outputs[folder / ".codex-plugin/plugin.json"] = json_text(adapter)
        if "claude" in clients:
            catalogs["claude"]["plugins"].append(entry)
            outputs[folder / ".claude-plugin/plugin.json"] = json_text(metadata)
        if "copilot" in clients:
            catalogs["copilot"]["plugins"].append(entry)

        selector = f"{key}@{name}"
        commands = {
            "codex": ("Codex", f"codex plugin add {selector}"),
            "claude": ("Claude Code", f"claude plugin install {selector}"),
            "copilot": ("GitHub Copilot CLI", f"copilot plugin install {selector}"),
            "pi": ("Pi (skills)", f"pi install {source}"),
        }
        docs += [f"## {key}", "", desc, "", "| Client | Install command |", "| --- | --- |"]
        for client in clients:
            label, command = commands[client]
            docs.append(f"| {label} | `{command}` |")
        docs += ["", "**Skills**", ""]
        docs += [f"- [{s}](../plugins/{key}/skills/{s}/SKILL.md)" for s in names]
        docs.append("")

    for client, catalog in catalogs.items():
        outputs[ROOT / LOCATIONS[client]] = json_text(catalog)
    outputs[ROOT / "docs/catalog.md"] = "\n".join(docs)
    return outputs, {client: len(catalog["plugins"]) for client, catalog in catalogs.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Regenerate manifests, catalogs and the index.")
    args = parser.parse_args()
    outputs, counts = build()
    stale = []
    for path, data in outputs.items():
        content = data.encode("utf-8")
        if path.is_file() and path.read_bytes() == content:
            continue
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        else:
            stale.append(path.relative_to(ROOT).as_posix())
    if stale:
        sys.exit("Regenerate with --write:\n" + "\n".join(stale))
    print(", ".join(f"{client}: {count}" for client, count in counts.items()))


if __name__ == "__main__":
    main()
