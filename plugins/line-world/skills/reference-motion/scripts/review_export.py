# /// script
# requires-python = ">=3.10"
# dependencies = ["rea-video @ git+https://github.com/JuneYaooo/rea-video.git@a124acd4a02b3a9b72b9e7dedca5d1bfcda2a7b8", "Pillow>=10"]
# ///
"""Review a delivered MP4 with rea-video and time-labelled decoded images.

Use --at for the editorial beats and --text-box for tightly bounded lines on
a white background. All boxes and display widths are in pixels.
"""
import argparse
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
from urllib.request import url2pathname

import cv2
import numpy as np
from PIL import Image, ImageDraw
from rea_video.media import video_info
from rea_video.shots import build_track, detect_shots
import rea_video.shots


PIN = "a124acd4a02b3a9b72b9e7dedca5d1bfcda2a7b8"

def provenance():
    dist=importlib.metadata.distribution("rea-video")
    metadata=json.loads(dist.read_text("direct_url.json") or "{}")
    revision=metadata.get("vcs_info",{}).get("commit_id")
    if revision is None and metadata.get("url","").startswith("file:"):
        checkout=Path(url2pathname(urlsplit(metadata["url"]).path))
        revision=subprocess.check_output(["git","-C",str(checkout),"rev-parse","HEAD"],text=True).strip()
        for module in ["shots.py","media.py","transitions.py"]:
            source=subprocess.check_output(["git","-C",str(checkout),"show",f"{PIN}:rea_video/{module}"])
            installed=(Path(rea_video.shots.__file__).parent/module).read_bytes()
            if installed.replace(b"\r\n",b"\n")!=source.replace(b"\r\n",b"\n"):
                raise ValueError(f"Installed upstream module differs from checkout revision: {module}")
    if revision!=PIN: raise ValueError(f"Expected rea-video {PIN}, found {revision}")
    return {"repository":"https://github.com/JuneYaooo/rea-video","revision":revision,"package_version":dist.version}


def activity(track):
    """Summarize conspicuous changes rather than equating motion with a cut."""
    active = np.flatnonzero(track.changed >= .005).tolist()
    groups = []
    for index in active:
        if groups and index - groups[-1][-1] <= max(1,round(.16*track.fps)):
            groups[-1].append(index)
        else:
            groups.append([index])
    return [{"first_frame":g[0],"last_frame":g[-1],"start_s":round(g[0]/track.fps,3),
             "end_s":round((g[-1]+1)/track.fps,3),"frames_over_threshold":len(g),
             "peak_fraction":round(float(max(track.changed[g])),4)} for g in groups if len(g)>=2]


def match_receipt(path, digest, fps, frames, shots):
    """Link detector marks to authored joins without treating each mark as an edit."""
    receipt=json.loads(path.read_text(encoding="utf-8-sig"))
    if (receipt.get("output_sha256") or receipt.get("sha256")) != digest:
        raise ValueError("Receipt and reviewed MP4 have different SHA-256 hashes")
    if receipt.get("fps") != fps or (receipt.get("frames") or receipt.get("decoded_frames")) != frames:
        raise ValueError("Receipt and reviewed MP4 have different clocks")
    if "transition_audit" in receipt:
        joins=[{"id":d["id"],"from":d["from"],"to":d["to"],"reason":d["reason"],
                "start_s":d["start_frame"]/fps,"end_s":(d["start_frame"]+d["duration_frames"])/fps}
               for d in receipt["transition_audit"]["decisions"]]
    elif isinstance(receipt.get("transitions"),list):
        joins=[{k:d[k] for k in ("id","from","to","start_s","end_s")} for d in receipt["transitions"]]
    else:
        raise ValueError("Receipt has no editorial decision list")
    beats=sorted({t for shot in shots for t in shot.get("beats",[])})
    for join in joins:
        if not 0 <= join["start_s"] < join["end_s"] <= frames/fps+1e-6:
            raise ValueError("Editorial join outside the video")
        join["detector_beats_in_window"]=[t for t in beats if join["start_s"]<=t<join["end_s"]]
    covered={beat for join in joins for beat in join["detector_beats_in_window"]}
    return {"receipt":path.name,"joins":joins,"styled":sum(d["id"]!="cut" for d in joins),
            "cuts":sum(d["id"]=="cut" for d in joins),"beats_outside_joins":sorted(set(beats)-covered)}


def source_frame(cap, seconds, fps, count):
    index=round(seconds*fps)
    if not 0<=index<count:
        raise ValueError(f"{seconds} s lies outside {count} frames at {fps} fps")
    cap.set(cv2.CAP_PROP_POS_FRAMES,index)
    ok,raw=cap.read()
    if not ok:
        raise ValueError(f"Could not decode frame {index}")
    return cv2.cvtColor(raw,cv2.COLOR_BGR2RGB),index


def text_measure(rgb,width,box):
    """Measure ink bounding box after resizing the whole frame to viewing size."""
    factor=width/rgb.shape[1]
    resized=cv2.resize(rgb,(width,round(rgb.shape[0]*factor)),interpolation=cv2.INTER_AREA)
    x,y,w,h=map(float,box)
    left,top,right,bottom=round(x*factor),round(y*factor),round((x+w)*factor),round((y+h)*factor)
    if not(0<=left<right<=width and 0<=top<bottom<=resized.shape[0]):
        raise ValueError("Text ROI outside image")
    gray=cv2.cvtColor(resized[top:bottom,left:right],cv2.COLOR_RGB2GRAY)
    yy,xx=np.nonzero(gray<170)
    if not len(xx):return {"display_width":width,"ink_width_px":0,"ink_height_px":0}
    return {"display_width":width,"ink_width_px":int(xx.max()-xx.min()+1),"ink_height_px":int(yy.max()-yy.min()+1),
            "ink_pixel_count":len(xx)}

