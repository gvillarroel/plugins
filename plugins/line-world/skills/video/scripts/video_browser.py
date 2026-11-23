"""Resolve the same Chromium channel for inspection and delivery."""
import os
import subprocess
import sys


def launch_browser(runtime, install_browser=False, channel=None):
    from playwright.sync_api import Error
    channel = channel or os.environ.get("LINE_WORLD_BROWSER_CHANNEL")
    if channel:
        return runtime.chromium.launch(headless=True, channel=channel, timeout=15000)
    try:
        return runtime.chromium.launch(headless=True, timeout=15000)
    except Error as exc:
        if "Executable doesn't exist" not in str(exc):
            raise
        if install_browser:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            return runtime.chromium.launch(headless=True, timeout=15000)
        if os.name == "nt":
            return runtime.chromium.launch(headless=True, channel="msedge", timeout=15000)
        raise
