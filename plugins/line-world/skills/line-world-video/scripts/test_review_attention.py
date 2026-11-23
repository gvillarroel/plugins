# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3", "av>=18,<20"]
# ///
import copy
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib

import numpy as np

from review_attention import SourceStillness, focus_handoffs, inspect, schedule, validate


def example():
    return {"fps":24,"frames":48,"tracks":{name:{"box":[i/4,0,.25,1]}
            for i,name in enumerate(["guide","trace","meter","label"])},
            "beats":[{"start":0,"end":48,"mode":"motion","focus":"guide","moving":["guide","trace"],
                      "idea":"Follow the guide and the duration it measures.",
                      "cues":[{"scene":"step","sentence":0}]}]}


def encode_fixture(path,tracks):
    pictures=[]
    for i in range(48):
        rgb=np.full((80,240,3),255,np.uint8)
        for lane in range(4):
            x=lane*60+10
            y=4+(i if lane in tracks else 0)
            rgb[y:y+12,x:x+28]=[158,27,50] if not lane else [75,75,75]
        pictures.append(rgb.tobytes())
    subprocess.run(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s","240x80",
                    "-r","24","-i","pipe:0","-c:v","libx264","-pix_fmt","yuv420p",str(path)],
                   input=b"".join(pictures),check=True)


def slow_fixture(path, fps, variant):
    """Three seconds of subpixel displacement, including a one-second reading hold."""
    names=["guide","trace","meter","label"]
    objects={name:{"box":[i/4,0,.25,1]} for i,name in enumerate(names)}
    cut=fps//2
    def beat(a,b,active):
        return {"start":a,"end":b,"mode":"motion" if active else "read",
                "focus":active[0] if active else "guide","moving":active,
                "idea":"Read the indicated positions on a stationary reference."}
    beats=([beat(0,cut,names[:2]),beat(cut,fps,names[2:])] if variant=="staggered"
           else [beat(0,fps,names[:2])])
    beats.extend([beat(fps,2*fps,[]),beat(2*fps,3*fps,names[1:3])])
    score={"fps":fps,"frames":3*fps,"tracks":objects,"beats":beats}
    x=np.arange(240,dtype=float)
    offsets=np.zeros(4)
    cmd=["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","gray","-s","240x80",
         "-r",str(fps),"-i","-","-c:v","libx264","-preset","veryfast","-crf","12" if variant=="lossy" else "0",
         "-pix_fmt","yuv420p",str(path)]
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
        for i in range(3*fps):
            current=next(b for b in beats if b["start"]<=i<b["end"])
            active=current["moving"]
            if variant=="four" and i<fps: active=names
            if variant=="missing": active=[n for n in active if n!="trace"]
            if variant=="unplanned-hold" and fps<i<2*fps: active=["label"]
            if i>current["start"]:
                offsets[[names.index(n) for n in active]]+=3/fps
            image=np.full((80,240),246,np.uint8)
            for lane,offset in enumerate(offsets):
                left=lane*60+17.35+offset
                coverage=np.clip(np.minimum(x+1,left+19)-np.maximum(x,left),0,1)
                # Analytic area coverage makes slow motion visible without integer-position jitter.
                image[26:48]=np.minimum(image[26:48],np.rint(246-107*coverage).astype(np.uint8))
                image[54:55,lane*60+10:lane*60+50]=182
            proc.stdin.write(image.tobytes())
        proc.stdin.close()
        if proc.wait(): raise RuntimeError("FFmpeg failed to encode the temporal fixture.")
    return validate(score)


