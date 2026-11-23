# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=11,<13"]
# ///
"""Prepare lossless local picture sources and timed beats for the Line World narrator."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from shutil import which
import subprocess
from tempfile import NamedTemporaryFile

from direction import SKILLS, frame, read, require


def write(path, data):
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
        except BaseException:
            output.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def paths_relative(base, value):
    return Path(os.path.relpath(value, base)).as_posix()


def clock(visual, timeline):
    scenes = timeline["scenes"]
    require(
        [s["id"] for s in visual["scenes"]] == [s["id"] for s in scenes],
        "Voice and picture scene IDs must match in order",
    )
    fps = visual["fps"]
    rate = timeline["sample_rate"]
    total = math.ceil(timeline["master"]["samples"] * fps / rate)
    positions = []
    for i, (beat, scene) in enumerate(zip(visual["scenes"], scenes)):
        start = round(scene["start_sample"] * fps / rate)
        end = round(scene["end_sample"] * fps / rate) if i + 1 < len(scenes) else total
        timing = beat.get("timing", {})
        if beat.get("readingOnly"):
            require(end-start>=math.ceil(.8*fps),f"{beat['id']}: reading needs at least 0.8 s")
            beat.update(cue=0,move=0,hold=end-start)
            positions.append((start,end))
            continue
        require(
            ("sentence" in timing) ^ ("effect" in timing),
            "Select a recorded sentence or sound effect",
        )
        kind="effect" if "effect" in timing else "sentence"
        idx=timing[kind]
        require(type(idx) is int and 0<=idx<len(scene[kind+"s"]),
                f"{beat['id']}: no recorded {kind} at index {idx}")
        for key in ("offsetSeconds","moveSeconds"):
            value=timing.get(key,0)
            require(type(value) in (int,float) and math.isfinite(value),f"{beat['id']}: {key} must be a finite time")
        if "effect" in timing:
            sample = scene["effects"][timing["effect"]]["absolute_start_sample"]
        else:
            field = timing.get("edge", "start")
            require(field in {"start", "end"}, "Choose a sentence start or end")
            sample = scene["sentences"][timing["sentence"]][
                "absolute_" + field + "_sample"
            ]
        cue = round((sample / rate + timing.get("offsetSeconds", 0)) * fps) - start
        move = round(timing["moveSeconds"] * fps)
        hold = end - start - cue - move
        require(
            cue >= 0 and move >= math.ceil(0.65 * fps) and hold >= math.ceil(0.8 * fps),
            f"{beat['id']}: the measured voice leaves insufficient movement or reading space",
        )
        beat.update(cue=cue, move=move, hold=hold)
        positions.append((start, end))
    return total, positions


def score(spec, timeline, total, positions):
    fps = spec["fps"]
    rate = timeline["sample_rate"]
    w, h = spec["size"]
    require(
        all(s["kind"] == "compare" and "note" not in s for s in spec["scenes"]),
        "Automatic attention regions apply to two-row comparisons. Pass --attention for another composition.",
    )
    if w / h < 1.25:
        top, bottom = 0.43, 0.76
    else:
        top, bottom = 0.42, 0.70
    centers = [top + (bottom - top) * f for f in (0.18, 0.79)]
    area = 0.09 if w / h < 1.25 else 0.12
    tracks = {
        f"fila{i + 1}": {
            "box": [
                0.04 if w / h < 1.25 else 0.28,
                y - area / 2,
                0.93 if w / h < 1.25 else 0.70,
                area,
            ],
            "meaning": f"Estado y longitud de la fila {i + 1}.",
        }
        for i, y in enumerate(centers)
    }
    cues = [
        (scene["id"], i, s)
        for scene in timeline["scenes"]
        for i, s in enumerate(scene["sentences"])
    ]
    beats = []
    for s, (start, end) in zip(spec["scenes"], positions):
        focus=f"fila{s.get('focusRow',1)}"
        require(focus in tracks,"focusRow must select row 1 or 2")
        active = start + s["cue"] + 1
        land = start + s["cue"] + s["move"]
        periods = ((start,end,[]),) if s.get("readingOnly") else (
            (start, active, []),
            (active, land, ["fila1", "fila2"]),
            (land, end, []),
        )
        for a, b, moving in periods:
            if b <= a:
                continue
            beats.append(
                {
                    "start": a,
                    "end": b,
                    "focus": focus,
                    "visible":["fila1","fila2"],
                    "moving": moving,
                    "mode": "motion" if moving else "read",
                    "idea": s.get("idea") or s["title"],
                    "cut": a == start and start > 0,
                    "cues": [
                        {"scene": scene, "sentence": i}
                        for scene, i, spoken in cues
                        if math.floor(spoken["absolute_start_sample"] * fps / rate) < b
                        and math.ceil(spoken["absolute_end_sample"] * fps / rate) > a
                    ],
                }
            )
    return {"fps": fps, "frames": total, "tracks": tracks, "beats": beats}


HTML = """<!doctype html><meta charset="utf-8"><style>*{margin:0}img{display:block}</style>
<img id="frame" alt=""><script>
const data=DATA, image=document.querySelector('#frame');
[image.width,image.height]=data.size;
window.renderAt=async(localSeconds,absoluteFrame)=>{
  const path=data.files[absoluteFrame-data.start];
  if(!path)throw Error('Frame outside this scene: '+absoluteFrame);
  if(image.getAttribute('src')!==path){image.src=path;await image.decode();}
};</script>"""


def prepare(recipe, timeline_file, root, attention_path=None):
    spec = read(recipe)
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    timeline_file = timeline_file.resolve()
    audio = json.loads(timeline_file.read_text(encoding="utf-8-sig"))
    total, positions = clock(spec, audio)
    attention = (
        json.loads(attention_path.read_text(encoding="utf-8-sig"))
        if attention_path
        else score(spec, audio, total, positions)
    )
    write(root / "atencion.json", attention)
    write(root / "direccion-sincronizada.json", spec)
    assets = root / "cuadros"
    assets.mkdir(exist_ok=True)
    frames = {}
    scenes = []
    for ordinal, (s, (a, b)) in enumerate(zip(spec["scenes"], positions)):
        paths = []
        last_index=None
        filename=None
        for local in range(b - a):
            index=0 if s.get("readingOnly") else min(max(local,s["cue"]),s["cue"]+s["move"]-1)
            if index!=last_index:
                im, _, _ = frame(spec, s, index)
                digest = hashlib.sha256(im.tobytes()).hexdigest()
                if digest not in frames:
                    frames[digest]="cuadros/" + digest + ".png"
                    im.save(root / frames[digest])
                filename=frames[digest]
                last_index=index
            paths.append(filename)
        html = f"plano-{ordinal + 1}.html"
        (root / html).write_text(
            HTML.replace(
                "DATA", json.dumps({"size": spec["size"], "files": paths, "start": a})
            ),
            encoding="utf-8",
        )
        scenes.append({"id": s["id"], "title": s["title"], "html": html})
    film = {
        "width": spec["size"][0],
        "height": spec["size"][1],
        "fps": spec["fps"],
        "audioTimeline": paths_relative(root, timeline_file),
        "attention": "atencion.json",
        "subtitleLanguage": "spa",
        "scenes": scenes,
        "assets": ["direccion-sincronizada.json", *frames.values()],
    }
    write(root / "film.json", film)
    return root / "film.json"


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("recipe", type=Path)
    cli.add_argument("audio_timeline", type=Path)
    cli.add_argument("--out", type=Path, required=True)
    cli.add_argument("--attention", type=Path)
    cli.add_argument("--render", action="store_true")
    cli.add_argument("--browser", choices=("msedge", "chrome", "chromium"))
    args = cli.parse_args()
    root=args.out.resolve()
    prepare(args.recipe,args.audio_timeline,root,args.attention)
    if args.render:
        command = [
            which("uv") or "uv",
            "run",
            "--python",
            "3.13",
            str(SKILLS / "line-world-video/scripts/compose_narrated.py"),
            str(root / "film.json"),
            "--output",
            str(root / "con-voz.mp4"),
            "--report",
            str(root / "revision.json"),
        ]
        if args.browser:
            command.extend(["--browser", args.browser])
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
