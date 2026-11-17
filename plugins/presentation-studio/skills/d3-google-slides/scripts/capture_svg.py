#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.52,<2"]
# ///

"""Capture a trusted local D3 visualization and its supported editable marks."""

from __future__ import annotations

import math
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright


_MAX_PIXELS = 25_000_000
_REMOTE = re.compile(r"^https?://", re.IGNORECASE)
_SOCKET = re.compile(r"^wss?://", re.IGNORECASE)
_CHANNELS = {
    "msedge": Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    "chrome": Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
}
_D3_IDLE = """root => ![root, ...root.querySelectorAll('*')].some(
    element => element.__transition && Object.keys(element.__transition).length
)"""


_INSPECT = r"""(root, {editable, allowGradients, frozen, paintUnits, markLimit = 1000}) => {
    if (!(root instanceof SVGSVGElement)) throw new Error('The selected element must be an SVG root.');
    const box = root.getBoundingClientRect();
    const direct = name => [...root.children].find(el => el.localName === name)?.textContent.trim();
    const report = {
        width: box.width, height: box.height, marks: [], unsupported: [],
        title: direct('title') || root.getAttribute('aria-label') || '',
        description: direct('desc') || '',
    };
    if (paintUnits) Object.assign(report, {paintUnits: [], backdropMarkCount: 0, globalUnsupported: []});
    if (!editable) return report;

    const skipped = new Set([
        'title', 'desc', 'metadata', 'defs', 'style', 'script', 'view',
        'clipPath', 'mask', 'filter', 'linearGradient', 'radialGradient', 'pattern', 'marker', 'symbol',
    ]);
    const motionNodes = ['animate', 'animateMotion', 'animateTransform', 'set'];
    if (frozen) motionNodes.forEach(tag => skipped.add(tag));
    let currentUnit = null;
    const paint = (value, keepTransparent = false) => {
        if (value === 'none') return null;
        if (value === 'transparent') return keepTransparent ? {color: '#000000', alpha: 0} : null;
        const rgb = value.match(/^rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\s*\)$/);
        if (!rgb) throw new Error('paint is not a solid RGB color');
        const alpha = Number(rgb[4] ?? 1);
        if (alpha === 0 && !keepTransparent) return null;
        const color = '#' + rgb.slice(1, 4).map(part => Number(part).toString(16).padStart(2, '0')).join('');
        return {color, alpha};
    };
    const note = (el, message) => {
        const label = el.id ? `${el.localName}#${el.id}` : el.localName;
        const entry = `${label}: ${message}`;
        const append = list => {
            if (list.length < 30 && !list.includes(entry)) list.push(entry);
        };
        append(report.unsupported);
        if (paintUnits) {
            append(currentUnit ? currentUnit.unsupported : report.globalUnsupported);
        }
    };
    const add = mark => {
        if (report.marks.length >= markLimit) throw new Error(`editable mark count exceeds ${markLimit}`);
        if (mark.kind === 'path') {
            // Python clips the actual filled and stroked path to the SVG viewport.
            report.marks.push(mark);
            return;
        }
        const {x, y, width, height, x1, y1, x2, y2, rotation = 0, strokeWidth = 0} = mark;
        const values = Object.values(mark).filter(value => typeof value === 'number');
        if (values.some(value => !Number.isFinite(value))) throw new Error('invalid geometry');
        const length = mark.kind === 'line' ? Math.hypot(x2 - x1, y2 - y1) : 0;
        const half = strokeWidth / 2;
        let minX = x ?? Math.min(x1, x2), maxX = x === undefined ? Math.max(x1, x2) : x + width;
        let minY = y ?? Math.min(y1, y2), maxY = y === undefined ? Math.max(y1, y2) : y + height;
        let marginX = length ? half * Math.abs(y2 - y1) / length : half;
        let marginY = length ? half * Math.abs(x2 - x1) / length : half;
        if (rotation) {
            const cosine = Math.cos(rotation), sine = Math.sin(rotation);
            const cx = x + (cosine * width - sine * height) / 2;
            const cy = y + (sine * width + cosine * height) / 2;
            const rw = mark.kind === 'ellipse' ? Math.hypot(cosine * width, sine * height)
                : Math.abs(cosine * width) + Math.abs(sine * height);
            const rh = mark.kind === 'ellipse' ? Math.hypot(sine * width, cosine * height)
                : Math.abs(sine * width) + Math.abs(cosine * height);
            [minX, maxX] = [cx - rw / 2, cx + rw / 2];
            [minY, maxY] = [cy - rh / 2, cy + rh / 2];
            if (mark.kind === 'rect') marginX = marginY = half * (Math.abs(cosine) + Math.abs(sine));
        }
        if (minX < marginX - 1 || minY < marginY - 1 ||
            maxX > box.width - marginX + 1 || maxY > box.height - marginY + 1) {
            throw new Error('paint extends beyond the selected SVG');
        }
        report.marks.push(mark);
    };
    const rect = (x, y, width, height, fill) => {
        if (width > 0 && height > 0 && fill) {
            if (fill.alpha !== 1) throw new Error('translucent CSS backdrop or border');
            add({kind: 'rect', x, y, width, height, fill: fill.color, stroke: null, strokeWidth: 0});
        }
    };
    const checkEffects = style => {
        if (style.clipPath !== 'none' || style.maskImage !== 'none' || style.filter !== 'none' ||
            style.mixBlendMode !== 'normal') {
            throw new Error('clip, mask, filter or blend');
        }
    };
    const svgViewport = el => {
        const svg = el.ownerSVGElement || root;
        const view = svg.viewBox.baseVal;
        return view.width > 0 && view.height > 0
            ? [view.width, view.height] : [svg.clientWidth, svg.clientHeight];
    };
    const svgLength = (value, reference) => {
        const match = value.match(/^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)(px|%)?$/i);
        if (!match) throw new Error('SVG length could not be resolved in local units');
        const magnitude = Number(match[1]) * (match[2] === '%' ? reference / 100 : 1);
        if (!Number.isFinite(magnitude)) throw new Error('nonfinite SVG length');
        return magnitude;
    };
    const localReference = (el, value) => {
        const match = value.match(/^url\("([^"]*)"\)$/);
        if (!match) throw new Error('expected a single local SVG reference');
        const target = new URL(match[1], el.baseURI), source = new URL(el.ownerDocument.URL);
        const id = decodeURIComponent(target.hash.slice(1));
        target.hash = source.hash = '';
        if (!id || target.href !== source.href) throw new Error('reference must target this SVG document');
        const reference = el.ownerDocument.getElementById(id);
        if (!reference || reference.namespaceURI !== root.namespaceURI) throw new Error('SVG reference was not found');
        return reference;
    };
    const linearGradient = (el, fill, matrix) => {
        const gradient = localReference(el, fill);
        if (gradient.localName !== 'linearGradient') {
            throw new Error('only local linear gradient fills are editable');
        }
        if ((gradient.getAttribute('gradientUnits') ?? 'objectBoundingBox') !== 'objectBoundingBox' ||
            (gradient.getAttribute('spreadMethod') ?? 'pad') !== 'pad' ||
            gradient.hasAttribute('href') || gradient.hasAttributeNS('http://www.w3.org/1999/xlink', 'href') ||
            gradient.hasAttribute('gradientTransform') ||
            !['auto', 'srgb'].includes(getComputedStyle(gradient).colorInterpolation.toLowerCase())) {
            throw new Error('linear gradient uses unsupported units, spread, inheritance, transform or color space');
        }
        if (matrix.a <= 0 || matrix.d <= 0 ||
            Math.abs(matrix.b) > 0.000001 * matrix.a || Math.abs(matrix.c) > 0.000001 * matrix.d) {
            throw new Error('editable gradient requires a positive axis-aligned object transform');
        }
        const coord = (attribute, defaultValue) => {
            const value = gradient.getAttribute(attribute);
            if (value === null) return defaultValue;
            if (/px/i.test(value)) throw new Error('gradient coordinates must be numbers or percentages');
            return svgLength(value.trim(), 1);
        };
        const x1 = coord('x1', 0), x2 = coord('x2', 1), y1 = coord('y1', 0), y2 = coord('y2', 0);
        const horizontal = y1 === y2 && x1 !== x2;
        const vertical = x1 === x2 && y1 !== y2;
        if (!horizontal && !vertical) throw new Error('editable gradient must be horizontal or vertical');
        const [start, end] = horizontal ? [x1, x2] : [y1, y2];
        if (Math.min(start, end) < 0 || Math.max(start, end) > 1) {
            throw new Error('gradient endpoints extend outside the object bounding box');
        }
        const reverse = end < start;
        const angleDegrees = (horizontal ? 0 : 90) + (reverse ? 180 : 0);
        const leadingOffset = reverse ? 1 - start : start;
        const span = Math.abs(end - start);
        const children = [...gradient.children].filter(child => !['title', 'desc'].includes(child.localName));
        if (!children.length || children.some(child => child.localName !== 'stop' || child.children.length)) {
            throw new Error('linear gradient requires explicit static stops');
        }
        const stops = children.map(stop => {
            const style = getComputedStyle(stop), color = paint(style.stopColor, true);
            const offset = stop.offset.animVal;
            if (!color || !Number.isFinite(offset) || offset < 0 || offset > 1) {
                throw new Error('invalid linear gradient stop');
            }
            return {offset: leadingOffset + span * offset, color: color.color,
                alpha: color.alpha * Number(style.stopOpacity)};
        });
        if (stops[0].offset > 0) stops.unshift({...stops[0], offset: 0});
        if (stops.at(-1).offset < 1) stops.push({...stops.at(-1), offset: 1});
        const key = stop => Math.round(stop.offset * 100000);
        if (stops.length < 2 || stops.some((stop, i) => i > 0 && key(stop) <= key(stops[i - 1]))) {
            throw new Error('gradient stops overlap or do not advance');
        }
        return {kind: 'linear', angleDegrees, stops};
    };
    const pathData = (el, style, kind, force, endpoints) => {
        if (kind === 'path') {
            if (style.d === 'none') return '';
            const match = style.d.match(/^path\("([^"]*)"\)$/);
            if (!match) throw new Error('computed SVG path could not be read');
            return match[1];
        }
        if (kind === 'polygon' || kind === 'polyline') {
            const points = el.animatedPoints;
            if (!points.numberOfItems) return '';
            const coordinates = Array.from({length: points.numberOfItems}, (_, i) => {
                const point = points.getItem(i);
                return `${point.x} ${point.y}`;
            });
            return 'M ' + coordinates.join(' L ') + (kind === 'polygon' ? ' Z' : '');
        }
        if (force && kind === 'line') {
            const [x1, y1, x2, y2] = endpoints;
            return `M ${x1} ${y1} L ${x2} ${y2}`;
        }
        if (force && (kind === 'circle' || kind === 'ellipse')) {
            const {x, y, width, height} = el.getBBox();
            if (!(width > 0 && height > 0)) return '';
            const rx = width / 2, ry = height / 2, cy = y + ry;
            const arc = `A ${rx} ${ry} 0 0 1`;
            return `M ${x + width} ${cy} ${arc} ${x} ${cy} ${arc} ${x + width} ${cy} Z`;
        }
        if (kind !== 'rect' || (!force && style.rx === 'auto' && style.ry === 'auto')) return null;
        const [vw, vh] = svgViewport(el);
        const rxValue = style.rx === 'auto' ? null : svgLength(style.rx, vw);
        const ryValue = style.ry === 'auto' ? null : svgLength(style.ry, vh);
        const {x, y, width, height} = el.getBBox();
        if (!(width > 0 && height > 0)) return '';
        const rx = Math.min(rxValue ?? ryValue, width / 2);
        const ry = Math.min(ryValue ?? rxValue, height / 2);
        const right = x + width, bottom = y + height;
        if (!(rx > 0 && ry > 0)) return force ? `M ${x} ${y} H ${right} V ${bottom} H ${x} Z` : null;
        const arc = `A ${rx} ${ry} 0 0 1`;
        return `M ${x + rx} ${y} H ${right - rx} ${arc} ${right} ${y + ry}
            V ${bottom - ry} ${arc} ${right - rx} ${bottom}
            H ${x + rx} ${arc} ${x} ${bottom - ry} V ${y + ry} ${arc} ${x + rx} ${y} Z`;
    };
    const isEllipsePath = d => {
        const tokens = d.match(/[+-]?(?:\d*\.\d+|\d+\.?)(?:[eE][+-]?\d+)?|[a-zA-Z]/g) || [];
        if (!(tokens.length === 19 || (tokens.length === 20 && tokens[19] === 'Z')) ||
            tokens[0] !== 'M' || tokens[3] !== 'A' || tokens[11] !== 'A') return false;
        const [x, y, rx, ry, angle, , sweep, x1, y1, rx2, ry2, angle2, , sweep2, x2, y2] =
            [1, 2, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18].map(i => Number(tokens[i]));
        if (rx <= 0 || ry <= 0 || rx !== rx2 || ry !== ry2 || angle || angle2 ||
            sweep !== sweep2 || x !== x2 || y !== y2) return false;
        return Math.abs(Math.hypot((x1 - x) / rx, (y1 - y) / ry) - 2) < 0.000001;
    };
    const pathStroke = (el, style, reference, stroke) => {
        if (!stroke) return {lineCap: 'butt', lineJoin: 'miter', miterLimit: 4, dashArray: [], dashOffset: 0};
        const dashArray = style.strokeDasharray === 'none' ? [] :
            style.strokeDasharray.split(/[,\s]+/).filter(Boolean).map(value => svgLength(value, reference));
        let pathScale = 1;
        if (dashArray.some(Boolean) && el.hasAttribute('pathLength')) {
            const length = Number(el.getAttribute('pathLength'));
            if (!(length > 0) || !Number.isFinite(length)) throw new Error('invalid SVG pathLength for dashes');
            pathScale = el.getTotalLength() / length;
        }
        return {lineCap: style.strokeLinecap, lineJoin: style.strokeLinejoin,
            miterLimit: Number(style.strokeMiterlimit),
            dashArray: dashArray.some(Boolean) ? dashArray.map(value => value * pathScale) : [],
            dashOffset: dashArray.some(Boolean) ? svgLength(style.strokeDashoffset, reference) * pathScale : 0};
    };
    const markerEndpoint = (el, style, kind, start, orient) => {
        if (!['line', 'path', 'polyline', 'polygon'].includes(kind)) throw new Error('unsupported arrow source shape');
        const d = kind === 'path' ? pathData(el, style, kind) : '';
        if (kind === 'path' && (d.match(/[mM]/g) ?? []).length !== 1) {
            throw new Error('arrow source requires one continuous SVG path');
        }
        const length = el.getTotalLength();
        if (!(length > 0)) throw new Error('arrow source has no tangent');
        const endpoint = el.getPointAtLength(start ? 0 : length);
        const automatic = ['auto', 'auto-start-reverse'].includes(orient);
        if (automatic && (kind === 'polygon' || /[zZ]/.test(d))) {
            throw new Error('automatically oriented arrows on closed paths require snapshot capture');
        }
        if (!automatic) {
            const match = orient.match(/^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)(deg)?$/i);
            const angle = match ? Number(match[1]) : NaN;
            if (!Number.isFinite(angle)) throw new Error('marker orientation must be auto or numeric degrees');
            return [endpoint, angle * Math.PI / 180];
        }
        const reverse = start && orient === 'auto-start-reverse' ? Math.PI : 0;
        if (kind === 'line') {
            const dx = el.x2.animVal.value - el.x1.animVal.value;
            const dy = el.y2.animVal.value - el.y1.animVal.value;
            return [endpoint, Math.atan2(dy, dx) + reverse];
        }
        let tangent = null;
        for (const fraction of [0.0001, 0.001, 0.01]) {
            const delta = Math.min(length * fraction, 0.08);
            const neighbor = el.getPointAtLength(start ? delta : length - delta);
            const dx = start ? neighbor.x - endpoint.x : endpoint.x - neighbor.x;
            const dy = start ? neighbor.y - endpoint.y : endpoint.y - neighbor.y;
            if (Math.hypot(dx, dy) > 0.000001) {
                tangent = Math.atan2(dy, dx);
                break;
            }
        }
        if (tangent === null) throw new Error('arrow source tangent could not be measured');
        return [endpoint, tangent + reverse];
    };
    const arrowMark = (el, style, kind, markerReference, start, matrix, reference) => {
        const marker = localReference(el, markerReference);
        if (marker.localName !== 'marker' || marker.hasAttribute('transform')) {
            throw new Error('arrow must use a local untransformed SVG marker');
        }
        const children = [...marker.children].filter(child => !skipped.has(child.localName));
        if (children.length !== 1 || children[0].localName !== 'path' ||
            [...children[0].children].some(child => !skipped.has(child.localName))) {
            throw new Error('arrow marker must contain one filled path');
        }
        const path = children[0];
        const markerStyle = getComputedStyle(marker), pathStyle = getComputedStyle(path);
        checkEffects(markerStyle);
        checkEffects(pathStyle);
        if (markerStyle.transform !== 'none' || pathStyle.transform !== 'none' ||
            pathStyle.stroke !== 'none' || pathStyle.display === 'none' || pathStyle.visibility !== 'visible') {
            throw new Error('arrow marker requires a visible untransformed path with no stroke');
        }
        let fillValue = pathStyle.fill;
        if (fillValue === 'context-stroke') fillValue = style.stroke;
        if (fillValue === 'context-fill') fillValue = style.fill;
        const fill = paint(fillValue);
        if (!fill) return null;
        const alpha = fill.alpha * Number(pathStyle.fillOpacity) * Number(pathStyle.opacity) * Number(markerStyle.opacity);
        if (!alpha) return null;
        const d = pathData(path, pathStyle, 'path');
        if (!d) return null;
        const attr = (name, fallback) => {
            const value = marker.getAttribute(name);
            if (value === null) return fallback;
            if (value.includes('%')) throw new Error('arrow marker coordinates must be numeric');
            return svgLength(value.trim(), 1);
        };
        const refX = attr('refX', 0), refY = attr('refY', 0);
        const width = attr('markerWidth', 3), height = attr('markerHeight', 3);
        if (width === 0 || height === 0) return null;
        if (width < 0 || height < 0) throw new Error('invalid arrow viewport');
        const units = marker.getAttribute('markerUnits') ?? 'strokeWidth';
        if (!['strokeWidth', 'userSpaceOnUse'].includes(units)) throw new Error('unsupported arrow marker units');
        const unitScale = units === 'strokeWidth' ? svgLength(style.strokeWidth, reference) : 1;
        if (!unitScale) return null;
        const ratio = (marker.getAttribute('preserveAspectRatio') ?? 'xMidYMid meet').trim();
        let sx = 1, sy = 1, left = 0, top = 0;
        if (marker.hasAttribute('viewBox')) {
            const view = marker.viewBox.baseVal;
            if (!(view.width > 0 && view.height > 0)) throw new Error('invalid arrow viewBox');
            sx = width / view.width;
            sy = height / view.height;
            if (ratio !== 'none') {
                if (!/^xMidYMid(?:\s+meet)?$/.test(ratio)) throw new Error('unsupported arrow preserveAspectRatio');
                sx = sy = Math.min(sx, sy);
            }
            left = (width - sx * view.width) / 2 - sx * view.x;
            top = (height - sy * view.height) / 2 - sy * view.y;
        }
        const bounds = path.getBBox();
        if (markerStyle.overflow !== 'visible' &&
            (left + sx * bounds.x < -0.000001 || top + sy * bounds.y < -0.000001 ||
            left + sx * (bounds.x + bounds.width) > width + 0.000001 ||
            top + sy * (bounds.y + bounds.height) > height + 0.000001)) {
            throw new Error('arrow path is clipped by its marker viewport');
        }
        const [endpoint, angle] = markerEndpoint(el, style, kind, start, marker.getAttribute('orient') ?? '0');
        const cosine = Math.cos(angle) * unitScale, sine = Math.sin(angle) * unitScale;
        // The viewBox alignment cancels between the marker path and its reference point.
        const a = cosine * sx, b = sine * sx, c = -sine * sy, d2 = cosine * sy;
        const e = endpoint.x - a * refX - c * refY, f = endpoint.y - b * refX - d2 * refY;
        const [A, B, C, D, E, F] = matrix;
        return {kind: 'path', d, matrix: [
            A * a + C * b, B * a + D * b, A * c + C * d2, B * c + D * d2,
            A * e + C * f + E, B * e + D * f + F,
        ], fill: fill.color, fillAlpha: alpha, stroke: null, strokeWidth: 0, fillRule: pathStyle.fillRule,
            ...pathStroke(path, pathStyle, reference, null)};
    };
    const backdrop = () => {
        const style = getComputedStyle(root);
        if (style.transform !== 'none' || style.boxShadow !== 'none' ||
            ['TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'].some(
                corner => style[`border${corner}Radius`] !== '0px')) {
            throw new Error('CSS transform, shadow or rounded border on the SVG root');
        }
        let color = null;
        for (let el = root; el; el = el.parentElement) {
            const css = getComputedStyle(el);
            checkEffects(css);
            if (css.opacity !== '1') throw new Error('composite opacity on the SVG or its ancestor');
            if (color) continue;
            if (css.backgroundImage !== 'none') throw new Error('image or gradient backdrop');
            color = paint(css.backgroundColor);
        }
        rect(0, 0, box.width, box.height, color);
        for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
            const thickness = parseFloat(style[`border${side}Width`]);
            if (!thickness) continue;
            if (style[`border${side}Style`] !== 'solid') throw new Error('non-solid SVG border');
            const border = paint(style[`border${side}Color`]);
            const horizontal = side === 'Top' || side === 'Bottom';
            rect(side === 'Right' ? box.width - thickness : 0,
                 side === 'Bottom' ? box.height - thickness : 0,
                 horizontal ? box.width : thickness, horizontal ? thickness : box.height, border);
        }
    };
    try { backdrop(); } catch (err) { note(root, err.message); }
    if (paintUnits) report.backdropMarkCount = report.marks.length;

    const visit = el => {
        const kind = el.localName;
        if (skipped.has(kind)) return;
        const style = getComputedStyle(el);
        if (style.display === 'none' || style.opacity === '0') return;
        if (el.closest('[data-d3-export-ignore]') || style.visibility !== 'visible' && kind !== 'g') return;
        const firstMark = report.marks.length;
        try {
            if (el.hasAttribute('data-d3-export-raster')) {
                throw new Error('The author marked this paint unit for raster fidelity');
            }
            checkEffects(style);
            if (kind === 'g') {
                if (style.opacity !== '1') throw new Error('composite group opacity');
                for (const child of el.children) visit(child);
                return;
            }
            if (!['rect', 'circle', 'ellipse', 'line', 'text', 'path', 'polyline', 'polygon'].includes(kind)) {
                throw new Error('element is outside the editable SVG subset');
            }
            if ([...el.children].some(child => !skipped.has(child.localName))) {
                throw new Error('element has nested marks, text runs or motion');
            }
            if (style.markerMid !== 'none') throw new Error('mid-path SVG markers require snapshot capture');
            const matrix = el.getScreenCTM();
            if (!matrix || matrix.is2D === false) throw new Error('SVG transform is unavailable or not two-dimensional');
            const coefficients = [matrix.a, matrix.b, matrix.c, matrix.d, matrix.e - box.x, matrix.f - box.y];
            const determinant = matrix.a * matrix.d - matrix.b * matrix.c;
            if (coefficients.some(value => !Number.isFinite(value)) || determinant === 0) {
                throw new Error('invalid or degenerate SVG transform');
            }
            const fillGradient = allowGradients && kind !== 'line' && style.fill.startsWith('url(')
                ? linearGradient(el, style.fill, matrix) : null;
            const fillPaint = kind === 'line' ? null : fillGradient
                ? (fillGradient.stops.some(stop => stop.alpha > 0)
                    ? {color: fillGradient.stops[0].color, alpha: 1} : null)
                : paint(style.fill);
            const strokePaint = paint(style.stroke);
            const opacity = Number(style.opacity);
            const reference = Math.hypot(...svgViewport(el)) / Math.SQRT2;
            const arrows = [];
            for (const [marker, start] of [[style.markerStart, true], [style.markerEnd, false]]) {
                if (marker === 'none') continue;
                if (opacity !== 1 || style.paintOrder !== 'normal' || style.vectorEffect !== 'none') {
                    throw new Error('SVG arrows use unsupported composite opacity, paint order or stroke transform');
                }
                const record = arrowMark(el, style, kind, marker, start, coefficients, reference);
                if (record) arrows.push(record);
            }
            const addArrows = () => arrows.forEach(add);
            const localStrokeWidth = strokePaint ? svgLength(style.strokeWidth, reference) : 0;
            const fillAlpha = fillPaint ? fillPaint.alpha * Number(style.fillOpacity) * opacity : 0;
            const strokeAlpha = localStrokeWidth > 0 ? strokePaint.alpha * Number(style.strokeOpacity) * opacity : 0;
            const fill = fillAlpha ? fillPaint.color : null;
            const stroke = strokeAlpha ? strokePaint.color : null;
            if (!fill && !stroke) return addArrows();
            if (fill && stroke && opacity !== 1) {
                throw new Error('composite opacity on overlapping fill and stroke');
            }
            if (stroke && style.vectorEffect !== 'none') throw new Error('non-scaling or transformed stroke');
            if (fill && stroke && style.paintOrder !== 'normal') throw new Error('non-default paint order');
            const fillStyle = {};
            if (fill && fillGradient) {
                fillStyle.fillGradient = {...fillGradient,
                    stops: fillGradient.stops.map(stop => ({...stop, alpha: stop.alpha * fillAlpha}))};
            } else if (fill && fillAlpha !== 1) {
                fillStyle.fillAlpha = fillAlpha;
            }
            const strokeStyle = stroke && strokeAlpha !== 1 ? {strokeAlpha} : {};
            const scaleX = Math.hypot(matrix.a, matrix.b), scaleY = Math.hypot(matrix.c, matrix.d);
            const dot = matrix.a * matrix.c + matrix.b * matrix.d;
            const affine = determinant < 0 || Math.abs(dot) > 0.000001 * scaleX * scaleY;
            const nonUniform = Math.abs(scaleX - scaleY) > 0.000001;
            const project = (x, y) => ({
                x: matrix.a * x + matrix.c * y + matrix.e - box.x,
                y: matrix.b * x + matrix.d * y + matrix.f - box.y,
            });
            const strokeWidth = localStrokeWidth * scaleX;
            const dashed = stroke && style.strokeDasharray !== 'none';
            const lineCap = style.strokeLinecap;
            const endpoints = kind === 'line' ? [
                el.x1.animVal.value, el.y1.animVal.value, el.x2.animVal.value, el.y2.animVal.value,
            ] : null;
            if (endpoints && endpoints[0] === endpoints[2] && endpoints[1] === endpoints[3]) {
                if (lineCap === 'butt') return addArrows();
                if (lineCap !== 'round' || dashed || affine || nonUniform) {
                    throw new Error('unsupported visible zero-length line cap');
                }
                const center = project(endpoints[0], endpoints[1]);
                add({kind: 'ellipse', x: center.x - strokeWidth / 2, y: center.y - strokeWidth / 2,
                    width: strokeWidth, height: strokeWidth, fill: stroke, fillAlpha: strokeAlpha,
                    stroke: null, strokeWidth: 0});
                return addArrows();
            }
            const customCap = kind === 'line' && lineCap !== 'butt' && (lineCap !== 'round' || strokeAlpha !== 1);
            const customJoin = kind === 'rect' && (style.strokeLinejoin !== 'miter' ||
                Number(style.strokeMiterlimit) < Math.SQRT2);
            const forcePath = affine || Boolean(stroke && (nonUniform || dashed || customCap || customJoin));
            const d = pathData(el, style, kind, forcePath, endpoints);
            if (d !== null) {
                if (kind === 'path' && fill && !stroke && !affine && isEllipsePath(d)) {
                    const bounds = el.getBBox();
                    const angle = Math.atan2(matrix.b, matrix.a);
                    add({kind: 'ellipse', ...project(bounds.x, bounds.y),
                        width: bounds.width * scaleX, height: bounds.height * scaleY,
                        rotation: angle, fill, ...fillStyle, stroke: null, strokeWidth: 0});
                    return addArrows();
                }
                if (d) add({kind: 'path', d, matrix: coefficients, fill, ...fillStyle, stroke, ...strokeStyle,
                    strokeWidth: stroke ? localStrokeWidth : 0, fillRule: style.fillRule,
                    ...pathStroke(el, style, reference, stroke)});
                return addArrows();
            }
            if (affine) throw new Error('sheared or reflected text');
            const angle = Math.atan2(matrix.b, matrix.a);
            const rotation = Math.abs(angle) > 0.000001 ? {rotation: angle} : {};
            if (kind === 'line') {
                const {x: x1, y: y1} = project(endpoints[0], endpoints[1]);
                const {x: x2, y: y2} = project(endpoints[2], endpoints[3]);
                add({kind, x1, y1, x2, y2, stroke, strokeWidth, ...strokeStyle});
                if (lineCap === 'round') {
                    const cap = (cx, cy) => add({kind: 'ellipse', x: cx - strokeWidth / 2,
                        y: cy - strokeWidth / 2, width: strokeWidth, height: strokeWidth,
                        fill: stroke, stroke: null, strokeWidth: 0});
                    cap(x1, y1);
                    cap(x2, y2);
                }
                return addArrows();
            }
            const bounds = el.getBBox();
            const area = {
                ...project(bounds.x, bounds.y), width: bounds.width * scaleX, height: bounds.height * scaleY,
            };
            if (area.width <= 0 || area.height <= 0) return;
            if (kind === 'text') {
                if (!fill || fillGradient || fillAlpha !== 1 || stroke || nonUniform || style.writingMode !== 'horizontal-tb' ||
                    style.direction !== 'ltr' || style.letterSpacing !== 'normal' ||
                    style.wordSpacing !== '0px' && style.wordSpacing !== 'normal' ||
                    style.textDecorationLine !== 'none' || style.textTransform !== 'none' ||
                    !['normal', 'nowrap'].includes(style.whiteSpace) || el.hasAttribute('textLength') ||
                    el.x.animVal.numberOfItems > 1 ||
                    el.y.animVal.numberOfItems > 1 || el.dx.animVal.numberOfItems > 1 ||
                    el.dy.animVal.numberOfItems > 1 || el.rotate.animVal.numberOfItems > 0) {
                    throw new Error('unsupported editable text formatting or positioning');
                }
                const text = [...el.childNodes]
                    .filter(node => [Node.TEXT_NODE, Node.CDATA_SECTION_NODE].includes(node.nodeType))
                    .map(node => node.textContent).join('').replace(/[\t\n\r ]+/g, ' ').replace(/^ | $/g, '');
                if (!text) return;
                if (/[\x00-\x08\x0c-\x1f\ue000-\uf8ff]/u.test(text)) {
                    throw new Error('editable text contains characters Google Slides strips');
                }
                const family = style.fontFamily.split(',')[0].trim().replace(/^['"]|['"]$/g, '');
                const generic = {'sans-serif': 'Arial', serif: 'Georgia', monospace: 'Courier New',
                    'system-ui': 'Arial', 'ui-sans-serif': 'Arial'};
                add({kind, ...area, ...rotation, text, fill, fontSize: parseFloat(style.fontSize) * scaleX,
                    fontFamily: generic[family] || family,
                    bold: Number(style.fontWeight) >= 600, italic: style.fontStyle !== 'normal',
                    align: {start: 'left', middle: 'center', end: 'right'}[style.textAnchor] || 'left'});
                return;
            }
            add({kind: kind === 'rect' ? 'rect' : 'ellipse', ...area, ...rotation, fill, ...fillStyle,
                stroke, strokeWidth: stroke ? strokeWidth : 0, ...strokeStyle});
        } catch (err) {
            report.marks.length = firstMark;
            note(el, err.message);
        }
    };
    const svgMotion = [...root.querySelectorAll(motionNodes.join(','))];
    if (svgMotion.length) {
        if (!frozen || !root.animationsPaused()) {
            note(root, 'SVG animation requires a snapshot or a frozen frame');
        } else {
            const sampledAttributes = new Set([
                'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry',
                'width', 'height', 'd', 'points', 'transform', 'opacity', 'fill',
                'fill-opacity', 'stroke', 'stroke-opacity', 'stroke-width',
                'stroke-dasharray', 'stroke-dashoffset', 'font-size', 'color',
                'visibility', 'display'
            ]);
            const geometryNodes = new Set(['g', 'rect', 'circle', 'ellipse', 'line', 'text', 'path', 'polyline', 'polygon']);
            for (const motion of svgMotion) {
                const target = motion.targetElement;
                const name = motion.getAttribute('attributeName');
                if (!target || !root.contains(target) || !geometryNodes.has(target.localName) ||
                    (!['animateMotion', 'animateTransform'].includes(motion.localName) && !sampledAttributes.has(name))) {
                    note(motion, 'frozen SVG animation target or property is outside the editable subset');
                }
            }
        }
    }
    if (root.getAnimations({subtree: true}).some(animation => animation.playState === 'running')) {
        note(root, 'CSS animation is still running');
    }
    for (const [childIndex, child] of [...root.children].entries()) {
        if (!paintUnits) {
            visit(child);
            continue;
        }
        const markStart = report.marks.length;
        currentUnit = {childIndex, tag: child.localName, id: child.id, markStart, unsupported: []};
        visit(child);
        currentUnit.markEnd = report.marks.length;
        if (currentUnit.markEnd > markStart || currentUnit.unsupported.length) {
            report.paintUnits.push(currentUnit);
        }
        currentUnit = null;
    }
    return report;
}"""


