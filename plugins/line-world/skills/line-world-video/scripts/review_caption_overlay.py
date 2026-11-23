"""Measure how default browser subtitles cover designated regions of an encoded video."""
import argparse
from bisect import bisect_right
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image
from playwright.sync_api import Error as BrowserError, TimeoutError as BrowserTimeout, sync_playwright

from caption_tracks import extract, write_atomic
from frame_notes import movie_clock


def regions_from(data):
    if not isinstance(data, list):
        raise ValueError("Supply a list of regions with an id and normalized [x, y, width, height].")
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError("A reading region needs a nonempty id.")
        box = item.get("box")
        if not isinstance(box, list) or len(box) != 4 or any(
                type(n) not in (int, float) or not math.isfinite(n) for n in box):
            raise ValueError("A region box needs four finite coordinates.")
        x, y, w, h = box
        if min(x,y) < 0 or min(w,h) <= 0 or x+w > 1.00000001 or y+h > 1.00000001:
            raise ValueError("The entire region must lie inside the picture.")
        start, end = item.get("startMs",0), item.get("endMs")
        if type(start) is not int or start < 0 or end is not None and (type(end) is not int or end <= start):
            raise ValueError("Use increasing, nonnegative integer milliseconds for a reading interval.")
    return data


def sample_times(cues, regions, step_ms=None):
    """Sample each interval of constant cue and region membership."""
    if step_ms is not None and (type(step_ms) is not int or step_ms < 1):
        raise ValueError("The maximum sample spacing must be a positive integer in milliseconds.")
    changes = {cue[key] for cue in cues for key in ("startMs","endMs")}
    changes.update(region[key] for region in regions for key in ("startMs","endMs")
                   if region.get(key) is not None)
    times = sorted(changes)
    for start, end in zip(times,times[1:]):
        active = [i for i,cue in enumerate(cues) if cue["startMs"] <= start < cue["endMs"]]
        if not active:
            continue
        count = math.ceil((end-start)/step_ms) if step_ms else 1
        for i in range(count):
            yield start+(i+.5)*(end-start)/count, active


def screenshot_rgb(player):
    with Image.open(BytesIO(player.screenshot(animations="allow"))) as im:
        return np.array(im.convert("RGB"), dtype=np.uint8)


def footprint(before, after, regions):
    if before.shape != after.shape or before.ndim != 3 or before.shape[2] != 3:
        raise ValueError("Expected two RGB captures of the same frame and player size.")
    height,width=before.shape[:2]
    changed=np.zeros((height,width),dtype=bool)
    for channel in range(3):
        difference=before[:,:,channel].astype(np.int16)
        np.subtract(difference,after[:,:,channel],out=difference)
        np.abs(difference,out=difference)
        changed |= difference>12
    xs=np.flatnonzero(changed.any(axis=0))
    ys=np.flatnonzero(changed.any(axis=1))
    if not len(xs):
        raise ValueError("The active subtitle produced no visible difference in this player.")
    result=[]
    for region in regions:
        x,y,w,h=region["box"]
        left,top=math.floor(x*width),math.floor(y*height)
        right,bottom=min(width,math.ceil((x+w)*width)),min(height,math.ceil((y+h)*height))
        mask=changed[top:bottom,left:right]
        touched=int(mask.sum())
        if touched:
            dark=np.max(before[top:bottom,left:right],axis=2)<195
            result.append({"id":region["id"],"changedPixels":touched,"regionPixels":int(mask.size),
                           "changedDarkPixels":int((dark&mask).sum()),"originalDarkPixels":int(dark.sum())})
    return {"subtitleBox":[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)],
            "changedPixels":int(changed.sum()),"intersections":result}


PLAYER = """<!doctype html><meta charset=utf-8><style>
html,body{margin:0;overflow:hidden;background:white}video{display:block;width:100vw;height:auto}
</style><video muted playsinline preload=auto></video>"""
SETUP = """({url,cues})=>{
  const v=document.querySelector('video');
  v.src=url;
  const track=v.addTextTrack('subtitles','Extracted captions');
  track.mode='hidden';
  for(const cue of cues)track.addCue(new VTTCue(cue.startMs/1000,cue.endMs/1000,cue.text));
  let request=0;
  window.lastCaptionPaint=0;
  window.paintMode=mode=>{
    track.mode=mode;
    const id=++request;
    requestAnimationFrame(()=>requestAnimationFrame(()=>{window.lastCaptionPaint=id;}));
    return id;
  };
  window.seekSample=time=>{
    if(Math.abs(v.currentTime-time)>1e-7)v.currentTime=time;
  };
  window.captionState=()=>({seeking:v.seeking,time:v.currentTime,
    words:[...track.activeCues].map(c=>c.text).sort()});
  v.addEventListener('loadedmetadata',()=>{
    for(const t of v.textTracks)if(t!==track)t.mode='disabled';
  },{once:true});
}"""


def wait_for_paint(page, mode, ms):
    request=page.evaluate("mode=>paintMode(mode)",mode)
    try:
        page.wait_for_function("id=>lastCaptionPaint===id",arg=request,polling=30,timeout=10000)
    except BrowserTimeout as exc:
        raise ValueError(f"Chromium did not paint {mode} subtitles at {ms:.3f} ms.") from exc


