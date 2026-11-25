#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Contract and browser regressions for the offline video-chart producer."""
import json
from pathlib import Path
import tempfile
import unittest

from playwright.sync_api import sync_playwright
import video_chart as producer


def comparison(values):
    return {"unit":"variación (%)","locale":"es-ES","signed":True,
            "records":[{"id":f"r{i}","label":f"Mercado {i}","value":v} for i,v in enumerate(values)]}


def timeline(values):
    dates = ["2024-02-01","2024-02-02","2024-02-07","2024-02-08","2024-03-01"]
    return {"kind":"time-series","unit":"grados","id":"temperatura","locale":"es-ES",
            "observations":[{"date":k,"value":v} for k,v in zip(dates,values)]}


class VideoChartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(executable_path=producer.browser_path())

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def render(self, spec, width=390, height=844):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path=Path(folder.name)
        producer.build_project(path,producer.check_data(spec))
        page=self.browser.new_page(viewport={"width":width,"height":height})
        self.addCleanup(page.close)
        page.goto((path/"scene.html").as_uri())
        page.evaluate("document.fonts.ready")
        page.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
        return page

    def audit(self,page):
        here=Path(__file__).parent
        layout=page.evaluate((here/"video_chart_audit.js").read_text(encoding="utf-8"))
        motion=page.evaluate((here/"video_chart_motion_audit.js").read_text(encoding="utf-8"),page.evaluate("VIDEO_DATA.duration"))
        self.assertFalse(layout["outside"])
        self.assertFalse(layout["overlaps"],layout["overlaps"])
        self.assertTrue(all(layout[k] for k in ("scale","validMarks","calendarSpacing","solidPaint","visibleNumbers","unitsVisible")))
        self.assertGreaterEqual(layout["minFontPx"],12)
        self.assertTrue(motion["ok"],motion["issues"])
        return layout,motion

    def test_eight_rows_mobile_mixed_missing_zero_and_focus(self):
        data=comparison([-12,-3,0,None,2.61,4,1,0.25])
        data["records"][2]["label"]="Serie de valores relativamente largos"
        page=self.render(data)
        layout,motion=self.audit(page)
        self.assertEqual(layout["values"],[-12,-3,0,None,2.61,4,1,0.25])
        self.assertEqual(motion["peak"],2)
        self.assertEqual(len(motion["perSecond"]),9)
        self.assertEqual(page.locator('[data-entity-id="r3"].record .source-value').text_content(),"Sin dato")
        self.assertEqual(page.locator('[data-entity-id="r3"].mark > *').count(),0)
        self.assertEqual(page.locator(".zero-dot").count(),1)
        color=page.locator(".record").last.locator("text").first.evaluate("e=>getComputedStyle(e).fill")
        self.assertEqual(color,"rgb(158, 27, 50)")
        self.assertEqual(page.locator(".record").last.locator(".source-value").text_content(),"+0,25")

    def test_legacy_positive_shape_and_reverse_seek(self):
        data={"unit":"units","records":[{"id":"a","label":"Alpha","value":12},{"id":"b","label":"Beta","value":24}]}
        page=self.render(data,1920,1080)
        self.audit(page)
        self.assertEqual(page.evaluate("renderAt(7).selectedId"),"b")
        original=page.locator("#stage").inner_html()
        for t in (0,5,2,7):
            page.evaluate("t=>renderAt(t)",t)
        self.assertEqual(page.locator("#stage").inner_html(),original)

    def test_all_null_and_negative_only(self):
        for values in ([None,None],[-7,-2]):
            with self.subTest(values=values):
                page=self.render(comparison(values))
                layout,_=self.audit(page)
                self.assertEqual(layout["values"],values)

    def test_irregular_utc_spacing_gaps_and_solid_holds(self):
        spec=timeline([-3,1,None,2,1])
        page=self.render(spec)
        layout,motion=self.audit(page)
        self.assertEqual(motion["peak"],3)
        self.assertEqual(motion["perSecond"][-1]["phase"],"reading")
        self.assertEqual(page.locator(".trend").get_attribute("d").count("M"),2)
        marks=page.locator(".observation").evaluate_all("nodes=>nodes.map(n=>+n.getAttribute('cx'))")
        self.assertAlmostEqual((marks[2]-marks[0])/(marks[1]-marks[0]),7,places=6)
        self.assertEqual(layout["values"],[-3,1,None,2,1])
        for t in (3,6):
            state=page.evaluate("t=>renderAt(t)",t)
            self.assertFalse(any(a["active"] for a in state["tracks"]))

    def test_single_value_and_missing_endpoints(self):
        page=self.render(timeline([None,0,None,None,None]))
        layout,motion=self.audit(page)
        self.assertEqual(motion["peak"],2)
        self.assertEqual(layout["values"],[None,0,None,None,None])
        self.assertEqual(page.evaluate("snapshot().value"),None)

    def test_progressive_dates_keep_the_peak_and_missing_mark_on_their_own_dates(self):
        data=timeline([3, None, 8, 5, 4])
        data["revealObservations"]=True
        page=self.render(data)
        first_date="2024-02-01"
        visible=lambda: page.locator("#timeline [data-date]:visible").evaluate_all(
            "nodes=>nodes.map(n=>n.dataset.date).sort()")
        self.assertEqual(page.evaluate("renderAt(0).value"),3)
        self.assertEqual(visible(),[first_date])
        self.assertEqual(page.evaluate("renderAt(1).value"),None)
        self.assertEqual(visible(),[first_date,"2024-02-02"])
        self.assertEqual(page.locator(".last-value").text_content(),"Sin dato")
        self.assertEqual(page.evaluate("renderAt(8).value"),4)
        self.assertEqual(visible(),[row["date"] for row in data["observations"]])
        self.assertEqual(page.evaluate("renderAt(0).value"),3)
        self.assertEqual(visible(),[first_date])

    def test_observed_value_and_date_keep_six_pixels_between_their_actual_boxes(self):
        for width,height in ((390,844),(1280,720)):
            page=self.render(timeline([-2.5,-1.2,None,4.8,3.4]),width,height)
            measure="""()=>document.querySelector('.last-date').getBoundingClientRect().top-
                        document.querySelector('.last-value').getBoundingClientRect().bottom"""
            if (producer.SKILL.parent/"line-world-video/assets/fonts/space-grotesk.ttf").is_file():
                self.assertTrue(page.evaluate("""()=>Array.from(document.fonts).some(f=>f.family==='ChartSpace' && f.status==='loaded')"""))
                self.assertIn("SIL OPEN FONT LICENSE",page.locator("#chart-font-license").text_content())
            self.assertGreaterEqual(page.evaluate(measure),5.95)
            page.add_style_tag(content="#stage text{font-family:monospace!important}")
            page.set_viewport_size({"width":width+1,"height":height})
            page.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            self.assertGreaterEqual(page.evaluate(measure),5.95)

    def test_does_not_coerce_bad_input(self):
        cases=[comparison([2,True]),comparison([2,float("nan")]),timeline([None]*5),
               {**timeline([1]*5),"revealObservations":"true"}]
        same=timeline([1]*5);same["observations"][1]["date"]="2024-02-01";cases.append(same)
        absent=timeline([1]*5);del absent["observations"][0]["value"];cases.append(absent)
        for spec in cases:
            with self.subTest(spec=json.dumps(spec)):
                with self.assertRaises(ValueError):
                    producer.check_data(spec)


if __name__=="__main__":
    unittest.main()
