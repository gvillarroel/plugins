#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=10,<13"]
# ///
"""Remove declared controls and fit an approved SVG presentation frame."""

from __future__ import annotations

import io
import math

from PIL import Image, ImageChops


def declared_frame(locator):
    """Translate an author-specified SVG user-space box into rendered CSS pixels."""
    raw = locator.get_attribute("data-d3-export-frame")
    if raw is None:
        return None
    try:
        x, y, width, height = map(float, raw.replace(",", " ").split())
    except ValueError:
        raise ValueError("Use four numbers in data-d3-export-frame.") from None
    if not all(map(math.isfinite, (x, y, width, height))) or min(width, height) <= 0:
        raise ValueError("Use a finite, positive data-d3-export-frame.")
    return locator.evaluate(r"""(svg, [x, y, width, height]) => {
        const matrix = svg.getScreenCTM();
        const bounds = svg.getBoundingClientRect();
        if (!matrix || Math.abs(matrix.b) > 1e-8 || Math.abs(matrix.c) > 1e-8 ||
            matrix.a <= 0 || matrix.d <= 0) {
            throw new Error('The SVG export frame requires an axis-aligned root.');
        }
        return [matrix.a*x + matrix.e - bounds.left, matrix.d*y + matrix.f - bounds.top,
                matrix.a*width, matrix.d*height];
    }""", [x, y, width, height])


def picture_crop(picture, box):
    with Image.open(io.BytesIO(picture)) as image:
        output = io.BytesIO()
        image.crop(box).save(output, format="PNG")
        return output.getvalue()


def margin_box(image):
    """Find removable flat margins without thresholding foreground paint."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    # RGB channels in fully transparent pixels do not affect visible paint.
    if alpha.getextrema()[1] == 0:
        return None
    if alpha.getpixel((0, 0)) == 0:
        painted = alpha.getbbox()
    else:
        background = rgba.getpixel((0, 0))
        corners = [(rgba.width - 1, 0), (0, rgba.height - 1), (rgba.width - 1, rgba.height - 1)]
        if background[3] != 255 or any(rgba.getpixel(point) != background for point in corners):
            return None
        rgb = rgba.convert("RGB")
        difference = ImageChops.difference(rgb, Image.new("RGB", rgb.size, background[:3]))
        painted = difference.getbbox()
        if alpha.getextrema()[0] != 255:
            return None
    if not painted:
        return None
    left, top, right, bottom = painted
    padding = max(8, round(min(right - left, bottom - top) * 0.07))
    # Keep a minimum viewport so small marks never become disproportionately large.
    xmin = min(left - padding, (left + right - rgba.width * 0.80) / 2)
    ymin = min(top - padding, (top + bottom - rgba.height * 0.80) / 2)
    xmax = max(right + padding, (left + right + rgba.width * 0.80) / 2)
    ymax = max(bottom + padding, (top + bottom + rgba.height * 0.80) / 2)
    return max(0, math.floor(xmin)), max(0, math.floor(ymin)), min(rgba.width, math.ceil(xmax)), min(rgba.height, math.ceil(ymax))


def translated_mark(mark, crop):
    left, top, right, bottom = crop
    copy = dict(mark)
    kind = mark["kind"]
    if kind == "path":
        a, b, c, d, x, y = mark["matrix"]
        copy["matrix"] = [a, b, c, d, x - left, y - top]
        return copy
    stroke = mark.get("strokeWidth", 0) / 2
    if kind == "line":
        x1, y1, x2, y2 = (mark[key] for key in ("x1", "y1", "x2", "y2"))
        x0, y0, x_end, y_end = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        copy.update(x1=x1 - left, y1=y1 - top, x2=x2 - left, y2=y2 - top)
    else:
        x, y, width, height = (mark[key] for key in ("x", "y", "width", "height"))
        angle = mark.get("rotation", 0)
        cosine, sine = math.cos(angle), math.sin(angle)
        corners = [(x + dx*cosine - dy*sine, y + dx*sine + dy*cosine)
                   for dx, dy in ((0, 0), (width, 0), (0, height), (width, height))]
        xs, ys = zip(*corners)
        x0, y0, x_end, y_end = min(xs), min(ys), max(xs), max(ys)
        copy.update(x=x - left, y=y - top)
    if x_end + stroke < left or y_end + stroke < top or x0 - stroke > right or y0 - stroke > bottom:
        return None
    if x0 - stroke >= left - 0.5 and y0 - stroke >= top - 0.5 and x_end + stroke <= right + 0.5 and y_end + stroke <= bottom + 0.5:
        return copy
    if kind == "rect" and not (stroke or mark.get("fillGradient") or mark.get("rotation")):
        x0, y0, x_end, y_end = max(left, x0), max(top, y0), min(right, x_end), min(bottom, y_end)
        if x_end <= x0 or y_end <= y0:
            return None
        copy.update(x=x0 - left, y=y0 - top, width=x_end - x0, height=y_end - y0)
        return copy
    raise ValueError("The export frame intersects an editable shape or label.")


def translated_layer(layer, crop):
    if "marks" in layer:
        return {"marks": [result for mark in layer["marks"] if (result := translated_mark(mark, crop)) is not None]}
    left, top, right, bottom = crop
    x, y, width, height = layer["frame"]
    with Image.open(io.BytesIO(layer["png"])) as image:
        sx, sy = width / image.width, height / image.height
        box = (max(0, round((left - x) / sx)), max(0, round((top - y) / sy)),
               min(image.width, round((right - x) / sx)), min(image.height, round((bottom - y) / sy)))
    if box[0] >= box[2] or box[1] >= box[3]:
        return None
    return {"png": picture_crop(layer["png"], box),
            "frame": (x + box[0]*sx - left, y + box[1]*sy - top,
                      (box[2] - box[0])*sx, (box[3] - box[1])*sy)}


def crop_presentation(picture, scene, declared, trim, available_size):
    if declared is None and not trim:
        return picture, scene
    with Image.open(io.BytesIO(picture)) as image:
        width, height = image.size
        sx, sy = width / scene["width"], height / scene["height"]
        if declared is not None:
            x, y, w, h = declared
            box = (round(x*sx), round(y*sy), round((x+w)*sx), round((y+h)*sy))
            if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
                raise ValueError("The declared export frame must fit inside the rendered SVG.")
        else:
            box = margin_box(image)
            if box is None:
                return picture, scene
            aw, ah = available_size
            scale = min(aw / (width/sx), ah / (height/sy))
            cropped_scale = min(aw / ((box[2] - box[0])/sx), ah / ((box[3] - box[1])/sy))
            if cropped_scale < scale * 1.08:
                return picture, scene
    crop = [coordinate / scale for coordinate, scale in zip(box, (sx, sy, sx, sy))]
    result = dict(scene, width=crop[2] - crop[0], height=crop[3] - crop[1], sourceCropPx=list(box))
    if scene.get("layers") or not scene["unsupported"]:
        try:
            if scene.get("layers"):
                result["layers"] = [value for layer in scene["layers"]
                                    if (value := translated_layer(layer, crop)) is not None]
            else:
                result["marks"] = translated_layer({"marks": scene["marks"]}, crop)["marks"]
        except ValueError as error:
            if declared is None:
                return picture, scene
            result["layers"] = None
            result["unsupported"] = [*scene["unsupported"], str(error)]
    return picture_crop(picture, box), result
