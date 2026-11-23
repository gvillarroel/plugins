# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3"]
# ///
"""Encode timed card exchanges and test the detected cadence against known edits."""
import argparse
from fractions import Fraction
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import random
import subprocess
import tempfile

import numpy as np
import cadence_scan
from caption_tracks import write_atomic


def cases(fps, count, seed):
    step = max(1, math.floor(fps*cadence_scan.RAPID_STEP_SECONDS))
    combinations = list(itertools.product((1,4),range(1,step+1),range(1,step+1),(1,4)))
    draws = random.Random(seed).sample(combinations,min(count,len(combinations)))
    result = []
    for i,(a,b,c,d) in enumerate(draws):
        moving = bool(i%2)
        rapid=max(b,c)/fps<=cadence_scan.RAPID_STEP_SECONDS+.000001
        result.append(("alternancia" if rapid else "cambios separados", [0,1,0,1], [a,b,c,d], moving, rapid))
        kind = i%4
        if kind==0:
            result.append(("corte", [0,1], [a,b+c+d], moving, False))
        elif kind==1:
            result.append(("ida y vuelta", [0,1,0], [a,b,c+d], moving, False))
        elif kind==2:
            result.append(("progresión", [0,1,2,3], [a,b,c,d], moving, False))
        else:
            result.append(("lecturas largas", [0,1,0,1], [a,step*3,step*3,d], moving, False))
    return result


