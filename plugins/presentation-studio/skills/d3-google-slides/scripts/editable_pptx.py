#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fonttools>=4.55,<5", "playwright>=1.52,<2",
#   "python-pptx>=1.0.2,<2", "shapely>=2.1,<3",
# ]
# ///
"""Export settled SVG marks as editable PowerPoint shapes for Google Slides import."""

from __future__ import annotations

import argparse
import io
import math
import re
import sys
from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen, replayRecording
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.svgLib.path import parse_path
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Pt
from shapely.affinity import affine_transform
from shapely.errors import GEOSException
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient

# The skill bundle can be mounted read-only.
sys.dont_write_bytecode = True

from path_geometry import MAX_VERTICES, FlattenPen, fill_geometry, stroke_geometry


POINTS_TO_EMU = 12_700
OUTLINE_TOLERANCE_PX = 0.10
CAPS = {"butt": "flat", "round": "rnd", "square": "sq"}
JOINS = {"miter": "miter", "round": "round", "bevel": "bevel"}
ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
ALIGN_FRACTION = {"left": 0, "center": 0.5, "right": 1}
NATIVE_SHAPES = {"rect": MSO_SHAPE.RECTANGLE, "ellipse": MSO_SHAPE.OVAL}
PATH_OPERATIONS = {"moveTo": "moveTo", "lineTo": "lnTo", "curveTo": "cubicBezTo",
                   "closePath": "close"}


class CurvePen(BasePen):
    """Collect contours with explicit closure and cubic control points."""

    def __init__(self):
        super().__init__(None)
        self.contours = []
        self.commands = []

    def _moveTo(self, point):
        self.commands = [("moveTo", (point,))]

    def _lineTo(self, point):
        self.commands.append(("lineTo", (point,)))

    def _curveToOne(self, control1, control2, end):
        self.commands.append(("curveTo", (control1, control2, end)))

    def _closePath(self):
        self.commands.append(("closePath", ()))
        self._endPath()

    def _endPath(self):
        if len(self.commands) > 1:
            if self.commands[-1][0] != "closePath":
                self.commands.append(("endPath", ()))
            self.contours.append(self.commands)
        self.commands = []


def xml_node(tag, **attributes):
    element = OxmlElement("a:" + tag)
    for name, value in attributes.items():
        element.set(name, str(value))
    return element


def rgb(hex_color):
    return RGBColor.from_string(hex_color.removeprefix("#").upper())


def add_alpha(color_node, alpha):
    if alpha != 1:
        color_node.append(xml_node("alpha", val=round(alpha * 100_000)))


def paint_fill(shape, color, alpha=1, gradient=None):
    if gradient is not None:
        shape.fill.gradient()
        definition = shape._element.spPr.find(qn("a:gradFill"))
        stops = definition.find(qn("a:gsLst"))
        for old_stop in list(stops):
            stops.remove(old_stop)
        for stop in gradient["stops"]:
            entry = xml_node("gs", pos=round(stop["offset"] * 100_000))
            tint = xml_node("srgbClr", val=str(rgb(stop["color"])))
            add_alpha(tint, stop.get("alpha", 1))
            entry.append(tint)
            stops.append(entry)
        definition.find(qn("a:lin")).set("ang", str(round(gradient["angleDegrees"] * 60_000)))
    elif color is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(color)
        tint = shape._element.spPr.xpath("./a:solidFill/a:srgbClr")[0]
        add_alpha(tint, alpha)


def paint_stroke(shape, color, width, alpha=1, cap="butt", join="miter", miter_limit=4):
    if color is None or width <= 0:
        shape.line.fill.background()
        return
    shape.line.color.rgb = rgb(color)
    shape.line.width = Pt(width)
    outline = shape._element.spPr.find(qn("a:ln"))
    add_alpha(outline.xpath("./a:solidFill/a:srgbClr")[0], alpha)
    outline.set("cap", CAPS[cap])
    corner = xml_node(JOINS[join])
    if join == "miter":
        corner.set("lim", str(round(miter_limit * 100_000)))
    outline.append(corner)


