"""Exercise edits to timing, order and element geometry, including ambiguous recuts."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from compare_frame_notes import compare, relocate
from frame_notes import digest, model, validate


def beat(start, end, subject):
    return {"start": start, "end": end, "idea": "Leer "+subject, "focus": subject, "mode": "read",
            "visible": [subject], "cues": [{"scene": subject, "sentence": 0}]}


class CompareNotes(unittest.TestCase):
    def setUp(self):
        self.tracks = {"oro": {"box": [.2,.3,.6,.6]}, "bono": {"box": [0,0,1,1]}}
        self.original = {"beats": [beat(0,4,"oro"),beat(4,10,"bono")], "tracks": self.tracks,
                         "pts": [i/10 for i in range(10)]}
        self.candidate = {"beats": [beat(0,3,"bono"),beat(3,10,"oro")], "tracks": deepcopy(self.tracks),
                          "pts": [i/10 for i in range(10)]}
        self.candidate["tracks"]["oro"]["box"]=[.1,.2,.8,.4]
        self.note = {"id":"oro","text":"¿Sigue legible <oro>?","kind":"conservar","element":"oro",
                     "frame":1,"endFrame":3,"point":[.35,.6]}

    def test_moves_frames_and_marker_across_reordered_scenes(self):
        moved = relocate(self.note, self.original, self.candidate)
        self.assertEqual((moved["frame"], moved["endFrame"], moved["point"]), (5, 9, [.3,.4]))
        self.assertEqual(moved["seconds"], .5)

    def test_missing_ambiguous_changed_or_unbound(self):
        variants = []
        changed = deepcopy(self.candidate)
        changed["beats"][1]["idea"] = "Otra cifra"
        variants.append(changed)
        repeated = deepcopy(self.candidate)
        repeated["beats"] = [beat(0,4,"oro"),beat(4,7,"bono"),beat(7,10,"oro")]
        variants.append(repeated)
        no_cue = deepcopy(self.candidate)
        no_cue["beats"][1].pop("cues")
        variants.append(no_cue)
        for target in variants:
            with self.subTest(target=target), self.assertRaises(ValueError):
                relocate(self.note, self.original, target)
        for note in ({**self.note,"element":None},{**self.note,"endFrame":6}):
            with self.subTest(note=note), self.assertRaises(ValueError):
                relocate(note, self.original, self.candidate)

    def test_one_frame_and_adjacent_equivalent_beats(self):
        self.original["beats"] = [beat(0,1,"oro"),beat(1,10,"bono")]
        self.candidate["beats"] = [beat(0,3,"bono"),beat(3,4,"oro"),beat(4,10,"oro")]
        note = {**self.note,"frame":0,"endFrame":0}
        moved = relocate(note, self.original, self.candidate)
        self.assertEqual((moved["frame"],moved["endFrame"]),(3,3))

    def test_compare_real_decoded_frames_and_reimport(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def fixture(name, info, size, fps):
                video=root/(name+".mp4")
                subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i",f"testsrc2=size={size}:rate={fps}",
                    "-frames:v","10","-c:v","libx264","-threads","1",str(video)],check=True)
                plan=root/(name+"-plan.json")
                plan.write_text(json.dumps({**info,"frames":10,"fps":fps}),encoding="utf-8")
                return video, plan
            before, old_plan=fixture("antes",self.original,"160x90",10)
            after, new_plan=fixture("nueva",self.candidate,"90x160",12)
            notes=root/"notas.json"
            notes.write_text(json.dumps({"version":1,"videoSha256":digest(before),"attentionSha256":digest(old_plan),
                "notes":[self.note,{**self.note,"id":"zona","element":None}]}),encoding="utf-8")
            out=root/"revision"
            report=compare(before,after,notes,old_plan,new_plan,out)
            self.assertEqual([r["status"] for r in report["notes"]],["por-revisar","sin-correspondencia"])
            entry=report["notes"][0]
            self.assertEqual(digest(out/entry["candidateImage"]),entry["candidateImageSha256"])
            document=json.loads((out/"notas-candidata.json").read_text(encoding="utf-8"))
            info=model(after,new_plan)
            moved=validate(document,info)[0]
            self.assertEqual(moved["seconds"],info["pts"][5])
            self.assertIn("&lt;oro&gt;",(out/"comparar.html").read_text(encoding="utf-8"))
            self.assertEqual(len(list(out.glob("*.png"))),3)


if __name__ == "__main__":
    unittest.main()