def geometry(size):
    width,height = size
    span = max(5,width//9)
    top = height//3
    return [(int((i+.5)*width/4)-span//2,top,span,max(8,height//8)) for i in range(4)]


def source_frames(case,size,boxes):
    _,states,holds,moving,_ = case
    w,h = size
    frame = np.full((h,w,3),255,np.uint8)
    frame[h//4:h//4+1,w//16:15*w//16] = 181
    for x,y,bw,bh in boxes:
        frame[y:y+bh,x:x+bw]=231
    total=sum(holds)
    tick=0
    for state,n in zip(states,holds):
        x,y,bw,bh=boxes[state]
        active=frame.copy()
        active[y:y+bh,x:x+bw]=[158,27,50]
        for _ in range(n):
            if moving:
                sample=active.copy()
                mark=round((w-w//8-1)*tick/max(1,total-1))
                sample[3*h//4:3*h//4+max(3,h//16),mark:mark+w//8]=105
                yield sample
            else:
                yield active
            tick+=1


def encode(clip, plans, size, fps, crf):
    width,height=size
    cmd=["ffmpeg","-v","error","-f","rawvideo","-pixel_format","rgb24","-video_size",f"{width}x{height}",
         "-framerate",str(fps),"-i","pipe:0","-c:v","libx264","-pix_fmt","yuv420p","-preset","veryfast",
         "-crf",str(crf),"-threads","2",str(clip)]
    boxes=geometry(size)
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as encoder:
        for case in plans:
            for frame in source_frames(case,size,boxes):
                encoder.stdin.write(frame)
        encoder.stdin.close()
        if encoder.wait():
            raise ValueError("The H.264 sample could not be encoded.")


def measure(clip, plans, size, fps, engines):
    w,h=size
    x,y,bw,bh=geometry(size)[0]
    # The band contains all four states; a second mark may travel independently below it.
    rows=[]
    cmd=["ffmpeg","-v","error","-xerror","-i",str(clip),"-map","0:v:0","-f","rawvideo",
         "-pix_fmt","rgb24","-threads","1","-"]
    with subprocess.Popen(cmd,stdout=subprocess.PIPE) as decoder:
        try:
            cursor=0
            for kind,states,holds,moving,expected in plans:
                probes={name:engine.RepeatedStates(fps) for name,engine in engines.items()}
                for _ in range(sum(holds)):
                    raw=decoder.stdout.read(w*h*3)
                    if len(raw)!=w*h*3:
                        raise ValueError("A timed card exchange ended before its last presentation frame.")
                    band=np.frombuffer(raw,np.uint8).reshape(h,w,3)[y-2:y+bh+2]
                    for checker in probes.values():
                        checker.observe(band)
                intervals={key:probe.report()["intervals"] for key,probe in probes.items()}
                outcomes={key:bool(spans) for key,spans in intervals.items()}
                source_states=[state for state,hold in zip(states,holds) for _ in range(hold)]
                witnesses={}
                for key,spans in intervals.items():
                    witnesses[key]=[]
                    for span in spans:
                        frames=span["strongestFrames"]
                        a,b,c,d=[source_states[t] for t in frames]
                        witnesses[key].append({"frames":frames,"sourceStates":[a,b,c,d],
                                               "alternating":a==c and b==d and a!=b})
                rows.append({"kind":kind, "startFrame":cursor, "states":states, "holds":holds, "witnesses":witnesses,
                             "movingSupport":moving, "expectedAlternation":expected, "detected":outcomes})
                cursor+=sum(holds)
            if decoder.stdout.read(1) or decoder.wait():
                raise ValueError("Unexpected trailing frames or H.264 decode error.")
        finally:
            if decoder.poll() is None:
                decoder.kill()
                decoder.wait()
    return rows


def summary(rows, key):
    return {"caught":sum(r["expectedAlternation"] and r["detected"][key] for r in rows),
            "missed":sum(r["expectedAlternation"] and not r["detected"][key] for r in rows),
            "falseAlarms":sum(not r["expectedAlternation"] and r["detected"][key] for r in rows),
            "approvedControls":sum(not r["expectedAlternation"] and not r["detected"][key] for r in rows),
            "unmatchedWitnesses":sum(r["expectedAlternation"] and r["detected"][key] and
                                     not any(w["alternating"] for w in r["witnesses"][key]) for r in rows)}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--fps",default="24",help="Exact delivery rate, for example 24 or 30000/1001")
    cli.add_argument("--size",default="160x96")
    cli.add_argument("--cases",type=int,default=30,help="Positive holds plus one control per case")
    cli.add_argument("--seed",type=int,default=47)
    cli.add_argument("--crf",type=int,default=17)
    cli.add_argument("--baseline",type=Path,help="Optional trusted earlier cadence_scan.py for a paired comparison")
    cli.add_argument("--report",type=Path,required=True)
    args=cli.parse_args()
    try:
        rate=Fraction(args.fps)
    except (ValueError,ZeroDivisionError):
        cli.error("Use a finite, positive frame rate such as 24 or 30000/1001.")
    try:
        w,h=map(int,args.size.lower().split("x"))
    except ValueError:
        cli.error("Use --size WIDTHxHEIGHT.")
    if not 1<=rate<=120 or min(w,h)<48 or w%2 or h%2 or not 0<=args.crf<=51 or args.cases<1:
        cli.error("Use positive cases, even delivery dimensions, 1–120 fps and CRF 0–51.")
    if args.report.exists():
        previous=json.loads(args.report.read_text(encoding="utf-8-sig"))
        if not isinstance(previous,dict) or previous.get("schema")!="line-world-encoded-cadence-v1":
            cli.error("Choose a new report or a previous cadence audit.")
    engines={"current":cadence_scan}
    if args.baseline:
        loaded=importlib.util.spec_from_file_location("baseline_cadence",args.baseline)
        old=importlib.util.module_from_spec(loaded)
        loaded.loader.exec_module(old)
        engines["previous"]=old
    plans=cases(float(rate),args.cases,args.seed)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.report.parent) as temporary:
        clip=Path(temporary)/"cuadros.mp4"
        encode(clip,plans,(w,h),rate,args.crf)
        with clip.open("rb") as stream:
            sha=hashlib.file_digest(stream,"sha256").hexdigest()
        rows=measure(clip,plans,(w,h),float(rate),engines)
    stats={key:summary(rows,key) for key in engines}
    report={"schema":"line-world-encoded-cadence-v1","frameSize":[w,h],"fps":float(rate),"rate":str(rate),"crf":args.crf,
            "seed":args.seed,"cases":len(rows),"frames":sum(sum(r["holds"]) for r in rows),
            "movieSha256":sha,"detectors":{key:hashlib.sha256(Path(mod.__file__).read_bytes()).hexdigest()
                                         for key,mod in engines.items()},
            "statistics":stats,"ok":not any(stats["current"][key] for key in ("missed","falseAlarms","unmatchedWitnesses")),"results":rows}
    write_atomic(args.report,json.dumps(report,ensure_ascii=False,separators=(",",":"))+"\n")
    print(json.dumps({key:report[key] for key in ("ok","frames","cases","statistics")}))
    return int(not report["ok"])


if __name__=="__main__":
    raise SystemExit(main())