def remove_theme_style(shape):
    style = shape._element.find(qn("p:style"))
    if style is not None:
        shape._element.remove(style)


def project_contours(contours, matrix):
    a, b, c, d, e, f = matrix
    return [[(command, tuple((a*x + c*y + e, b*x + d*y + f) for x, y in points))
             for command, points in contour] for contour in contours]


def path_bounds(contours):
    pen = BoundsPen(None)
    for contour in contours:
        replayRecording(contour, pen)
    return pen.bounds


def inside_viewport(bounds, viewport, margin=0):
    left, top, right, bottom = bounds
    fuzz = 1e-6
    return (left - margin >= -fuzz and top - margin >= -fuzz
            and right + margin <= viewport[0] + fuzz and bottom + margin <= viewport[1] + fuzz)


def closed_contour(contour):
    return contour if contour[-1][0] == "closePath" else [*contour[:-1], ("closePath", ())]


def is_closed(contour):
    return contour[-1][0] == "closePath"


def normalize_evenodd(curves, flat):
    """Return direction-corrected cubics for disjoint or properly nested simple rings."""
    if len(curves) != len(flat):
        return None
    rings = [Polygon(points) for points, _ in flat if len(points) >= 3]
    if len(rings) != len(curves) or any(not p.is_valid or not p.area for p in rings):
        return None
    output = []
    for i, (curve, polygon) in enumerate(zip(curves, rings, strict=True)):
        depth = 0
        for j, other in enumerate(rings):
            if i == j or not polygon.intersects(other):
                continue
            if polygon.boundary.intersects(other.boundary):
                return None
            depth += other.contains(polygon)
        contour = closed_contour(curve)
        if polygon.exterior.is_ccw != (depth % 2 == 0):
            pen = RecordingPen()
            replayRecording(contour, ReverseContourPen(pen))
            contour = pen.value
        output.append(contour)
    return output


def polygon_contours(geometry):
    if geometry.geom_type == "Polygon":
        if not geometry.is_empty:
            polygon = orient(geometry, sign=1)
            for ring in (polygon.exterior, *polygon.interiors):
                first, *points = list(ring.coords)[:-1]
                yield [("moveTo", (first,)), *(("lineTo", (point,)) for point in points),
                       ("closePath", ())]
    elif hasattr(geometry, "geoms"):
        for child in geometry.geoms:
            yield from polygon_contours(child)


def custom_shape(shapes, contours, fit, color, alpha=1, outline=None, gradient=None):
    left, top, scale = fit
    points = [point for contour in contours for _, values in contour for point in values]
    if len(points) > MAX_VERTICES:
        raise ValueError("A custom shape exceeds the editable vertex limit.")
    min_x, min_y = map(min, zip(*points))
    max_x, max_y = map(max, zip(*points))
    if gradient is not None:
        min_x, min_y, max_x, max_y = path_bounds(contours)
    width = max(1, round((max_x - min_x) * scale * POINTS_TO_EMU))
    height = max(1, round((max_y - min_y) * scale * POINTS_TO_EMU))
    shape = shapes.add_shape(MSO_SHAPE.RECTANGLE, Pt(left + min_x * scale),
                             Pt(top + min_y * scale), width, height)
    remove_theme_style(shape)
    props = shape._element.spPr
    geometry = xml_node("custGeom")
    for tag in ("avLst", "gdLst", "ahLst", "cxnLst"):
        geometry.append(xml_node(tag))
    geometry.append(xml_node("rect", l="l", t="t", r="r", b="b"))
    paths = xml_node("pathLst")
    # The Google Slides importer accepts the stock w/h attributes on custom paths.
    # Specify paint at the enclosing shape level to retain editable geometry.
    path = xml_node("path", w=width, h=height)
    for contour in contours:
        for operation, control_points in contour:
            if operation == "endPath":
                continue
            command = xml_node(PATH_OPERATIONS[operation])
            for x, y in control_points:
                command.append(xml_node("pt", x=round((x-min_x)*scale*POINTS_TO_EMU),
                                        y=round((y-min_y)*scale*POINTS_TO_EMU)))
            path.append(command)
    paths.append(path)
    geometry.append(paths)
    props.replace(props.find(qn("a:prstGeom")), geometry)
    paint_fill(shape, color, alpha, gradient)
    paint_stroke(shape, *(outline or (None, 0)))
    return shape


