#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydub==0.25.1", "audioop-lts==0.2.2; python_version >= '3.13'"]
# ///
"""Render contained, declarative PyDub edits without overwriting source audio."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from pydub import AudioSegment, generators
from pydub.exceptions import CouldntDecodeError, CouldntEncodeError
from pydub.silence import detect_silence


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def contained(root, value):
    path = Path(value)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(root):
        raise ValueError("Path must stay inside the explicit workspace root.")
    return path


def number(value, name, low=None, high=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number.")
    if integer and not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if low is not None and value < low or high is not None and value > high:
        raise ValueError(f"{name} is outside the allowed range.")
    return value


def known(obj, allowed, name):
    if not isinstance(obj, dict) or set(obj) - set(allowed):
        raise ValueError(f"{name} must be an object with supported keys only.")


def finite(value):
    return value if math.isfinite(value) else None


def load_audio(path):
    with Path(path).open("rb") as stream:
        return AudioSegment.from_file(stream, format="wav" if Path(path).suffix.lower() == ".wav" else None)


def metrics(audio):
    return {"duration_ms": len(audio), "sample_rate": audio.frame_rate,
            "channels": audio.channels, "sample_width_bytes": audio.sample_width,
            "rms_dbfs": finite(audio.dBFS), "sample_peak_dbfs": finite(audio.max_dBFS)}


def publish(temp, destination):
    # Same-volume hard-link publication is atomic and fails if destination exists.
    # There is no replacement fallback that could overwrite another worker.
    os.link(temp, destination)


def json_temp(destination, value):
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".pydub-", suffix=".json", dir=destination.parent)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return Path(name)


def save_new(destination, value):
    temp = json_temp(destination, value)
    try:
        publish(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


def doctor():
    return {"ok": True, "python": sys.version.split()[0],
            "pydub": importlib.metadata.version("pydub"),
            "ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"),
            "pcm_wav_ready": True,
            "compressed_formats_ready": bool(shutil.which("ffmpeg"))}


def inspect(root, value, silence_threshold=None):
    path = contained(root, value)
    if not path.is_file():
        raise ValueError("Audio input must be an existing regular file.")
    audio = load_audio(path)
    result = {"ok": True, "path": path.relative_to(root).as_posix(),
              "sha256": sha(path), **metrics(audio)}
    if silence_threshold is not None:
        number(silence_threshold, "silence threshold", -120, 0)
        result["silence_ranges_ms"] = detect_silence(audio, min_silence_len=200,
                                                    silence_thresh=silence_threshold, seek_step=10)
    probe = shutil.which("ffprobe")
    if probe:
        check = subprocess.run([probe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                               capture_output=True, text=True, timeout=60)
        if check.returncode:
            raise ValueError("ffprobe rejected the audio: " + check.stderr[-1000:])
        result["container"] = json.loads(check.stdout)
    return result


CLIP_KEYS = {"id", "file", "tone", "silence_ms", "start_ms", "end_ms", "gain_db",
             "fade_in_ms", "fade_out_ms", "reverse", "repeat", "pan", "high_pass_hz",
             "low_pass_hz", "position_ms", "duck_db", "crossfade_ms"}


def clip_audio(root, clip, rate, channels, cache=None):
    known(clip, CLIP_KEYS, "clip")
    if not isinstance(clip.get("id"), str) or not clip["id"].strip():
        raise ValueError("Each clip needs a nonempty string id.")
    if sum(key in clip for key in ("file", "tone", "silence_ms")) != 1:
        raise ValueError("Each clip needs exactly one file, tone or silence_ms source.")
    source = None
    if "file" in clip:
        path = contained(root, clip["file"])
        if not path.is_file():
            raise ValueError("Clip source must be an existing regular file.")
        cache = cache if cache is not None else {}
        if path not in cache:
            before = sha(path)
            decoded = load_audio(path)
            if before != sha(path):
                raise ValueError("Source changed during decoding; retry with a stable input.")
            cache[path] = (decoded, before)
        audio, source_digest = cache[path]
        source = {"path": path.relative_to(root).as_posix(), "sha256": source_digest}
    elif "tone" in clip:
        tone = clip["tone"]
        known(tone, {"kind", "frequency_hz", "duration_ms", "gain_db"}, "tone")
        duration = number(tone.get("duration_ms"), "tone duration", 1, integer=True)
        frequency = number(tone.get("frequency_hz", 440), "frequency", 1, rate / 2 - 1)
        kinds = {"sine": generators.Sine, "square": generators.Square,
                 "sawtooth": generators.Sawtooth, "noise": generators.WhiteNoise}
        kind = tone.get("kind", "sine")
        if kind not in kinds:
            raise ValueError("Unsupported tone kind.")
        generator = kinds[kind](sample_rate=rate) if kind == "noise" else kinds[kind](frequency, sample_rate=rate)
        audio = generator.to_audio_segment(duration=duration,
                                          volume=number(tone.get("gain_db", -18), "tone gain", -120, 0))
    else:
        audio = AudioSegment.silent(duration=number(clip["silence_ms"], "silence duration", 1, integer=True), frame_rate=rate)
    start = number(clip.get("start_ms", 0), "start_ms", 0, len(audio), integer=True)
    end = number(clip.get("end_ms", len(audio)), "end_ms", 0, len(audio), integer=True)
    if end <= start:
        raise ValueError("Clip trim must contain audio.")
    audio = audio[start:end].set_frame_rate(rate).set_channels(channels).set_sample_width(2)
    reverse = clip.get("reverse", False)
    if not isinstance(reverse, bool):
        raise ValueError("reverse must be a boolean.")
    if reverse:
        audio = audio.reverse()
    audio = audio * number(clip.get("repeat", 1), "repeat", 1, 1000, integer=True)
    audio = audio.apply_gain(number(clip.get("gain_db", 0), "gain_db", -120, 60))
    for key, method in (("high_pass_hz", "high_pass_filter"), ("low_pass_hz", "low_pass_filter")):
        if key in clip:
            audio = getattr(audio, method)(number(clip[key], key, 1, rate / 2 - 1))
    if "pan" in clip:
        if channels != 2:
            raise ValueError("Pan requires stereo output.")
        audio = audio.pan(number(clip["pan"], "pan", -1, 1))
    for key, method in (("fade_in_ms", "fade_in"), ("fade_out_ms", "fade_out")):
        duration = number(clip.get(key, 0), key, 0, len(audio), integer=True)
        if duration:
            audio = getattr(audio, method)(duration)
    return audio, source


def render(root, plan_path, output_path, report_path):
    root = Path(root).resolve()
    plan_file, output, report = [contained(root, p) for p in (plan_path, output_path, report_path)]
    if len({plan_file, output, report}) != 3:
        raise ValueError("Plan, output and report must have different paths.")
    if output.exists() or report.exists():
        raise ValueError("Output/report already exists; choose new paths.")
    plan_bytes = plan_file.read_bytes()
    plan_digest = hashlib.sha256(plan_bytes).hexdigest()
    plan = json.loads(plan_bytes.decode("utf-8-sig"))
    known(plan, {"schema_version", "mode", "sample_rate", "channels", "clips", "duration_ms", "peak_dbfs", "bitrate"}, "plan")
    if type(plan.get("schema_version")) is not int or plan["schema_version"] != 1:
        raise ValueError("Use schema_version 1.")
    mode = plan.get("mode", "sequence")
    if mode not in ("sequence", "timeline"):
        raise ValueError("Use sequence or timeline mode.")
    rate = number(plan.get("sample_rate", 48000), "sample_rate", 8000, 192000, integer=True)
    channels = number(plan.get("channels", 2), "channels", 1, 2, integer=True)
    clips = plan.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError("Provide a nonempty clips array.")
    prepared, sources, identifiers, cache = [], [], set(), {}
    for clip in clips:
        audio, source = clip_audio(root, clip, rate, channels, cache)
        if clip["id"] in identifiers:
            raise ValueError("Clip ids must be unique.")
        identifiers.add(clip["id"])
        if source:
            if contained(root, source["path"]) in (output, report, plan_file):
                raise ValueError("Do not replace source audio with output or metadata.")
            sources.append(source)
        prepared.append((clip, audio))
    if mode == "sequence":
        if "duration_ms" in plan:
            raise ValueError("duration_ms belongs to timeline mode.")
        result, previous_length = None, 0
        for clip, audio in prepared:
            if "position_ms" in clip or "duck_db" in clip:
                raise ValueError("position_ms and duck_db belong to timeline mode.")
            fade = number(clip.get("crossfade_ms", 0), "crossfade_ms", 0, len(audio), integer=True)
            if result is None:
                if fade:
                    raise ValueError("The first clip cannot crossfade.")
                result = audio
            else:
                number(fade, "crossfade_ms", 0, previous_length)
                result = result.append(audio, crossfade=fade)
            previous_length = len(audio)
    else:
        ends = []
        for clip, audio in prepared:
            if "crossfade_ms" in clip:
                raise ValueError("crossfade_ms belongs to sequence mode.")
            position = number(clip.get("position_ms", 0), "position_ms", 0, integer=True)
            ends.append(position + len(audio))
        duration = number(plan.get("duration_ms", max(ends)), "duration_ms", max(ends), integer=True)
        result = AudioSegment.silent(duration=duration, frame_rate=rate).set_channels(channels)
        for clip, audio in prepared:
            result = result.overlay(audio, position=clip.get("position_ms", 0),
                                    gain_during_overlay=number(clip.get("duck_db", 0), "duck_db", -120, 0))
    if "peak_dbfs" in plan:
        target = number(plan["peak_dbfs"], "peak_dbfs", -120, 0)
        if result.max:
            result = result.apply_gain(target - result.max_dBFS)
    formats = {".wav": ("wav", None), ".mp3": ("mp3", None), ".ogg": ("ogg", None),
               ".flac": ("flac", None), ".m4a": ("ipod", "aac")}
    if output.suffix.lower() not in formats:
        raise ValueError("Use a supported audio output extension.")
    bitrate = plan.get("bitrate")
    if bitrate is not None and (not isinstance(bitrate, str) or not re.fullmatch(r"[1-9][0-9]{0,3}k", bitrate)):
        raise ValueError("bitrate must have a form such as 192k.")
    fmt, codec = formats[output.suffix.lower()]
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".pydub-", suffix=output.suffix, dir=output.parent)
    os.close(descriptor)
    temp = Path(name)
    report_temp = None
    try:
        with result.set_sample_width(2).export(str(temp), format=fmt, codec=codec, bitrate=bitrate):
            pass
        decoded = load_audio(temp)
        receipt = {"ok": True, "schema_version": 1, "plan_sha256": plan_digest, "sources": sources,
                   "output": output.relative_to(root).as_posix(), "sha256": sha(temp),
                   "size_bytes": temp.stat().st_size, "mode": mode, "clip_ids": list(c["id"] for c in clips),
                   "intended_duration_ms": len(result), **metrics(decoded)}
        report_temp = json_temp(report, receipt)
        # Publish metadata first: a race cannot cause an old worker to delete or
        # replace audio. A crash can leave a receipt without audio; callers verify
        # both exact paths and hashes before marking the task complete.
        publish(report_temp, report)
        publish(temp, output)
        return receipt
    finally:
        temp.unlink(missing_ok=True)
        if report_temp:
            report_temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    p = sub.add_parser("inspect")
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--input", required=True)
    p.add_argument("--output")
    p.add_argument("--silence-threshold-dbfs", type=float)
    p = sub.add_parser("render")
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--plan", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            result = doctor()
        elif args.command == "inspect":
            result = inspect(args.root.resolve(), args.input, args.silence_threshold_dbfs)
            if args.output:
                save_new(contained(args.root.resolve(), args.output), result)
        else:
            result = render(args.root, args.plan, args.output, args.report)
        print(json.dumps(result, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError, CouldntDecodeError, CouldntEncodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