def _launch_options(playwright, browser: str) -> dict[str, str]:
    if browser in _CHANNELS:
        return {"channel": browser}
    if browser not in {"auto", "chromium"}:
        raise ValueError(f"Unsupported browser: {browser}")
    if browser == "auto" and sys.platform == "win32" and not Path(playwright.chromium.executable_path).exists():
        for channel, executable in _CHANNELS.items():
            if executable.exists():
                return {"channel": channel}
    return {}


@dataclass
class CaptureGuard:
    """Remember blocked requests and source errors for one local page."""

    blocked_fonts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    blocked_remote: bool = False

    def check(self) -> None:
        if self.blocked_remote:
            raise ValueError("Use a self-contained source. Browser capture blocked remote requests.")
        if self.errors:
            raise ValueError(f"The source reported a browser error: {self.errors[0]}")


def _is_decorative_font(request) -> bool:
    url = urlsplit(request.url)
    if url.scheme != "https" or url.username or url.password or url.port is not None:
        return False
    return (
        request.resource_type == "stylesheet"
        and url.hostname == "fonts.googleapis.com"
        and url.path in {"/css", "/css2"}
    ) or (
        request.resource_type == "font"
        and url.hostname == "fonts.gstatic.com"
        and url.path.startswith("/s/")
    )