def add_path(shapes, mark, fit, viewport, approximations):
    pen = CurvePen()
    source = " ".join(mark["d"].split())
    parse_path(source, pen)
    if not pen.contours:
        return None
    a, b, c, d, e, f = mark["matrix"]
    norm = math.hypot(a, b, c, d)
    local_tolerance = OUTLINE_TOLERANCE_PX / norm
    flat = None

    def flattened():
        nonlocal flat
        if flat is None:
            flattener = FlattenPen(local_tolerance)
            parse_path(source, flattener)
            flat = flattener.contours
        return flat

    def clip(geometry):
        projected = affine_transform(geometry, [a, c, b, d, e, f])
        return list(polygon_contours(projected.intersection(box(0, 0, *viewport))))

    projected = project_contours(pen.contours, mark["matrix"])
    bounds = path_bounds(projected)
    if bounds is None:
        return None
    fill = mark["fill"]
    stroke = mark["stroke"]
    gradient = mark.get("fillGradient")
    filled = None
    flattened_fill = False
    if fill:
        if mark["fillRule"] == "evenodd":
            normalized = normalize_evenodd(pen.contours, flattened())
            if normalized is not None:
                filled = project_contours(normalized, mark["matrix"])
        else:
            filled = [closed_contour(contour) for contour in projected]
        if filled is None or not inside_viewport(bounds, viewport):
            if gradient is not None:
                raise ValueError("A clipped or intersecting gradient needs a fidelity snapshot.")
            filled = clip(fill_geometry(flattened(), mark["fillRule"]))
            flattened_fill = True
            approximations.add("Some filled contours were flattened for clipping or winding normalization.")
    outlined = None
    native_outline = None
    if stroke:
        if mark["lineCap"] not in CAPS or mark["lineJoin"] not in JOINS:
            raise ValueError("The SVG stroke cap or join needs a fidelity snapshot.")
        scale_x, scale_y = math.hypot(a, b), math.hypot(c, d)
        uniform = math.isclose(scale_x, scale_y, rel_tol=1e-6)
        orthogonal = abs(a*c+b*d) <= 1e-6 * scale_x * scale_y
        join_margin = mark["miterLimit"] if mark["lineJoin"] == "miter" else 1
        cap_margin = math.sqrt(2) if mark["lineCap"] == "square" else 1
        margin = mark["strokeWidth"] * scale_x * max(join_margin, cap_margin) / 2
        if uniform and orthogonal and not mark["dashArray"] and inside_viewport(bounds, viewport, margin):
            native_outline = (stroke, mark["strokeWidth"] * scale_x * fit[2],
                              mark.get("strokeAlpha", 1), mark["lineCap"],
                              mark["lineJoin"], mark["miterLimit"])
        else:
            outlined = clip(stroke_geometry(flattened(), mark, local_tolerance))
            approximations.add("Some strokes were converted to editable filled outlines to preserve dashes, clipping, or affine scaling.")

    if filled and native_outline and not flattened_fill and all(map(is_closed, projected)):
        return custom_shape(shapes, filled, fit, fill, mark.get("fillAlpha", 1),
                            outline=native_outline, gradient=gradient)
    if filled and (native_outline or outlined):
        group = shapes.add_group_shape()
        add_path_parts(group.shapes, filled, outlined, projected, mark, fit, native_outline)
        return group
    return add_path_parts(shapes, filled, outlined, projected, mark, fit, native_outline)


