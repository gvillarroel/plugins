#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3"]
# ///
"""Detect empty or guide-only encoded intervals without confusing white with space."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path
import numpy as np
import cadence_scan
import frame_notes
from caption_tracks import write_atomic

POLICY = {"width": 640, "height": 360, "background": [255, 255, 255],
          "pixelDelta": 18, "minimumInkRatio": .001,
          "minimumSpanX": .05, "minimumSpanY": .05}


def fingerprint(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def measure(rgb, policy=POLICY):
    delta=np.max(np.abs(rgb.astype(np.int16)-np.asarray(policy['background'],dtype=np.int16)),axis=2)
    mask=delta>=policy['pixelDelta'];rows=np.any(mask,axis=1);cols=np.any(mask,axis=0)
    yy=np.flatnonzero(rows);xx=np.flatnonzero(cols)
    ink=float(mask.mean());sx=float((xx[-1]-xx[0]+1)/rgb.shape[1]) if len(xx) else 0.;sy=float((yy[-1]-yy[0]+1)/rgb.shape[0]) if len(yy) else 0.
    uniform=bool(ink>.99 and np.max(np.max(rgb,axis=(0,1)).astype(np.int16)-np.min(rgb,axis=(0,1)).astype(np.int16))<=2)
    insufficient=uniform or ink<policy['minimumInkRatio'] or sx<policy['minimumSpanX'] or sy<policy['minimumSpanY']
    return {'inkRatio':ink,'spanX':sx,'spanY':sy,'insufficient':insufficient}


def scan(video, *, cache=None, video_sha=None, policy=None):
    automatic_size=not policy or not ({'width','height'} & policy.keys())
    policy={**POLICY,**(policy or {})};video=Path(video).resolve();digest=video_sha or fingerprint(video)
    identity=hashlib.sha256(json.dumps({'video':digest,'policy':policy,'script':fingerprint(Path(__file__)),
        'cadence':fingerprint(Path(cadence_scan.__file__)), 'clock':fingerprint(Path(frame_notes.__file__)),
        'automaticSize':automatic_size},sort_keys=True).encode()).hexdigest()
    cache=Path(cache) if cache else None
    if cache and cache.is_file():
        try:
            previous=json.loads(cache.read_text(encoding='utf-8'))
        except (UnicodeError,json.JSONDecodeError):
            previous={}
        if isinstance(previous,dict) and previous.get('scanSha256')==identity and previous.get('resultSha256')==hashlib.sha256(json.dumps(previous.get('result'),sort_keys=True).encode()).hexdigest():
            return {**previous['result'],'reused':True}
    clock=frame_notes.movie_clock(video)
    times=[*clock['pts'], clock['pictureEnd']]
    fps=len(clock['pts'])/(times[-1]-times[0])
    if automatic_size:
        source_width,source_height=clock['width'],clock['height']
        scale=max(policy['width'],policy['height'])/max(source_width,source_height)
        policy.update(width=max(1,round(source_width*scale)),height=max(1,round(source_height*scale)))
    width,height=policy['width'],policy['height'];frame_bytes=width*height*3
    process=subprocess.Popen(['ffmpeg','-v','error','-xerror','-threads','1','-filter_threads','1','-i',str(video),
        '-map','0:v:0','-an','-sn','-vf',f'scale={width}:{height}','-fps_mode','passthrough','-threads','1',
        '-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    count=0;intervals=[];worst=None;low=0
    cadence=cadence_scan.RepeatedStates(fps,presentation_times=times)
    try:
        while True:
            raw=process.stdout.read(frame_bytes)
            if not raw:break
            if len(raw)!=frame_bytes:raise ValueError('Incomplete decoded content frame.')
            if count>=len(clock['pts']):raise ValueError('FFmpeg returned an extra presentation frame.')
            rgb=np.frombuffer(raw,np.uint8).reshape(height,width,3)
            value=measure(rgb,policy)
            cadence.observe(rgb)
            if worst is None or value['inkRatio']<worst['inkRatio']:worst={'frame':count,'seconds':times[count],**value}
            if value['insufficient']:
                if not intervals or intervals[-1]['lastFrame']!=count-1:
                    intervals.append({'firstFrame':count,'lastFrame':count,'start':times[count],'end':times[count+1],'frames':1,'minimumInkRatio':value['inkRatio']})
                else:
                    interval=intervals[-1];interval['lastFrame']=count;interval['end']=times[count+1];interval['frames']+=1;interval['minimumInkRatio']=min(interval['minimumInkRatio'],value['inkRatio'])
                low+=1
            count+=1
        errors=process.stderr.read().decode('utf-8',errors='replace');code=process.wait()
        if code or errors.strip():raise ValueError(errors[-1800:] or 'Encoded content decode failed.')
    finally:
        if process.poll() is None:process.kill();process.wait()
        process.stdout.close();process.stderr.close()
    expected=len(clock['pts'])
    if count!=expected:raise ValueError('Content scan did not cover every encoded frame.')
    result={'ok':count>0 and low==0,'videoSha256':digest,'scanSha256':identity,'frames':count,'fps':fps,'policy':policy,'insufficientFrames':low,'intervals':intervals,'lowestInkFrame':worst,'firstPicture':times[0],'pictureEnd':times[-1],'scope':'Every presented picture on its own timestamp. Measure non-background ink and two-dimensional extent at the reported dimensions. Pair with semantic source anchors.'}
    result['cadence']=cadence.report()
    if cache:
        write_atomic(cache,json.dumps({'scanSha256':identity,'resultSha256':hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest(),'result':result},indent=2)+'\n')
    return {**result,'reused':False}


def source_presence(page, duration, fps):
    """Reject source frames with no semantic anchor before a default render."""
    page.add_script_tag(path=str(Path(__file__).resolve().parent.parent/'assets/runtime/visual-review.js'))
    return page.evaluate('''({duration,fps})=>{const root=document.querySelector('#stage');if(!root)throw Error('A rendered SVG stage is required.');let minimum=1,empty=[];const frames=Math.round(duration*fps);for(let frame=0;frame<frames;frame++){renderAt(frame/fps);const result=LineWorldVisualReview.content(root);minimum=Math.min(minimum,result.visibleAnchors);if(result.empty){const last=empty.at(-1);if(last&&last.lastFrame===frame-1){last.lastFrame=frame;last.end=(frame+1)/fps;last.frames++;}else empty.push({firstFrame:frame,lastFrame:frame,start:frame/fps,end:(frame+1)/fps,frames:1})}}return{ok:!empty.length,frames,minimumVisibleAnchors:minimum,emptyIntervals:empty}}''',{'duration':duration,'fps':fps})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--video',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parent.parent) or args.output.resolve()==args.video.resolve():parser.error('Keep generated content reports outside the skill and separate from the movie.')
    result=scan(args.video,cache=args.output)
    ok=result['ok'] and result['cadence']['ok']
    print(json.dumps({'ok':ok,**{k:result[k] for k in ['frames','insufficientFrames','intervals','cadence','reused']}}))
    return 0 if ok else 2


if __name__=='__main__':raise SystemExit(main())
