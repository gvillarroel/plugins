"""Install the checksum-pinned official Open Ontologies release for this user."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

import requests

VERSION = "2.1.0"
SOURCE_COMMIT = "ef6e781c71aaccaa35c2a1cd06169f0c862d5769"
BASE = f"https://github.com/fabio-rovai/open-ontologies/releases/download/v{VERSION}"
ASSETS = {
    ("Windows", "AMD64"): (
        "open-ontologies-x86_64-pc-windows-msvc.exe",
        "1d81ff3933868bfed001b63d8bdd6f9cb3c0807389d4e3064a51a41d7d60f480",
    ),
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


def main():
    identity = (platform.system(), platform.machine())
    if identity not in ASSETS:
        raise SystemExit(f"No pinned official engine asset for {identity!r}")
    asset, expected = ASSETS[identity]
    directory = Path.home() / ".knowledge-catalog-curator/engines/open-ontologies"
    target = directory / VERSION / ("open-ontologies.exe" if os.name == "nt" else "open-ontologies")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        temporary = target.with_suffix(".download")
        digest, size = hashlib.sha256(), 0
        try:
            with requests.get(BASE + "/" + asset, stream=True, timeout=(15, 60)) as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        size += len(chunk)
                        if size > 100_000_000:
                            raise ValueError("Official engine download exceeded the 100 MB bound")
                        digest.update(chunk)
                        output.write(chunk)
            if digest.hexdigest() != expected:
                raise ValueError("The engine does not match the pinned official release checksum")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    if os.name != "nt":
        target.chmod(0o755)
    help_result = subprocess.run(
        [str(target), "--help"], capture_output=True, text=True, timeout=15, check=True
    )
    if "AI-native ontology engine" not in help_result.stdout:
        raise ValueError("The downloaded engine did not expose the expected CLI")
    license_response = requests.get(
        f"https://raw.githubusercontent.com/fabio-rovai/open-ontologies/v{VERSION}/LICENSE", timeout=20
    )
    license_response.raise_for_status()
    (target.parent / "LICENSE.txt").write_text(license_response.text, encoding="utf-8")
    manifest = {
        "provider": "open-ontologies",
        "version": VERSION,
        "binary": str(target.resolve()),
        "binary_sha256": expected,
        "release_url": BASE + "/" + asset,
        "source_commit": SOURCE_COMMIT,
        "version_source": "Checksum-pinned official release; the CLI has no --version flag",
        "cli_help_verified": True,
        "license": "MIT",
        "integrity": "SHA-256 matches the pinned official release asset; no signed-tag verification claimed",
    }
    manifest_path = directory / "runtime.json"
    pending = manifest_path.with_suffix(".pending")
    pending.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    pending.replace(manifest_path)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