def load_local_page(page, source: Path, *, allow_decorative_fonts: bool = False) -> CaptureGuard:
    """Navigate a new page in a context with service workers blocked.

    Decorative fonts use browser fallbacks only when explicitly permitted.
    Call check after deferred rendering to catch requests made after load.
    Use distinct contexts for concurrent source pages.
    """
    source = source.resolve()
    if not source.is_file() or source.suffix.lower() not in {".html", ".htm", ".svg"}:
        raise ValueError("Capture requires an existing trusted local HTML or SVG file.")
    guard = CaptureGuard()

    def block_request(route):
        request = route.request
        if allow_decorative_fonts and _is_decorative_font(request):
            if request.url not in guard.blocked_fonts:
                guard.blocked_fonts.append(request.url)
        else:
            guard.blocked_remote = True
        route.abort()

    def block_socket(socket):
        guard.blocked_remote = True
        socket.close()

    # The first request of a popup is visible to context routes only.
    page.context.route(_REMOTE, block_request)
    page.context.route_web_socket(_SOCKET, block_socket)
    page.on("pageerror", lambda error: guard.errors.append(str(error)))
    try:
        page.goto(source.as_uri(), wait_until="load", timeout=30_000)
    except PlaywrightError:
        guard.check()
        raise
    guard.check()
    return guard


