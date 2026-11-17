#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build offline batchUpdate bodies from settled D3 geometry."""

import math
import re
from pathlib import Path


Frame = tuple[float, float, float, float]
OBJECT_ID = re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_:-]{4,49}")
SHAPE_TYPES = {"rect": "RECTANGLE", "ellipse": "ELLIPSE", "text": "TEXT_BOX"}
TEXT_ALIGNMENTS = {"left": "START", "center": "CENTER", "right": "END"}
NO_PAINT = {"propertyState": "NOT_RENDERED"}


def points(value: float) -> dict:
    return {"magnitude": value, "unit": "PT"}


def rgb(color: str) -> dict:
    channels = [int(color[start:start + 2], 16) / 255 for start in (1, 3, 5)]
    return {"rgbColor": dict(zip(("red", "green", "blue"), channels))}


def solid_fill(color: str, alpha: float = 1) -> dict:
    return {"solidFill": {"color": rgb(color), "alpha": alpha}}


def element_properties(page_id: str, box: Frame) -> dict:
    x, y, width, height = box
    return {
        "pageObjectId": page_id,
        "size": {"width": points(width), "height": points(height)},
        "transform": {
            "scaleX": 1,
            "scaleY": 1,
            "translateX": x,
            "translateY": y,
            "unit": "PT",
        },
    }


def line_requests(mark: dict, page_id: str, object_id: str, fit: Frame, scale: float) -> list[dict]:
    x, y, _, _ = fit
    x1 = x + mark["x1"] * scale
    y1 = y + mark["y1"] * scale
    dx = (mark["x2"] - mark["x1"]) * scale
    dy = (mark["y2"] - mark["y1"]) * scale

    # Rotate a positive-size diagonal onto the segment, including axis-aligned lines.
    length = math.hypot(dx, dy)
    if not length:
        raise ValueError("Editable lines need distinct endpoints.")
    side = length / math.sqrt(2)
    cosine = (dx + dy) / (2 * side)
    sine = (dy - dx) / (2 * side)
    properties = element_properties(page_id, (x1, y1, side, side))
    properties["transform"].update(scaleX=cosine, scaleY=cosine, shearX=-sine, shearY=sine)
    return [
        {"createLine": {"objectId": object_id, "elementProperties": properties, "category": "STRAIGHT"}},
        {"updateLineProperties": {
            "objectId": object_id,
            "lineProperties": {
                "lineFill": solid_fill(mark["stroke"], mark.get("strokeAlpha", 1)),
                "weight": points(mark["strokeWidth"] * scale),
                "dashStyle": "SOLID",
                "startArrow": "NONE",
                "endArrow": "NONE",
            },
            "fields": "lineFill,weight,dashStyle,startArrow,endArrow",
        }},
    ]


def text_requests(mark: dict, object_id: str, scale: float) -> list[dict]:
    text_range = {"type": "ALL"}
    text_style = {
        "foregroundColor": {"opaqueColor": rgb(mark["fill"])},
        "fontFamily": mark["fontFamily"],
        "fontSize": points(mark["fontSize"] * scale),
        "bold": mark["bold"],
        "italic": mark["italic"],
    }
    paragraph_style = {
        "alignment": TEXT_ALIGNMENTS[mark["align"]],
        "lineSpacing": 100,
        "spaceAbove": points(0),
        "spaceBelow": points(0),
    }
    return [
        {"insertText": {"objectId": object_id, "text": mark["text"], "insertionIndex": 0}},
        {"updateTextStyle": {
            "objectId": object_id,
            "textRange": text_range,
            "style": text_style,
            "fields": ",".join(text_style),
        }},
        {"updateParagraphStyle": {
            "objectId": object_id,
            "textRange": text_range,
            "style": paragraph_style,
            "fields": ",".join(paragraph_style),
        }},
    ]


def shape_requests(mark: dict, page_id: str, object_id: str, fit: Frame, scale: float) -> list[dict]:
    left, top, _, _ = fit
    x = left + mark["x"] * scale
    y = top + mark["y"] * scale
    width = mark["width"] * scale
    height = mark["height"] * scale
    angle = mark.get("rotation", 0)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    fields = "shapeBackgroundFill,outline"

    if mark["kind"] == "text":
        # Allow for native text insets and font metrics while keeping the SVG anchor.
        horizontal_inset = 7.2
        vertical_inset = 4.0
        width_slack = max(4.0, width * 0.08)
        align_fraction = {"left": 0, "center": 0.5, "right": 1}[mark["align"]]
        left_padding = horizontal_inset + width_slack * align_fraction
        box = (
            x - cosine * left_padding + sine * vertical_inset,
            y - sine * left_padding - cosine * vertical_inset,
            width + 2 * horizontal_inset + width_slack,
            height + 2 * vertical_inset,
        )
        style = {
            "shapeBackgroundFill": NO_PAINT,
            "outline": NO_PAINT,
            "contentAlignment": "MIDDLE",
            "autofit": {"autofitType": "NONE"},
        }
        # The other Autofit properties are read-only in the Slides API.
        fields += ",contentAlignment,autofit.autofitType"
    else:
        box = (x, y, width, height)
        outline = NO_PAINT
        if mark["stroke"] is not None and mark["strokeWidth"] > 0:
            outline = {
                "outlineFill": solid_fill(mark["stroke"], mark.get("strokeAlpha", 1)),
                "weight": points(mark["strokeWidth"] * scale),
                "dashStyle": "SOLID",
            }
        style = {
            "shapeBackgroundFill": (
                solid_fill(mark["fill"], mark.get("fillAlpha", 1))
                if mark["fill"] is not None else NO_PAINT
            ),
            "outline": outline,
        }
    properties = element_properties(page_id, box)
    if angle:
        properties["transform"].update(scaleX=cosine, scaleY=cosine, shearX=-sine, shearY=sine)
    requests = [
        {"createShape": {
            "objectId": object_id,
            "shapeType": SHAPE_TYPES[mark["kind"]],
            "elementProperties": properties,
        }},
        {"updateShapeProperties": {
            "objectId": object_id,
            "shapeProperties": style,
            "fields": fields,
        }},
    ]
    if mark["kind"] == "text":
        requests.extend(text_requests(mark, object_id, scale))
    return requests


