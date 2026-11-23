#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Prepare editable Vids scenes from MP4 chapters and a measured narration transcript."""
import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

import vids_batch
import vids_plan
from batch_clips import sha


def run(args):
    result = subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(f"{args[0]} failed: {result.stderr.strip()[-1600:]}")
    return result.stdout


def inspect(path):
    args = ["ffprobe", "-v", "error", "-threads", "1", "-of", "json"]
    info = json.loads(run([*args, "-show_streams", "-show_chapters", str(path)]))
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not video:
        raise ValueError("A video stream is required.")
    fps = Fraction(video["avg_frame_rate"])
    if fps.denominator != 1 or not 1 <= fps <= 120:
        raise ValueError("The Vids story requires a constant integer frame rate from 1 to 120.")
    frames = json.loads(run([*args, "-select_streams", "v:0", "-show_frames", "-show_entries",
                             "frame=best_effort_timestamp,key_frame", str(path)]))["frames"]
    time_base = Fraction(video["time_base"])
    if not frames or any(f["best_effort_timestamp"] * time_base != i / fps for i, f in enumerate(frames)):
        raise ValueError("Every decoded video frame must follow the declared frame clock from zero.")
    return info, video, int(fps), frames


def boundaries(info, fps, count):
    chapters = info.get("chapters", [])
    if not chapters:
        raise ValueError("The MP4 has no embedded chapters.")
    cuts = []
    previous = Fraction(0)
    for chapter in chapters:
        base = Fraction(chapter["time_base"])
        start, end = (chapter[k] * base for k in ("start", "end"))
        first, last = round(start * fps), round(end * fps)
        if start != previous or last <= first or last > count:
            raise ValueError("Chapters must cover consecutive, nonempty frame ranges from zero.")
        cuts.append((first, last, chapter.get("tags", {}).get("title", "")))
        previous = end
    if cuts[-1][1] != count:
        raise ValueError("The last chapter must cover the final video frame.")
    return cuts


