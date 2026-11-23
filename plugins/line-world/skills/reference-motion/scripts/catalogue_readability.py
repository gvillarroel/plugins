# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=10,<13","playwright==1.61.0"]
# ///
"""Decode the exported catalogue, compare with the baseline atlas, and measure visible type at 390 px."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

from PIL import Image, ImageDraw, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

import generate_motion as generator


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def decode(path, indices, width, height):
    values=sorted(set(indices))
    choose="+".join(f"eq(n\\,{i})" for i in values)
    args=["ffmpeg","-v","error","-nostdin","-i",str(path),"-map","0:v:0","-vf",
          f"select='{choose}',scale={width}:{height}:flags=lanczos","-fps_mode","passthrough",
          "-pix_fmt","rgb24","-f","rawvideo","-threads","1","-"]
    raw=subprocess.run(args,capture_output=True,check=True).stdout
    chunk=width*height*3
    if len(raw)!=chunk*len(values): raise ValueError(f"Unexpected frame count in {path}")
    return {frame:Image.frombytes("RGB",(width,height),raw[i*chunk:(i+1)*chunk]) for i,frame in enumerate(values)}


def transition_stats(path, start, duration):
    frames=decode(path,range(max(0,start-1),start+duration+1),96,54)
    stats=[]
    previous=None
    for f,im in frames.items():
        pixels=list(im.get_flattened_data() if hasattr(im,"get_flattened_data") else im.getdata())
        accent=sum(abs(r-158)<20 and abs(g-27)<20 and abs(b-50)<20 for r,g,b in pixels)/len(pixels)
        full=max(ImageStat.Stat(im).stddev)<4
        delta=0 if previous is None else sum(ImageStat.Stat(ImageChops.difference(im,previous)).mean)/3
        stats.append({"frame":f,"mean_step_rgb":round(delta,2),"brand_accent_fraction":round(accent,3),"nearly_solid":full})
        previous=im
    return stats


def sheet(rows, path):
    w=max(sum(im.width for _,im in cells) for _,cells in rows)
    h=sum(max(im.height for _,im in cells)+38 for _,cells in rows)
    out=Image.new("RGB",(w,h),"white")
    draw=ImageDraw.Draw(out)
    y=0
    for name,cells in rows:
        draw.text((5,y+1),name,fill="#333e48")
        x=0
        for label,im in cells:
            out.paste(im,(x,y+17))
            draw.text((x+5,y+im.height+18),label,fill="#333e48")
            x+=im.width
        y+=max(im.height for _,im in cells)+38
    out.save(path,quality=91,subsampling=0)


def compare_export(archive, case, spec, receipt, indices):
    with zipfile.ZipFile(archive) as bundle, tempfile.TemporaryDirectory() as tmp:
        old_spec=json.loads(bundle.read(case.name+"/recipe.json"))
        old_review=json.loads(bundle.read(case.name+"/review.json"))
        if old_spec!=spec or receipt["decoded"]["frames"]!=old_review["decoded"]["frames"]:
            raise ValueError(f"{case.name}: before/after content or frame clock changed")
        old=Path(tmp)/"before.mp4"
        old.write_bytes(bundle.read(case.name+"/example.mp4"))
        if hashlib.sha256(old.read_bytes()).hexdigest()!=old_review["sha256"]:
            raise ValueError(f"{case.name}: baseline checksum mismatch")
        prior=decode(old,indices,390,219)
    current=decode(case/"example.mp4",indices,390,219)
    comparison=[]
    row=[]
    for f in indices:
        difference=ImageChops.difference(prior[f],current[f])
        error=sum(ImageStat.Stat(difference).mean)/3
        comparison.append({"frame":f,"mean_change_rgb":round(error,3)})
        row.extend([(f"Antes {f/spec['fps']:.2f} s",prior[f]),(f"Después {f/spec['fps']:.2f} s",current[f])])
    return {"before_sha256":old_review["sha256"],"same_input_recipe":True,
            "same_frame_count":True,"frames":comparison},row


def type_measurement(page, frame):
    return page.evaluate("""async frame=>{
      const ctx=CanvasRenderingContext2D.prototype,original=ctx.fillText,labels=[];
      ctx.fillText=function(label,x,y,...rest){
        const metrics=this.measureText(label),t=this.getTransform();
        const ink=(metrics.actualBoundingBoxAscent+metrics.actualBoundingBoxDescent)*Math.hypot(t.c,t.d);
        if(String(label).trim())labels.push({text:String(label),ink_px_390:+(ink*390/this.canvas.width).toFixed(2),
          x_390:+(t.transformPoint({x,y}).x*390/this.canvas.width).toFixed(2),
          y_390:+(t.transformPoint({x,y}).y*390/this.canvas.width).toFixed(2)});
        return original.call(this,label,x,y,...rest);
      };
      try {await MotionRecipe.draw(frame);return labels;} finally {ctx.fillText=original;}
    }""",frame)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("catalog",type=Path,help="folder with exports, baseline.json and atlas-baseline.jpg")
    cli.add_argument("--out",type=Path,required=True)
    cli.add_argument("--previous-archive",type=Path,help="optional ZIP of the original recipes, MP4s and review files")
    args=cli.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    baseline=read(args.catalog/"baseline.json")
    atlas=Image.open(args.catalog/"atlas-baseline.jpg").convert("RGB")
    cases=sorted(p for p in (args.catalog/"exports").iterdir() if (p/"example.mp4").exists())
    mobile_rows,transition_rows,changes=[],[],[]
    records={}
    with sync_playwright() as runtime:
        browser=generator.launch(runtime,None)
        try:
            page,defaults,transitions=generator.setup(browser)
            for case in cases:
                family,name=case.name.split("-",1)
                spec=read(case/"recipe.json")
                review=read(case/"review.json")
                mp4=case/"example.mp4"
                with mp4.open("rb") as stream: sha=hashlib.file_digest(stream,"sha256").hexdigest()
                if sha!=review["sha256"]: raise ValueError(f"MP4 checksum mismatch for {case.name}")
                fps=spec["fps"];n=review["decoded"]["frames"]
                base_index=list(baseline["patterns"]).index(name)
                left=(base_index%3)*320;top=(base_index//3)*206
                before=atlas.crop((left,top,left+320,top+180))
                entry={"sha256":sha,"fps":fps,"frames":n,"duration_s":round(n/fps,3),"baseline_cell":base_index,
                       "source_media":spec.get("assets",{}),"reviewed_frames":[]}
                if family=="element":
                    hold=n-round(fps*review["scenes"][0]["hold_seconds"])
                    early=max(0,review["sampledFrames"][1])
                    indices=[early,hold,n-1]
                    seen=decode(mp4,indices,390,round(390*spec["height"]/spec["width"]))
                    generator.load(page,spec,case,defaults,transitions)
                    entry["labels"]=type_measurement(page,n-1)
                    entry["hold_frame"]=hold
                    entry["reviewed_frames"]=indices
                    entry["reading_hold_s"]=review["scenes"][0]["hold_seconds"]
                    entry["hold_rgb_change"]=round(sum(ImageStat.Stat(ImageChops.difference(seen[hold],seen[n-1])).mean)/3,3)
                    mobile=n-1 if review["scenes"][0].get("hold_media",{}).get("video_assets") else hold
                    row=[("Baseline: atlas",before.resize((390,seen[hold].height),Image.Resampling.LANCZOS)),
                         (f"MP4 {early/fps:.2f} s",seen[early]),(f"MP4 {mobile/fps:.2f} s",seen[mobile])]
                    mobile_rows.append((name,row))
                else:
                    cut=review["transitions"]["decisions"][0];start=cut["start_frame"];span=cut["duration_frames"]
                    indices=[start-1,*[start+round((span-1)*p) for p in (.12,.5,.88)],start+span]
                    seen=decode(mp4,indices,256,144)
                    entry["start_frame"]=start;entry["duration_frames"]=span;entry["reviewed_frames"]=indices
                    entry["motion"]=transition_stats(mp4,start,span)
                    row=[("Baseline: atlas",before.resize((256,144),Image.Resampling.LANCZOS))]
                    row.extend((f"MP4 {f/fps:.2f} s",seen[f]) for f in indices)
                    transition_rows.append((name,row))
                records[case.name]=entry
                if args.previous_archive:
                    probes=([early,hold] if family=="element" else [start+span//2,start+span])
                    comparison,row=compare_export(args.previous_archive,case,spec,review,probes)
                    entry["before_after"]=comparison
                    if any(v["mean_change_rgb"]>.05 for v in comparison["frames"]): changes.append((case.name,row))
        finally:
            browser.close()
    for name,rows in [("elementos",mobile_rows),("transiciones",transition_rows),("cambios",changes)]:
        for i in range(0,len(rows),3):
            sheet(rows[i:i+3],out/f"{name}-{i//3+1:02}.jpg")
    data={"baseline_engine":baseline["engine"],"decoded_movies":len(cases),"cases":records}
    (out/"mediciones.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"{len(cases)} películas con fotogramas y medidas a 390 px")


if __name__=="__main__":
    main()