_WAIT_RENDER = """async () => {
    await document.fonts.ready;
    await new Promise(resolve => {
        requestAnimationFrame(() => requestAnimationFrame(resolve));
        setTimeout(resolve, 500);
    });
}"""


_FREEZE_FRAME = r"""async (root, seconds) => {
    if (!(root instanceof SVGSVGElement)) throw new Error('The selected element must be an SVG root.');
    root.pauseAnimations();
    root.setCurrentTime(seconds);
    // Finished CSS animations with fill-mode:none can disappear from getAnimations().
    // Recreate those named CSS effects before seeking so an early frame stays reachable.
    const restart = [];
    for (const element of [root, ...root.querySelectorAll('*')]) {
        const style = getComputedStyle(element);
        const names = style.animationName.split(/,\s*/).filter(name => name !== 'none');
        if (!names.length || style.display === 'none' || !element.getClientRects().length) continue;
        const active = element.getAnimations().filter(animation => animation instanceof CSSAnimation);
        if (active.length >= names.length) continue;
        restart.push([element, element.style.getPropertyValue('animation-name'),
            element.style.getPropertyPriority('animation-name')]);
        element.style.setProperty('animation-name', 'none', 'important');
    }
    for (const [element] of restart) getComputedStyle(element).animationName;
    for (const [element, value, priority] of restart) {
        if (value) element.style.setProperty('animation-name', value, priority);
        else element.style.removeProperty('animation-name');
    }
    const animations = root.getAnimations({subtree: true});
    for (const animation of animations) {
        animation.pause();
        animation.currentTime = seconds * 1000;
    }
    await Promise.all(animations.map(animation => animation.ready));
    const ignoredKeyframeKeys = new Set(['offset', 'computedOffset', 'easing', 'composite']);
    const sampledProperties = new Set([
        'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry',
        'width', 'height', 'd', 'transform', 'opacity', 'fill', 'fillOpacity',
        'stroke', 'strokeOpacity', 'strokeWidth', 'strokeDasharray',
        'strokeDashoffset', 'fontSize', 'color', 'visibility', 'display'
    ]);
    return [...new Set(animations.flatMap(animation =>
        animation.effect?.getKeyframes().flatMap(keyframe =>
            Object.keys(keyframe).filter(key => !ignoredKeyframeKeys.has(key) && !sampledProperties.has(key))
        ) ?? []
    ))].sort();
}"""