def path_requests(mark: dict, page_id: str, object_id: str, fit: Frame, scale: float,
                  viewport: tuple[float, float], tolerance: float) -> list[dict]:
    from path_geometry import path_paints

    parts = [(points, paint["color"], paint["alpha"])
             for paint in path_paints(mark, viewport, tolerance, scale)
             for points in paint["triangles"]]
    if not parts:
        return []
    x, y, _, _ = fit
    children = []
    requests = []
    for index, ((a, b, c), color, alpha) in enumerate(parts, start=1):
        part_id = object_id if len(parts) == 1 else f"{object_id}-t{index}"
        children.append(part_id)
        # RIGHT_TRIANGLE has intrinsic vertices (0,0), (0,100), (100,100).
        properties = element_properties(page_id, (x + a[0] * scale, y + a[1] * scale, 100, 100))
        properties["transform"].update(
            scaleX=(c[0] - b[0]) * scale / 100,
            shearY=(c[1] - b[1]) * scale / 100,
            shearX=(b[0] - a[0]) * scale / 100,
            scaleY=(b[1] - a[1]) * scale / 100,
        )
        requests.extend([
            {"createShape": {"objectId": part_id, "shapeType": "RIGHT_TRIANGLE",
                             "elementProperties": properties}},
            {"updateShapeProperties": {
                "objectId": part_id,
                "shapeProperties": {"shapeBackgroundFill": solid_fill(color, alpha), "outline": NO_PAINT},
                "fields": "shapeBackgroundFill,outline",
            }},
        ])
    if len(children) > 1:
        requests.append({"groupObjects": {"groupObjectId": object_id, "childrenObjectIds": children}})
    return requests


def build_batch(
    scene: dict,
    mode: str,
    page_id: str,
    prefix: str,
    frame: Frame,
    preview: Path,
    alt_title: str,
    alt_description: str,
    revision: str | None,
    create_slide: bool,
    path_tolerance: float = 0.45,
) -> tuple[dict, list[str], Frame]:
    """Return a request body, ordered visual IDs, and fitted bounds in points."""
    if mode not in ("editable", "image"):
        raise ValueError("Batch mode must be editable or image.")
    if not page_id or (create_slide and not OBJECT_ID.fullmatch(page_id)):
        raise ValueError("Supply the destination page ID or a valid ID for the new slide.")
    left, top, width, height = frame
    scene_width = scene["width"]
    scene_height = scene["height"]
    if not all(math.isfinite(value) for value in (*frame, scene_width, scene_height)):
        raise ValueError("Source dimensions and frame coordinates must be finite.")
    if min(width, height, scene_width, scene_height) <= 0:
        raise ValueError("Source and frame dimensions must be positive.")
    scale = min(width / scene_width, height / scene_height)
    fitted_width = scene_width * scale
    fitted_height = scene_height * scale
    fit = (left + (width - fitted_width) / 2, top + (height - fitted_height) / 2, fitted_width, fitted_height)
    count = 1 if mode == "image" else len(scene["marks"])
    if not count:
        raise ValueError("Editable mode requires visible supported marks.")
    ids = [f"{prefix}-{index}" for index in range(1, count + 1)]
    if page_id in ids or any(not OBJECT_ID.fullmatch(object_id) for object_id in ids):
        raise ValueError("The object prefix must produce valid Slides IDs distinct from the page ID.")

    requests = []
    if create_slide:
        requests.append({"createSlide": {"objectId": page_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
    if mode == "image":
        object_id = ids[0]
        requests.extend([
            {"createImage": {
                "objectId": object_id,
                "elementProperties": element_properties(page_id, fit),
                "url": str(preview.resolve()),
            }},
            {"updatePageElementAltText": {
                "objectId": object_id,
                "title": alt_title,
                "description": alt_description,
            }},
        ])
    else:
        actual_ids = []
        triangle_count = 0
        for mark, object_id in zip(scene["marks"], ids, strict=True):
            if mark["kind"] == "path":
                native = path_requests(mark, page_id, object_id, fit, scale,
                                       (scene_width, scene_height), path_tolerance)
                triangle_count += sum("createShape" in request for request in native)
                if triangle_count > 1600:
                    raise ValueError("The slide exceeds the editable path complexity limit. Increase --path-tolerance.")
                if native:
                    requests.extend(native)
                    actual_ids.append(object_id)
                continue
            build_requests = line_requests if mark["kind"] == "line" else shape_requests
            requests.extend(build_requests(mark, page_id, object_id, fit, scale))
            actual_ids.append(object_id)
        if not actual_ids:
            raise ValueError("The SVG has no visible geometry in the destination frame.")
        ids = actual_ids

    body = {"requests": requests}
    if revision:
        body["writeControl"] = {"requiredRevisionId": revision}
    return body, ids, fit
