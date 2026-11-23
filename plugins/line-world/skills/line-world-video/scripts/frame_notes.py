"""Create an offline, frame-linked critique page or verify the annotations it exports."""
import argparse
from bisect import bisect_right
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
from caption_tracks import extract as extract_subtitles, webvtt, write_atomic


TEMPLATE = Path(__file__).resolve().parents[1] / "assets/templates/frame-notes.html"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_url(source, page):
    return quote(Path(os.path.relpath(source.resolve(), page.resolve().parent)).as_posix(), safe="/")


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def movie_clock(path):
    data = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration:format=duration:chapter=start_time,end_time:chapter_tags=title:frame=best_effort_timestamp_time,duration_time,pkt_duration_time",
        "-show_chapters", "-of", "json", str(path)]))
    stream = data["streams"][0]
    pts = [float(f["best_effort_timestamp_time"]) for f in data["frames"]]
    if not pts or any(b <= a for a, b in zip(pts, pts[1:])):
        raise ValueError("The decoded video needs strictly increasing presentation timestamps.")
    # Browser MP4 mediaTime honors a positive edit-list offset, including films with a leading voice.
    origin = min(0, pts[0])
    times = [round(t-origin, 6) for t in pts]
    last_frame = data["frames"][-1]
    frame_duration = float(last_frame.get("duration_time") or last_frame.get("pkt_duration_time") or 0)
    picture_end = times[0] + float(stream.get("duration") or 0)
    if frame_duration > 0:
        picture_end = times[-1] + frame_duration
    elif picture_end <= times[-1]:
        picture_end = times[-1] + (times[-1]-times[-2] if len(times)>1 else 1/30)
    end = max(picture_end,float(data.get("format",{}).get("duration") or 0))
    chapters = [{"start": float(c["start_time"])-origin, "end": float(c["end_time"])-origin,
                 "title": c.get("tags", {}).get("title", "")} for c in data.get("chapters", [])]
    return {"width": stream["width"], "height": stream["height"], "pts": times, "duration": end,
            "pictureEnd":picture_end, "timestampOrigin":origin, "chapters": chapters}


def model(video, attention=None):
    info = movie_clock(video)
    info.update(videoSha256=digest(video), tracks={}, beats=[], attentionSha256=None)
    if attention:
        score = read(attention)
        if not isinstance(score, dict):
            raise ValueError("The attention plan must be an object.")
        fps = score.get("fps")
        if len(info["pts"]) != score.get("frames") or type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0:
            raise ValueError("The attention plan and movie have different clocks.")
        if any(abs((t-info["pts"][0])-i/score["fps"]) > .0001 for i,t in enumerate(info["pts"])):
            raise ValueError("The attention plan and video frame timestamps differ.")
        tracks, beats = score.get("tracks"), score.get("beats")
        if not isinstance(tracks, dict) or not isinstance(beats, list) or not beats:
            raise ValueError("Missing beats or subject boxes in the attention plan.")
        for name, track in tracks.items():
            box = track.get("box") if isinstance(track, dict) else None
            if not name.strip() or not isinstance(box, list) or len(box) != 4 or not all(map(finite_number, box)):
                raise ValueError(f"Invalid subject box for {name!r}.")
            x, y, w, h = box
            if min(x, y) < 0 or min(w, h) <= 0 or x+w > 1.000001 or y+h > 1.000001:
                raise ValueError(f"The box for {name!r} lies outside the picture.")
        cursor = 0
        for beat in beats:
            if not isinstance(beat, dict) or any(type(beat.get(k)) is not int for k in ("start", "end")):
                raise ValueError("Beat boundaries must be integer frame numbers.")
            visible = beat.get("visible", list(tracks))
            if (beat["start"] != cursor or not cursor < beat["end"] <= len(info["pts"]) or
                    not isinstance(visible, list) or any(not isinstance(k, str) or k not in tracks for k in visible)):
                raise ValueError("Beat boundaries or visible subjects differ from the attention plan.")
            cursor = beat["end"]
        if cursor != len(info["pts"]):
            raise ValueError("The attention plan ends before the video.")
        info.update(tracks=tracks, beats=beats, attentionSha256=digest(attention))
    return info


