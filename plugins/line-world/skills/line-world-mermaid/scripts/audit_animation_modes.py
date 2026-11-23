# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=10,<13","playwright==1.61.0"]
# ///
"""Render all public Mermaid animation choices and audit deterministic SVG and decoded MP4 states."""

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zlib

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat
from playwright.sync_api import Error as BrowserError, sync_playwright

from animate_mermaid_svg import ANIMATION_CHOICES

HERE = Path(__file__).resolve().parent
SOURCES = HERE.parent / "assets/examples/animation-coverage"
MATRIX = {
    "flow": (
        "auto",
        "sequence",
        "organic",
        "fade",
        "draw",
        "pop",
        "slide-up",
        "slide-left",
        "zoom",
        "none",
    ),
    "map": ("auto", "mindmap-level", "mindmap-branch", "none"),
    "cause": ("auto", "ishikawa", "none"),
    "sequence": ("auto", "sequence", "none"),
}
W, H, FPS = 512, 288, 12


def run(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace")[-2000:])
    return result.stdout


def save(path, obj):
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_svg(page, path):
    svg = path.read_text(encoding="utf-8")
    svg = svg[svg.index("<svg") :]
    page.set_content(
        "<html><head><style>*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:white}"
        "main{position:absolute;inset:10px}main>svg{width:100%!important;height:100%!important;"
        "max-width:none!important;max-height:none!important;display:block}"
        "svg *{animation-play-state:paused!important}</style></head><body><main>"
        + svg
        + "</main></body></html>"
    )
    return page.evaluate("""async()=>{
      await document.fonts.ready;
      const a=document.getAnimations();window.clips=a;
      for(const clip of a){clip.pause();clip.currentTime=0;}
      return a.map(clip=>({name:clip.animationName||"",duration:clip.effect.getComputedTiming().endTime}));
    }""")


def capture(page, time):
    partial = page.evaluate(
        """async time=>{
      for(const a of window.clips)a.currentTime=time;
      await new Promise(requestAnimationFrame);
      // Reading layout applies the requested timeline in this same task.
      document.querySelector('svg').getBoundingClientRect();
      const hidden = new WeakSet();
      let partial=0;
      const between = v => v>0.00001 && v<0.99999;
      const rgba = v => v.startsWith('rgba(') && between(+v.slice(5,-1).split(',').at(-1));
      for (const el of document.querySelectorAll('svg, svg *')) {
        if (hidden.has(el.parentElement) || el.closest('defs,style,marker,clipPath,mask,metadata,title,desc')) {
          hidden.add(el); continue;
        }
        const css=getComputedStyle(el);
        if (css.display==='none' || css.visibility==='hidden' || +css.opacity===0) {
          hidden.add(el); continue;
        }
        if (between(+css.opacity) || (css.fill!=='none' && (between(+css.fillOpacity)||rgba(css.fill))) ||
            (css.stroke!=='none' && (between(+css.strokeOpacity)||rgba(css.stroke)))) partial++;
      }
      const active=new Set(window.clips.filter(a=>{
        const {delay,duration,iterations}=a.effect.getTiming();
        return time>=delay && time<delay+duration*iterations;
      }).map(a=>a.effect.target));
      return {partial,active:active.size};
    }""",
        time,
    )
    data = page.screenshot(type="png", animations="allow")
    return Image.open(io.BytesIO(data)).convert("RGB"), partial


def delta(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3


def flat_interiors(im):
    """Count flat RGB areas only, excluding the two-pixel neighborhood of painted edges."""
    boundary = Image.new("L", im.size, 0)
    for x, y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        r, g, b = ImageChops.difference(im, ImageChops.offset(im, x, y)).split()
        boundary = ImageChops.lighter(
            boundary, ImageChops.lighter(r, ImageChops.lighter(g, b))
        )
    flat = boundary.point(lambda n: 255 if n == 0 else 0).filter(
        ImageFilter.MinFilter(3)
    )
    masked = Image.new("RGB", im.size, "white")
    masked.paste(im, mask=flat)
    colors = masked.getcolors(4096)
    if colors is None:
        from collections import Counter
        return Counter(masked.getdata())
    return {color: count for count, color in colors}


def decoded(path, frames):
    with subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-fps_mode",
            "passthrough",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-threads",
            "1",
            "-",
        ], stdout=subprocess.PIPE
    ) as decoder:
        stride = W * H * 3
        for index in range(frames):
            frame = decoder.stdout.read(stride)
            if len(frame) != stride:
                raise ValueError(f"{path}: incomplete frame {index}")
            yield Image.frombytes("RGB", (W,H), frame)
        if decoder.stdout.read(1) or decoder.wait():
            raise ValueError(f"{path}: unexpected stream length or decode failure")