_FRAME_IS_FROZEN = """(root, seconds) =>
    root.animationsPaused() && Math.abs(root.getCurrentTime() - seconds) < 0.001 &&
    root.getAnimations({subtree: true}).every(animation =>
        animation.playState === 'paused' &&
        Math.abs(animation.currentTime - seconds * 1000) < 1
    )
"""


def freeze_svg_frame(locator, seconds: float) -> list[str]:
    """Seek SMIL and SVG-local CSS/Web Animations to a selected frame.

    JavaScript timers and force simulations are governed by the source and wait_ms.
    """
    if not math.isfinite(seconds) or not 0 <= seconds <= 60:
        raise ValueError("Frozen frame time must be between 0 and 60 seconds.")
    try:
        unsupported = locator.evaluate(_FREEZE_FRAME, seconds)
        if not locator.evaluate(_FRAME_IS_FROZEN, seconds):
            raise ValueError("The browser could not verify the selected SVG and CSS animation time.")
    except PlaywrightError as error:
        raise ValueError(f"The browser could not freeze the selected SVG frame: {error}") from error
    return unsupported


def inspect_locator(locator, *, editable: bool = True, allow_gradients: bool = False,
                    frozen: bool = False, paint_units: bool = False, mark_limit: int = 1000) -> dict:
    """Extract marks from one already-loaded SVG locator without a screenshot."""
    return locator.evaluate(
        _INSPECT,
        {"editable": editable, "allowGradients": allow_gradients, "frozen": frozen, "paintUnits": paint_units,
         "markLimit": mark_limit},
    )


