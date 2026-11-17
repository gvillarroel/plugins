#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools>=4.55,<5", "shapely>=2.1,<3"]
# ///
"""Approximate SVG path paint with native triangle geometry."""

from __future__ import annotations

from collections import Counter
from math import acos, ceil, hypot, pi

from fontTools.pens.basePen import BasePen
from fontTools.svgLib.path import parse_path
from shapely import constrained_delaunay_triangles, union_all
from shapely.affinity import affine_transform
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point as ShapelyPoint, Polygon, box
from shapely.ops import polygonize, substring


Point = tuple[float, float]
Triangle = tuple[Point, Point, Point]
MAX_VERTICES = 12_000
MAX_TRIANGLES = 2_000


def midpoint(a: Point, b: Point) -> Point:
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def distance_to_segment(point: Point, start: Point, end: Point) -> float:
    x, y = end[0] - start[0], end[1] - start[1]
    dx, dy = point[0] - start[0], point[1] - start[1]
    length_squared = x * x + y * y
    if not length_squared:
        return hypot(dx, dy)
    t = min(1.0, max(0.0, (dx * x + dy * y) / length_squared))
    return hypot(dx - t * x, dy - t * y)


class FlattenPen(BasePen):
    def __init__(self, tolerance: float):
        super().__init__(None)
        self.tolerance = tolerance
        self.contours: list[tuple[list[Point], bool]] = []
        self.points: list[Point] = []
        self.vertex_count = 0

    def _moveTo(self, point: Point) -> None:
        self.points = [point]

    def _lineTo(self, point: Point) -> None:
        self.vertex_count += 1
        if self.vertex_count > MAX_VERTICES:
            raise ValueError("A path exceeds the editable vertex limit.")
        self.points.append(point)

    def _curveToOne(self, b: Point, c: Point, d: Point) -> None:
        self.flatten_cubic(self.points[-1], b, c, d, 0)

    def flatten_cubic(self, a: Point, b: Point, c: Point, d: Point, depth: int) -> None:
        error = max(distance_to_segment(b, a, d), distance_to_segment(c, a, d))
        if error <= self.tolerance:
            self._lineTo(d)
            return
        if depth >= 18:
            raise ValueError("A path cannot be flattened within the editable tolerance.")
        ab, bc, cd = midpoint(a, b), midpoint(b, c), midpoint(c, d)
        abc, bcd = midpoint(ab, bc), midpoint(bc, cd)
        center = midpoint(abc, bcd)
        self.flatten_cubic(a, ab, abc, center, depth + 1)
        self.flatten_cubic(center, bcd, cd, d, depth + 1)

    def _closePath(self) -> None:
        self.finish(closed=True)

    def _endPath(self) -> None:
        self.finish(closed=False)

    def finish(self, closed: bool) -> None:
        if self.points:
            self.contours.append((self.points, closed))
            self.points = []


def closed_points(points: list[Point]) -> list[Point]:
    return points if points[0] == points[-1] else [*points, points[0]]


def winding_at(point: Point, ring: list[Point]) -> int:
    x, y = point
    winding = 0
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        if min(ay, by) <= y < max(ay, by) and ax + (y - ay) * (bx - ax) / (by - ay) > x:
            winding += 1 if by > ay else -1
    return winding


def fill_geometry(contours: list[tuple[list[Point], bool]], rule: str):
    rings = [closed_points(points) for points, _ in contours if len(points) >= 3]
    if len(rings) == 1:
        polygon = Polygon(rings[0])
        if polygon.is_valid:
            return polygon
    linework = union_all([LineString(ring) for ring in rings])
    included = []
    for face in polygonize(linework):
        sample = face.representative_point()
        winding = sum(winding_at((sample.x, sample.y), ring) for ring in rings)
        painted = winding % 2 != 0 if rule == "evenodd" else winding != 0
        if painted:
            included.append(face)
    return union_all(included)


def dash_lines(line: LineString, pattern: list[float], offset: float, closed: bool, cap: str):
    if not pattern or not any(pattern):
        return [line]
    if len(pattern) % 2:
        pattern = pattern * 2
    period = sum(pattern)
    if line.length / period * len(pattern) > MAX_VERTICES:
        raise ValueError("A dashed path exceeds the editable segment limit.")
    position = -(offset % period)
    index = 0
    intervals: list[tuple[float, float]] = []
    dots = []
    while position <= line.length:
        end = position + pattern[index]
        if index % 2 == 0:
            start, stop = max(0, position), min(line.length, end)
            if stop > start:
                intervals.append((start, stop))
            elif pattern[index] == 0 and 0 <= position <= line.length and cap != "flat":
                if cap == "square":
                    raise ValueError("Square-capped zero-length dashes need a snapshot.")
                dots.append(line.interpolate(position))
        position = end
        index = (index + 1) % len(pattern)
    pieces = [substring(line, start, end) for start, end in intervals]
    if closed and len(pieces) > 1 and intervals[0][0] == 0 and intervals[-1][1] == line.length:
        pieces = [LineString([*pieces[-1].coords, *list(pieces[0].coords)[1:]]), *pieces[1:-1]]
    return [*pieces, *dots]