class AttentionTests(unittest.TestCase):
    def test_native_source_identity_and_residual_limits(self):
        def png(rgb):
            def chunk(kind, data):
                return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data))
            header=struct.pack(">IIBBBBB",240,80,8,2,0,0,0)
            scanlines=b"".join(b"\0"+row.tobytes() for row in rgb)
            return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",header)+chunk(b"IDAT",zlib.compress(scanlines))+chunk(b"IEND",b"")

        score=example()
        score.update(fps=12,frames=12)
        score["beats"][0].update(end=12,moving=["guide","trace","meter"])
        with tempfile.TemporaryDirectory() as directory:
            movie=Path(directory)/"four.mkv"
            for case in ("small-residual","visible-jump","broad-residual","real-thin-mark"):
                with self.subTest(case=case):
                    capture=SourceStillness(score,240,80)
                    encoded=[]
                    for frame in range(12):
                        source=np.full((80,240,3),255,np.uint8)
                        for lane in range(3):
                            x=lane*60+frame*2
                            source[25:45,x:x+20]=80
                        x=194+(frame if case=="real-thin-mark" else 0)
                        source[20:32,x]=35
                        capture.observe(png(source))
                        delivered=source.copy()
                        if frame and case=="small-residual":
                            delivered[45:47,200:204]=233
                        if frame and case=="visible-jump":
                            delivered[45:47,200:204]=135
                        if frame and case=="broad-residual":
                            delivered[40:48,200:216]=238
                        encoded.append(delivered.tobytes())
                    subprocess.run(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s","240x80",
                                    "-r","12","-i","pipe:0","-c:v","libx264rgb","-crf","0","-threads","1",str(movie)],
                                   input=b"".join(encoded),check=True)
                    evidence=capture.receipt(hashlib.sha256(movie.read_bytes()).hexdigest())
                    original=inspect(movie,score)
                    checked=inspect(movie,score,evidence)
                    self.assertIn("over-three",{i["code"] for i in original["issues"]})
                    self.assertEqual(checked["ok"],case=="small-residual",checked["issues"])
                    if case=="real-thin-mark":
                        self.assertNotIn("label",evidence["constantRGBA"])
                    else:
                        self.assertEqual(checked["nativeStillness"]["label"]["certified"],case=="small-residual")
                    modified=copy.deepcopy(score)
                    modified["beats"][0]["idea"]="Another idea"
                    with self.assertRaisesRegex(ValueError,"different export or plan"):
                        inspect(movie,modified,evidence)
                    with self.assertRaisesRegex(ValueError,"different export or plan"):
                        inspect(movie,score,{**evidence,"movieSha256":"0"*64})

    def test_unreadable_primary_subject_exchange_before_any_picture_is_rendered(self):
        score=example()
        score["frames"]=96
        def visit(a,b,focus):
            return {"start":a,"end":b,"mode":"motion","focus":focus,"moving":["guide","trace"],
                    "idea":"Compare the two successive marks."}
        score["beats"]=[visit(0,48,"guide"),visit(48,54,"trace"),visit(54,62,"guide"),visit(62,96,"trace")]
        with self.assertRaisesRegex(ValueError,"Rapid alternation.*48, 54, 62"):
            validate(score)
        score["beats"]=[visit(0,24,"guide"),visit(24,48,"trace"),visit(48,72,"guide"),visit(72,96,"trace")]
        self.assertEqual(focus_handoffs(validate(score))["rapidReturns"],[])
        score["tracks"]["trace"]["subject"]="measurement"
        score["tracks"]["guide"]["subject"]="measurement"
        self.assertEqual(focus_handoffs(validate(score))["visits"],[{"subject":"measurement","start":0,"end":96}])
    def test_duplicate_reference_does_not_replace_an_uncovered_half_sentence(self):
        score=example()
        first,second=copy.deepcopy(score["beats"][0]),copy.deepcopy(score["beats"][0])
        first.update(end=24,cues=first["cues"]*2)
        second.update(start=24,cues=[])
        score["beats"]=[first,second]
        audio={"sample_rate":48000,"master":{"samples":96000},"scenes":[{"id":"step","sentences":[
            {"absolute_start_sample":0,"absolute_end_sample":96000}]}]}
        with self.assertRaisesRegex(ValueError,"listed twice"):
            validate(score,audio)

    def test_preflight_clock_focus_and_duplicates(self):
        score=example()
        audio={"sample_rate":48000,"master":{"samples":96000},"scenes":[{"id":"step","sentences":[
            {"absolute_start_sample":2400,"absolute_end_sample":92000}]}]}
        validate(score,audio)
        self.assertEqual([x["second"] for x in schedule(score)],[0,1])
        for name,value in [("start",1),("end",46),("moving",["guide"]),("focus","missing"),
                           ("moving",list(score["tracks"])),("cues",[]),("cues",score["beats"][0]["cues"]*2)]:
            reject=copy.deepcopy(score)
            reject["beats"][0][name]=value
            with self.subTest(name=name,value=value),self.assertRaises(ValueError):
                validate(reject,audio)

    def test_two_real_changes_and_four_or_silent_mutations(self):
        with tempfile.TemporaryDirectory() as d:
            movie=Path(d)/"example.mp4"
            score=validate(example())
            encode_fixture(movie,[0,1])
            good=inspect(movie,score)
            self.assertTrue(good["ok"],good["issues"])
            self.assertTrue(all(row["beats"][0]["peakSimultaneous"]==2 for row in good["seconds"]))
            encode_fixture(movie,[0,1,2,3])
            codes={e["code"] for e in inspect(movie,score)["issues"]}
            self.assertIn("over-three",codes)
            self.assertIn("unplanned-movement",codes)
            encode_fixture(movie,[0])
            self.assertIn("planned-element-stayed-still",{e["code"] for e in inspect(movie,score)["issues"]})

    def test_slow_concurrency_and_staggered_regions_across_delivery_rates(self):
        with tempfile.TemporaryDirectory() as directory:
            movie=Path(directory)/"slow.mp4"
            for fps in (24,30,60,100):
                for variant,expected in (("correct",2),("staggered",2),("four",4)):
                    with self.subTest(fps=fps,variant=variant):
                        score=slow_fixture(movie,fps,variant)
                        report=inspect(movie,score)
                        first=report["seconds"][0]["beats"]
                        union={key for part in first for key in part["accumulatedMovement"]}
                        self.assertEqual(max(p["peakSimultaneous"] for p in first),expected)
                        self.assertEqual(len(union),2 if variant=="correct" else 4)
                        self.assertEqual(report["ok"],variant!="four",report["issues"])
                        self.assertEqual("over-three" in {i["code"] for i in report["issues"]}, variant=="four")
                        self.assertFalse(report["seconds"][1]["beats"][0]["accumulatedMovement"])

    def test_slow_missing_subject_unplanned_read_and_lossy_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            movie=Path(directory)/"controlled.mp4"
            for variant,code in (("missing","planned-element-stayed-still"),
                                 ("unplanned-hold","unplanned-accumulated-movement"),("lossy",None)):
                with self.subTest(variant=variant):
                    report=inspect(movie,slow_fixture(movie,100,variant))
                    codes={i["code"] for i in report["issues"]}
                    if code:
                        self.assertIn(code,codes)
                    else:
                        self.assertTrue(report["ok"],report["issues"])


if __name__=="__main__":
    unittest.main()
