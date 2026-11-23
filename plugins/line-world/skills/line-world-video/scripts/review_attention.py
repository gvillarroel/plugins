# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3"]
# ///
"""Pre-render and post-export hooks for a narrated film's second-by-second attention plan."""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
from graphlib import CycleError, TopologicalSorter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from cadence_scan import RAPID_STEP_SECONDS, RepeatedStates, SubjectCadence


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def required(condition, message):
    if not condition:
        raise ValueError(message)


def focus_handoffs(score):
    """Collapse a subject's reveal and reading hold into one visit, then check the editorial handoffs."""
    visits=[]
    for beat in score["beats"]:
        track=score["tracks"][beat["focus"]]
        subject=track.get("subject",beat["focus"])
        required(isinstance(subject,str) and subject.strip(),"A focus subject must have a stable name.")
        if visits and visits[-1]["subject"]==subject:
            visits[-1]["end"]=beat["end"]
        else:
            visits.append({"subject":subject,"start":beat["start"],"end":beat["end"]})
    maximum=max(1,math.floor(RAPID_STEP_SECONDS*score["fps"]))
    repeats=[]
    for a,b,c,d in zip(visits,visits[1:],visits[2:],visits[3:]):
        if a["subject"]==c["subject"] and b["subject"]==d["subject"] and max(b["end"]-b["start"],c["end"]-c["start"])<=maximum:
            repeats.append({"subjects":[a["subject"],b["subject"]],"frames":[a["end"]-1,b["start"],c["start"],d["start"]]})
    return {"visits":visits,"rapidReturns":repeats,"maximumIntermediateFrames":maximum}


def validate(score, narration=None):
    """All intervals are half-open frame numbers on the export clock."""
    fps=score.get("fps")
    required(type(fps) is int and 1 <= fps <= 120, "Provide a positive integer export fps up to 120.")
    frames=score.get("frames")
    required(type(frames) is int and frames>0, "The export needs a frame count.")
    tracks=score.get("tracks")
    required(isinstance(tracks,dict) and len(tracks)>=2, "Define at least two named visual elements.")
    for name,track in tracks.items():
        required(isinstance(track,dict),f"{name}: the track must be an object.")
        box=track.get("box")
        required(isinstance(name,str) and name.strip() and isinstance(box,list) and len(box)==4,
                 f"{name}: provide a stable element ID and normalized [x,y,w,h].")
        required(all(type(n) in (float,int) and math.isfinite(n) for n in box),f"{name}: invalid box.")
        x,y,w,h=box
        required(min(x,y)>=0 and min(w,h)>0 and x+w<=1.000001 and y+h<=1.000001,
                 f"{name}: box lies outside the visible image.")
        behind=track.get("occludes",[])
        required(isinstance(behind,list) and all(isinstance(n,str) and n in tracks for n in behind)
                 and len(set(behind))==len(behind) and name not in behind,
                 f"{name}: occludes must identify distinct tracks behind this opaque rectangle.")
    try:
        TopologicalSorter({name:track.get("occludes",[]) for name,track in tracks.items()}).prepare()
    except CycleError as exc:
        raise ValueError(f"The declared foreground/background order contains a cycle: {exc.args[-1]}.") from exc
    beats=score.get("beats")
    required(isinstance(beats,list) and beats,"Define contiguous beats in source frames.")
    cursor=0
    for beat in beats:
        a,b=beat["start"],beat["end"]
        required(type(a) is int and type(b) is int and a==cursor and a<b<=frames,
                 "The beats must cover the film once without gaps or overlaps.")
        cursor=b
        focus=beat["focus"]
        active=beat["moving"]
        required(focus in tracks and isinstance(beat.get("idea"),str) and beat["idea"].strip(),
                 f"Frame {a}: name the focus and the idea the viewer should understand.")
        required(isinstance(active,list) and len(set(active))==len(active) and set(active)<=tracks.keys(),
                 f"Frame {a}: each moving element needs its own known ID.")
        mode=beat["mode"]
        required(mode in ("motion","read"),f"Frame {a}: mode must be motion or read.")
        required(type(beat.get("cut",False)) is bool, f"Frame {a}: cut must be a boolean.")
        required(len(active)<=3,f"Frame {a}: more than three independently moving elements.")
        if mode=="motion":
            required(2<=len(active) and focus in active,
                     f"Frame {a}: a dynamic beat needs the main focus and one or two supporting movements.")
        required(isinstance(beat.get("visible",list(tracks)),list) and
                 set([focus,*active])<=set(beat.get("visible",tracks))<=tracks.keys(),
                 f"Frame {a}: visible elements must include the focus and all moving elements.")
    required(cursor==frames,"The plan does not cover the end of the film.")
    returns=focus_handoffs(score)["rapidReturns"]
    if returns:
        first=returns[0]
        raise ValueError(f"Rapid alternation of the primary focus between {first['subjects']} at frames {first['frames']}.")
    required(len({name for beat in beats for name in beat["moving"]})>=2,
             "The film must actually animate two distinct elements.")
    if narration is not None:
        rate=narration["sample_rate"]
        samples=narration["master"].get("samples",narration["master"].get("frames"))
        required(math.ceil(samples*fps/rate)==frames,"The final frame must cover the measured voice master.")
        sentences={(s["id"],i): row for s in narration["scenes"] for i,row in enumerate(s["sentences"])}
        coverage=Counter()
        for beat in beats:
            seen=set()
            for cue in beat.get("cues",[]):
                key=(cue["scene"],cue["sentence"])
                required(key in sentences,f"Unknown narration sentence {key}.")
                required(key not in seen,f"Frame {beat['start']}: narration sentence {key} is listed twice.")
                seen.add(key)
                phrase=sentences[key]
                first=math.floor(phrase["absolute_start_sample"]*fps/rate)
                last=math.ceil(phrase["absolute_end_sample"]*fps/rate)
                overlap=max(0,min(beat["end"],last)-max(beat["start"],first))
                required(overlap>0,f"Frame {beat['start']}: {key} is spoken at a different time.")
                coverage[key]+=overlap
        for key,phrase in sentences.items():
            count=math.ceil(phrase["absolute_end_sample"]*fps/rate)-math.floor(phrase["absolute_start_sample"]*fps/rate)
            required(coverage[key]==count,f"Sentence {key} has missing or duplicated visual coverage.")
    return score