def stroke_geometry(contours: list[tuple[list[Point], bool]], mark: dict, tolerance: float):
    radius = mark["strokeWidth"] / 2
    cap = {"butt": "flat", "round": "round", "square": "square"}[mark["lineCap"]]
    join = {"miter": "mitre", "round": "round", "bevel": "bevel"}[mark["lineJoin"]]
    angle = acos(max(0, 1 - tolerance / radius))
    quadrant = min(48, max(2, ceil(pi / (4 * angle)))) if angle else 48
    buffers = []
    for points, closed in contours:
        if len(points) < 2:
            continue
        line = LineString(closed_points(points) if closed else points)
        if not line.length:
            if closed or cap == "flat":
                continue
            if cap == "square" or mark["dashArray"]:
                raise ValueError("The visible zero-length stroke needs a snapshot.")
            pieces = [ShapelyPoint(points[0])]
        else:
            pieces = dash_lines(line, mark["dashArray"], mark["dashOffset"], closed, cap)
        buffers.extend(piece.buffer(radius, quad_segs=quadrant, cap_style=cap, join_style=join,
                                    mitre_limit=mark["miterLimit"]) for piece in pieces)
    return union_all(buffers)


def triangle_edges(points: Triangle):
    return zip(points, points[1:] + points[:1])


def edge_key(a: Point, b: Point) -> tuple[Point, Point]:
    return (a, b) if a < b else (b, a)


def cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def close_seams(points: Triangle, edges: Counter, overlap: float) -> Triangle:
    """Expand only shared edges so an opaque fill keeps its outside contour."""
    lines = []
    for a, b in triangle_edges(points):
        dx, dy = b[0] - a[0], b[1] - a[1]
        offset = overlap if edges[edge_key(a, b)] > 1 else 0
        length = hypot(dx, dy)
        lines.append(((a[0] - dy * offset / length, a[1] + dx * offset / length), (dx, dy)))
    result = []
    for i, original in enumerate(points):
        a, direction = lines[i - 1]
        b, other = lines[i]
        factor = cross((b[0] - a[0], b[1] - a[1]), other) / cross(direction, other)
        x, y = a[0] + direction[0] * factor, a[1] + direction[1] * factor
        # Acute triangles can otherwise grow far past a neighboring contour.
        if hypot(x - original[0], y - original[1]) > overlap * 3:
            result.append(original)
        else:
            result.append((x, y))
    return tuple(result)


def triangles_for(geometry, overlap: float) -> list[Triangle]:
    triangles = []
    for polygon in constrained_delaunay_triangles(geometry).geoms:
        if polygon.area < 1e-6:
            continue
        a, b, c = list(polygon.exterior.coords)[:3]
        if cross((b[0] - a[0], b[1] - a[1]), (c[0] - a[0], c[1] - a[1])) > 0:
            b, c = c, b
        triangles.append((a, b, c))
        if len(triangles) > MAX_TRIANGLES:
            raise ValueError("A path exceeds the editable triangle limit.")
    if not overlap:
        return triangles
    edges = Counter(edge_key(a, b) for triangle in triangles for a, b in triangle_edges(triangle))
    return [close_seams(triangle, edges, overlap) for triangle in triangles]


def path_paints(mark: dict, viewport: tuple[float, float], tolerance: float, scale: float) -> list[dict]:
    """Return ordered opaque or translucent meshes in the captured viewport."""
    a, b, c, d, e, f = mark["matrix"]
    # The Frobenius norm bounds maximum distortion in screen coordinates.
    local_tolerance = tolerance / hypot(a, b, c, d)
    pen = FlattenPen(local_tolerance)
    parse_path(" ".join(mark["d"].split()), pen)
    viewport_box = box(0, 0, *viewport)
    paints = []
    try:
        for kind, build in (("fill", fill_geometry), ("stroke", stroke_geometry)):
            color = mark[kind]
            if color is None or (kind == "stroke" and mark["strokeWidth"] <= 0):
                continue
            alpha = mark.get(f"{kind}Alpha", 1)
            if kind == "fill":
                geometry = build(pen.contours, mark["fillRule"])
            else:
                geometry = build(pen.contours, mark, local_tolerance)
            transformed = affine_transform(geometry, [a, c, b, d, e, f]).intersection(viewport_box)
            overlap = min(0.20 / scale, tolerance) if alpha == 1 else 0
            mesh = triangles_for(transformed, overlap)
            if mesh:
                paints.append({"color": color, "alpha": alpha, "triangles": mesh})
    except GEOSException as error:
        raise ValueError(f"SVG path geometry cannot be triangulated. {error}") from error
    return paints
