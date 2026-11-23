#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=10.1,<13"]
# ///
"""Create a tiny original editorial reference for an offline semantic trial."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


def run(arguments: list[str]) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"{arguments[0]} failed: {result.stderr[-1800:]}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} must be on PATH.")
    candidates = [args.font] if args.font else [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    font_path = next((path for path in candidates if path and path.is_file()), None)
    if font_path is None:
        raise SystemExit("Provide a local bold sans-serif font using --font.")
    destination = args.output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(font_path), size=58)
    for index, word in enumerate(("HOLD", "FOCUS")):
        image = Image.new("RGB", (320, 480), "#f2eddf")
        draw = ImageDraw.Draw(image)
        draw.text((160, 223), word, font=font, fill="#171717", anchor="mm", stroke_width=0)
        # A recurring accent changes sides with the hard cut, keeping source
        # conventions observable from multiple sampled frames.
        x = 56 if index == 0 else 200
        draw.rectangle((x, 288, x + 64, 300), fill="#c9342d")
        image.save(destination / f"shot-{index + 1}.png")
    output = destination / "reference.mp4"
    run([
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-loop", "1",
        "-framerate", "12", "-i", str(destination / "shot-1.png"), "-loop", "1",
        "-framerate", "12", "-i", str(destination / "shot-2.png"), "-filter_complex",
        "[0:v]trim=duration=2,setpts=PTS-STARTPTS[a];[1:v]trim=duration=2,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-frames:v", "48", "-r", "12", "-an", "-c:v", "libx264",
        "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(output),
    ])
    media = json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(output)]))
    video = next(stream for stream in media["streams"] if stream["codec_type"] == "video")
    if (video["width"], video["height"], int(video["nb_read_frames"]), float(video["duration"])) != (320, 480, 48, 4.0):
        raise SystemExit("Fixture properties differ from the frozen contract.")
    payload = output.read_bytes()
    (destination / "reference.base64.txt").write_text(base64.b64encode(payload).decode("ascii") + "\n", encoding="ascii")
    record = {
        "fixture_id": "video-style-editorial-20261031",
        "creator": "Repository-authored procedural fixture",
        "rights": "Original shapes and copy; local system font rendered into pixels; no third-party media.",
        "source": "reference.mp4",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "width": 320, "height": 480, "fps": 12, "duration_seconds": 4,
        "shots": [
            {"start_s": 0, "end_s": 2, "text": "HOLD", "accent": "lower left"},
            {"start_s": 2, "end_s": 4, "text": "FOCUS", "accent": "lower right"},
        ],
        "palette": {"background": "#f2eddf", "type": "#171717", "accent": "#c9342d"},
        "font_file_used_for_fixture_only": font_path.name,
        "ffprobe": media,
    }
    (destination / "fixture-manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in ("fixture_id", "sha256", "bytes", "width", "height", "fps", "duration_seconds")}))


if __name__ == "__main__":
    main()
