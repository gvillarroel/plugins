#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=10.1,<13"]
# ///
"""Sample a local reference video and label a contact sheet with decoded timestamps."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(f"{Path(command[0]).name} failed: {result.stderr[-2500:].strip()}")
    return result


def probe(source: Path) -> tuple[dict, dict, float, float]:
    metadata = json.loads(run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)
    ]).stdout)
    video = next((s for s in metadata.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("The input contains no video stream.")
    duration = float(video.get("duration") or metadata.get("format", {}).get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("A finite, positive video duration is required.")
    try:
        fps = float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ValueError, ZeroDivisionError):
        fps = 0
    if not math.isfinite(fps) or fps <= 0:
        fps = 25.0
    return metadata, video, duration, fps


def inspect(source: Path, output_dir: Path, samples: int) -> dict:
    source = source.resolve()
    output_dir = output_dir.resolve()
    if not source.is_file():
        raise ValueError(f"Input video does not exist: {source}")
    if not 1 <= samples <= 60:
        raise ValueError("--samples must be between 1 and 60.")
    for executable in ("ffmpeg", "ffprobe"):
        if shutil.which(executable) is None:
            raise ValueError(f"Install {executable} and make it available on PATH.")
    metadata, video, duration, fps = probe(source)
    reported_duration = duration
    start_time = float(video.get("start_time") or 0)
    tail = json.loads(run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals",
        f"{max(0.0, start_time + duration - 3):.6f}%", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time,duration_time", "-of", "json", str(source),
    ]).stdout)
    decoded_times = [float(frame["best_effort_timestamp_time"]) - start_time
                     for frame in tail.get("frames", []) if "best_effort_timestamp_time" in frame]
    if not decoded_times:
        raise ValueError("The video has no decodable frame near its reported end.")
    last = max(0.0, max(decoded_times))
    decoded_end = max(float(frame["best_effort_timestamp_time"]) - start_time +
                      float(frame.get("duration_time") or 1 / fps)
                      for frame in tail["frames"] if "best_effort_timestamp_time" in frame)
    duration = max(duration, decoded_end)
    requested = [last * i / (samples - 1) if samples > 1 else 0.0 for i in range(samples)]
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, timestamp in enumerate(requested, 1):
        filename = f"frame-{index:03d}.jpg"
        target = frames_dir / filename
        result = run([
            "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "info", "-ss", f"{timestamp:.9f}",
            "-copyts", "-i", str(source), "-map", "0:v:0", "-frames:v", "1", "-vf", "showinfo",
            "-q:v", "2", "-update", "1", "-y", str(target),
        ])
        decoded = re.search(r"\bn:\s*0\s+pts:\s*-?\d+\s+pts_time:([-+\d.eE]+)", result.stderr)
        if not target.is_file() or decoded is None:
            raise ValueError(f"No decoded frame/timestamp at {timestamp:.3f}s; inspect the source duration.")
        actual = float(decoded.group(1)) - start_time
        if actual < -0.001 or actual > duration + 1 / fps:
            raise ValueError(f"Decoded timestamp {actual:.6f}s is outside the source timeline.")
        frames.append({
            "index": index,
            "requested_timestamp_seconds": round(timestamp, 6),
            "timestamp_seconds": round(max(0.0, actual), 6),
            "path": f"frames/{filename}",
        })

    columns = min(4, samples)
    rows = math.ceil(samples / columns)
    cell_width, cell_height, header = 264, 292, 44
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height + header), "#202124")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=15)
    draw.text((10, 12), f"Reference contact sheet | {samples} samples | {duration:.3f}s", fill="white", font=font)
    for index, frame in enumerate(frames):
        x, y = (index % columns) * cell_width, (index // columns) * cell_height + header
        with Image.open(output_dir / frame["path"]) as image:
            thumbnail = ImageOps.contain(image.convert("RGB"), (244, 248))
            sheet.paste(thumbnail, (x + (cell_width - thumbnail.width) // 2, y + 8 + (248 - thumbnail.height) // 2))
        draw.text((x + 10, y + 266), f"{frame['index']:02d} | {frame['timestamp_seconds']:.3f}s", fill="white", font=font)
    sheet.save(output_dir / "contact-sheet.jpg", quality=92)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    manifest = {
        "schema_version": 1,
        "source": str(source),
        "source_sha256": digest.hexdigest(),
        "duration_seconds": duration,
        "reported_duration_seconds": reported_duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": fps,
        "last_frame_timestamp_seconds": round(last, 6),
        "has_audio": any(s.get("codec_type") == "audio" for s in metadata.get("streams", [])),
        "sampling": "Uniform requested times; timestamp_seconds records the first decoded source frame at or after each request.",
        "contact_sheet": "contact-sheet.jpg",
        "frames": frames,
        "ffprobe": metadata,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()
    try:
        manifest = inspect(args.input, args.output_dir, args.samples)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"manifest": str(args.output_dir / "manifest.json"), "contact_sheet": str(args.output_dir / "contact-sheet.jpg"), "samples": len(manifest["frames"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