def add_path_parts(shapes, filled, outlined, projected, mark, fit, native_outline):
    shape = None
    if filled:
        shape = custom_shape(shapes, filled, fit, mark["fill"], mark.get("fillAlpha", 1),
                             gradient=mark.get("fillGradient"))
    if native_outline:
        shape = custom_shape(shapes, projected, fit, None, outline=native_outline)
    if outlined:
        shape = custom_shape(shapes, outlined, fit, mark["stroke"], mark.get("strokeAlpha", 1))
    return shape


def rotated_box(mark, fit, box_x=0, box_y=0, extra_width=0, extra_height=0):
    x, y, scale = fit
    rotation = mark.get("rotation", 0)
    cosine, sine = math.cos(rotation), math.sin(rotation)
    width = mark["width"] * scale + extra_width
    height = mark["height"] * scale + extra_height
    dx = box_x + width / 2
    dy = box_y + height / 2
    center_x = x + mark["x"] * scale + cosine*dx - sine*dy
    center_y = y + mark["y"] * scale + sine*dx + cosine*dy
    return tuple(map(Pt, (center_x - width / 2, center_y - height / 2, width, height)))


def add_text(shapes, mark, fit):
    scale = fit[2]
    slack = max(16.0, mark["width"] * scale * 0.10)
    padding = 4.0
    shape = shapes.add_textbox(*rotated_box(
        mark, fit, -slack*ALIGN_FRACTION[mark["align"]], -padding, slack, 2*padding,
    ))
    frame = shape.text_frame
    frame.margin_top = frame.margin_bottom = frame.margin_left = frame.margin_right = Pt(0)
    frame.word_wrap = False
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    paragraph = frame.paragraphs[0]
    paragraph.text = mark["text"]
    paragraph.alignment = ALIGN[mark["align"]]
    paragraph.space_before = paragraph.space_after = Pt(0)
    paragraph.font.name = mark["fontFamily"]
    paragraph.font.size = Pt(mark["fontSize"] * scale)
    paragraph.font.color.rgb = rgb(mark["fill"])
    paragraph.font.bold = mark["bold"]
    paragraph.font.italic = mark["italic"]
    shape.rotation = math.degrees(mark.get("rotation", 0))
    return shape


def add_mark(shapes, mark, fit, viewport, approximations):
    kind = mark["kind"]
    x, y, scale = fit
    if kind == "path":
        return add_path(shapes, mark, fit, viewport, approximations)
    if kind == "text":
        return add_text(shapes, mark, fit)
    if kind == "line":
        shape = shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Pt(x + mark["x1"] * scale),
                                     Pt(y + mark["y1"] * scale), Pt(x + mark["x2"] * scale),
                                     Pt(y + mark["y2"] * scale))
    else:
        shape = shapes.add_shape(NATIVE_SHAPES[kind], *rotated_box(mark, fit))
        paint_fill(shape, mark["fill"], mark.get("fillAlpha", 1), mark.get("fillGradient"))
        shape.rotation = math.degrees(mark.get("rotation", 0))
    remove_theme_style(shape)
    paint_stroke(shape, mark["stroke"], mark["strokeWidth"] * scale, mark.get("strokeAlpha", 1))
    return shape