def integer(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(label + " must be a nonnegative sample index.")
    return value


def build_story(cuts, timeline, project, fps, video, title, language, mode):
    rate = integer(timeline["sample_rate"], "sample_rate")
    if not rate:
        raise ValueError("sample_rate must be positive.")
    rows = timeline["scenes"]
    if len(rows) != len(cuts):
        raise ValueError("The chapter and transcript scene counts differ.")
    if project:
        if [s["id"] for s in project["scenes"]] != [s["id"] for s in rows]:
            raise ValueError("Project scene IDs/order differ from the measured transcript.")
        for field, actual in (("fps", fps), ("width", video["width"]), ("height", video["height"])):
            if field in project and project[field] != actual:
                raise ValueError("Project and video disagree on " + field)
    scenes = []
    previous = 0
    for i, (row, (first, last, chapter_title)) in enumerate(zip(rows, cuts)):
        sid = row["id"]
        scene_title = project["scenes"][i].get("title") if project else None
        if chapter_title and scene_title and chapter_title != scene_title:
            raise ValueError(f"Chapter title differs from project scene {sid}.")
        start, end = (integer(row[k], k) for k in ("start_sample", "end_sample"))
        if start != previous or end <= start or any(abs(Fraction(n * fps, rate) - f) > Fraction(1, 2)
                                                     for n, f in ((start, first), (end, last))):
            raise ValueError(f"Chapter and narration clocks disagree for {sid}.")
        phrases = []
        last_sample = start
        for sentence in row["sentences"]:
            a, b = (integer(sentence[k], k) for k in ("absolute_start_sample", "absolute_end_sample"))
            text = sentence["text"]
            if not isinstance(text, str) or not text.strip() or not last_sample <= a < b <= end:
                raise ValueError(f"Invalid or overlapping measured sentence in {sid}.")
            if a * fps < first * rate or b * fps > last * rate:
                raise ValueError(f"A chapter cut crosses speech in {sid}.")
            phrases.append({"text": text.strip(), "sourceStartSample": a, "sourceEndSample": b})
            last_sample = b
        seconds = (last - first) / fps
        scenes.append({"id": sid, "title": chapter_title or scene_title or sid, "sourceClip": f"clips/{sid}.mp4",
                       "script": " ".join(p["text"] for p in phrases), "sentences": phrases,
                       "sourceStartFrame": first, "sourceEndFrameExclusive": last,
                       "clipSeconds": seconds, "essentialAnimationSeconds": seconds})
        previous = end
    return vids_plan.validate_story({"projectTitle": title, "language": language, "fps": fps, "width": video["width"],
                                     "height": video["height"], "audioMode": mode, "sourceSampleRate": rate, "scenes": scenes})


FFMPEG = ["ffmpeg", "-nostdin", "-v", "error", "-filter_threads", "1", "-filter_complex_threads", "1"]


def cut_clip(source, target, scene, fps, embedded):
    first, last = scene["sourceStartFrame"], scene["sourceEndFrameExclusive"]
    trim = f"trim=start_frame={first}:end_frame={last},setpts=PTS-STARTPTS"
    audio = ["-map", "0:a:0", "-af", f"atrim=start={first/fps:.9f}:end={last/fps:.9f},asetpts=PTS-STARTPTS",
             "-c:a", "aac", "-b:a", "192k"] if embedded else ["-an"]
    run([*FFMPEG, "-threads", "1", "-i", str(source), "-map", "0:v:0", "-vf", trim, *audio,
         "-map_metadata", "-1", "-map_chapters", "-1", "-c:v", "libx264", "-threads", "1", "-crf", "12",
         "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)])
    info, video, clip_fps, frames = inspect(target)
    if (clip_fps, len(frames), frames[0]["key_frame"]) != (fps, last - first, 1):
        raise ValueError("The output frame clock or opening keyframe is wrong: " + scene["id"])
    duration = Fraction(video["duration_ts"]) * Fraction(video["time_base"])
    if duration != Fraction(last - first, fps):
        raise ValueError("The output video duration differs from its chapter.")
    audio_streams = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if len(audio_streams) != int(embedded):
        raise ValueError("The clip audio mode differs from the request.")
    audio_duration = None
    if embedded:
        audio_stream = audio_streams[0]
        audio_duration = float(audio_stream["duration"])
        if float(audio_stream["start_time"]) != 0 or abs(audio_duration - float(duration)) > 1 / fps:
            raise ValueError("Embedded audio is offset or shorter than the chapter: " + scene["id"])
    # Measure every decoded output frame against its corresponding source frame.
    # Both paths use the same pixel format. No raw video is written to disk.
    compare = f"[0:v:0]{trim},format=yuv420p[ref];[1:v:0][ref]psnr=stats_file=-:shortest=1[v]"
    stats = run([*FFMPEG, "-threads", "1", "-i", str(source), "-threads", "1", "-i", str(target),
                 "-filter_complex", compare, "-map", "[v]", "-an", "-f", "null", "-"])
    scores = [float(s) for s in re.findall(r"\bpsnr_avg:(\S+)", stats)]
    if len(scores) != len(frames) or min(scores) < 38:
        raise ValueError("Decoded frames failed source alignment/quality verification: " + scene["id"])
    def score(value):
        return value if math.isfinite(value) else "identical"
    return {"id": scene["id"], "frames": len(frames), "durationSeconds": float(duration),
            "firstFramePsnrDb": score(scores[0]), "lastFramePsnrDb": score(scores[-1]),
            "minimumFramePsnrDb": score(min(scores)), "audioTracks": len(audio_streams),
            "audioDurationSeconds": audio_duration, "sha256": sha(target)}


def prepare(video_file, output, *, project_file=None, timeline_file=None, title=None, language=None, mode="native"):
    video_file, output = Path(video_file), Path(output)
    if output.exists():
        raise ValueError("Choose a new project directory to preserve existing clips and native observations.")
    project = vids_plan.read(project_file) if project_file else None
    if project is not None:
        timeline_file = Path(project_file).parent / project["audioTimeline"]
    if not timeline_file:
        raise ValueError("Provide a measured project or narration timeline.")
    timeline = vids_plan.read(timeline_file)
    info, video, fps, frames = inspect(video_file)
    if mode == "embedded":
        audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        if not audio or float(audio.get("start_time", 0)) != 0:
            raise ValueError("Embedded mode needs source audio beginning at zero.")
    cuts = boundaries(info, fps, len(frames))
    project = project or {}
    story = build_story(cuts, timeline, project, fps, video, title or project.get("projectTitle") or video_file.stem,
                        language or project.get("language") or "es", mode)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".vids-chapters-") as tmp:
        stage = Path(tmp) / "project"
        (stage / "clips").mkdir(parents=True)
        reports = []
        for scene in story["scenes"]:
            clip = cut_clip(video_file, stage / scene["sourceClip"], scene, fps, mode == "embedded")
            first = scene["sourceStartFrame"]
            clip.update(sourceStartFrame=first, sourceEndFrameExclusive=scene["sourceEndFrameExclusive"],
                        sourceStartsOnKeyframe=bool(frames[first]["key_frame"]))
            reports.append(clip)
        vids_plan.write(stage / "story.json", story)
        vids_plan.prepare(story, stage / "handoff")
        if mode == "native":
            vids_batch.build(stage, encode=False)
        receipt = {"status": "verified-local-chapter-clips", "sourceFile": video_file.name,
                   "sourceSha256": sha(video_file), "timelineSha256": sha(timeline_file), "fps": fps,
                   "frames": len(frames), "durationSeconds": len(frames) / fps, "audioMode": mode,
                   "sceneCount": len(reports), "sentenceCount": sum(len(s["sentences"]) for s in story["scenes"]),
                   "scenes": reports}
        vids_plan.write(stage / "chapter-checks.json", receipt)
        stage.rename(output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--project", type=Path, help="Measured producer project JSON with an audioTimeline reference.")
    source.add_argument("--timeline", type=Path, help="Sample-clock timeline JSON with scene IDs and exact sentences.")
    parser.add_argument("--audio", choices=("native", "embedded"), default="native",
                        help="Native prepares silent visuals for Vids narration. Embedded retains the first source audio track.")
    parser.add_argument("--title")
    parser.add_argument("--language")
    args = parser.parse_args()
    try:
        receipt = prepare(args.video, args.output, project_file=args.project, timeline_file=args.timeline,
                          mode=args.audio, title=args.title, language=args.language)
        print(json.dumps({k: v for k, v in receipt.items() if k != "scenes"}, ensure_ascii=True))
    except (KeyError, ValueError, TypeError, OSError, ZeroDivisionError) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
