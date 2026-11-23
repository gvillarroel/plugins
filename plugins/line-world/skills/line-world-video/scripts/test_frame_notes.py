# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Verify the offline frame-review page through its public controls and exported JSON."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from playwright.sync_api import sync_playwright
from frame_notes import build, evidence, model, validate
from inspect_focus import browser_path


class FrameReview(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.video = self.root / "prueba con espacio.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10:duration=0.9",
                        "-threads", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.video)], check=True)
        self.score = self.root/"attention.json"
        self.score.write_text(json.dumps({"fps":10, "frames":9, "tracks":{"dato":{"box":[.1,.1,.8,.8]}},
            "beats":[{"start":0,"end":9,"focus":"dato","visible":["dato"],"idea":"Observar el dato."}]}), encoding="utf-8")
        self.info = model(self.video, self.score)

    def test_wrong_film_hidden_target_and_coordinates(self):
        note = {"id":"uno","element":"dato","frame":2,"endFrame":4,"point":[.4,.5],"kind":"ajustar","text":"Prolongar la lectura."}
        doc = {"version":1,"videoSha256":self.info["videoSha256"],"attentionSha256":self.info["attentionSha256"],"notes":[note]}
        self.assertEqual(validate(doc,self.info),[note])
        for update in ({"videoSha256":"x"},{"attentionSha256":"x"},{"notes":[note,note]},
                       {"notes":[{**note,"endFrame":9}]},{"notes":[{**note,"point":[0,0]}]},
                       {"notes":[{**note,"element":"ausente"}]}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate({**doc,**update}, self.info)

    def test_plain_video_notes_and_malformed_plans(self):
        video_only = model(self.video)
        doc = {"version":1, "videoSha256":video_only["videoSha256"], "attentionSha256":None, "notes":[]}
        self.assertEqual(validate(doc, video_only), [])
        with self.assertRaises(ValueError):
            validate({**doc,"attentionSha256":self.info["attentionSha256"]},video_only)
        score = json.loads(self.score.read_text(encoding="utf-8"))
        for change in ({"tracks":{"dato":{"box":[0,0,-.1,1]}}},{"tracks":{"dato":{"box":[0,0,1.1,1]}}},
                       {"beats":[{**score["beats"][0],"visible":"dato"}]},{"beats":[{**score["beats"][0],"end":9.0}]}):
            self.score.write_text(json.dumps({**score,**change}), encoding="utf-8")
            with self.subTest(change=change), self.assertRaises(ValueError):
                model(self.video,self.score)

    def test_positive_picture_offset_uses_the_actual_presented_frame(self):
        delayed=self.root/"con-entrada-de-voz.mp4"
        pictures=b"".join(bytes([20*i])*(160*90) for i in range(10))
        subprocess.run(["ffmpeg","-v","error","-itsoffset","0.4","-f","rawvideo","-pix_fmt","gray","-s","160x90",
            "-framerate","10","-i","pipe:0","-f","lavfi","-i","anullsrc=r=48000:d=1.8","-map","0:v","-map","1:a",
            "-fps_mode","vfr","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-threads","1",str(delayed)],input=pictures,check=True)
        info=model(delayed)
        self.assertAlmostEqual(info["pts"][2],.6)
        self.assertAlmostEqual(info["pictureEnd"],1.4)
        self.assertAlmostEqual(info["duration"],1.8)
        output=self.root/"revisar-con-voz.html"
        build(delayed,output,None,"Entrada de voz")
        runtime=self.enterContext(sync_playwright())
        browser=runtime.chromium.launch(executable_path=browser_path())
        self.addCleanup(browser.close)
        page=browser.new_page()
        page.goto(output.as_uri())
        page.wait_for_function("movie.readyState>=2 && pending===null && movie.currentTime>=.4")
        page.evaluate("go(2)")
        page.wait_for_function("frame===2 && pending===null")
        png=page.locator("#movie").screenshot()
        pixel=subprocess.check_output(["ffmpeg","-v","error","-i","pipe:0","-vf","scale=1:1",
            "-pix_fmt","rgb24","-frames:v","1","-f","rawvideo","pipe:1"],input=png)
        self.assertLess(abs(pixel[0]-40),5)
        self.assertIn("0:00,600",page.locator("#time").inner_text())

    def test_cue_inside_a_held_variable_rate_frame_and_reverse_seeks(self):
        marks = self.root / "voz.srt"
        marks.write_text("1\n00:00:00,210 --> 00:00:00,410\nDurante la pausa.\n", encoding="utf-8")
        video = self.root / "variable.mp4"
        shades = [24, 58, 92, 126, 160, 194]
        commands = [
            "ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "160x90",
            "-framerate", "10", "-i", "pipe:0", "-i", str(marks), "-map", "0:v", "-map", "1:s",
            "-vf", "setpts=N+3*floor(N/2)", "-fps_mode", "vfr", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-c:s", "mov_text", "-metadata:s:s:0", "language=spa",
            "-threads", "1", str(video),
        ]
        subprocess.run(commands, input=b"".join(bytes([v])*(160*90) for v in shades), check=True)
        self.assertEqual(model(video)["pts"], [0, .1, .5, .6, 1, 1.1])
        page_file = self.root / "revision.html"
        build(video, page_file, None, "Cadencia variable", "spa")
        runtime = self.enterContext(sync_playwright())
        browser = runtime.chromium.launch(executable_path=browser_path())
        self.addCleanup(browser.close)
        page = browser.new_page()
        page.goto(page_file.as_uri())
        page.wait_for_function("movie.readyState>=2")
        page.get_by_text("Subtítulos del vídeo", exact=True).click()
        page.get_by_role("button", name="0:00,210 · Durante la pausa.").click()
        page.wait_for_function("frame===1 && pending===null && Math.abs(movie.currentTime-.21)<.001")
        subtitle=page.locator("#spoken")
        switch=page.get_by_role("button",name="Subtítulos",exact=True)
        self.assertEqual(subtitle.inner_text(), "Durante la pausa.")
        self.assertEqual(switch.get_attribute("aria-pressed"),"true")
        for viewport in ({"width":390,"height":844},{"width":1280,"height":720}):
            page.set_viewport_size(viewport)
            subtitle_box=subtitle.bounding_box()
            movie_box=page.locator("#movie").bounding_box()
            self.assertGreaterEqual(subtitle_box["y"],movie_box["y"]+movie_box["height"])
            self.assertLessEqual(subtitle_box["x"]+subtitle_box["width"],viewport["width"])
        switch.click()
        self.assertTrue(subtitle.is_hidden())
        switch.click()
        self.assertTrue(subtitle.is_visible())
        self.assertIn("0:00,210", page.locator("#time").inner_text())
        for index in (5, 0, 2, 4, 1, 3):
            page.evaluate("go", index)
            page.wait_for_function(f"frame==={index} && pending===null")
            image = page.locator("#movie").screenshot()
            center = subprocess.check_output(
                ["ffmpeg", "-v", "error", "-i", "pipe:0", "-vf", "crop=1:1:iw/2:ih/2",
                 "-pix_fmt", "rgb24", "-frames:v", "1", "-f", "rawvideo", "pipe:1"], input=image)
            self.assertLess(abs(center[0] - shades[index]), 5, f"Wrong picture for frame {index}")

    def test_mark_range_edit_reload_export_and_extract(self):
        output = self.root/"preview"/"review.html"
        build(self.video, output, self.score, "Prueba")
        runtime = self.enterContext(sync_playwright())
        launch = {"executable_path":browser_path()} if browser_path() else {}
        browser = runtime.chromium.launch(**launch)
        self.addCleanup(browser.close)
        page = browser.new_page(viewport={"width":390,"height":844}, accept_downloads=True)
        page.goto(output.as_uri())
        page.wait_for_function("movie.readyState>=2")
        self.assertTrue(page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
        page.get_by_role("button",name="Fotograma siguiente").click()
        page.wait_for_function("pending===null && frame===1")
        page.get_by_role("button",name="Marcar centro").click()
        page.get_by_label("Nota",exact=True).fill("Aumentar la cifra.")
        page.get_by_role("button",name="Fotograma siguiente").click()
        page.wait_for_function("pending===null && frame===2")
        page.get_by_role("button",name="Hasta este cuadro").click()
        page.get_by_role("button",name="Guardar nota").click()
        with page.expect_download() as event:
            page.get_by_role("button",name="Exportar notas").click()
        downloaded = json.loads(Path(event.value.path()).read_text(encoding="utf-8"))
        found = validate(downloaded, self.info)
        self.assertEqual((found[0]["frame"],found[0]["endFrame"],found[0]["element"]), (1,2,"dato"))
        evidence(self.video, self.root/"frames", found, self.info)
        self.assertEqual(found[0]["evidence"]["pixel"], [80,45])
        self.assertTrue((self.root/"frames"/found[0]["evidence"]["file"]).is_file())
        page.reload()
        page.get_by_role("button",name="0:00,100 · f1 · Ajustar").click()
        page.get_by_label("Nota",exact=True).fill("Conservar la pausa.")
        page.get_by_label("Decisión").select_option("conservar")
        page.get_by_role("button",name="Guardar nota").click()
        self.assertEqual(page.locator("li").count(), 1)
        self.assertIn("Conservar la pausa",page.locator("li").inner_text())
        incorrect=self.root/"incorrecto.json"
        incorrect.write_text(json.dumps({**downloaded,"videoSha256":"bad"}),encoding="utf-8")
        page.locator("#file").set_input_files(incorrect)
        page.wait_for_function("document.querySelector('#status').innerText.includes('otra versión')")
        self.assertEqual(page.locator("li").count(), 1)


if __name__=="__main__":
    unittest.main()
