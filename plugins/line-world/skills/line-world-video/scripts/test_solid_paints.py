#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Exercise source-paint detection in a real Chromium rendering context."""
import os
import unittest
from pathlib import Path

from playwright.sync_api import Error as BrowserError, sync_playwright


RUNTIME = Path(__file__).resolve().parents[1] / "assets/runtime/review-solid-paints.js"
MOTION = """
<script>
window.renderAt = async (t, frame) => {
  const c = document.querySelector('#export').getContext('2d');
  c.clearRect(0, 0, 240, 160);
  c.fillStyle = '#ffffff';
  c.fillRect(0, 0, 240, 160);
  if (frame) {
    const gradient = c.createLinearGradient(0, 0, 90, 60);
    gradient.addColorStop(0, 'red');
    gradient.addColorStop(1, 'white');
    c.fillStyle = gradient;
    c.fillRect(10, 10, 30, 30);
    c.strokeStyle = c.createPattern(document.querySelector('#tile'), 'repeat');
    c.strokeRect(20, 20, 40, 40);
    c.strokeStyle = 'rgba(0,0,0,.5)';
    c.strokeText('Partial stroke', 30, 60);
    c.fillStyle = '#333e48';
    c.save();
    c.globalAlpha = .8;
    c.fillText('Partial label', 30, 90);
    c.restore();
    c.shadowBlur = 4;
    c.shadowColor = '#00000088';
    c.fillRect(120, 55, 30, 25);
    c.shadowBlur = 0;
    c.filter = 'blur(2px)';
    c.fillRect(120, 90, 30, 25);
    c.filter = 'none';
  }
};
</script>
"""


class SolidPaintReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = sync_playwright().start()
        cls.addClassCleanup(cls.runtime.stop)
        try:
            cls.browser = cls.runtime.chromium.launch()
        except BrowserError as error:
            if os.name != "nt" or "Executable doesn't exist" not in str(error):
                raise
            cls.browser = cls.runtime.chromium.launch(channel="msedge")
        cls.addClassCleanup(cls.browser.close)

    def load(self, html):
        page = self.browser.new_page(viewport={"width": 240, "height": 160})
        self.addCleanup(page.close)
        page.add_init_script(path=RUNTIME)
        page.route("https://paint-test.invalid/", lambda route: route.fulfill(content_type="text/html", body=html))
        page.goto("https://paint-test.invalid/")
        return page

    def inspect(self, page, frame=7):
        return page.evaluate("""async frame => {
          lineWorldPaintReview.begin(frame);
          await window.renderAt?.(0, frame);
          return lineWorldPaintReview.inspect();
        }""", frame)

    def test_dom_gradients_patterns_opacities_and_soft_shadows(self):
        page = self.load("""
<style>
  body { margin: 0; background: linear-gradient(white, #e7e7e7); }
  #container { opacity: .6; }
  #label { color: rgba(51,62,72,.8); text-shadow: #0006 0px 0px 3px; }
  #shelf { width: 160px; height: 20px; box-shadow: 1px 1px 4px #3336; }
  #shelf::before { content: ''; display: block; width: 50px; height: 10px; background: radial-gradient(white, red); }
</style>
<div id="container"><span id="label">Partial text</span></div><div id="shelf"></div>
<svg width="200" height="75" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="wash"><stop stop-color="#000"/><stop offset="100%" stop-color="#fff"/></linearGradient>
    <pattern id="tile" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="3" height="3" fill="#696969"/></pattern>
    <filter id="soft"><feGaussianBlur stdDeviation="3"/></filter>
    <path id="fromSymbol" d="M0 0h12v8H0z" fill="url(#wash)"/>
  </defs>
  <rect id="gradient" x="5" y="5" width="25" height="25" fill="url(#wash)"/>
  <rect id="pattern" x="35" y="5" width="25" height="25" fill="url(#tile)"/>
  <path id="faded" d="M70 5h20v20H70z" fill="#9e1b32" fill-opacity=".5"/>
  <circle id="blurred" cx="110" cy="15" r="12" filter="url(#soft)"/>
  <use id="reuse" href="#fromSymbol" x="130" y="15"/>
</svg>
""")
        receipt = self.inspect(page)
        self.assertEqual((receipt["frame"], receipt["surface"]), (7, "dom"))
        self.assertEqual(receipt["covered"], ["svg-paint", "css-paint"])
        observed = {(f["target"], f["kind"]) for f in receipt["findings"]}
        self.assertEqual(observed, {
            ("body", "gradient"), ("#container", "opacity"), ("#label", "opacity"), ("#label", "shadow"),
            ("#shelf", "shadow"), ("#shelf::before", "gradient"), ("#gradient", "gradient"),
            ("#pattern", "pattern"), ("#faded", "opacity"), ("#blurred", "filter"),
            ("#reuse ↦ #fromSymbol", "gradient"),
        })

    def test_hidden_shapes_media_and_crisp_edges_do_not_fail(self):
        page = self.load("""
<style>
  body { margin: 0; }
  .grad { background: repeating-linear-gradient(90deg, #fff 0 1px, #696969 1px 2px); }
  .clip { position: relative; width: 40px; height: 15px; overflow: hidden; }
  .clip > div { position: absolute; top: 40px; width: 30px; height: 20px; }
  img, video { width: 24px; height: 24px; }
</style>
<div class="grad" hidden>Hidden gradient</div>
<div style="opacity:0"><span style="opacity:.2">Invisible label</span></div>
<div style="visibility:hidden"><span class="grad">Invisible paint</span></div>
<div class="clip"><div class="grad"></div></div>
<div class="grad" style="position:absolute;left:300px;width:30px;height:15px"></div>
<div style="color:#333e48; box-shadow:1px 1px 0 #333; text-shadow:0 0 3px transparent">Crisp label</div>
<figure style="opacity:.6"><img alt="" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24'%3E%3C/svg%3E">
<video style="filter:blur(3px)"></video></figure>
<svg width="150" height="25">
  <defs><linearGradient id="unused"><stop stop-color="red"/></linearGradient>
    <circle id="notUsed" r="8" fill="url(#unused)"/></defs>
  <circle cx="25" cy="10" r="8" fill="#9e1b32"/>
  <circle cx="50" cy="10" r="8" fill-opacity="0" fill="rgba(51,62,72,.5)"/>
  <path opacity=".4" stroke-width="0" fill="none" stroke="none" d="M60 0h15v15H60z"/>
  <image x="85" width="15" height="15" opacity=".6" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"/>
</svg>
""")
        self.assertEqual(self.inspect(page)["findings"], [])

    def test_direct_export_canvas_uses_its_own_drawing_history(self):
        page = self.load("""
<style>body { background: linear-gradient(white, red); }</style>
<canvas id="export" data-export-surface width="240" height="160"></canvas>
<canvas hidden id="tile" width="5" height="5"></canvas>
<script>
  const tile = document.querySelector('#tile').getContext('2d');
  tile.fillStyle = 'rgba(0,0,0,.5)';
  tile.fillRect(0,0,5,5);
</script>
""" + MOTION)
        receipt = self.inspect(page)
        self.assertEqual(receipt["surface"], "canvas-2d")
        self.assertEqual(receipt["covered"], ["canvas-2d"])
        self.assertEqual({f["target"] for f in receipt["findings"]}, {"#export"})
        self.assertEqual({f["kind"] for f in receipt["findings"]}, {"gradient", "pattern", "opacity", "shadow", "filter"})
        self.assertEqual(self.inspect(page, frame=0)["findings"], [])

    def test_canvas_boot_paint_and_offscreen_blit_but_not_media_pixels(self):
        page = self.load("""
<canvas id="export" data-export-surface width="240" height="160"></canvas>
<img id="original" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24'%3E%3Crect width='24' height='24' fill-opacity='.5'/%3E%3C/svg%3E">
<script>
const ctx = document.querySelector('canvas').getContext('2d');
ctx.fillStyle = '#9e1b3240';
ctx.fillRect(4, 4, 50, 50);
const source = new OffscreenCanvas(24, 24);
const drawing = source.getContext('2d');
drawing.fillStyle = drawing.createLinearGradient(0, 0, 24, 24);
drawing.fillStyle.addColorStop(0, 'red');
drawing.fillStyle.addColorStop(1, 'white');
drawing.fillRect(0, 0, 24, 24);
window.renderAt = async (t, number) => {
  if (number === 1) {
    ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);
    const sourceImage = document.querySelector('img');
    await sourceImage.decode();
    ctx.globalAlpha = .5;
    ctx.shadowColor = 'black';
    ctx.shadowBlur = 4;
    ctx.drawImage(sourceImage, 20, 20);
  }
  if (number === 2) ctx.drawImage(source, 20, 20);
};
</script>
""")
        self.assertEqual({f["kind"] for f in self.inspect(page, 0)["findings"]}, {"opacity"})
        self.assertEqual(self.inspect(page, 1)["findings"], [])
        self.assertEqual({f["kind"] for f in self.inspect(page, 2)["findings"]}, {"gradient"})

    def test_canvas_without_a_2d_context_indicates_missing_coverage(self):
        page = self.load('<canvas data-export-surface width="240" height="160"></canvas>')
        self.assertEqual(self.inspect(page), {"frame": 7, "surface": "canvas-unsupported", "covered": [], "findings": []})

    def test_mismatched_canvas_uses_viewport_inspection(self):
        page = self.load("""
<div id="label" style="filter:drop-shadow(0 0 4px #3339)">Text</div>
<canvas id="small" data-export-surface width="100" height="80"></canvas>
<script>
const ctx = document.querySelector('canvas').getContext('2d');
ctx.fillStyle = '#0033aacc';
ctx.fillText('partial paint', 4, 18);
</script>
""")
        receipt = self.inspect(page)
        self.assertEqual(receipt["surface"], "dom")
        self.assertIn("canvas-2d",receipt["covered"])
        self.assertEqual({(f["target"], f["kind"]) for f in receipt["findings"]}, {
            ("#label", "shadow"), ("#small", "opacity"),
        })


if __name__ == "__main__":
    unittest.main()
