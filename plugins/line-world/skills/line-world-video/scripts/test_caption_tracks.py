"""Verify extraction from multiple delivered subtitle streams and millisecond-accurate offline review."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from playwright.sync_api import sync_playwright
from caption_tracks import compare_speech, extract, languages, parse_srt, plain, reading_summary, webvtt
from frame_notes import build
from inspect_focus import browser_path


class Captions(unittest.TestCase):
    def test_authored_track_and_automatic_track_in_one_language(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            reviewed=root/"reviewed.srt"
            script="1\n00:00:00,123 --> 00:00:01,111\nCayó el oro.\nSubió TLT.\n"
            reviewed.write_text(script,encoding="utf-8-sig")
            automatic=root/"automatic.srt"
            automatic.write_text(script.replace("Cayó el oro.","Calló el oro."),encoding="utf-8")
            movie=root/"native.mp4"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","color=s=160x90:r=10:d=1.5",
                "-i",automatic,"-i",reviewed,"-map","0:v","-map","1:s","-map","2:s","-c:v","libx264",
                "-threads","1","-c:s","mov_text","-metadata:s:s:0","language=spa","-metadata:s:s:1","language=spa",
                "-disposition:s:0","0","-disposition:s:1","default",movie],check=True)
            cli=Path(__file__).with_name("caption_tracks.py")
            expected=root/"expected.srt"
            def compare(reference):
                expected.write_text(reference,encoding="utf-8")
                attempt=subprocess.run([sys.executable,"-B",cli,movie,root/"export.vtt","--language","spa",
                    "--require-default","--compare-srt",expected],capture_output=True)
                return attempt.returncode,json.loads(attempt.stdout)
            code,report=compare(script)
            self.assertEqual((code,report["streamIndex"],report["authoredSrt"]["ok"]),(0,2,True))
            self.assertEqual([s["default"] for s in report["candidateStreams"]],[False,True])
            for wrong in (script.replace("123","124"), script.replace("111","110"),
                          script.replace("oro.\nSubió","oro. Subió"), script.replace("TLT","oro"),
                          script+"\n2\n00:00:01,200 --> 00:00:01,450\nFalta.\n"):
                with self.subTest(reference=wrong):
                    code,report=compare(wrong)
                    self.assertEqual(code,2)
                    self.assertTrue(report["authoredSrt"]["differences"])

    def test_phrase_alignment_and_material_numeric_changes(self):
        scene={"id":"bonos","sentences":[{"text":"El tipo bajó −0,23 puntos.","absolute_start_sample":100,"absolute_end_sample":1700},
             {"text":"El precio subió.","absolute_start_sample":1900,"absolute_end_sample":2600}]}
        rows=[{"startMs":100,"endMs":750,"text":"El tipo bajó"},{"startMs":750,"endMs":1700,"text":"−0,23 puntos."},
              {"startMs":1900,"endMs":2600,"text":"El precio subió."}]
        self.assertTrue(compare_speech(rows,[scene],1000)["ok"])
        # The internal split is free to move while the spoken phrase stays covered.
        self.assertTrue(compare_speech([{**rows[0],"endMs":650},{**rows[1],"startMs":650},rows[2]],[scene],1000)["ok"])
        for wrong in ("+0,23 puntos.","−2,30 puntos.","−0,23 dólares."):
            report=compare_speech([rows[0],{**rows[1],"text":wrong},rows[2]],[scene],1000)
            self.assertFalse(report["textMatches"])
            self.assertEqual(report["issues"][0]["cue"],2)
        report=compare_speech([*rows[:2],{**rows[2],"startMs":2150}],[scene],1000)
        self.assertTrue(report["textMatches"])
        self.assertFalse(report["clockMatches"])
        self.assertEqual(report["issues"][0]["code"],"phrase-clock")
        self.assertFalse(compare_speech(rows,[{"id":"bonos","sentences":[]}],1000)["available"])

    def test_srt_preserves_breaks_unicode_and_time(self):
        text="\ufeff1\r\n00:59:59,999 --> 01:00:01,100\r\nDiez & oro\r\n<i>−23 pb</i>\r\n"
        rows=parse_srt(text)
        self.assertEqual((rows[0]["startMs"],rows[0]["endMs"]),(3599999,3601100))
        self.assertEqual(plain(rows[0]["text"]),"Diez & oro\n−23 pb")
        self.assertIn("00:59:59.999 --> 01:00:01.100",webvtt(rows))
        self.assertEqual(reading_summary(rows)["maxLines"],2)
        for malformed in (text+"\n2\nUn bloque roto",text.replace("01:00:01","00:00:01"), text.replace("59:59","60:59")):
            with self.subTest(malformed=malformed),self.assertRaises(ValueError):
                parse_srt(malformed)
        self.assertEqual(languages({"language":"fra"}),("fra","fra"))
        self.assertEqual(languages({"audioLanguage":"spa","subtitleLanguage":"eng"}),("spa","eng"))
        with self.assertRaises(ValueError):
            languages({"subtitleLanguage":"en"})

    def test_delivered_languages_forward_and_backward_cue_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def srt(name,one,two):
                path=root/(name+".srt")
                path.write_text(f"1\n00:00:00,125 --> 00:00:00,570\n{one}\n\n2\n00:00:00,750 --> 00:00:01,400\n{two}\n",encoding="utf-8")
                return str(path)
            spanish=srt("es","El tipo bajó.","Veintitrés puntos básicos.")
            english=srt("en","Yields fell.","Twenty-three basis points.")
            movie=root/"voz.mp4"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","color=s=320x180:r=10:d=1.5","-i",spanish,
                "-i",english,"-map","0:v","-map","1:s","-map","2:s","-c:v","libx264","-threads","1","-c:s","mov_text",
                "-metadata:s:s:0","language=spa","-metadata:s:s:1","language=eng",
                "-disposition:s:0","0","-disposition:s:1","default",str(movie)],check=True)
            self.assertEqual(extract(movie)["language"],"eng")
            self.assertEqual(extract(movie,"spa")["cues"][1]["startMs"],750)
            with self.assertRaises(ValueError):
                extract(movie,"fra")
            output=root/"revision.html"
            build(movie,output,None,"Revisión","spa")
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=browser_path())
                try:
                    page=browser.new_page(viewport={"width":390,"height":844},accept_downloads=True)
                    page.goto(output.as_uri())
                    page.wait_for_function("movie.readyState>=2")
                    page.get_by_text("Subtítulos del vídeo",exact=True).click()
                    later=page.get_by_role("button",name="0:00,750 · Veintitrés puntos básicos.")
                    later.click()
                    page.wait_for_function("frame===7 && pending===null && Math.abs(movie.currentTime-.750)<.001")
                    self.assertEqual(page.locator("#spoken").inner_text(),"Veintitrés puntos básicos.")
                    page.get_by_role("button",name="0:00,125 · El tipo bajó.").click()
                    page.wait_for_function("frame===1 && pending===null && Math.abs(movie.currentTime-.125)<.001")
                    self.assertEqual(page.locator("#spoken").inner_text(),"El tipo bajó.")
                    self.assertEqual(page.locator("#cueList [aria-current=true]").count(),1)
                    page.evaluate("go(6)")
                    page.wait_for_function("pending===null")
                    self.assertEqual(page.locator("#spoken").inner_text(),"")
                    with page.expect_download() as event:
                        page.get_by_role("button",name="Descargar WebVTT").click()
                    vtt=Path(event.value.path()).read_text(encoding="utf-8")
                    self.assertIn("00:00:00.125 --> 00:00:00.570\nEl tipo bajó.",vtt)
                    self.assertNotIn("Yields",vtt)
                finally:
                    browser.close()


if __name__=="__main__":
    unittest.main()