@contextmanager
def hide_controls(locator, selectors=()):
    """Hide export-only exclusions without changing the authored layout."""
    nodes = locator.evaluate_handle(r"""(target, selectors) => {
        const matches = [...document.querySelectorAll(selectors.join(', '))];
        if (matches.some(node => node.contains(target))) {
            throw new Error('An export exclusion contains the selected visual.');
        }
        const nodes = [...new Set(matches.flatMap(node => [node, ...node.querySelectorAll('*')]))];
        const previous = nodes.map(node => [node, node.getAttribute('style')]);
        for (const node of nodes) node.style?.setProperty('visibility', 'hidden', 'important');
        return previous;
    }""", ["[data-d3-export-ignore]", *selectors])
    try:
        yield
    finally:
        nodes.evaluate(r"""nodes => {
            for (const [node, style] of nodes) {
                if (style === null) node.removeAttribute('style');
                else node.setAttribute('style', style);
            }
        }""")
        nodes.dispose()


def capture_locator(
    locator, *, device_scale: int = 1, editable: bool = True, allow_gradients: bool = False,
    wait_ms: int = 0, frame_seconds: float | None = None, paint_units: bool = False, mark_limit: int = 1000,
) -> tuple[bytes, dict]:
    """Capture one selected SVG in a caller-owned Playwright page."""
    if device_scale not in {1, 2, 3} or not 0 <= wait_ms <= 60_000 or not 1 <= mark_limit <= 6000:
        raise ValueError("Capture requires scale 1–3, wait 0–60000 ms, and a mark limit from 1 to 6000.")
    locator.first.wait_for(state="attached", timeout=15_000)
    if locator.count() != 1:
        raise ValueError("Select exactly one SVG with --selector.")
    locator.scroll_into_view_if_needed(timeout=15_000)
    page = locator.page
    page.evaluate(_WAIT_RENDER)
    if wait_ms:
        page.wait_for_timeout(wait_ms)
    settled = True
    if editable:
        try:
            page.wait_for_function(_D3_IDLE, arg=locator.element_handle(), timeout=2500)
        except PlaywrightTimeout:
            settled = False
    frozen = frame_seconds is not None
    css_properties = freeze_svg_frame(locator, frame_seconds) if frozen else []
    options = {
        "editable": editable, "allow_gradients": allow_gradients, "frozen": frozen, "paint_units": paint_units,
        "mark_limit": mark_limit,
    }
    report = inspect_locator(locator, **options)
    width, height = report["width"], report["height"]
    device_scale = max(device_scale, page.evaluate("window.devicePixelRatio"))
    if (min(width, height) < 1 or max(width, height) * device_scale > 16_384 or
            math.ceil(width * device_scale) * math.ceil(height * device_scale) > _MAX_PIXELS):
        raise ValueError("The selected SVG is empty or exceeds the capture size limit.")
    png = locator.screenshot(type="png", omit_background=True, timeout=15_000)
    if frozen and not locator.evaluate(_FRAME_IS_FROZEN, frame_seconds):
        raise ValueError("The selected SVG or CSS animation time changed during capture.")
    changed = (editable and (paint_units or not report["unsupported"]) and
               inspect_locator(locator, **options) != report)

    def note(message):
        report["unsupported"].append(message)
        if paint_units:
            report["globalUnsupported"].append(message)

    if editable and not settled:
        note("D3 transitions are still running. Capture a later frame.")
    if editable and css_properties:
        note("Frozen CSS properties outside the editable subset: " + ", ".join(css_properties))
    if changed:
        note("Editable SVG geometry or paint changed during capture.")
    if frozen:
        report["frameSeconds"] = frame_seconds
    return png, report


