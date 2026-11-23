"""Revisit frame notes after a recut or reflow. Write exact frames, a review page and importable candidate notes."""
import argparse
from bisect import bisect_right
from html import escape
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from frame_notes import digest, extract_frame, model, read, validate


def signature(beat):
    """Match an editorial moment using the narration, focus and purpose of the beat."""
    cues = beat.get("cues")
    if not isinstance(cues, list) or not cues:
        raise ValueError("El tramo carece de referencias a la narración.")
    keys = []
    for cue in cues:
        if not isinstance(cue, dict) or not isinstance(cue.get("scene"), str) or type(cue.get("sentence")) is not int:
            raise ValueError("El tramo carece de una referencia válida a escena y frase.")
        keys.append((cue["scene"], cue["sentence"]))
    if not beat.get("focus") or not beat.get("idea") or not beat.get("mode"):
        raise ValueError("Falta el foco, la idea o el tipo de movimiento en el tramo.")
    return tuple(sorted(keys)), beat["focus"], beat["idea"].strip(), beat["mode"]


def matching_ranges(info, key, element):
    ranges = []
    for beat in info["beats"]:
        try:
            matches = signature(beat) == key
        except ValueError:
            matches = False
        if not matches or element and element not in beat.get("visible", info["tracks"]):
            continue
        if ranges and ranges[-1][1] == beat["start"]:
            ranges[-1][1] = beat["end"]
        else:
            ranges.append([beat["start"], beat["end"]])
    return ranges


def locate(frame, source, candidate, element=None):
    starts = [beat["start"] for beat in source["beats"]]
    beat = source["beats"][bisect_right(starts, frame)-1]
    key = signature(beat)
    original = matching_ranges(source, key, element)
    target = matching_ranges(candidate, key, element)
    if len(original) != 1 or len(target) != 1:
        raise ValueError("El tramo cambió, se repite o el elemento dejó de estar visible.")
    start, limit = original[0]
    if not start <= frame < limit:
        raise ValueError("El elemento no aparece en el tramo señalado.")
    first, end = target[0]
    # Align the first and last presented frames even when fps, beat length or scene order changed.
    f = (frame-start) / max(1, limit-start-1)
    return first + round(f * (end-first-1))


def relocate(note, source, candidate):
    element = note.get("element")
    if not element or element not in candidate["tracks"]:
        raise ValueError("Selecciona el detalle de nuevo. Falta un elemento común a las dos versiones.")
    frame = locate(note["frame"], source, candidate, element)
    end = frame if note["endFrame"] == note["frame"] else locate(note["endFrame"], source, candidate)
    if end < frame:
        raise ValueError("Las frases del intervalo cambiaron de orden.")
    x, y, w, h = source["tracks"][element]["box"]
    nx, ny, nw, nh = candidate["tracks"][element]["box"]
    u, v = note["point"]
    point = [nx + nw * (u-x)/w, ny + nh * (v-y)/h]
    beat = next(b for b in candidate["beats"] if b["start"] <= frame < b["end"])
    return {"id": note["id"], "text": note["text"], "kind": note["kind"], "element": element,
            "frame": frame, "endFrame": end, "point": [round(max(0, min(v, 1)), 6) for v in point],
            "seconds": candidate["pts"][frame], "scene": beat["cues"][0]["scene"], "cues": beat["cues"], "idea": beat["idea"]}


def figure(label, note, info, path):
    x, y = [coord*100 for coord in note["point"]]
    when = f'{info["pts"][note["frame"]]:.3f}'.replace(".", ",")
    return (f'<figure><div class="picture"><img src="{path.name}" alt="Fotograma de la versión {label.lower()}">'
            f'<i style="left:{x:.6f}%;top:{y:.6f}%" aria-label="Punto señalado"></i></div>'
            f'<figcaption>{label} · {when} s · f{note["frame"]} · {info["width"]} × {info["height"]}</figcaption></figure>')


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def compare(before, after, notes_file, before_plan, after_plan, out):
    source = model(before, before_plan)
    candidate = model(after, after_plan)
    notes = validate(read(notes_file), source)
    target_notes = {"version": 1, "videoSha256": candidate["videoSha256"], "attentionSha256": candidate["attentionSha256"], "notes": []}
    report = {"source": source["videoSha256"], "candidate": candidate["videoSha256"], "notes": []}
    sections = []
    out.mkdir(parents=True, exist_ok=True)
    inputs = {p.resolve() for p in (before, after, notes_file, before_plan, after_plan)}
    with tempfile.TemporaryDirectory(dir=out) as temp:
        stage = Path(temp)
        for index, note in enumerate(notes, 1):
            old_frame = stage / f"nota-{index:03d}-original-f{note['frame']:06d}.png"
            extract_frame(before, note["frame"], old_frame)
            panels = figure("Original", note, source, old_frame)
            result = {"id": note["id"], "sourceFrame": note["frame"], "sourceImage": old_frame.name,
                      "sourceImageSha256": digest(old_frame)}
            try:
                moved = relocate(note, source, candidate)
            except ValueError as error:
                result.update(status="sin-correspondencia", reason=str(error))
                panels += f'<p>{escape(str(error))}</p>'
            else:
                new_frame = stage / f"nota-{index:03d}-candidata-f{moved['frame']:06d}.png"
                extract_frame(after, moved["frame"], new_frame)
                target_notes["notes"].append(moved)
                result.update(status="por-revisar", candidateFrame=moved["frame"], candidateImage=new_frame.name,
                              candidatePoint=moved["point"], candidateImageSha256=digest(new_frame))
                panels += figure("Candidata", moved, candidate, new_frame)
            report["notes"].append(result)
            action = "Ajustar" if note["kind"] == "ajustar" else "Conservar"
            element = note.get("element")
            name = "Zona de la imagen"
            if element:
                words = re.sub(r"^[^-]+-\d+-", "", element).replace("-", " ").replace("_", " ")
                name = source["tracks"][element].get("label") or words[:1].upper()+words[1:]
            sections.append(f'<section><h2>{action} · {escape(name)}</h2>'
                            f'<p>{escape(note["text"])}</p><div class="pair">{panels}</div></section>')
        validate(target_notes, candidate)
        write_json(stage/"notas-candidata.json", target_notes)
        write_json(stage/"correspondencias.json", report)
        template = Path(__file__).resolve().parents[1]/"assets/templates/frame-comparison.html"
        (stage/"comparar.html").write_text(template.read_text(encoding="utf-8").replace("<!--NOTES-->", "".join(sections)), encoding="utf-8")
        files = list(stage.iterdir())
        if any((out/file.name).resolve() in inputs for file in files):
            raise ValueError("Elige una carpeta de salida separada de los archivos de entrada.")
        for file in sorted(files, key=lambda p: p.name == "comparar.html"):
            file.replace(out/file.name)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("notes", type=Path)
    parser.add_argument("--before-plan", required=True, type=Path)
    parser.add_argument("--after-plan", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = compare(args.before, args.after, args.notes, args.before_plan, args.after_plan, args.out)
    missing = sum(note["status"] == "sin-correspondencia" for note in report["notes"])
    print(json.dumps({"page": str(args.out/"comparar.html"), "notes": len(report["notes"]), "unmatched": missing}))
    return 2 if missing else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        sys.exit(2)