def build(scenes, page_size, frame):
    if not scenes:
        raise ValueError("At least one captured SVG scene is required.")
    page_width, page_height = page_size
    if not all(72 <= axis <= 4032 for axis in page_size):
        raise ValueError("PowerPoint slide dimensions must be between 72 and 4032 points.")
    frame_x, frame_y, frame_width, frame_height = frame or (0, 0, *page_size)
    if (not all(map(math.isfinite, (*page_size, frame_x, frame_y, frame_width, frame_height)))
            or min(page_width, page_height, frame_width, frame_height) <= 0
            or min(frame_x, frame_y) < 0
            or frame_x + frame_width > page_width + 1e-8 or frame_y + frame_height > page_height + 1e-8):
        raise ValueError("Use a positive finite slide size and a frame that fits inside it.")
    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = map(Pt, page_size)
    notes = []
    for number, scene in enumerate(scenes, 1):
        if scene.get("unsupported"):
            raise ValueError(f"Slide {number} has unsupported SVG content. " + " ".join(scene["unsupported"]))
        width, height = scene["width"], scene["height"]
        if not math.isfinite(width) or not math.isfinite(height) or min(width, height) <= 0:
            raise ValueError(f"Slide {number} has invalid SVG dimensions.")
        scale = min(frame_width / width, frame_height / height)
        fit = (frame_x + (frame_width - width * scale) / 2,
               frame_y + (frame_height - height * scale) / 2, scale)
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        approximations = set()
        try:
            for mark in scene["marks"]:
                add_mark(slide.shapes, mark, fit, (width, height), approximations)
        except GEOSException as error:
            raise ValueError(f"Slide {number} has unsupported path geometry. {error}") from error
        if not len(slide.shapes):
            raise ValueError(f"Slide {number} has no visible editable marks.")
        notes.append((number, len(slide.shapes), sorted(approximations)))
    output = io.BytesIO()
    presentation.save(output)
    return output.getvalue(), notes


def build_editable_pptx(
    scenes: list[dict], page_size: tuple[float, float] = (720, 405),
    frame: tuple[float, float, float, float] | None = None,
) -> bytes:
    """Return a PPTX containing native editable shapes, connectors, and text."""
    return build(scenes, page_size, frame)[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=Path, required=True,
                        help="Trusted local SVG or HTML. Repeat once per slide.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview-dir", type=Path)
    parser.add_argument("--selector", help="CSS selector for one SVG root per source.")
    parser.add_argument("--viewport", default="1280x720")
    parser.add_argument("--wait-ms", type=int, default=0)
    parser.add_argument("--frame-seconds", type=float,
                        help="Sample SVG and CSS animation at this time in seconds.")
    parser.add_argument("--system-fonts", action="store_true",
                        help="Block decorative Google Fonts and use installed fonts.")
    parser.add_argument("--browser", choices=("auto", "chromium", "msedge", "chrome"), default="auto")
    parser.add_argument("--page-size", nargs=2, type=float, default=(720, 405), metavar=("W", "H"),
                        help="Page width and height in points. Default is 720 by 405.")
    parser.add_argument("--frame", nargs=4, type=float, metavar=("X", "Y", "W", "H"),
                        help="Top-left and size of the visual frame in points. Default is the whole slide.")
    args = parser.parse_args()
    dimensions = re.fullmatch(r"(\d+)x(\d+)", args.viewport, re.IGNORECASE)
    if not dimensions or any(not 100 <= int(axis) <= 4096 for axis in dimensions.groups()):
        parser.error("Use a viewport WIDTHxHEIGHT with each axis between 100 and 4096.")
    if not 0 <= args.wait_ms <= 60_000:
        parser.error("Use a wait between 0 and 60000 milliseconds.")
    if args.output.suffix.lower() != ".pptx" or args.output.resolve() in {p.resolve() for p in args.source}:
        parser.error("Use a .pptx output distinct from all source files.")
    viewport = tuple(map(int, dimensions.groups()))
    from capture_svg import capture

    try:
        images = []
        scenes = []
        for source in args.source:
            image, scene = capture(source, args.selector, viewport, args.wait_ms, 2, True,
                                   args.browser, allow_gradients=True, frame_seconds=args.frame_seconds,
                                   allow_decorative_fonts=args.system_fonts)
            images.append(image)
            scenes.append(scene)
        output, notes = build(scenes, tuple(args.page_size), tuple(args.frame) if args.frame else None)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(output)
        if args.preview_dir:
            args.preview_dir.mkdir(parents=True, exist_ok=True)
            for index, (source, image) in enumerate(zip(args.source, images, strict=True), 1):
                (args.preview_dir / f"{index:02d}-{source.stem}.png").write_bytes(image)
        for slide, count, approximations in notes:
            print(f"Slide {slide} contains {count} editable objects.")
            for note in approximations:
                print(f"Slide {slide}. {note}")
    except (ValueError, OSError) as error:
        print(f"Editable PPTX export failed. {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