def focus_track(cap,box,expected):
    """Locate a red focus in the same specified ROI on every decoded frame."""
    x,y,w,h=box
    cap.set(cv2.CAP_PROP_POS_FRAMES,0)
    bounds=[]
    while True:
        ok,bgr=cap.read()
        if not ok:break
        if x<0 or y<0 or w<=0 or h<=0 or x+w>bgr.shape[1] or y+h>bgr.shape[0]:
            raise ValueError("Focus ROI outside frame")
        b,g,r=cv2.split(bgr[y:y+h,x:x+w].astype(np.int16))
        yy,xx=np.nonzero((r>75)&(r-g>50)&(r-b>35))
        bounds.append([int(xx.min()+x),int(yy.min()+y),int(xx.max()+x),int(yy.max()+y)] if len(xx) else None)
    if len(bounds)!=expected:raise ValueError("Focus track did not decode every frame")
    visible=np.asarray([v for v in bounds if v is not None])
    return {"roi_source_px":box,"frames":expected,"present_frames":len(visible),
            "mask":"R > 75, R-G > 50, R-B > 35",
            "min_bounds_xyxy":visible.min(axis=0).tolist() if len(visible) else None,
            "max_bounds_xyxy":visible.max(axis=0).tolist() if len(visible) else None}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("video",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--receipt",type=Path,help="Hash-bound generator QA with authored scene joins")
    p.add_argument("--at",type=float,nargs="+",required=True)
    p.add_argument("--text-box",nargs=6,action="append",default=[],metavar=("NAME","SEC","X","Y","W","H"))
    p.add_argument("--focus-box",nargs=4,type=int,metavar=("X","Y","W","H"))
    args=p.parse_args()
    digest=sha256(args.video.read_bytes()).hexdigest()
    args.out.mkdir(parents=True,exist_ok=True)
    info=video_info(args.video)
    track=build_track(str(args.video),info)
    proposals=[shot.to_dict() for shot in detect_shots(track)]
    probe=cv2.VideoCapture(str(args.video))
    count=int(probe.get(cv2.CAP_PROP_FRAME_COUNT))
    if count!=track.n:
        raise ValueError(f"Decoded track {track.n} vs container frame count {count}")
    rows=(len(args.at)+2)//3
    width=390;height=round(width*info.display_size[1]/info.display_size[0])
    sheet=Image.new("RGB",(3*width,rows*(height+23)),"#f0f0f0")
    pen=ImageDraw.Draw(sheet)
    timestamps=[]
    boxes=[]
    try:
        for index,t in enumerate(args.at):
            rgb,frame=source_frame(probe,t,track.fps,count)
            tile=cv2.resize(rgb,(width,height),interpolation=cv2.INTER_AREA)
            x=(index%3)*width;y=(index//3)*(height+23)
            sheet.paste(Image.fromarray(tile),(x,y))
            pen.text((x+4,y+height+3),f"{frame/track.fps:0.3f} s   |   f{frame}",fill="#333e48")
            timestamps.append({"frame":frame,"time_s":round(frame/track.fps,3)})
        for name,t,*box in args.text_box:
            rgb,frame=source_frame(probe,float(t),track.fps,count)
            boxes.append({"label":name,"frame":frame,"time_s":round(frame/track.fps,3),
                          "roi_source_px":list(map(float,box)),
                          "measurements":[text_measure(rgb,w,box) for w in (info.display_size[0],390)]})
        focus=focus_track(probe,args.focus_box,count) if args.focus_box else None
    finally:
        probe.release()
    decisions=match_receipt(args.receipt,digest,track.fps,count,proposals) if args.receipt else None
    if digest!=sha256(args.video.read_bytes()).hexdigest():
        raise ValueError("The reviewed MP4 changed during the analysis")
    doc={"source_file":args.video.name,"sha256":digest,
         "rea_video":{**provenance(),
                      "api":["rea_video.shots.build_track","rea_video.shots.detect_shots"],"input":"delivered MP4; every frame at source frame rate"},
         "fps":track.fps,"frames":count,"duration_s":round(count/track.fps,6),"frame_size":list(info.display_size),
         "shot_proposals":proposals,"activity_rule":"rea-video track.changed >= 0.005 on native-time 96 px thumbnails; merge gaps <= 0.16 s; at least 2 positive samples; intra-shot motion is included.",
         "activity_windows":activity(track),"inspected_frames":timestamps,
         "ink_rule":"Tightly chosen single text line against white. Resize the entire decoded frame with area filtering. Measure bounding box of pixels with grayscale < 170.",
         "text_boxes":boxes,"red_focus_track":focus}
    if decisions is not None: doc["editorial"]=decisions
    sheet.save(args.out/"frames.png")
    (args.out/"rea.json").write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"{args.video.name}: {count} frames, {len(proposals)} proposed shots, {len(doc['activity_windows'])} activity windows")


if __name__=="__main__":
    main()
