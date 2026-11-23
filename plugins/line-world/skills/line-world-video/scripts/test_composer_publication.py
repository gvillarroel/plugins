# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2", "numpy>=2,<3", "av>=18,<20"]
# ///
"""Exercise the public CLI's failure report and source/output protection."""
import json
from pathlib import Path
import hashlib
import subprocess
import sys
import tempfile
import unittest

from compose_narrated import prepare_caption_track


COMPOSER = Path(__file__).with_name("compose_narrated.py")


class ComposerPublication(unittest.TestCase):
    def test_caption_preparation_preserves_implicit_and_explicit_styles_and_times(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "captions.srt"
            source.write_text("1\n00:00:02,117 --> 00:00:02,319\nDos marcas.\n\n"
                              "2\n00:00:03,471 --> 00:00:03,920\n<i>¡Una!</i>\n<b>Deux — 東京.</b>\n\n"
                              "3\n00:00:04,110 --> 00:00:04,940\n<u>¿Oro?</u> Sí.\n",
                              encoding="utf-8")
            hashes = set()
            for index in range(3):
                delivery = root / f"track-{index}.mp4"
                prepare_caption_track(source, delivery)
                exported = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(delivery),
                                                    "-map", "0:s:0", "-f", "srt", "-"], encoding="utf-8")
                self.assertEqual(exported.strip(), source.read_text(encoding="utf-8").strip())
                hashes.add(hashlib.sha256(delivery.read_bytes()).hexdigest())
            self.assertEqual(len(hashes), 1)
            probe = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "s:0",
                                             "-show_entries", "packet=pts_time,duration_time,size",
                                             "-of", "json", str(delivery)])
            packets = json.loads(probe)["packets"]
            self.assertEqual([(p["pts_time"], p["duration_time"]) for p in packets
                              if p["size"] == "2" and float(p.get("duration_time", 0)) > 0],
                             [("0.000000", "2.117000"), ("2.319000", "1.152000"), ("3.920000", "0.190000")])

    def call(self, project, report, output=None, *options):
        args = ["--output", str(output)] if output else ["--preflight"]
        return subprocess.run([sys.executable, str(COMPOSER), str(project), "--report", str(report), *args, *options],
                              capture_output=True, text=True, timeout=60)

    def test_invalid_project_preserves_existing_movie(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            movie, project, report = root/"film.mp4", root/"film.json", root/"review.json"
            movie.write_bytes(b"accepted version")
            project.write_text("[]", encoding="utf-8")
            result = self.call(project, report, movie)
            self.assertNotEqual(result.returncode, 0)
            failed = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual((failed["ok"], failed["published"], failed["stage"]), (False, False, "preflight"))
            self.assertIn("JSON object", failed["error"])
            self.assertEqual(movie.read_bytes(), b"accepted version")

    def test_report_cannot_replace_broken_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project, timeline = root/"project.json", root/"voice.json"
            project.write_text('{"audioTimeline":"voice.json","scenes":[]}', encoding="utf-8")
            timeline.write_bytes(b"incomplete timeline")
            for path in (project, timeline):
                with self.subTest(path=path.name):
                    previous = path.read_bytes()
                    self.assertNotEqual(self.call(project, path).returncode, 0)
                    self.assertEqual(path.read_bytes(), previous)

    def test_manifest_asset_cannot_become_an_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project, footage, report = root/"project.json", root/"footage.mp4", root/"review.json"
            project.write_text('{"assets":["footage.mp4"],"scenes":[]}', encoding="utf-8")
            footage.write_bytes(b"original footage")
            result = self.call(project, report, footage)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(footage.read_bytes(), b"original footage")
            self.assertIn("project input", json.loads(report.read_text(encoding="utf-8"))["error"])

    def test_paint_and_verbatim_failures_preserve_a_genuine_accepted_movie(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            project,report,movie=root/"film.json",root/"review.json",root/"film.mp4"
            master=root/"master.wav"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","sine=f=450:r=48000:d=1","-c:a","pcm_s16le",str(master)],check=True)
            def write(name,data):
                (root/name).write_text(json.dumps(data),encoding="utf-8")
            write("voice.json",{"sample_rate":48000,"master":{"file":master.name,"samples":48000,
                "sha256":hashlib.sha256(master.read_bytes()).hexdigest()},"scenes":[{"id":"a","start_sample":0,"end_sample":48000,
                    "sentences":[{"text":"Dos marcas.","absolute_start_sample":0,"absolute_end_sample":48000}]}]})
            captions=root/"captions.srt"
            captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nDos marcas.\n",encoding="utf-8")
            write("attention.json",{"fps":12,"frames":12,"tracks":{"a":{"box":[0,0,.5,1]},"b":{"box":[.5,0,.5,1]}},
                  "beats":[{"start":0,"end":12,"focus":"a","moving":["a","b"],"mode":"motion","idea":"Dos marcas avanzan.",
                            "cues":[{"scene":"a","sentence":0}]}]})
            plan={"regions":[{"id":"papel","role":"surface","box":[.1,.05,.3,.1]}]}
            write("paint.json",plan)
            write("film.json",{"width":320,"height":180,"fps":12,"audioTimeline":"voice.json","attention":"attention.json",
                  "solidRegions":"paint.json","captionMode":"verbatim","scenes":[{"id":"a","title":"Marcas","html":"scene.html"}]})
            scene=root/"scene.html"
            drawing="""<canvas data-export-surface width="320" height="180"></canvas><script>
            const c=document.querySelector('canvas').getContext('2d');
            window.renderAt=(t,f)=>{c.fillStyle='#fff';c.fillRect(0,0,320,180);c.fillStyle='#9e1b32';
            c.fillRect(10+f*6,60,32,32);c.fillStyle='#696969';c.fillRect(175+f*6,80,32,32);};
            </script>"""
            scene.write_text(drawing,encoding="utf-8")
            result=self.call(project,report,movie)
            self.assertEqual(result.returncode,0,result.stderr)
            accepted=hashlib.sha256(movie.read_bytes()).hexdigest()
            receipt=json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(receipt["published"] and receipt["solidRegions"]["ok"])
            self.assertEqual(receipt["sourcePaint"]["scenes"][0]["framesChecked"],12)
            # An equivalent lossless master and a recovered browser frame
            # must preserve every delivered byte, including the sound.
            flac=root/"master.flac"
            subprocess.run(["ffmpeg","-v","error","-i",str(master),str(flac)],check=True)
            clock=json.loads((root/"voice.json").read_text())
            clock["master"].update(file=flac.name,sha256=hashlib.sha256(flac.read_bytes()).hexdigest())
            write("voice.json",clock)
            stall="if(f===5&&!localStorage.once){localStorage.once='1';return new Promise(()=>{});}"
            scene.write_text(drawing.replace("(t,f)=>{","(t,f)=>{"+stall),encoding="utf-8")
            result=self.call(project,report,movie,"--frame-timeout","2")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn("exception was never retrieved",result.stderr.lower())
            recovered=json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(recovered["sourcePaint"]["scenes"][0]["recoveredFrame"],5)
            self.assertEqual(hashlib.sha256(movie.read_bytes()).hexdigest(),accepted)
            delivered=subprocess.check_output(["ffmpeg","-v","error","-i",str(movie),"-map","0:s:0","-f","srt","-"])
            self.assertEqual(delivered.decode("utf-8").strip(),captions.read_text(encoding="utf-8").strip())
            scene.write_text(drawing.replace("(t,f)=>{","(t,f)=>{if(f===5)return new Promise(()=>{});"),encoding="utf-8")
            result=self.call(project,report,movie,"--frame-timeout","2")
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertNotIn("exception was never retrieved",result.stderr.lower())
            stalled=json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(stalled["sourcePaint"]["scenes"][0]["stalledFrame"],5)
            self.assertIn("frame 5",stalled["error"])
            self.assertFalse(stalled["published"])
            self.assertEqual(hashlib.sha256(movie.read_bytes()).hexdigest(),accepted)
            for failure in ("degradado","interior","palabras"):
                with self.subTest(failure=failure):
                    scene.write_text(drawing.replace("c.fillStyle='#9e1b32';",
                        "const g=c.createLinearGradient(0,0,320,0);g.addColorStop(0,'red');g.addColorStop(1,'white');c.fillStyle=g;")
                        if failure=="degradado" else drawing,encoding="utf-8")
                    write("paint.json",{"regions":[{**plan["regions"][0],"role":"primary"}]} if failure=="interior" else plan)
                    if failure=="palabras":
                        captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nTres marcas.\n",encoding="utf-8")
                    result=self.call(project,report,movie)
                    self.assertEqual(result.returncode,2,result.stdout)
                    rejected=json.loads(report.read_text(encoding="utf-8"))
                    self.assertFalse(rejected["published"])
                    self.assertEqual(hashlib.sha256(movie.read_bytes()).hexdigest(),accepted)
                    if failure=="degradado":
                        self.assertEqual(rejected["sourcePaint"]["scenes"][0]["findings"][0]["kind"],"gradient")
                    elif failure=="interior":
                        self.assertEqual(rejected["solidRegions"]["regions"][0]["failureIntervals"],[{"start":0,"end":12}])
                    else:
                        self.assertFalse(rejected["preRender"]["captions"]["speech"]["textMatches"])

            # With authored styling, retain a lead, gap, new line and a
            # last cue ending before the picture rather than resetting time.
            authored=json.loads(project.read_text(encoding="utf-8"))
            write(project.name,{**authored,"captionMode":"authored","subtitleLanguage":"spa"})
            captions.write_text("1\n00:00:00,220 --> 00:00:00,401\n<i>Dos</i>\nmarcas.\n\n"
                                "2\n00:00:00,576 --> 00:00:00,811\nObservación.\n",encoding="utf-8")
            result=self.call(project,report,movie)
            self.assertEqual(result.returncode,0,result.stderr)
            delivered=subprocess.check_output(["ffmpeg","-v","error","-i",str(movie),"-map","0:s:0","-f","srt","-"])
            self.assertEqual(delivered.decode("utf-8").strip(),captions.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