def render_case(page, native, kind, mode, folder, appearance):
    folder.mkdir(parents=True, exist_ok=True)
    svg = folder / "animation.svg"
    meta = folder / "plan.json"
    run(
        [
            sys.executable,
            str(HERE / "animate_mermaid_svg.py"),
            "--svg-input",
            str(native),
            "-o",
            str(svg),
            "--animation",
            mode,
            "--appearance",
            appearance,
            "--duration-ms",
            "600",
            "--stagger-ms",
            "160",
            "--total-ms",
            "2000",
            "--animation-report",
            str(meta),
        ]
    )
    plan = json.loads(meta.read_text(encoding="utf-8"))
    load_svg(page, native)
    static, _ = capture(page, 0)
    visible_branches = 0
    if kind in {"map", "dense"}:
        branches = page.evaluate("""()=>Array.from(document.querySelectorAll('path[class*="section-edge-"]'),edge=>{
          const matrix=edge.getScreenCTM();
          return [.25,.5,.75].map(f=>{
            const p=edge.getPointAtLength(f*edge.getTotalLength()).matrixTransform(matrix);
            return [p.x,p.y];
          });
        })""")
        page.add_style_tag(
            content='path[class*="section-edge-"]{visibility:hidden!important}'
        )
        without, _ = capture(page, 0)
        difference = ImageChops.difference(static, without)
        for points in branches:
            if any(
                difference.crop(
                    (int(x) - 2, int(y) - 2, int(x) + 3, int(y) + 3)
                ).getbbox()
                for x, y in points
            ):
                visible_branches += 1
        if visible_branches != len(branches) or not branches:
            raise ValueError(
                f"{kind}: only {visible_branches}/{len(branches)} native connectors paint pixels"
            )
    native_colors = set(flat_interiors(static))
    animations = load_svg(page, svg)
    finish = max([a["duration"] for a in animations] + [plan["duration_ms"], 0])
    # Keep the static control on screen long enough for a real repeated-frame comparison.
    n = max(12, math.ceil((finish + 550) / 1000 * FPS) + 1)
    expected = []
    fingerprints = hashlib.sha256()
    select = [0, round((n - 1) * .26), round((n - 1) * .53), n - 1]
    sampled = {}
    def original(index):
        return Image.frombytes("RGB", (W,H),zlib.decompress(expected[index]))
    states = []
    unexpected = []
    path = folder / "example.mp4"
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        candidate = Path(tmp) / "movie.mp4"
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgb24",
            "-video_size",
            f"{W}x{H}",
            "-framerate",
            str(FPS),
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(candidate),
        ]
        with subprocess.Popen(cmd, stdin=subprocess.PIPE) as encoder:
            try:
                for i in range(n):
                    im, state = capture(page, i / FPS * 1000)
                    expected.append(zlib.compress(im.tobytes(),level=1))
                    fingerprints.update(im.resize((96,54)).tobytes())
                    states.append(state)
                    unexpected.append(
                        sum(
                            n
                            for color, n in flat_interiors(im).items()
                            if color not in native_colors
                        )
                    )
                    encoder.stdin.write(im.tobytes())
                encoder.stdin.close()
                if encoder.wait():
                    raise ValueError("FFmpeg encoder failed")
            finally:
                if encoder.poll() is None:
                    encoder.kill()
        errors = []
        for index, im in enumerate(decoded(candidate,n)):
            errors.append(delta(original(index),im))
            if index in {*select,n-3}:
                sampled[index]=im
        if max(errors) > 3:
            raise ValueError(f"{kind}/{mode}: MP4 differs from browser state")
        mid = n // 3
        seek, _ = capture(page, mid / FPS * 1000)
        seek_difference = ImageChops.difference(seek, original(mid))
        seek_peak = max(high for low, high in seek_difference.getextrema())
        r,g,b=seek_difference.split()
        seek_changed=W*H-ImageChops.lighter(r,ImageChops.lighter(g,b)).histogram()[0]
        if seek_changed:
            original(mid).save(folder / "seek-forward.png")
            seek.save(folder / "seek-backward.png")
            if appearance == "solid" or seek_peak > 1 or seek_changed > 16:
                raise ValueError(
                    f"{kind}/{mode}: seek changed {seek_changed} pixels, largest channel difference {seek_peak}"
                )
        final_delta = delta(sampled[n-1],sampled[n-3])
        beginning_delta = delta(original(0),original(-1))
        tail_error = delta(original(-1), original(-3))
        if tail_error > 0.005 or final_delta > 0.35:
            raise ValueError(f"{kind}/{mode}: reading hold moved")
        content = ImageStat.Stat(original(-1)).stddev
        if max(content) < 3:
            raise ValueError(f"{kind}/{mode}: final diagram is empty")
        if mode == "none" and (
            animations or plan["animated"] or beginning_delta > 0.005
        ):
            raise ValueError(f"{kind}/none: supposed static control moved")
        if mode != "none" and (not animations or beginning_delta < 0.12):
            raise ValueError(
                f"{kind}/{mode}: supposed animation has no visible change ({beginning_delta:.3f})"
            )
        if appearance == "solid":
            if max(s["partial"] for s in states) or max(unexpected) > 4:
                raise ValueError(
                    f"{kind}/{mode}: partial elements {max(s['partial'] for s in states)}, "
                    f"unexpected flat interior pixels {max(unexpected)}"
                )
            if max(s["active"] for s in states) > plan["entrance_limit"]:
                raise ValueError(
                    f"{kind}/{mode}: measured motion exceeded the entrance limit"
                )
        candidate.replace(path)
    # The final image should restore the exact native diagram, including arrowheads.
    original_delta = delta(static,original(-1))
    if original_delta > 0.35:
        raise ValueError(
            f"{kind}/{mode}: final native geometry/paint differs ({original_delta:.3f})"
        )
    cells = [sampled[i].resize((256, 144), Image.Resampling.LANCZOS) for i in select]
    return {
        "diagram": kind,
        "mode": mode,
        "requested": plan["requested"],
        "effective": plan["effective"],
        "elements": plan["animated"],
        "visible_mindmap_branches": visible_branches,
        "effects": plan["effects"],
        "css_animations": len(animations),
        "frames": n,
        "fps": FPS,
        "duration_s": n / FPS,
        "active_ms": finish,
        "start_to_end_rgb": round(beginning_delta, 3),
        "max_codec_rgb_error": round(max(errors), 3),
        "tail_change_rgb": round(final_delta, 3),
        "end_vs_native_rgb_error": round(original_delta, 3),
        "seek_pixel_exact": seek_changed == 0,
        "seek_changed_pixels": seek_changed,
        "seek_max_channel_error": seek_peak,
        "partial_opacity_frames": sum(state["partial"] > 0 for state in states),
        "max_partial_elements": max(state["partial"] for state in states),
        "max_active_elements": max(state["active"] for state in states),
        "max_off_palette_interior_pixels": max(unexpected),
        "sampled_frames": select,
        "sequence_sha256": fingerprints.hexdigest(),
        "svg_sha256": sha(svg),
        "mp4_sha256": sha(path),
    }, cells


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", type=Path, required=True)
    cli.add_argument("--browser", choices=("chrome", "msedge", "chromium"))
    cli.add_argument("--appearance", choices=("solid", "native"), default="solid")
    cli.add_argument(
        "--dense",
        action="store_true",
        help="Only run a 21-node mind-map level stress case",
    )
    cli.add_argument(
        "--native-sources",
        type=Path,
        help="Reuse a previous exact same set of four native SVGs",
    )
    cli.add_argument(
        "--mmdc-browser",
        type=Path,
        help="optional Chromium executable used by Mermaid CLI",
    )
    args = cli.parse_args()
    requested = {m for modes in MATRIX.values() for m in modes}
    if requested != set(ANIMATION_CHOICES):
        raise ValueError("Coverage choices drifted from the public CLI")
    matrix = {"dense": ("mindmap-level",)} if args.dense else MATRIX
    out = args.out.resolve()
    sources = out / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    config = sources / "config.json"
    save(
        config,
        {
            "theme": "neutral",
            "htmlLabels": False,
            "deterministicIds": True,
            "deterministicIDSeed": "lineworld-coverage",
            "flowchart": {"htmlLabels": False},
        },
    )
    results = []
    source_receipts = {}
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(
                **({"channel": args.browser} if args.browser else {})
            )
        except BrowserError:
            if args.browser or sys.platform != "win32":
                raise
            browser = pw.chromium.launch(channel="msedge")
        try:
            page = browser.new_page(
                viewport={"width": W, "height": H},
                device_scale_factor=1,
                reduced_motion="no-preference",
            )
            mmdc = []
            if args.mmdc_browser:
                config2 = Path(tmp) / "puppeteer.json"
                save(config2, {"executablePath": str(args.mmdc_browser.resolve())})
                mmdc = ["--mmdc-arg=-p", f"--mmdc-arg={config2}"]
            for kind, modes in matrix.items():
                src = sources / (kind + ".mmd")
                native = sources / (kind + ".svg")
                shutil.copyfile(SOURCES / src.name, src)
                if args.native_sources:
                    supplied = args.native_sources / native.name
                    if supplied.resolve() != native.resolve():
                        shutil.copyfile(supplied, native)
                else:
                    run(
                        [
                            sys.executable,
                            str(HERE / "animate_mermaid_svg.py"),
                            str(src),
                            "-o",
                            str(native),
                            "--animation",
                            "none",
                            "--config-file",
                            str(config),
                            *mmdc,
                        ]
                    )
                source_receipts[kind] = {
                    "source_sha256": sha(src),
                    "native_svg_sha256": sha(native),
                }
                sheet = Image.new("RGB", (1024, 177 * len(modes)), "white")
                draw = ImageDraw.Draw(sheet)
                for row, mode in enumerate(modes):
                    result, images = render_case(
                        page,
                        native,
                        kind,
                        mode,
                        out / "cases" / (kind + "--" + mode),
                        args.appearance,
                    )
                    results.append(result)
                    y = 177 * row
                    draw.text(
                        (5, y + 1),
                        f"{kind} / {mode} -> {result['effective']}",
                        fill="#333e48",
                    )
                    for i, im in enumerate(images):
                        sheet.paste(im, (256 * i, y + 15))
                        draw.text(
                            (256 * i + 5, y + 159),
                            f"{result['sampled_frames'][i] / FPS:.2f} s",
                            fill="#333e48",
                        )
                    print(kind, mode, result["frames"], flush=True)
                sheet.save(out / (kind + ".jpg"), quality=90)
        finally:
            browser.close()
    save(
        out / "coverage.json",
        {
            "version": 2,
            "appearance": args.appearance,
            "choices": sorted({m for modes in matrix.values() for m in modes}),
            "sources": source_receipts,
            "case_count": len(results),
            "checked_mp4_frames": sum(v["frames"] for v in results),
            "cases": results,
        },
    )


if __name__ == "__main__":
    main()