def inspect(page, movie, cues, clock, regions, step_ms):
    page.evaluate(SETUP,{"url":movie.resolve().as_uri(),"cues":cues})
    page.wait_for_function("document.querySelector('video').readyState>=2",timeout=20000)
    player=page.locator("video")
    rows=[]
    for ms,active in sample_times(cues,regions,step_ms):
        if ms/1000 > clock["duration"]:
            raise ValueError("A subtitle midpoint falls past the end of the movie.")
        wait_for_paint(page,"hidden",ms)
        page.evaluate("t=>seekSample(t)",ms/1000)
        expected={"time":ms/1000,"words":sorted(cues[i]["text"] for i in active)}
        try:
            page.wait_for_function("""expected=>{
                const actual=captionState();
                return !actual.seeking && Math.abs(actual.time-expected.time)<.001 &&
                       JSON.stringify(actual.words)===JSON.stringify(expected.words);
            }""",arg=expected,polling=30,timeout=10000)
        except BrowserTimeout as exc:
            observed=page.evaluate("()=>captionState()")
            raise ValueError(f"The video or subtitles did not reach {ms:.3f} ms. Observed {observed}.") from exc
        bare=screenshot_rgb(player)
        wait_for_paint(page,"showing",ms)
        captioned=screenshot_rgb(player)
        current=[r for r in regions if r.get("startMs",0)<=ms and (r.get("endMs") is None or ms<r["endMs"])]
        row=footprint(bare,captioned,current)
        frame=bisect_right(clock["pts"],ms/1000)-1
        rows.append({"timeMs":round(ms,3),"frame":frame if frame>=0 else None,
                     "cues":[i+1 for i in active],"activeRegions":[r["id"] for r in current],**row})
    return rows


def display_size(source, width=None):
    if width is None:
        return dict(source)
    if type(width) is not int or width < 1:
        raise ValueError("The display width must be a positive integer in CSS pixels.")
    return {"width":width,"height":math.ceil(width*source["height"]/source["width"])}


def review(movie,regions,language=None,browser_name=None,step_ms=None,display_width=None):
    regions=regions_from(regions)
    captions=extract(movie,language)
    if not captions or not captions["cues"]:
        raise ValueError("The video needs a timed text subtitle track.")
    clock=movie_clock(movie)
    if any(region.get("startMs",0)>=clock["duration"]*1000 for region in regions):
        raise ValueError("A reading region starts past the end of the movie.")
    size={k:clock[k] for k in ("width","height")}
    viewport=display_size(size,display_width)
    with TemporaryDirectory() as directory, sync_playwright() as runtime:
        page_file=Path(directory)/"subtitles.html"
        page_file.write_text(PLAYER,encoding="utf-8")
        try:
            browser=runtime.chromium.launch(channel=browser_name)
        except BrowserError as error:
            if browser_name or sys.platform!="win32" or "Executable doesn't exist" not in str(error):
                raise
            browser=runtime.chromium.launch(channel="msedge")
        try:
            page=browser.new_page(viewport=viewport,device_scale_factor=1)
            page.goto(page_file.as_uri())
            rows=inspect(page,movie,captions["cues"],clock,regions,step_ms)
            version=browser.version
        finally:
            browser.close()
    with movie.open("rb") as source:
        checksum=hashlib.file_digest(source,"sha256").hexdigest()
    return {"videoSha256":checksum,"size":size,"displaySizeCssPx":viewport,"browserVersion":version,
            "renderer":"Chromium default WebVTT, with text and timestamps extracted from the delivered track",
            "language":captions["language"],"cues":len(captions["cues"]),"maxStepMs":step_ms,
            "regions":len(regions),"samples":rows,
            "samplesWithActiveRegions":sum(bool(r["activeRegions"]) for r in rows),
            "samplesWithIntersections":sum(bool(r["intersections"]) for r in rows) if regions else None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video",type=Path)
    parser.add_argument("--regions",type=Path,help="JSON list of normalized reading regions with optional startMs and endMs")
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--language",help="Three-letter language tag in the MP4")
    parser.add_argument("--browser",choices=("msedge","chrome","chromium"))
    parser.add_argument("--display-width",type=int,help="Actual player width in CSS pixels. Height follows the video aspect ratio.")
    parser.add_argument("--step-ms",type=int,help="Maximum spacing inside a continuous caption and region interval")
    parser.add_argument("--require-clear",action="store_true",help="Return an error if a subtitle covers any declared region")
    args=parser.parse_args()
    if args.report.resolve() in {args.video.resolve(),args.regions.resolve() if args.regions else None}:
        parser.error("Choose a report path distinct from the input files.")
    regions=json.loads(args.regions.read_text(encoding="utf-8-sig")) if args.regions else []
    if args.require_clear and not regions:
        parser.error("--require-clear needs at least one reading region.")
    result=review(args.video,regions,args.language,args.browser,args.step_ms,args.display_width)
    write_atomic(args.report,json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"cues":result["cues"],"samples":len(result["samples"]),
                      "samplesWithIntersections":result["samplesWithIntersections"]}))
    return int(args.require_clear and result["samplesWithIntersections"]>0)


if __name__=="__main__":
    try:
        sys.exit(main())
    except (OSError,ValueError,BrowserError) as exc:
        raise SystemExit(str(exc)) from exc
