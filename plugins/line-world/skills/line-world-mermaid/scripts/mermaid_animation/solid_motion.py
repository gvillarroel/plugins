"""Opaque entrance treatments and simultaneous-motion scheduling for Line World."""

from heapq import heappop, heappush
import re


OPACITY_KEYS = {
    "opacity",
    "fill-opacity",
    "stroke-opacity",
    "stop-opacity",
    "flood-opacity",
}
PAINT_KEYS = {
    "fill",
    "stroke",
    "stop-color",
    "flood-color",
    "color",
    "background-color",
}
DECLARATION = re.compile(r"(?P<key>[-\w]+)\s*:\s*(?P<value>[^;}]+)")


def opaque_paint(value):
    """Remove fractional alpha from SVG paint while leaving a fully clear paint clear."""
    if re.fullmatch(r"#[\da-fA-F]{4}|#[\da-fA-F]{8}", value):
        n = 1 if len(value) == 5 else 2
        return value[:-n] if int(value[-n:], 16) else "transparent"
    match = re.fullmatch(r"(rgba?|hsla?)\(([^)]+)\)", value, re.I)
    if match:
        body = match[2].strip()
        if "/" in body:
            components, alpha = body.split("/", 1)
        elif body.count(",") == 3:
            components, alpha = body.rsplit(",", 1)
        else:
            return value
        if float(alpha.strip().rstrip("%")) == 0:
            return "transparent"
        return match[1][:3] + "(" + components.strip() + ")"
    return value


def solid_declaration(key, value):
    bare, priority = re.fullmatch(
        r"(.*?)(\s*!important\s*)?", value.strip(), re.I
    ).groups()
    if key in OPACITY_KEYS and re.fullmatch(r"[+-]?(?:\d*\.)?\d+%?", bare):
        bare = "1" if float(bare.rstrip("%")) > 0 else "0"
    elif key in PAINT_KEYS:
        bare = opaque_paint(bare)
    return bare + (priority or "")


def solid_source_paints(root):
    def rewrite(match):
        key, value = match["key"], match["value"]
        if key not in OPACITY_KEYS | PAINT_KEYS:
            return match[0]
        return key + ":" + solid_declaration(key, value)

    for element in root.iter():
        for key in (OPACITY_KEYS | PAINT_KEYS) & element.attrib.keys():
            element.set(key, solid_declaration(key, element.get(key)))
        if "style" in element.attrib:
            element.set("style", DECLARATION.sub(rewrite, element.get("style")))
        if element.tag.rsplit("}", 1)[-1] == "style" and element.text:
            element.text = DECLARATION.sub(rewrite, element.text)


def active_candidates(candidates):
    return sorted(
        (c for c in candidates if c.effect != "none" and c.duration_ms > 0),
        key=lambda c: c.delay_ms,
    )


def arrange(candidates, limit=None):
    """Delay a candidate only when its starting time would exceed the limit."""
    endings = []
    peak = 0
    last_start = 0
    for candidate in active_candidates(candidates):
        start = max(last_start, candidate.delay_ms)
        while endings and endings[0] <= start:
            heappop(endings)
        if limit and len(endings) >= limit:
            start = heappop(endings)
            while endings and endings[0] <= start:
                heappop(endings)
        if limit:
            candidate.delay_ms = start
        last_start = start
        heappush(endings, start + candidate.duration_ms)
        peak = max(peak, len(endings))
    return peak


def solid_css():
    # 'backwards' hides the mark before its cue and restores original SVG geometry
    # afterwards. visibility is discrete, and both visible paint endpoints are opaque.
    return """
.am-step {
  animation-delay: var(--am-delay, 0ms);
  animation-duration: var(--am-duration, 650ms);
  animation-fill-mode: backwards;
  animation-timing-function: var(--am-easing, ease-out);
  transform-box: fill-box;
  transform-origin: center;
}
.am-effect-fade { animation-name: am-solid-wipe; }
.am-effect-pop { animation-name: am-solid-pop; }
.am-effect-slide-up { animation-name: am-solid-up; }
.am-effect-slide-left { animation-name: am-solid-left; }
.am-effect-zoom { animation-name: am-solid-zoom; }
.am-effect-draw, .am-effect-grow-arrow, .am-effect-radial-arrow {
  animation-name: am-solid-draw;
}
@keyframes am-solid-wipe {
  from { visibility: hidden; clip-path: inset(-5% 100% -5% -5%); }
  to { visibility: visible; clip-path: inset(-5% -5% -5% -5%); }
}
@keyframes am-solid-pop {
  0% { visibility: hidden; transform: scale(.90); }
  70% { visibility: visible; transform: scale(1.02); }
  100% { visibility: visible; transform: none; }
}
@keyframes am-solid-up {
  from { visibility: hidden; transform: translateY(14px); }
  to { visibility: visible; transform: none; }
}
@keyframes am-solid-left {
  from { visibility: hidden; transform: translateX(18px); }
  to { visibility: visible; transform: none; }
}
@keyframes am-solid-zoom {
  from { visibility: hidden; transform: scale(.86); }
  to { visibility: visible; transform: none; }
}
@keyframes am-solid-draw {
  from { visibility: hidden; stroke-dasharray: var(--am-length); stroke-dashoffset: var(--am-length); marker-end: none; }
  95% { visibility: visible; stroke-dasharray: var(--am-length); stroke-dashoffset: var(--am-tip); marker-end: none; }
  to { visibility: visible; stroke-dasharray: var(--am-length); stroke-dashoffset: 0; marker-end: var(--am-marker-end,none); }
}
@media (prefers-reduced-motion: reduce) {
  .am-step { animation: none !important; }
}
""".strip()
