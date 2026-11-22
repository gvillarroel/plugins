#!/usr/bin/env python3
"""Check lifecycle hooks from the same plugin in isolated CLI profiles."""

import argparse
from base64 import b64encode
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from secrets import token_urlsafe
import shutil
import socket
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep
from urllib.request import Request, urlopen


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "multi-client-hooks"
MARKET = "hook-probe-market"
PLUGIN = FIXTURE.name
ANSWER = "fixture-ok"
AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
ENV_KEYS = {
    "APPDATA", "COMSPEC", "HOME", "LOCALAPPDATA", "PATH", "PATHEXT", "PROGRAMDATA",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "SYSTEMDRIVE", "SYSTEMROOT",
    "TEMP", "TMP", "USERPROFILE", "WINDIR",
}


def json_file(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def use_portable_manifest(plugin):
    path = plugin / "plugin.json"
    manifest = json.loads(path.read_bytes())
    manifest.pop("hooks")
    manifest["$schema"] = AGENT_PLUGINS_SCHEMA
    manifest["extensions"] = {"com.openai": {"hooks": "./hooks/codex.json"}}
    json_file(path, manifest)


class ModelStub(BaseHTTPRequestHandler):
    """Reply to the synthetic prompt locally over Chat Completions or Responses."""

    def log_message(self, *_args):
        pass

    def send_body(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/v1/models":
            self.send_error(404)
            return
        body = {"object": "list", "data": [{"id": "gpt-4o-mini", "object": "model", "created": 0,
                                           "owned_by": "probe"}]}
        self.send_body(json.dumps(body).encode(), "application/json")

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/v1/chat/completions":
            common = {"id": "chatcmpl-probe", "created": 1, "model": "gpt-4o-mini",
                      "object": "chat.completion.chunk"}
            chunks = [
                {**common, "choices": [{"index": 0, "delta": {"role": "assistant", "content": ANSWER},
                                        "finish_reason": None}]},
                {**common, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ]
            body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        elif self.path == "/v1/responses":
            message = {"id": "msg_probe", "type": "message", "status": "completed", "role": "assistant",
                       "content": [{"type": "output_text", "text": ANSWER, "annotations": []}]}
            response = {"id": "resp_probe", "object": "response", "created_at": 0, "status": "completed",
                        "output": [message], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
            events = [
                {"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
                {"type": "response.output_item.added", "output_index": 0,
                 "item": {**message, "status": "in_progress", "content": []}},
                {"type": "response.output_text.delta", "output_index": 0, "content_index": 0,
                 "item_id": "msg_probe", "delta": ANSWER},
                {"type": "response.output_item.done", "output_index": 0, "item": message},
                {"type": "response.completed", "response": response},
            ]
            body = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
        else:
            self.send_error(404)
            return
        self.send_body(body.encode(), "text/event-stream")


@contextmanager
def model_stub():
    with ThreadingHTTPServer(("127.0.0.1", 0), ModelStub) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/v1"
        finally:
            server.shutdown()
            thread.join()


def run(command, cwd, env, *args):
    result = subprocess.run([*command, *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, encoding="utf-8", errors="replace", timeout=45)
    if result.returncode:
        raise RuntimeError(f"{command} {args} exited {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def read_markers(path):
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def report(client, version, layout, markers, expected):
    print(json.dumps({"client": client, "version": version, "layout": layout, "markers": markers}), flush=True)
    if markers not in expected:
        raise RuntimeError(f"{client} {layout}: expected one of {expected}, found {markers}")


def install(command, client, market, project, env, plugin=PLUGIN):
    locations = {
        "claude": ".claude-plugin/marketplace.json",
        "codex": ".agents/plugins/marketplace.json",
        "copilot": ".github/plugin/marketplace.json",
    }
    entry = {"name": plugin, "source": f"./{plugin}"}
    index = {"name": MARKET, "owner": {"name": "Local probe"}, "plugins": [entry]}
    if client == "codex":
        entry["source"] = {"source": "local", "path": entry["source"]}
        entry["policy"] = {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    json_file(market / locations[client], index)
    run(command, project, env, "plugin", "marketplace", "add", str(market))
    action = "add" if client == "codex" else "install"
    run(command, project, env, "plugin", action, f"{plugin}@{MARKET}")


def base_environment():
    return {key: value for key, value in os.environ.items() if key.upper() in ENV_KEYS}


def codex_profile(profile, model_url):
    (profile / "config.toml").write_text(f"""
model = "probe-model"
model_provider = "local_probe"
web_search = "disabled"
approval_policy = "never"
sandbox_mode = "read-only"

[model_providers.local_probe]
name = "Local fixture"
base_url = "{model_url}"
env_key = "HOOK_PROBE_TOKEN"
wire_api = "responses"
request_max_retries = 0
stream_max_retries = 0

[features]
plugin_discovery_prefetch = false
remote_plugin = false

[analytics]
enabled = false
""".lstrip(), encoding="utf-8")


def verify_manifest_client(client, command, model_url, layout):
    with TemporaryDirectory(prefix=f"{client} hook probe ") as temporary:
        root = Path(temporary)
        market = root / "market"
        plugin = market / PLUGIN
        project = root / "project"
        profile = root / "profile"
        marker_file = root / "events.txt"
        project.mkdir()
        profile.mkdir()
        shutil.copytree(FIXTURE, plugin)
        if layout == "portable":
            use_portable_manifest(plugin)
        env = base_environment()
        env.update(
            CODEX_HOME=str(profile), CLAUDE_CONFIG_DIR=str(profile), COPILOT_HOME=str(profile),
            COPILOT_CACHE_HOME=str(root / "copilot-cache"), HOOK_PROBE_LOG=str(marker_file),
            HOOK_PROBE_TOKEN="fixture-token", COPILOT_PROVIDER_BASE_URL=model_url,
            COPILOT_PROVIDER_TYPE="openai", COPILOT_MODEL="gpt-4o-mini",
            CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1", DISABLE_AUTOUPDATER="1",
            DISABLE_TELEMETRY="1", NO_COLOR="1",
        )
        version = run(command, project, env, "--version").splitlines()[0]
        if client == "codex":
            codex_profile(profile, model_url)
        install(command, client, market, project, env)
        prompt = f"Reply {ANSWER} without using tools."
        if client == "claude":
            run(command, project, env, "--init-only")
            expected = [["claude:SessionStart"]]
        elif client == "copilot":
            response = run(command, project, env, "-p", prompt)
            if ANSWER not in response:
                raise RuntimeError(f"Missing loopback model response: {response}")
            expected = [["copilot:sessionStart"]]
        else:
            args = ("--skip-git-repo-check", "--ephemeral", "--json", prompt)
            response = run(command, project, env, "exec", *args)
            if ANSWER not in response:
                raise RuntimeError(f"Missing loopback model response: {response}")
            report(client, version, f"{layout} without trust", read_markers(marker_file), [[]])
            # This override applies only to the disposable profile and this fixture's own hook.
            response = run(command, project, env, "exec", "--dangerously-bypass-hook-trust", *args)
            if ANSWER not in response:
                raise RuntimeError(f"Missing loopback model response: {response}")
            expected = [["codex:SessionStart"]]
        if layout == "portable" and client != "claude":
            expected.append([])
        report(client, version, layout, read_markers(marker_file), expected)


def opencode_request(base_url, path, headers, data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = Request(base_url + path, body, headers)
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def wait_for_server(server, log):
    deadline = monotonic() + 20
    while monotonic() < deadline and server.poll() is None:
        if "listening on " in log.read_text(encoding="utf-8", errors="replace"):
            return
        sleep(0.1)
    raise RuntimeError("OpenCode did not start listening")


def wait_for_opencode_plugin(base_url, headers):
    deadline = monotonic() + 15
    while monotonic() < deadline:
        inventory = opencode_request(base_url, "/api/plugin", headers)["data"]
        if any(entry["id"] == PLUGIN and entry["state"]["status"] == "active" for entry in inventory):
            return
        sleep(0.05)
    raise RuntimeError("OpenCode did not activate the configured plugin")


def stop_server(server):
    if server.poll() is None:
        if os.name == "nt":
            # A Windows shim may own child processes that still have the database open.
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(server.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if server.poll() is None:
            server.kill()
    server.wait(timeout=10)


def verify_opencode(command, layout):
    with TemporaryDirectory(prefix="opencode hook probe ") as temporary:
        root = Path(temporary)
        project = root / "project"
        marker_file = root / "events.txt"
        log = root / "server.log"
        profile = root / "profile"
        shutil.copytree(FIXTURE, project)
        if layout != "legacy with config":
            use_portable_manifest(project)
        enabled = layout != "manifest only"
        password = token_urlsafe()
        env = base_environment()
        env.update(
            OPENCODE_TEST_HOME=str(profile), OPENCODE_PASSWORD=password,
            OPENCODE_SERVER_PASSWORD=password, OPENCODE_DISABLE_AUTOUPDATE="1",
            OPENCODE_DISABLE_MODELS_FETCH="1", OPENCODE_DISABLE_DEFAULT_PLUGINS="1",
            OPENCODE_DB=":memory:", HOOK_PROBE_LOG=str(marker_file),
        )
        for directory in ("CONFIG", "CACHE", "STATE", "DATA"):
            env[f"XDG_{directory}_HOME"] = str(profile / directory.lower())
        version = run(command, project, env, "--version")
        v2 = version.removeprefix("opencode ").removeprefix("v").startswith("2.")
        if enabled:
            config = {"plugins": ["./hooks/opencode-v2"]} if v2 else {"plugin": ["./hooks/opencode-v1.mjs"]}
            json_file(project / "opencode.json", config)
        with socket.socket() as port_probe:
            port_probe.bind(("127.0.0.1", 0))
            port = port_probe.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        auth = b64encode(f"opencode:{password}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        with log.open("wb") as output, subprocess.Popen(
            [*command, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
            cwd=project, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
        ) as server:
            try:
                wait_for_server(server, log)
                if v2:
                    if enabled:
                        wait_for_opencode_plugin(base_url, headers)
                    session = opencode_request(base_url, "/api/session", headers, {"title": "Hook probe"})
                    if not session["data"].get("id"):
                        raise RuntimeError("OpenCode did not create a session")
                    marker = "opencode-v2:session.created"
                else:
                    session = opencode_request(base_url, "/session", headers, {"title": "Hook probe"})
                    if not session.get("id"):
                        raise RuntimeError("OpenCode did not create a session")
                    marker = "opencode:session.created"
                if enabled:
                    deadline = monotonic() + 5
                    while monotonic() < deadline and not marker_file.exists():
                        sleep(0.1)
            finally:
                stop_server(server)
        report("opencode", version, layout, read_markers(marker_file), [[marker] if enabled else []])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client", choices=("claude", "codex", "copilot", "opencode"))
    parser.add_argument("--executable", help="Use a specific binary or CLI shim instead of PATH")
    args = parser.parse_args()
    executable = shutil.which(args.executable or args.client)
    if not executable:
        parser.error(f"CLI not found: {args.executable or args.client}")
    if args.client == "opencode":
        for layout in ("manifest only", "portable with config", "legacy with config"):
            verify_opencode((executable,), layout)
    else:
        command = (executable, "--no-auto-update") if args.client == "copilot" else (executable,)
        with model_stub() as model_url:
            for layout in ("portable", "legacy"):
                verify_manifest_client(args.client, command, model_url, layout)


if __name__ == "__main__":
    main()