def build(video, output, attention, title, subtitle_language=None):
    sources = [video, TEMPLATE] + ([attention] if attention else [])
    if output.resolve() in {p.resolve() for p in sources} or output.suffix.lower() != ".html":
        raise ValueError("Choose a separate .html review page.")
    data = model(video, attention)
    track = extract_subtitles(video, subtitle_language)
    if track and track["cues"]:
        data["captions"] = {**track, "vtt": webvtt(track["cues"])}
    data.update(title=title or video.stem, video=file_url(video, output))
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    content = TEMPLATE.read_text(encoding="utf-8").replace("__FRAME_NOTES_DATA__", encoded)
    write_atomic(output,content)


def validate(document, info):
    if not isinstance(document, dict) or document.get("version") != 1 or document.get("videoSha256") != info["videoSha256"]:
        raise ValueError("These notes belong to another version of the movie.")
    if info["attentionSha256"] != document.get("attentionSha256"):
        raise ValueError("These notes use a different attention plan. Supply the plan used to create them.")
    notes = document.get("notes")
    if not isinstance(notes, list):
        raise ValueError("Expected a list of notes.")
    known = set()
    starts = [b["start"] for b in info["beats"]]
    for i, note in enumerate(notes):
        if not isinstance(note, dict):
            raise ValueError(f"Note {i+1} must be an object.")
        key, frame, end = (note.get(k) for k in ("id", "frame", "endFrame"))
        if not isinstance(key, str) or not key or key in known:
            raise ValueError(f"Note {i+1} needs a unique ID.")
        known.add(key)
        if type(frame) is not int or type(end) is not int or not 0 <= frame <= end < len(info["pts"]):
            raise ValueError(f"Note {i+1} has an invalid frame range.")
        point = note.get("point")
        if not isinstance(point, list) or len(point) != 2 or not all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in point):
            raise ValueError(f"Note {i+1} needs a point in the picture.")
        if not isinstance(note.get("text"), str) or not note["text"].strip() or len(note["text"])>2000:
            raise ValueError(f"Note {i+1} needs 1–2000 characters.")
        if note.get("kind") not in {"ajustar","conservar"}:
            raise ValueError(f"Note {i+1} has an unknown decision.")
        if note.get("element") is not None:
            if not starts:
                raise ValueError(f"Note {i+1} names an element without an attention plan.")
            beat = info["beats"][bisect_right(starts, frame)-1]
            name = note["element"]
            if not isinstance(name,str) or name not in beat.get("visible", info["tracks"]):
                raise ValueError(f"Note {i+1} refers to a hidden element.")
            x,y,w,h = info["tracks"][name]["box"]
            if not (x-.00001 <= point[0] <= x+w+.00001 and y-.00001 <= point[1] <= y+h+.00001):
                raise ValueError(f"Note {i+1} lies outside the chosen element.")
    return notes


def extract_frame(video, frame, path):
    # Decode by frame index. Seeking a keyframe alone would be ambiguous for VFR input.
    command = ["ffmpeg","-v","error","-nostdin","-y","-threads","2","-i",str(video),"-map","0:v:0",
               "-vf",f"select=eq(n\\,{frame})","-frames:v","1","-threads","1",str(path)]
    subprocess.run(command, check=True)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError(f"Failed to extract frame {frame}.")


def evidence(video, folder, notes, info):
    folder.mkdir(parents=True, exist_ok=True)
    for i, note in enumerate(notes, start=1):
        frame = note["frame"]
        path = folder / f"nota-{i:03d}-f{frame:06d}.png"
        extract_frame(video, frame, path)
        note["evidence"] = {"file": path.name, "sha256": digest(path), "seconds": info["pts"][frame],
                            "pixel": [min(info[k]-1, int(coord*info[k])) for k,coord in zip(("width","height"),note["point"])]}
    (folder/"notas-verificadas.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("video", type=Path)
    make.add_argument("output", type=Path)
    make.add_argument("--title")
    make.add_argument("--subtitle-language", help="Read this subtitle stream from the delivered movie, e.g. spa")
    check = commands.add_parser("check")
    check.add_argument("video", type=Path)
    check.add_argument("notes", type=Path)
    check.add_argument("--evidence", type=Path)
    for command in (make, check):
        command.add_argument("--attention", type=Path)
    args = parser.parse_args()
    if args.command=="build":
        build(args.video, args.output, args.attention, args.title, args.subtitle_language)
        print(args.output)
    else:
        info = model(args.video, args.attention)
        notes = validate(read(args.notes), info)
        if args.evidence:
            evidence(args.video, args.evidence, notes, info)
        print(json.dumps({"ok": True, "notes": len(notes), "frames": len(info["pts"])}))


if __name__=="__main__":
    try:
        main()
    except (OSError, ValueError, IndexError, KeyError, subprocess.SubprocessError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2)
