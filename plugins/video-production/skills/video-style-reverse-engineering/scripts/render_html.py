#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.49,<2"]
# ///
"""Capture deterministic local HTML frames through window.renderAt(seconds)."""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from playwright.sync_api import Error as PlaywrightError, sync_playwright


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(f"{Path(command[0]).name} failed: {result.stderr[-2500:].strip()}")
    return result


def render(html: Path, output: Path, width: int, height: int, fps: int, duration: float, audio: Path | None = None) -> dict:
    html, output = html.resolve(), output.resolve()
    if not html.is_file():
        raise ValueError(f"HTML input does not exist: {html}")
    if html == output:
        raise ValueError("HTML input and output must be different paths.")
    if output.suffix.lower() != ".mp4":
        raise ValueError("--output must name an .mp4 file.")
    if not (2 <= width <= 4096 and 2 <= height <= 4096) or width % 2 or height % 2:
        raise ValueError("Width and height must be even integers between 2 and 4096 for yuv420p.")
    if not 1 <= fps <= 60 or not math.isfinite(duration) or duration <= 0:
        raise ValueError("FPS must be between 1 and 60; duration must be finite and positive.")
    if duration > 18000 / fps:
        raise ValueError("The requested render must contain between 1 and 18000 frames.")
    frame_count = round(duration * fps)
    if frame_count < 1 or frame_count > 18000:
        raise ValueError("The requested render must contain between 1 and 18000 frames.")
    if not math.isclose(frame_count, duration * fps, abs_tol=1e-6, rel_tol=0):
        raise ValueError("duration * fps must be a whole frame count for an exact-duration constant-FPS video.")
    if audio is not None:
        audio = audio.resolve()
        if not audio.is_file():
            raise ValueError(f"Audio input does not exist: {audio}")
        if audio == output:
            raise ValueError("Audio input and output must be different paths.")
    for executable in ("ffmpeg", "ffprobe"):
        if shutil.which(executable) is None:
            raise ValueError(f"Install {executable} and make it available on PATH.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="html-render-", dir=output.parent) as temporary:
        work = Path(temporary)
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except PlaywrightError as error:
                raise ValueError("Chromium is unavailable. Install it with: uv run --with playwright python -m playwright install chromium") from error
            try:
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                failures: list[str] = []
                page.on("pageerror", lambda error: failures.append(str(error)))
                page.goto(html.as_uri(), wait_until="load", timeout=30000)
                page.evaluate("""() => Promise.race([
                    document.fonts.ready,
                    new Promise((_, reject) => setTimeout(() => reject(new Error('Font loading timed out')), 15000))
                ])""")
                page.evaluate("""async () => {
                    await Promise.race([Promise.all(Array.from(document.images).map(async image => {
                        if (!image.complete) await new Promise((resolve, reject) => {
                            image.addEventListener('load', resolve, {once: true});
                            image.addEventListener('error', () => reject(new Error('Image failed: ' + image.src)), {once: true});
                        });
                        if (!image.naturalWidth) throw new Error('Image failed: ' + image.src);
                        if (image.decode) await image.decode();
                    })), new Promise((_, reject) => setTimeout(() => reject(new Error('Image loading timed out')), 15000))]);
                }""")
                if not page.evaluate("() => typeof window.renderAt === 'function'"):
                    raise ValueError("HTML must expose window.renderAt(seconds), which sets every animated state from that timestamp.")
                for index in range(frame_count):
                    page.evaluate("""async t => await Promise.race([
                        Promise.resolve().then(() => window.renderAt(t)),
                        new Promise((_, reject) => setTimeout(() => reject(new Error('renderAt timed out')), 15000))
                    ])""", index / fps)
                    if failures:
                        raise ValueError("HTML execution failed: " + "; ".join(failures[:3]))
                    page.screenshot(path=str(work / f"frame-{index:06d}.png"), timeout=30000)
            finally:
                browser.close()
        encoded = work / "encoded.mp4"
        command = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-framerate", str(fps), "-i", str(work / "frame-%06d.png")]
        if audio is not None:
            command += ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-af", "apad", "-c:a", "aac", "-b:a", "192k"]
        command += ["-frames:v", str(frame_count), "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", "-y", str(encoded)]
        run(command)
        metadata = json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(encoded)]).stdout)
        video = next(s for s in metadata["streams"] if s.get("codec_type") == "video")
        measured_duration = float(video.get("duration") or metadata["format"]["duration"])
        measured_fps = float(Fraction(video["avg_frame_rate"]))
        if (video["width"], video["height"], int(video["nb_read_frames"])) != (width, height, frame_count):
            raise ValueError("Encoded dimensions or frame count differ from the render contract.")
        if not math.isclose(measured_duration, duration, abs_tol=1e-4) or not math.isclose(measured_fps, fps, abs_tol=1e-6):
            raise ValueError("Encoded duration or FPS differ from the render contract.")
        audio_streams = [s for s in metadata["streams"] if s.get("codec_type") == "audio"]
        if bool(audio_streams) != (audio is not None):
            raise ValueError("Encoded audio presence differs from the render contract.")
        if audio_streams and not math.isclose(float(audio_streams[0].get("duration", 0)), duration, abs_tol=.05):
            raise ValueError("Encoded audio duration differs from the render contract.")
        encoded.replace(output)
    return {"output": str(output), "width": width, "height": height, "fps": fps, "duration_seconds": measured_duration, "frame_count": frame_count, "has_audio": audio is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--width", required=True, type=int)
    parser.add_argument("--height", required=True, type=int)
    parser.add_argument("--fps", required=True, type=int)
    parser.add_argument("--duration", required=True, type=float)
    parser.add_argument("--audio", type=Path)
    args = parser.parse_args()
    try:
        result = render(args.html, args.output, args.width, args.height, args.fps, args.duration, args.audio)
    except (ValueError, OSError, PlaywrightError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
