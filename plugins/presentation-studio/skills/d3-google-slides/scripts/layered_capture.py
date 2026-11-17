#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=10,<13", "playwright>=1.52,<2"]
# ///
"""Isolate unsupported SVG paint units and prove browser compositing fidelity."""

from __future__ import annotations

import io
from itertools import groupby

from PIL import Image, ImageChops, ImageFilter


_ISOLATE = r"""(root, {visible, transparent}) => {
    const keep = new Set(visible);
    const definitions = new Set(['title','desc','defs','style','script','metadata',
        'clipPath','mask','filter','linearGradient','radialGradient','pattern','marker','symbol',
        'animate','animateMotion','animateTransform','set']);
    const children = [...root.children];
    const original = {children: [], backdrop: []};
    for (const [index, child] of children.entries()) {
        if (keep.has(index) || definitions.has(child.localName)) continue;
        original.children.push([index, child.getAttribute('style')]);
        child.style.setProperty('display', 'none', 'important');
    }
    if (transparent) {
        for (let el = root; el; el = el.parentElement) {
            original.backdrop.push(el.getAttribute('style'));
            el.style.setProperty('background', 'transparent', 'important');
            el.style.setProperty('box-shadow', 'none', 'important');
            if (el === root) el.style.setProperty('border-color', 'transparent', 'important');
        }
    }
    return original;
}"""


_RESTORE = r"""(root, original) => {
    const reset = (el, style) => style === null ? el.removeAttribute('style') : el.setAttribute('style', style);
    for (const [index, style] of original.children) reset(root.children[index], style);
    let node = root;
    for (const style of original.backdrop) {
        reset(node, style);
        node = node.parentElement;
    }
}"""


_INDEPENDENT = r"""root => {
    const supported = node => {
        const css = getComputedStyle(node);
        return css.mixBlendMode === 'normal' &&
            (!css.backdropFilter || css.backdropFilter === 'none');
    };
    for (let node = root; node; node = node.parentElement) {
        if (!supported(node)) return false;
    }
    return [...root.querySelectorAll('*')].every(supported);
}"""


def image_from(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("RGBA")


def snapshot(locator, indices: list[int], transparent: bool) -> Image.Image:
    original = locator.evaluate(_ISOLATE, {"visible": indices, "transparent": transparent})
    try:
        return image_from(locator.screenshot(omit_background=True, timeout=20_000))
    finally:
        locator.evaluate(_RESTORE, original)


def over_white(image: Image.Image) -> Image.Image:
    background = Image.new("RGBA", image.size, "white")
    background.alpha_composite(image)
    return background.convert("RGB")


def composition_error(original: Image.Image, reconstructed: Image.Image) -> tuple[float, int]:
    original_rgb, reconstructed_rgb = over_white(original), over_white(reconstructed)
    difference = ImageChops.difference(original_rgb, reconstructed_rgb)
    channels = difference.split()
    # Isolated transparent text can use different browser subpixel antialiasing.
    # Measure strong remaining deviations after normalizing one pixel of edge paint.
    edge = ImageFilter.BoxBlur(1)
    stable = ImageChops.difference(original_rgb.filter(edge), reconstructed_rgb.filter(edge)).split()
    peak = ImageChops.lighter(ImageChops.lighter(stable[0], stable[1]), stable[2])
    bad = sum(peak.histogram()[41:])
    error = sum(value * count for channel in channels
                for value, count in enumerate(channel.histogram())) / (3 * original.width * original.height)
    return error, bad


def isolate_layers(locator, scene: dict, source_png: bytes) -> tuple[list[dict] | None, str | None]:
    units = scene.get("paintUnits", [])
    if (scene.get("globalUnsupported") or not any(unit["unsupported"] for unit in units) or
            not any(not unit["unsupported"] and unit["markEnd"] > unit["markStart"] for unit in units)):
        return None, "No independently editable paint units could be isolated."
    if not locator.evaluate(_INDEPENDENT):
        return None, "Layer paint depends on the backdrop or another layer."
    spans = [(unsupported, list(group)) for unsupported, group in
             groupby(units, key=lambda unit: bool(unit["unsupported"]))]
    if len(spans) > 24:
        return None, "The SVG exceeds the isolated layer limit."

    reference = image_from(source_png)
    canvas = snapshot(locator, [], transparent=False)
    if canvas.size != reference.size:
        return None, "The SVG changed size during layer isolation."
    backdrop = scene["marks"][:scene.get("backdropMarkCount", 0)]
    layers = [{"marks": backdrop}] if backdrop else []
    for unsupported, span in spans:
        image = snapshot(locator, [unit["childIndex"] for unit in span], transparent=True)
        if image.size != reference.size:
            return None, "An isolated layer changed the SVG dimensions."
        canvas.alpha_composite(image)
        if not unsupported:
            marks = [mark for unit in span
                     for mark in scene["marks"][unit["markStart"]:unit["markEnd"]]]
            layers.append({"marks": marks})
            continue
        bounds = image.getchannel("A").getbbox()
        if bounds is None:
            continue
        cropped = io.BytesIO()
        image.crop(bounds).save(cropped, format="PNG")
        sx, sy = scene["width"] / image.width, scene["height"] / image.height
        left, top, right, bottom = bounds
        layers.append({
            "png": cropped.getvalue(),
            "frame": (left * sx, top * sy, (right - left) * sx, (bottom - top) * sy),
        })
    mean, bad = composition_error(reference, canvas)
    if mean > 0.2 or bad > max(8, reference.width * reference.height * 0.0005):
        return None, f"Layer compositing differs from the source ({mean:.3f} RGB MAE, {bad} affected pixels)."
    if not any("png" in layer for layer in layers):
        return None, "The unsupported unit had no visible isolated paint."
    scene["hybridCheck"] = {"rgbMeanError": mean, "strongDifferencePixels": bad,
                            "pixels": reference.width * reference.height}
    return layers, None
