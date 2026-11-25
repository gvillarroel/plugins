# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=11,<13"]
# ///
"""Render and independently decode an editable, frame-indexed Line World direction sheet."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from functools import lru_cache
from decimal import Decimal
from PIL import (
    Image,
    ImageChops,
    ImageColor,
    ImageDraw,
    ImageFilter,
    ImageFont,
    ImageStat,
)

SKILLS = Path(__file__).resolve().parents[2]
SHARED = SKILLS / "line-world-video/assets"
PALETTE = SHARED / "palettes/video-colors.json"
FONT = SHARED / "fonts/space-grotesk.ttf"
CANONICAL = json.loads(PALETTE.read_text(encoding="utf-8"))["colorsets"]["colorset1"]
ROLES = CANONICAL["roles"]
COLORS = {ImageColor.getrgb(c) for c in CANONICAL["allowed"]}
PAPER, INK, RED, GRAY, RULE = (
    ROLES[k] for k in ("surface", "ink", "primary", "muted", "line")
)
KINDS = {"transfer", "trace", "compare"}
STACKED_BAR_HEIGHTS = (0.42, 0.565)


def require(check, message):
    if not check:
        raise ValueError(message)


def integer(value):
    return type(value) is int


def read(path):
    spec = json.loads(path.read_text(encoding="utf-8-sig"),parse_float=json_decimal)
    require(spec.get("version") == 1, "version must be 1")
    fps = spec.get("fps")
    require(integer(fps) and 12 <= fps <= 60, "fps must be 12–60")
    size = spec.get("size")
    require(
        isinstance(size, list)
        and len(size) == 2
        and all(integer(n) and 320 <= n <= 3840 and n % 2 == 0 for n in size),
        "size needs two even dimensions between 320 and 3840",
    )
    require(
        isinstance(spec.get("anchor"), dict),
        "anchor must identify the persistent subject",
    )

    def text(s):
        return isinstance(s, str) and bool(s.strip())

    require(
        all(text(spec["anchor"].get(k)) for k in ("label", "value")),
        "anchor requires label and value",
    )
    require(type(spec["anchor"].get("showLabel", True)) is bool, "anchor.showLabel must be true or false")
    require(
        isinstance(spec.get("scenes"), list) and bool(spec["scenes"]),
        "scenes must be a nonempty list",
    )
    ids = set()
    for s in spec["scenes"]:
        require(
            isinstance(s, dict) and text(s.get("id")) and s["id"] not in ids,
            "each scene needs a unique id",
        )
        ids.add(s["id"])
        require(
            s.get("kind") in KINDS and text(s.get("title")),
            f"{s['id']}: missing treatment or title",
        )
        require(type(s.get("readingOnly",False)) is bool,"readingOnly must be true or false")
        labels = s.get("labels", [])
        require(
            isinstance(labels, list) and all(text(v) for v in labels),
            "labels must be strings",
        )
        count = len(labels)
        require(
            2 <= count <= 5 if s["kind"] == "trace" else count == 2,
            "use two labels or 2–5 for a trace",
        )
        if s["kind"] != "transfer":
            values = s.get("values", [])
            require(
                isinstance(values, list)
                and len(values) == count
                and all(type(x) in (int, float) and math.isfinite(x) for x in values),
                "supply finite numeric measurements; describe inequality bounds in the note",
            )
            if "fromValues" in s:
                start = s["fromValues"]
                require(
                    s["kind"] == "compare"
                    and isinstance(start, list)
                    and len(start) == 2
                    and all(
                        type(x) in (int, float) and math.isfinite(x) for x in start
                    ),
                    "fromValues requires two finite comparison values",
                )
            require(text(s.get("unit")), "provide the measurement unit")
        require(
            all(integer(s.get(k)) for k in ("cue", "move", "hold"))
            and s["cue"] >= 0
            and (s["move"] == 0 and s["cue"] == 0 if s.get("readingOnly") else s["move"] >= math.ceil(0.65 * fps))
            and s["hold"] >= math.ceil(0.8 * fps),
            "each scene needs cue >= 0, movement >= 0.65 s, reading hold >= 0.8 s",
        )
        if "note" in s:
            require(text(s["note"]), "note must contain meaningful text")
    return spec


@lru_cache(maxsize=96)
def font(px):
    return ImageFont.truetype(str(FONT), max(10, round(px)))


def rect(draw, xy, fill):
    x0, y0, x1, y1 = map(round, xy)
    if x1 > x0 and y1 > y0:
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=fill)


def label(draw, xy, value, px, limit, fill=INK, anchor="lm", max_lines=3):
    x, y = xy
    lines, size = fit_text(value, round(px), round(limit), max_lines)
    face = font(size)
    leading = round(size * 1.10)
    boxes = []
    for row, line in enumerate(lines):
        at = (round(x), round(y + (row - (len(lines) - 1) / 2) * leading))
        bounds = draw.textbbox(at, line, font=face, anchor=anchor)
        require(
            bounds[0] >= 0
            and bounds[1] >= 0
            and bounds[2] <= draw._image.width
            and bounds[3] <= draw._image.height,
            f"Text exceeds the canvas: {value!r}",
        )
        draw.text(at, line, font=face, fill=fill, anchor=anchor)
        boxes.append(bounds)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


@lru_cache(maxsize=600)
def fit_text(value, px, limit, max_lines):
    normalized = " ".join(value.split())
    for size in range(max(11, px), 9, -1):
        face = font(size)
        lines = [""]
        for word in normalized.split(" "):
            candidate = (lines[-1] + " " + word).strip()
            if face.getlength(candidate) <= limit:
                lines[-1] = candidate
            elif lines[-1] and face.getlength(word) <= limit:
                lines.append(word)
            else:
                break
        else:
            if len(lines) <= max_lines:
                return lines, size
    raise ValueError(f"Text does not fit {limit}px across {max_lines} lines: {value!r}")


def json_decimal(token):
    value = float(token)
    if not math.isfinite(value) or Decimal(str(value)) != Decimal(token):
        raise ValueError(f"El número {token} pierde precisión al pasar a la escala del gráfico. "
                         "Usa una base o unidad documentada que conserve la diferencia.")
    return value


_UNIT_FORMS = (
    ("euro","euros"),("dólar","dólares"),("céntimo","céntimos"),("centavo","centavos"),
    ("milisegundo","milisegundos"),("segundo","segundos"),("minuto","minutos"),("hora","horas"),("día","días"),
    ("metro","metros"),("kilómetro","kilómetros"),("centímetro","centímetros"),
    ("litro","litros"),("mililitro","mililitros"),("gramo","gramos"),("kilogramo","kilogramos"),
    ("grado","grados"),("grado Celsius","grados Celsius"),("unidad","unidades"),
    ("punto básico","puntos básicos"),("punto porcentual","puntos porcentuales"),
)
_UNITS_BY_SPELLING = {form.casefold(): pair for pair in _UNIT_FORMS for form in pair}


def unit_for(value, unit):
    forms = _UNITS_BY_SPELLING.get(unit.casefold())
    if not forms:
        return unit
    selected = forms[0 if abs(value) == 1 else 1]
    return selected[:1].upper() + selected[1:] if unit[:1].isupper() else selected


def measure_label(value, unit):
    return f"{number(value)} {unit_for(value, unit)}"


def number(n):
    decimal = Decimal(str(n))
    value = format(decimal if decimal else Decimal(0), "f")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value.replace(".", ",")


@lru_cache(maxsize=64)
def place_trace_labels(size, points, values, px, slot, area):
    """Choose positions against the finished curve, so a reading never crosses its own stroke."""
    mask = Image.new("L", size)
    draw = ImageDraw.Draw(mask)
    draw.line(points, fill=255, width=max(3, round(px * 0.25)))
    for x, y in points:
        pad = max(3, round(px * 0.34))
        draw.rectangle((x - pad, y - pad, x + pad, y + pad), fill=255)
    positions = []
    x0, y0, x1, y1 = area
    for (x, y), value in zip(points, values):
        lines, fs = fit_text(value, round(px), round(slot), 1)
        face = font(fs)
        options = []
        for anchor, dx, dy in (
            ("mm", 0, -1.05),
            ("lm", 0.75, -0.75),
            ("rm", -0.75, -0.75),
            ("lm", 0.75, 0.75),
            ("rm", -0.75, 0.75),
            ("mm", 0, 1.05),
            ("mm", 0, -1.75),
            ("mm", 0, 1.75),
            ("lm", 0.6, -1.6),
            ("rm", -0.6, -1.6),
            ("mm", 0, -2.5),
            ("mm", 0, 2.5),
            ("lm", 0.6, -2.5),
            ("rm", -0.6, -2.5),
            ("mm", 0, -3.4),
        ):
            at = (round(x + dx * px), round(y + dy * px))
            box = draw.textbbox(at, lines[0], font=face, anchor=anchor)
            pad = 2
            shift = round(max(0, x0 + pad - box[0]) - max(0, box[2] + pad - x1))
            if shift:
                at = (at[0] + shift, at[1])
                box = draw.textbbox(at, lines[0], font=face, anchor=anchor)
            checking = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
            if (
                checking[0] < x0
                or checking[1] < y0
                or checking[2] > x1
                or checking[3] > y1
            ):
                continue
            overlap = mask.crop(checking).histogram()[255]
            options.append((overlap, len(options), at, anchor, checking))
        require(bool(options), f"No room for a measured trace label: {value}")
        overlap, _, at, anchor, checking = min(options)
        require(overlap == 0, f"Trace label collides with the data: {value}")
        draw.rectangle(checking, fill=255)
        positions.append((at, anchor))
    return positions


def check_flat_ink(im):
    """Exclude anti-aliased letter/line borders and inspect the remaining flat ink."""
    boundary = Image.new("L", im.size)
    for x, y in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        r, g, b = ImageChops.difference(im, ImageChops.offset(im, x, y)).split()
        boundary = ImageChops.lighter(
            boundary, ImageChops.lighter(r, ImageChops.lighter(g, b))
        )
    interior = boundary.point(lambda n: 255 if n == 0 else 0).filter(
        ImageFilter.MinFilter(3)
    )
    masked = Image.new("RGB", im.size, PAPER)
    masked.paste(im, mask=interior)
    palette = masked.getcolors(1024)
    require(
        palette is not None and all(c in COLORS for n, c in palette),
        "flat source paint departs from the Line World palette",
    )


def frame(spec, scene, index):
    w, h = spec["size"]
    portrait = w / h < 1.25
    scale = min(w / 510, h / 780) if portrait else min(w / 850, h / 450)
    pad = max(14, round(min(w, h) * 0.065))
    image = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(image)
    title_px = round(36 * scale)
    stacked = spec.get("layout") == "stacked-comparison" and w < h and scene["kind"] == "compare"
    if stacked:
        left, right = pad, w - pad
        anchor_box = (pad, 0, right, round(h * 0.135))
        subject = spec["anchor"]["value"]
        if spec["anchor"].get("showLabel", True):
            subject = spec["anchor"]["label"] + " · " + subject
        label(d, (left, h * 0.075), subject, 25 * scale, right - left, ROLES["secondaryHighlight"], max_lines=3)
        title_y, title_px = h * 0.215, round(49 * scale)
        top, bottom = (h * fraction for fraction in STACKED_BAR_HEIGHTS)
    elif portrait:
        anchor_box = (pad, pad, w - pad, round(h * 0.21))
        ax, ay = pad, pad + 15 * scale
        label(d, (ax, ay), spec["anchor"]["label"], 22 * scale, w * 0.43, ROLES["secondaryHighlight"])
        label(
            d, (w - pad, ay), spec["anchor"]["value"], 31 * scale, w * 0.43, RED, "rm"
        )
        rect(d, (pad, h * 0.19, w - pad, h * 0.19 + 2), RULE)
        title_y = h * 0.28
        left, right = pad, w - pad
        top, bottom = h * 0.43, h * 0.76
    else:
        divider = round(w * 0.256)
        anchor_box = (pad, pad, divider - pad, h - pad)
        ax, ay = pad, h * 0.36
        caption = label(
            d, (ax, ay), spec["anchor"]["label"], 22 * scale, divider - pad * 2, ROLES["secondaryHighlight"]
        )
        value_box = label(
            d,
            (ax, h * 0.59),
            spec["anchor"]["value"],
            41 * scale,
            divider - pad * 2,
            RED,
            max_lines=2,
        )
        require(
            caption[3] + 4 * scale < value_box[1], "Persistent subject labels overlap"
        )
        rect(d, (divider, pad, divider + 2, h - pad), RULE)
        left, right = divider + pad, w - pad
        title_y = h * 0.21
        top, bottom = h * 0.42, h * 0.70
    width = right - left
    height = bottom - top
    image.info["titleBox"]=label(d, (left, title_y), scene["title"], title_px, width)
    raw = 1 if scene.get("readingOnly") else max(0, min(1, (index - scene["cue"]) / (scene["move"] - 1)))
    p = raw * raw * (3 - 2 * raw)
    layers = {}

    def layer(name):
        im = Image.new("RGBA", (w, h))
        layers[name] = im
        return ImageDraw.Draw(im)

    line = max(2, round(3 * scale))
    size = max(5, round(7 * scale))
    labels = scene["labels"]
    kind = scene["kind"]
    if kind == "transfer":
        x1 = left + width * 0.13
        x2 = right - width * 0.13
        y = (top + bottom) / 2
        d.line((x1, y, x2, y), fill=RULE, width=line)
        for x, word, alignment in ((left, labels[0], "lm"), (right, labels[1], "rm")):
            label(
                d,
                (x, y + height * 0.35),
                word,
                24 * scale,
                width * 0.45,
                anchor=alignment,
            )
        x = round(x1 + (x2 - x1) * p)
        a = layer("ruta")
        if x > round(x1):
            a.line((x1, y, x, y), fill=INK, width=line)
        rect(layer("solicitud"), (x - size, y - size, x + size, y + size), RED)
    elif kind == "trace":
        values = scene["values"]
        low = min(0, *values)
        high = max(0, *values)
        span = high - low or 1
        baseline = bottom + height * low / span
        x1 = left + width * 0.12
        x2 = right - width * 0.13
        pts = [
            (x1 + (x2 - x1) * i / (len(values) - 1), baseline - height * v / span)
            for i, v in enumerate(values)
        ]
        d.line((x1, baseline, x2, baseline), fill=RULE, width=line)
        for (x, y), word in zip(pts, labels):
            slot = (x2 - x1) / (len(values) - 1)
            label(
                d,
                (x, bottom + 50 * scale),
                word,
                22 * scale,
                min(slot * 0.9, width * 0.23),
                anchor="mm",
            )
        step = p * (len(pts) - 1)
        k = min(len(pts) - 2, int(step))
        x0, y0 = pts[k]
        x1, y1 = pts[k + 1]
        fraction = step - k
        tip = (x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction)
        a = layer("medición")
        if p > 0:
            a.line([*pts[: k + 1], tip], fill=INK, width=line)
        units = [measure_label(v,scene["unit"]) for v in values]
        label_width = min(slot * 0.92, width * 0.22)
        positions = place_trace_labels(
            (w, h),
            tuple(pts),
            tuple(units),
            22 * scale,
            label_width,
            (left, top - height * 0.26, right, bottom + 26 * scale),
        )
        for j, (value, (location, alignment)) in enumerate(zip(units, positions)):
            if j <= step:
                label(
                    a,
                    location,
                    value,
                    22 * scale,
                    label_width,
                    anchor=alignment,
                    max_lines=1,
                )
        x, y = tip
        rect(layer("punto de lectura"), (x - size, y - size, x + size, y + size), RED)
    else:
        values = scene["values"]
        initial = scene.get("fromValues", [0, 0])
        low = min(0, *values, *initial)
        high = max(0, *values, *initial)
        span = high - low or 1
        if stacked:
            bar_left, usable = left, width
            value_width = width * 0.45
        else:
            bar_left = left + width * 0.29
            usable = width * (0.49 if scene.get("oneLineValues") else 0.56)
            value_width = width * (0.205 if scene.get("oneLineValues") else 0.14)
        zero_x = bar_left - low * usable / span
        if low < 0:
            if stacked:
                for y in (top, bottom):
                    d.line((zero_x,y-12*scale,zero_x,y+12*scale),fill=INK,width=line)
            else:
                d.line((zero_x,top-height*.02,zero_x,bottom-height*.03),fill=INK,width=line)
            zero_label_y = bottom + 29 * scale if stacked else top - 20 * scale
            image.info["zeroLabelBox"] = label(d,(zero_x,zero_label_y),"0",22*scale,usable,anchor="mm")
        image.info["comparisonRows"] = []
        for i, (word, v, paint) in enumerate(zip(labels, values, (GRAY, RED))):
            y = (top, bottom)[i] if stacked else top + height * (0.18 + 0.61 * i)
            label_y = y - 48 * scale if stacked else y
            name_box = label(d, (left, label_y), word, (27 if stacked else 22) * scale,
                             width * (0.50 if stacked else 0.26), max_lines=2 if stacked else 3)
            rect(d, (bar_left, y - 5 * scale, bar_left + usable, y + 5 * scale), RULE)
            a = layer(f"barra {i + 1}")
            live = initial[i] + (v - initial[i]) * p
            end = zero_x + usable * live / span
            rect(
                a,
                (min(zero_x, end), y - 8 * scale, max(zero_x, end), y + 8 * scale),
                paint,
            )
            if v == 0 and initial[i] == 0:
                # Grow a vertical zero tick in place; its x never implies nonzero quantity.
                rect(
                    a,
                    (
                        zero_x - line,
                        y - 10 * scale * p,
                        zero_x + line,
                        y + 10 * scale * p,
                    ),
                    paint,
                )
            small = abs(v - initial[i]) * usable / span < 2
            displayed = initial[i] if "fromValues" in scene and p == 0 else v
            show_numbers = "fromValues" not in scene or p == 0 or p == 1
            printed = measure_label(displayed,scene["unit"]) if show_numbers else ""
            value_box = label(
                a if small or "fromValues" in scene else d,
                (
                    right - min(8 * scale, width * 0.025) * (1 - p) if small else right,
                    label_y,
                ),
                printed,
                (40 if stacked else 22) * scale,
                value_width,
                anchor="rm",
                max_lines=1 if scene.get("oneLineValues") else 3,
            )
            image.info["comparisonRows"].append({"label":word,"displayed":printed,"color":paint,
                "labelBox":name_box,"valueBox":value_box,"zero":zero_x,"end":end,"y":y})
    if spec.get("sourceCaption"):
        credit_y = h * (0.67 if stacked else 0.925)
        image.info["sourceBox"]=label(d,(left,credit_y),spec["sourceCaption"],19*scale,width,ROLES["secondaryHighlight"],max_lines=2)
    if "note" in scene:
        temporary = Image.new("RGBA", (w, h))
        note_draw = ImageDraw.Draw(temporary)
        label(note_draw, (left, h * 0.87), scene["note"], 21 * scale, width, RED)
        note_progress = max(0, min(1, (raw - 0.60) / 0.40))
        x = round(left + width * note_progress)
        if x < w:
            temporary.paste((0, 0, 0, 0), (x, 0, w, h))
        layers["resultado"] = temporary
    fingerprints = {}
    for name, im in layers.items():
        box = im.getbbox()
        fingerprints[name] = hashlib.sha256(
            repr(box).encode() + (im.crop(box).tobytes() if box else b"")
        ).digest()
        if box:
            image.paste(im.crop(box), box, im.getchannel("A").crop(box))
    return image, fingerprints, image.crop(tuple(map(round, anchor_box))).tobytes()


def make(spec, target, source):
    w, h = spec["size"]
    fps = spec["fps"]
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        f"{w}x{h}",
        "-framerate",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-crf",
        "16",
        "-threads",
        "2",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(target),
    ]
    records = []
    samples = []
    keys = {}
    global_frame = 0
    anchor = None
    largest_error = 0.0
    maximum = 0
    with subprocess.Popen(command, stdin=subprocess.PIPE) as enc:
        try:
            for beat in spec["scenes"]:
                n = sum(beat[k] for k in ("cue", "move", "hold"))
                previous = {}
                counts = []
                hold_hash = None
                for i in range(n):
                    im, marks, identity = frame(spec, beat, i)
                    if anchor is None:
                        anchor = identity
                    require(identity == anchor, "persistent subject moved across shots")
                    changed = (
                        sum(previous[k] != v for k, v in marks.items())
                        if previous
                        else 0
                    )
                    counts.append(changed)
                    previous = marks
                    if i >= beat["cue"] + beat["move"]:
                        digest = hashlib.sha256(im.tobytes()).digest()
                        require(
                            hold_hash is None or hold_hash == digest,
                            "reading hold moved",
                        )
                        hold_hash = digest
                    if i in {0, beat["cue"] + beat["move"] // 2, n - 1}:
                        check_flat_ink(im)
                        keys[global_frame + i] = (
                            beat,
                            i,
                            hashlib.sha256(im.tobytes()).digest(),
                        )
                    enc.stdin.write(im.tobytes())
                peak = max(counts)
                require(
                    peak == 0 if beat.get("readingOnly") else 2 <= peak <= 3,
                    f"{beat['id']}: expected two or three simultaneous visible changes, measured {peak}",
                )
                maximum = max(maximum, peak)
                records.append(
                    {
                        "id": beat["id"],
                        "kind": beat["kind"],
                        "startFrame": global_frame,
                        "endFrame": global_frame + n,
                        "movementStart": global_frame + beat["cue"],
                        "readingStart": global_frame + beat["cue"] + beat["move"],
                        "peakChangingLayers": peak,
                        "framesWithTwoOrThreeChanges": sum(n >= 2 for n in counts),
                        "holdFrames": beat["hold"],
                    }
                )
                global_frame += n
            enc.stdin.close()
            require(enc.wait() == 0, "encoding failed")
        finally:
            if enc.poll() is None:
                enc.kill()
    # Recreate each expected frame from the editable source, then compare it to the decoded stream.
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(target),
        "-map",
        "0:v:0",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-threads",
        "1",
        "-",
    ]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as dec:
        for beat, record in zip(spec["scenes"], records):
            for i in range(record["endFrame"] - record["startFrame"]):
                data = dec.stdout.read(w * h * 3)
                require(len(data) == w * h * 3, "missing encoded frame")
                im = Image.frombytes("RGB", (w, h), data)
                position = record["startFrame"] + i
                if position in keys:
                    sw = round(320 * w / max(w, h))
                    sh = round(320 * h / max(w, h))
                    samples.append(
                        (position, im.resize((sw, sh), Image.Resampling.LANCZOS))
                    )
                expected, _, _ = frame(spec, beat, i)
                err = sum(ImageStat.Stat(ImageChops.difference(im, expected)).mean) / 3
                largest_error = max(largest_error, err)
        require(
            not dec.stdout.read(1) and dec.wait() == 0, "output frame count differs"
        )
    require(largest_error <= 3, "encoded film differs from its source")
    for beat, i, expected in reversed(keys.values()):
        im, _, _ = frame(spec, beat, i)
        require(
            hashlib.sha256(im.tobytes()).digest() == expected,
            "backward seek changed the image",
        )
    return {
        "fps": fps,
        "size": [w, h],
        "frames": global_frame,
        "scenes": records,
        "measuredPeak": maximum,
        "maxDecodedRgbError": round(largest_error, 4),
        "exactBackwardSeeks": len(keys),
        "flatPaletteSamples": len(keys),
        "anchorSha256": hashlib.sha256(anchor).hexdigest(),
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "canonicalPaletteSha256": hashlib.sha256(PALETTE.read_bytes()).hexdigest(),
        "fontSha256": hashlib.sha256(FONT.read_bytes()).hexdigest(),
        "mp4Sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }, samples


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("recipe", type=Path)
    cli.add_argument("-o", "--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    require(output.suffix.lower() == ".mp4", "use an MP4 output")
    require(
        args.recipe.resolve() != output.with_suffix(".json"),
        "give the output and recipe distinct basenames",
    )
    spec = read(args.recipe)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as stage:
        target = Path(stage) / output.name
        report, samples = make(spec, target, args.recipe)
        sw, sh = samples[0][1].size
        sheet = Image.new("RGB", (sw * 3, (sh + 22) * len(spec["scenes"])), PAPER)
        draw = ImageDraw.Draw(sheet)
        for k, (index, im) in enumerate(samples):
            x = sw * (k % 3)
            y = (sh + 22) * (k // 3)
            sheet.paste(im, (x, y))
            draw.text((x + 5, y + sh + 3), f"{index / spec['fps']:.2f} s", fill=INK)
        sheet.save(target.with_suffix(".jpg"), quality=90)
        target.with_suffix(".json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        for suffix in (".jpg", ".json", ".mp4"):
            os.replace(target.with_suffix(suffix), output.with_suffix(suffix))
    print(
        f"{output.name}: {report['frames']} frames, {report['measuredPeak']} moving layers maximum"
    )


if __name__ == "__main__":
    main()