def schedule(score):
    rows=[]
    for i in range(math.ceil(score["frames"]/score["fps"])):
        a=i*score["fps"]
        b=min(score["frames"],a+score["fps"])
        parts=[{"from":max(a,x["start"]),"to":min(b,x["end"]),"focus":x["focus"],"mode":x["mode"],
                "moving":x["moving"],"idea":x["idea"],"cues":x.get("cues",[])}
               for x in score["beats"] if x["start"]<b and x["end"]>a]
        rows.append({"second":i,"beats":parts})
    return rows


def mask_for_track(box,width,height):
    x,y,w,h=box
    rect=np.zeros((height,width),dtype=bool)
    rect[math.floor(y*height):math.ceil((y+h)*height),
         math.floor(x*width):math.ceil((x+w)*width)]=True
    return rect


def visible_regions(names,tracks,masks,shape):
    """A declared stationary opaque foreground owns the portion of a rear surface it covers."""
    exposed={name:masks[name] for name in names}
    for front in names:
        for back in tracks[front].get("occludes",[]):
            if back in exposed:
                exposed[back]=exposed[back] & ~masks[front]
    coverage=np.zeros(shape,dtype=np.int32)
    for mask in exposed.values():
        coverage+=mask
    owned={name:mask & (coverage==1) for name,mask in exposed.items()}
    for front in names:
        behind=[n for n in tracks[front].get("occludes",[]) if n in owned]
        if not behind:
            continue
        ys,xs=np.nonzero(masks[front])
        if not ys.size:
            continue
        # RGB edge reconstruction and the temporal 3×3 filter mix neighbors across a plate's border.
        # Keep that narrow border in total coverage, but never assign it to either moving subject.
        y0,y1,x0,x1=ys.min(),ys.max()+1,xs.min(),xs.max()+1
        interior=np.zeros(shape,dtype=bool)
        if y1-y0>4 and x1-x0>4:
            interior[y0+2:y1-2,x0+2:x1-2]=True
        owned[front]&=interior
        for back in behind:
            owned[back][max(0,y0-2):y1+2,max(0,x0-2):x1+2]=False
    return coverage,owned


