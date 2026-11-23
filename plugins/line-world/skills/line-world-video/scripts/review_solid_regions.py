# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3"]
# ///
"""Check the actual decoded RGB interiors of specified solid surfaces against the Line World palette."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from caption_tracks import write_atomic


PALETTE=Path(__file__).resolve().parents[1]/"assets/palettes/video-colors.json"


def regions(plan, width, height, frames):
    palettes=json.loads(PALETTE.read_text(encoding="utf-8"))["colorsets"]
    if not isinstance(plan,dict) or plan.get("colorset","colorset1") not in palettes:
        raise ValueError("Choose a known Line World colorset for the solid regions.")
    palette=palettes[plan.get("colorset","colorset1")]
    rows=plan.get("regions")
    if not isinstance(rows,list) or not rows:
        raise ValueError("Define the interior rectangles to check on the delivered picture.")
    found=set()
    result=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get("id"),str) or not row["id"].strip() or row["id"] in found:
            raise ValueError("Give each solid region a unique ID.")
        name=row["id"]
        found.add(name)
        if ("role" in row)==("color" in row):
            raise ValueError(f"{name}: choose a palette role or an exact palette color.")
        color=palette["roles"].get(row.get("role")) if "role" in row else row["color"]
        if not isinstance(color,str) or color.lower() not in palette["allowed"]:
            raise ValueError(f"{name}: the requested color does not belong to the selected palette.")
        start,end=row.get("start",0),row.get("end",frames)
        if type(start) is not int or type(end) is not int or not 0<=start<end<=frames:
            raise ValueError(f"{name}: use a positive half-open range of movie frame numbers.")
        box=row.get("box")
        if not isinstance(box,list) or len(box)!=4 or any(type(n) not in (int,float) or not math.isfinite(n) for n in box):
            raise ValueError(f"{name}: supply a normalized interior rectangle [x,y,width,height].")
        x,y,w,h=box
        if min(x,y)<0 or min(w,h)<=0 or x+w>1.000001 or y+h>1.000001:
            raise ValueError(f"{name}: the interior extends beyond the delivered picture.")
        left,top=math.ceil(x*width-1e-8),math.ceil(y*height-1e-8)
        right,bottom=math.floor((x+w)*width+1e-8),math.floor((y+h)*height+1e-8)
        if min(right-left,bottom-top)<3:
            raise ValueError(f"{name}: choose at least three native pixels inside each edge.")
        result.append({"id":name,"color":color.lower(),"pixels":[left,top,right-left,bottom-top],"start":start,"end":end})
    return result


def inspect_region(video, region):
    x,y,w,h=region["pixels"]
    sw,sh=min(64,w),min(64,h)
    rgb=bytes.fromhex(region["color"][1:])
    expected=np.frombuffer(rgb,np.uint8).astype(np.int16)
    start,end=region["start"],region["end"]
    filters=(f"trim=start_frame={start}:end_frame={end},format=rgb24,"
             f"crop={w}:{h}:{x}:{y}:exact=1,scale={sw}:{sh}:flags=neighbor")
    command=["ffmpeg","-v","error","-xerror","-nostdin","-threads","2","-filter_threads","1","-i",str(video),
             "-map","0:v:0","-vf",filters,"-fps_mode","passthrough","-pix_fmt","rgb24","-threads","1","-f","rawvideo","pipe:1"]
    result={**region,"sampleGrid":[sw,sh],"framesChecked":0,"maxP95Error":0,"maxChannelSpread":0,
            "failureIntervals":[],"worstFrame":start}
    with subprocess.Popen(command,stdout=subprocess.PIPE) as proc:
        try:
            for frame in range(start,end):
                raw=proc.stdout.read(sw*sh*3)
                if len(raw)!=sw*sh*3:
                    raise ValueError(f"{region['id']}: missing decoded frame {frame}.")
                pixels=np.frombuffer(raw,np.uint8).reshape(-1,3).astype(np.int16)
                error=np.max(np.abs(pixels-expected),axis=1)
                p95=int(np.quantile(error,.95,method="higher"))
                low,high=np.quantile(pixels,[.05,.95],axis=0,method="nearest")
                spread=int(np.max(high-low))
                if max(p95,spread)>max(result["maxP95Error"],result["maxChannelSpread"]):
                    result["worstFrame"]=frame
                result["maxP95Error"]=max(p95,result["maxP95Error"])
                result["maxChannelSpread"]=max(spread,result["maxChannelSpread"])
                result["framesChecked"]+=1
                if p95>8 or spread>8:
                    intervals=result["failureIntervals"]
                    if intervals and intervals[-1]["end"]==frame:
                        intervals[-1]["end"]=frame+1
                    else:
                        intervals.append({"start":frame,"end":frame+1})
            if proc.stdout.read(1) or proc.wait():
                raise ValueError(f"{region['id']}: FFmpeg did not finish the selected frame range.")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    result["ok"]=not result["failureIntervals"]
    return result


def inspect(video, plan, known_size=None):
    if known_size is None:
        data=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-count_frames",
            "-show_entries","stream=width,height,nb_read_frames","-of","json",str(video)]))
        stream=data["streams"][0]
        known_size=stream["width"],stream["height"],int(stream["nb_read_frames"])
    checked=[inspect_region(video,r) for r in regions(plan,*known_size)]
    return {"ok":all(row["ok"] for row in checked),"colorset":plan.get("colorset","colorset1"),"regions":checked,
            "channelTolerance":8,"scope":"Native RGB interior samples, up to 64 × 64 per rectangle on every selected frame. "
            "Checks palette error at the 95th percentile and channel spread between the 5th and 95th percentiles."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    if args.report.resolve() in {args.video.resolve(),args.plan.resolve()}:
        parser.error("Write the report separately from its inputs.")
    try:
        report=inspect(args.video,json.loads(args.plan.read_text(encoding="utf-8-sig")))
    except (ValueError,OSError,KeyError,IndexError,subprocess.SubprocessError) as exc:
        report={"ok":False,"error":str(exc)}
    write_atomic(args.report,json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"ok":report["ok"],"report":str(args.report),"error":report.get("error")}))
    return 0 if report["ok"] else 2


if __name__=="__main__":
    sys.exit(main())