def capture(
    source: Path,
    selector: str | None,
    viewport: tuple[int, int],
    wait_ms: int,
    device_scale: int,
    editable: bool,
    browser: str,
    *,
    allow_gradients: bool = False,
    frame_seconds: float | None = None,
    allow_decorative_fonts: bool = False,
) -> tuple[bytes, dict]:
    source = source.resolve()
    if not source.is_file() or source.suffix.lower() not in {".html", ".htm", ".svg"}:
        raise ValueError("Capture requires an existing trusted local HTML or SVG file.")
    if (min(viewport) <= 0 or max(viewport) > 10_000 or device_scale not in {1, 2, 3} or
            wait_ms < 0 or wait_ms > 60_000 or math.prod(viewport) * device_scale**2 > _MAX_PIXELS):
        raise ValueError("Capture requires a positive bounded viewport, scale 1–3, and wait 0–60000 ms.")

    guard = None
    try:
        with sync_playwright() as playwright:
            chromium = playwright.chromium.launch(**_launch_options(playwright, browser))
            context = chromium.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                device_scale_factor=device_scale,
                service_workers="block",
            )
            page = context.new_page()
            page.bring_to_front()
            guard = load_local_page(page, source, allow_decorative_fonts=allow_decorative_fonts)
            locator = page.locator(selector or "svg")
            locator.first.wait_for(state="attached", timeout=15_000)
            if locator.count() != 1:
                raise ValueError("Select exactly one SVG with --selector.")
            if source.suffix.lower() == ".svg":
                ratio = locator.evaluate("""el => {
                    const box = el.viewBox?.baseVal;
                    return el === document.documentElement && box?.width > 0 && box.height > 0 &&
                        !el.hasAttribute('width') && !el.hasAttribute('height') &&
                        !el.style.width && !el.style.height ? box.width / box.height : null;
                }""")
                if ratio:
                    width = min(viewport[0], viewport[1] * ratio)
                    page.set_viewport_size({"width": max(1, round(width)), "height": max(1, round(width / ratio))})
            with hide_controls(locator):
                png, report = capture_locator(
                    locator, device_scale=device_scale, editable=editable, allow_gradients=allow_gradients,
                    wait_ms=wait_ms, frame_seconds=frame_seconds,
                )
            guard.check()
            if guard.blocked_fonts:
                report["blockedFonts"] = guard.blocked_fonts
            context.close()
            chromium.close()
    except PlaywrightError as error:
        if guard:
            guard.check()
        raise ValueError(f"Browser capture failed: {error}") from error

    return png, report