def adjacent_support(changed):
    """Count coherent edges while excluding isolated single-pixel codec noise."""
    supported=np.zeros_like(changed)
    horizontal=changed[:,1:] & changed[:,:-1]
    vertical=changed[1:,:] & changed[:-1,:]
    supported[:,1:] |= horizontal
    supported[:,:-1] |= horizontal
    supported[1:,:] |= vertical
    supported[:-1,:] |= vertical
    return supported


def smooth_excursion(span):
    """A spatially coherent colour excursion survives a 3×3 signed average."""
    h,w=span.shape[:2]
    padded=np.pad(span,((1,1),(1,1),(0,0)),mode="edge")
    neighbourhood=sum(padded[y:y+h,x:x+w] for y in range(3) for x in range(3))
    return np.max(np.abs(neighbourhood),axis=2)>=8*9


def pixel_box(box,width,height):
    x,y,w,h=box
    return (math.floor(x*width),math.floor(y*height),
            min(width,math.ceil((x+w)*width)),min(height,math.ceil((y+h)*height)))


def score_hash(score):
    return hashlib.sha256(json.dumps(score,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


class SourceStillness:
    """Retain only native rectangles that are byte-identical throughout capture."""
    def __init__(self,score,width,height):
        self.decoder=None
        self.score=score
        self.size=(width,height)
        self.boxes={key:pixel_box(track["box"],width,height) for key,track in score["tracks"].items()}
        self.hashes={}
        self.frames=0

    def observe(self,png):
        if self.boxes:
            import av
            if self.decoder is None:
                self.decoder=av.CodecContext.create("png","r")
                self.decoder.thread_count=1
            # Every browser PNG is a standalone image; an unmarked packet can
            # be interpreted as a difference against the previous decoded PNG.
            packet=av.Packet(png)
            packet.is_keyframe=True
            picture=self.decoder.decode(packet)[0]
            required((picture.width,picture.height)==self.size,"Source frame dimensions changed.")
            rgb=picture.to_ndarray(format="rgba")
            for name,(x,y,right,bottom) in list(self.boxes.items()):
                digest=hashlib.sha256(rgb[y:bottom,x:right].tobytes()).hexdigest()
                if self.frames and digest!=self.hashes[name]:
                    del self.boxes[name],self.hashes[name]
                else:
                    self.hashes[name]=digest
        self.frames+=1

    def receipt(self,movie_sha):
        required(self.frames==self.score["frames"],"Source stillness needs every capture frame.")
        return {"version":1,"frames":self.frames,"size":list(self.size),"scoreSha256":score_hash(self.score),
                "movieSha256":movie_sha,"constantRGBA":dict(self.hashes)}


def check_stillness(video,score,width,height,evidence):
    """Certify only local, low-amplitude codec residuals in proven static rectangles."""
    with video.open("rb") as handle:
        movie_sha=hashlib.file_digest(handle,"sha256").hexdigest()
    proof=evidence.get("constantRGBA")
    required(evidence.get("version")==1 and evidence.get("frames")==score["frames"] and
             evidence.get("size")==[width,height] and evidence.get("scoreSha256")==score_hash(score)
             and evidence.get("movieSha256")==movie_sha,"Source stillness refers to a different export or plan.")
    required(isinstance(proof,dict) and proof.keys()<=score["tracks"].keys() and
             all(isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v) for v in proof.values()),
             "Malformed source stillness evidence.")
    boxes={name:pixel_box(score["tracks"][name]["box"],width,height) for name in proof}
    results={}
    for name,(x,y,r,b) in boxes.items():
        area=(r-x)*(b-y)
        results[name]={"certified":True,"maxChannelDelta":0,"maxPixelsAtLeast7":0,"maxMeanChannelDelta":0.0,
                       "pixelLimit":min(16,max(1,math.floor(area*.002)))}
    if not boxes:
        return results
    # Decode only the union's bounding rectangle, in original RGB coordinates.
    x=min(b[0] for b in boxes.values()); y=min(b[1] for b in boxes.values())
    w=max(b[2] for b in boxes.values())-x; h=max(b[3] for b in boxes.values())-y
    cmd=["ffmpeg","-v","error","-xerror","-threads","2","-filter_threads","1","-i",str(video),"-map","0:v:0",
         "-vf",f"format=rgb24,crop={w}:{h}:{x}:{y}:exact=1","-fps_mode","passthrough","-pix_fmt","rgb24",
         "-threads","1","-f","rawvideo","pipe:1"]
    with subprocess.Popen(cmd,stdout=subprocess.PIPE) as proc:
        try:
            for frame in range(score["frames"]):
                raw=proc.stdout.read(w*h*3)
                required(len(raw)==w*h*3,"Missing native frame during source stillness check.")
                rgb=np.frombuffer(raw,np.uint8).reshape(h,w,3)
                if frame==0:
                    first=previous=rgb
                    continue
                for name,(left,top,right,bottom) in boxes.items():
                    row=results[name]
                    if not row["certified"]:
                        continue
                    region=np.s_[top-y:bottom-y,left-x:right-x]
                    current=rgb[region].astype(np.int16)
                    for anchor in ((first,) if frame==1 else (first,previous)):
                        delta=np.abs(current-anchor[region])
                        peak=int(delta.max())
                        count=int(np.count_nonzero(delta.max(axis=2)>=7))
                        mean=float(delta.mean())
                        row["maxChannelDelta"]=max(row["maxChannelDelta"],peak)
                        row["maxPixelsAtLeast7"]=max(row["maxPixelsAtLeast7"],count)
                        row["maxMeanChannelDelta"]=max(row["maxMeanChannelDelta"],round(mean,5))
                        if peak>48 or count>row["pixelLimit"] or mean>.12:
                            row.update(certified=False,firstExceededFrame=frame)
                            break
                previous=rgb
            required(not proc.stdout.read(1) and proc.wait()==0,"Native stillness decode failed.")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    return results


def inspect(video,score,source_stillness=None):
    info=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time","-of","json",str(video)]))
    stream=info["streams"][0]
    fps,frames=score["fps"],score["frames"]
    required(Fraction(stream["avg_frame_rate"])==fps and len(info["frames"])==frames,
             "Encoded cadence or frame count differs from the attention plan.")
    required(all(abs(float(row["best_effort_timestamp_time"])-n/fps) < .5/fps for n,row in enumerate(info["frames"])),
             "Encoded timestamps differ from the attention plan.")
    size=min(1,240/max(stream["width"],stream["height"]))
    w,h=max(1,round(stream["width"]*size)),max(1,round(stream["height"]*size))
    masks={k:mask_for_track(v["box"],w,h) for k,v in score["tracks"].items()}
    residuals=check_stillness(video,score,stream["width"],stream["height"],source_stillness) if source_stillness is not None else {}
    certified={name for name,row in residuals.items() if row["certified"]}
    seconds=schedule(score)
    issues=[]
    def issue(code,frame,detail):
        if issues and issues[-1]["code"]==code and issues[-1]["detail"]==detail and issues[-1]["endFrame"]==frame:
            issues[-1]["endFrame"]=frame+1
        else:
            issues.append({"code":code,"startFrame":frame,"endFrame":frame+1,"detail":detail})
    cmd=["ffmpeg","-v","error","-xerror","-threads","2","-filter_threads","1","-i",str(video),"-map","0:v:0",
         "-vf",f"scale={w}:{h}:flags=area","-fps_mode","passthrough","-pix_fmt","rgb24","-threads","1","-f","rawvideo","pipe:1"]
    current=-1
    previous=None
    anchor=None
    anchor_frame=-1
    cadence=RepeatedStates(fps)
    subject_cadence=SubjectCadence(fps)
    with subprocess.Popen(cmd,stdout=subprocess.PIPE) as proc:
        try:
            for frame in range(frames):
                raw=proc.stdout.read(w*h*3)
                required(len(raw)==w*h*3,f"Missing decoded frame {frame}.")
                rgb=np.frombuffer(raw,np.uint8).reshape(h,w,3).astype(np.int16)
                cadence.observe(rgb)
                if current<0 or frame==beat["end"]:
                    current+=1
                    beat=score["beats"][current]
                    names=beat.get("visible",list(masks))
                    coverage,owned=visible_regions(names,score["tracks"],masks,(h,w))
                    thresholds={name:(max(3,math.ceil(mask.sum()*.0009)),max(5,math.ceil(mask.sum()*.001)))
                                for name,mask in owned.items()}
                    for name in names:
                        required(owned[name].sum()>=6,
                                 f"Frame {frame}: {name} needs a distinguishable screen region.")
                    subject_cadence.configure(owned, frame, cut=bool(beat.get("cut")))
                subject_cadence.observe(rgb)
                second=seconds[frame//fps]
                part=next(p for p in second["beats"] if p["from"]<=frame<p["to"])
                counts=part.setdefault("movingFrameCounts",{})
                witnesses=part.setdefault("accumulatedMovement",{})
                if frame==part["from"] or anchor is None:
                    # A new beat, second or cut cannot inherit motion from an earlier reading pose.
                    anchor=rgb
                    anchor_frame=frame
                span=rgb-anchor
                span_size=np.max(np.abs(span),axis=2)
                strong_span=span_size>18
                soft_span=adjacent_support(smooth_excursion(span))
                for name,mask in owned.items():
                    if name in certified:
                        continue
                    strong_limit,soft_limit=thresholds[name]
                    count=int(np.count_nonzero(mask & strong_span))
                    soft_count=int(np.count_nonzero(mask & soft_span))
                    if count>=strong_limit or soft_count>=soft_limit:
                        witness=witnesses.setdefault(name,{"referenceFrame":anchor_frame,"firstFrame":frame,
                                                           "maxChangedPixels":0})
                        witness["maxChangedPixels"]=max(witness["maxChangedPixels"],count,soft_count)
                # A cut can replace the entire frame. Only the declared first frame is exempt.
                cut=(frame==beat["start"] and beat.get("cut",False))
                if previous is not None and not cut:
                    step=rgb-previous
                    size_step=np.max(np.abs(step),axis=2)
                    delta=size_step>18
                    soft_step=adjacent_support(size_step>=7)
                    # A several-frame excursion corroborates very weak steps, but a track
                    # contributes to concurrency only if THIS pair of frames actually changes.
                    inner=np.einsum("ijk,ijk->ij",step,span,dtype=np.int32)
                    tiny=(size_step>=2) & (span_size>=12)
                    forward=adjacent_support(tiny & (inner>0))
                    backwards=adjacent_support(tiny & (inner<0))
                    moving=[]
                    for name,mask in owned.items():
                        if name in certified:
                            continue
                        strong_limit,soft_limit=thresholds[name]
                        strong=np.count_nonzero(mask & delta)>=strong_limit
                        soft=(name in witnesses and
                              (np.count_nonzero(mask & soft_step)>=soft_limit or
                               np.count_nonzero(mask & forward)>=soft_limit or
                               np.count_nonzero(mask & backwards)>=soft_limit))
                        pair_changed=strong or soft
                        if pair_changed:
                            moving.append(name)
                            counts[name]=counts.get(name,0)+1
                    part["peakSimultaneous"]=max(part.get("peakSimultaneous",0),len(moving))
                    if len(moving)>3: issue("over-three",frame,sorted(moving))
                    undeclared=set(moving)-set(beat["moving"])
                    if undeclared: issue("unplanned-movement",frame,sorted(undeclared))
                    if np.count_nonzero(delta & (coverage==0))>=max(9,math.ceil(.0018*w*h)):
                        issue("movement-outside-planned-elements",frame,"Check the focus and its supporting elements.")
                previous=rgb
            required(not proc.stdout.read(1) and proc.wait()==0,"FFmpeg did not complete the attention review.")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    for row in seconds:
        for part in row["beats"]:
            unplanned=set(part["accumulatedMovement"])-set(part["moving"])
            if unplanned:
                issue("unplanned-accumulated-movement",part["from"],sorted(unplanned))
            if part["mode"]!="motion" or part["to"]-part["from"]<max(3,fps//3):
                continue
            missing=[k for k in part["moving"] if k not in part["accumulatedMovement"] and not part["movingFrameCounts"].get(k)]
            if missing:
                issue("planned-element-stayed-still",part["from"],missing)
    repetition=cadence.report()
    repetition["subjectIntervals"]=subject_cadence.finish()
    for span in repetition["intervals"]:
        issues.append({"code":"rapid-alternation","startFrame":span["firstFrame"],
                       "endFrame":span["lastFrame"]+1,"detail":span["strongestFrames"]})
    for span in repetition["subjectIntervals"]:
        issues.append({"code":"rapid-subject-alternation","startFrame":span["firstFrame"],
                       "endFrame":span["lastFrame"]+1,"detail":{"subject":span["subject"],"frames":span["strongestFrames"]}})
    repetition["ok"] = repetition["ok"] and not repetition["subjectIntervals"]
    return {"ok":not issues,"seconds":seconds,"issues":issues,"frames":frames,"fps":fps,"cadence":repetition,
            "focusHandoffs":focus_handoffs(score),
            "occlusions":{name:track["occludes"] for name,track in score["tracks"].items() if track.get("occludes")},
            "nativeStillness":residuals,"sampleSize":[w,h],"scope":"Instantaneous peaks use adjacent decoded frames in exclusive subject regions. "
            "Accumulated movement is independently measured against the first pose in each beat/second; it cannot increase concurrency. "
            "The 240-pixel measurement cannot reliably isolate sub-resolution subjects or distinguish camera movement from object movement."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=["pre-render","post-export"])
    p.add_argument("score",type=Path)
    p.add_argument("--audio-timeline",type=Path)
    p.add_argument("--video",type=Path)
    p.add_argument("--source-report",type=Path,help="Optional successful composer receipt bound to this encoded film and attention plan.")
    p.add_argument("--report",required=True,type=Path)
    args=p.parse_args()
    inputs=[arg.resolve() for arg in [args.score,args.audio_timeline,args.video] if arg]
    if args.report.resolve() in inputs or (args.source_report and args.report.resolve()==args.source_report.resolve()): p.error("Write the report separately from its sources.")
    if args.stage=="post-export" and not args.video: p.error("post-export requires --video")
    if args.source_report and args.stage!="post-export": p.error("--source-report requires post-export")
    try:
        score=validate(read(args.score),read(args.audio_timeline) if args.audio_timeline else None)
        evidence=None
        if args.source_report:
            composer=read(args.source_report)
            required(isinstance(composer,dict) and composer.get("ok") and composer.get("published") and isinstance(composer.get("sourceStillness"),dict)
                     and composer.get("sourceStillnessSha256")==score_hash(composer["sourceStillness"])
                     and composer.get("candidateSha256")==composer["sourceStillness"].get("movieSha256"),
                     "The composer receipt does not attest to a published source stillness check.")
            evidence=composer["sourceStillness"]
        report=inspect(args.video,score,evidence) if args.stage=="post-export" else {"ok":True,"seconds":schedule(score),"focusHandoffs":focus_handoffs(score)}
        report["stage"]=args.stage
        if evidence is not None:
            report["sourceStillnessSha256"]=score_hash(evidence)
        report["sha256"]={}
        for path in inputs:
            with path.open("rb") as stream: report["sha256"][str(path)]=hashlib.file_digest(stream,"sha256").hexdigest()
    except (KeyError,TypeError,ValueError,OSError,IndexError,subprocess.SubprocessError) as e:
        report={"ok":False,"stage":args.stage,"error":str(e)}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",dir=args.report.parent,encoding="utf-8",delete=False) as handle:
        json.dump(report,handle,ensure_ascii=False,indent=2)
        temp=Path(handle.name)
    try: os.replace(temp,args.report)
    finally: temp.unlink(missing_ok=True)
    print(json.dumps({"ok":report["ok"],"stage":args.stage,"report":str(args.report),
                      "issues":len(report.get("issues",[])),"error":report.get("error")},ensure_ascii=False))
    return 0 if report["ok"] else 2


if __name__=="__main__":
    raise SystemExit(main())
