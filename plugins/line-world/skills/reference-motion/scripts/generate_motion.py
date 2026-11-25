# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.61.0", "Pillow>=10,<13"]
# ///
"""Generate Line World graphics from JSON and verify them before publishing the output."""
import argparse
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw
from playwright.sync_api import Error as BrowserError, sync_playwright

sys.dont_write_bytecode=True
from motion_recipe import asset_descriptor, compile_recipe, require
from verify_movie import verify_movie

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=("motion.js","diagram-motion.js","systems-motion.js","demo-art.js","presets.js","recipe.js")
MIME={".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".webp":"image/webp"}


def save_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def launch(runtime, channel, *, args=None):
    if channel: return runtime.chromium.launch(channel=channel,args=args)
    try:
        return runtime.chromium.launch(args=args)
    except BrowserError:
        if sys.platform=="win32": return runtime.chromium.launch(channel="msedge",args=args)
        raise


def setup(browser):
    page=browser.new_page()
    page.goto("about:blank")
    for file in SCRIPTS: page.add_script_tag(path=str(ROOT/"assets"/file))
    defaults=page.evaluate("Object.fromEntries(LineWorldMotion.artifacts.map(id=>[id,LineWorldPresets.defaults(id)]))")
    transitions=page.evaluate("LineWorldMotion.transitions")
    return page,defaults,transitions


def example(key,defaults,transitions):
    def scene(k): return {"id":k,"artifact":k,"props":defaults[k]}
    if key in defaults: return {"version":1,"scenes":[scene(key)]}
    if key.startswith("video-"):
        study=json.loads((ROOT/"assets/diagramas-bytebytego.json").read_text(encoding="utf-8"))
        match=next((item for item in study["scenes"] if item["id"]==key),None)
        require(match is not None,"Escena de estudio desconocida: "+key)
        return {**study,"scenes":[match]}
    require(key in transitions,"Patrón desconocido: "+key)
    a,b=scene("editorial-split"),scene("insight-band")
    b["transition"]={"id":key,"reason":"Pasar de la vista del andén a su ubicación en la red."}
    return {"version":1,"scenes":[a,b]}


def pipe_jpeg_frames(command, frames):
    marker=b"--lineworld"
    with subprocess.Popen([*command,"-c:v","mjpeg","-f","mpjpeg","-boundary_tag","lineworld","pipe:1"],
                          stdout=subprocess.PIPE) as process:
        stream=process.stdout
        try:
            while boundary:=stream.readline():
                require(boundary.strip() in (marker,marker+b"--"),"Límite de fotograma JPEG no válido")
                content_type=stream.readline()
                if not content_type:
                    break
                require(content_type.lower().strip()==b"content-type: image/jpeg","Se esperaba un fotograma JPEG")
                key,separator,length=stream.readline().partition(b":")
                require(key.lower()==b"content-length" and separator and length.strip().isdigit(),
                        "Longitud de fotograma JPEG no válida")
                require(stream.readline()==b"\r\n","Cabecera de fotograma JPEG incompleta")
                size=int(length)
                data=stream.read(size)
                require(len(data)==size and stream.readline()==b"\r\n","Fotograma JPEG incompleto")
                frames.append(data)
            require(process.wait()==0,"FFmpeg no pudo decodificar el clip")
        finally:
            if process.poll() is None: process.kill()


def video_frames(path, item, plan, limit, target, *, still=False):
    probe=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries",
                          "stream=duration,width,height,avg_frame_rate:format=duration","-of","json",str(path)],
                         check=True,capture_output=True,text=True)
    metadata=json.loads(probe.stdout)
    require(metadata.get("streams"),f"Falta la pista de imagen en {path.name}")
    stream=metadata["streams"][0]
    duration=float(stream.get("duration") or metadata["format"]["duration"])
    start=item.get("in_s",0)
    end=item.get("out_s",duration)
    require(math.isfinite(duration) and start<end<=duration+1e-4,
            f"{path.name}: se solicita [{start},{end}) fuera de los {duration:.4f} s de la fuente")
    # Only material that a scene can display is decoded. Integer output-frame
    # indices avoid browser seek/keyframe drift and support VFR source footage.
    fps=plan["fps"]
    count=min(limit,max(1,math.ceil((end-start)*fps)))
    filt=f"trim=duration={end-start:.9f},setpts=PTS-STARTPTS"
    if not still:
        filt+=f",fps={fps}:round=up:eof_action=pass"
    # Avoid writing 8K intermediates for a small delivered canvas. A 2× canvas
    # allowance retains detail when a person is cropped into a narrow panel.
    cap=2*max(plan["width"],plan["height"])
    if max(stream["width"],stream["height"])>cap:
        filt+=f",scale='min(iw,{cap})':'min(ih,{cap})':force_original_aspect_ratio=decrease"
    command=["ffmpeg","-v","error","-xerror","-nostdin","-ss",str(start),"-i",str(path),
             "-map","0:v:0","-an","-vf",filt,"-frames:v",str(count),"-q:v","2","-threads","1"]
    if isinstance(target,Path):
        target.mkdir()
        subprocess.run([*command,"-start_number","0",str(target/"%08d.jpg")],check=True)
        decoded=sum(1 for _ in target.glob("*.jpg"))
    else:
        pipe_jpeg_frames(command,target)
        decoded=len(target)
    require(decoded>0,f"El tramo elegido de {path.name} no contiene fotogramas")
    return {"frames":decoded,"in_s":start,"out_s":end,"source_duration_s":duration,"source_fps":stream.get("avg_frame_rate"),
            "source_width":stream["width"],"source_height":stream["height"]}


def release_video_frames(page):
    state=getattr(page,"_line_world_video",None)
    if state is None:
        return
    if state["cache"]: state["cache"].cleanup()
    state.update(cache=None,frames={})


def load(page,spec,directory,defaults,transitions,*,memory_clips=False):
    plan=compile_recipe(spec,defaults,transitions,page.evaluate("LineWorldPresets.mediaTokens"))
    files={}
    if not hasattr(page,"_line_world_video"):
        state={"cache":None,"frames":{}}
        page._line_world_video=state
        def frame_data(key, index):
            source=state["frames"][key]
            index=int(index)
            data=(source/f"{index:08d}.jpg").read_bytes() if isinstance(source,Path) else source[index]
            return "data:image/jpeg;base64,"+base64.b64encode(data).decode("ascii")
        page.expose_function("lineWorldFrameData",frame_data)
        page.on("close",lambda *args: release_video_frames(page))
    state=page._line_world_video
    release_video_frames(page)
    plan["media"]={}
    for index,(key,value) in enumerate(spec.get("assets",{}).items()):
        item=asset_descriptor(value)
        path=directory/item["path"]
        require(path.is_file(),f"Medio local sin resolver: {item['path']}")
        files[key]=dict(item)
        digest=hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda:stream.read(1024*1024),b""): digest.update(block)
        files[key]["sha256"]=digest.hexdigest()
        if item["kind"]=="image":
            mime=MIME[path.suffix.lower()]
            files[key]["url"]=f"data:{mime};base64,"+base64.b64encode(path.read_bytes()).decode("ascii")
        elif item["kind"]=="video-frame":
            frames=[]
            metadata=video_frames(path,{"in_s":item["still_s"]},plan,1,frames,still=True)
            files[key].update(kind="image", source_kind="video-frame", source_duration_s=metadata["source_duration_s"],
                              source_fps=metadata["source_fps"], frame_sha256=hashlib.sha256(frames[0]).hexdigest(),
                              url="data:image/jpeg;base64,"+base64.b64encode(frames[0]).decode("ascii"))
        else:
            limit=max((s["end"]-s["start"] for s in plan["scenes"] if key in s["video_assets"]),default=1)
            if memory_clips:
                source=[]
            else:
                if not state["cache"]: state["cache"]=tempfile.TemporaryDirectory(prefix="line-world-clips-")
                source=Path(state["cache"].name)/str(index)
            files[key].update(video_frames(path,item,plan,limit,source))
            state["frames"][key]=source
        plan["media"][key]={k:v for k,v in files[key].items() if k!="url"}
    page.evaluate("([plan,assets])=>MotionRecipe.load(plan,assets)",[plan,files])
    return plan


def image_at(page,frame,validate=False):
    return base64.b64decode(page.evaluate("args=>MotionRecipe.png(...args)",[frame,validate]))


def audit_plan(page,plan):
    reviewed=[]
    for index,scene in enumerate(plan["scenes"]):
        start=scene["start"]; begin=start+scene["bridge"]; hold=begin+scene["reveal"]
        frames={start,begin,hold,scene["end"]-1}
        for part,span in [(start,scene["bridge"]),(begin,scene["reveal"])]:
            frames.update(part+int(i*max(0,span-1)/8) for i in range(9))
        before=image_at(page,hold)
        require(page.evaluate("i=>MotionRecipe.settled(i)",index),scene["id"]+": el movimiento sigue activo al comenzar la pausa de lectura")
        for f in sorted(frames):
            errors=page.evaluate("([f,h])=>MotionRecipe.audit(f,h)",[f,f>=hold])
            require(not errors,f"{scene['id']} @ {f/plan['fps']:.2f} s: "+", ".join(errors))
        live=scene["video_assets"]
        last=image_at(page,scene["end"]-1)
        if not live:
            require(last==before,scene["id"]+": movimiento durante la pausa de lectura")
        image_at(page,start)
        require(image_at(page,hold)==before,scene["id"]+": resultado distinto al volver al mismo fotograma")
        reviewed.append({"id":scene["id"],"artifact":scene["artifact"],"frames_checked":sorted(frames),
                         "hold_seconds":scene["hold"]/plan["fps"],"reading_frame_sha256":hashlib.sha256(before).hexdigest(),
                         "hold_media":{"labels_settled":True,"video_assets":live,"image_changed":last!=before,
                           "source_clock":[{"asset":k,"first_frame":start,
                               "final_source_frame_at":start+min(scene["end"]-start,plan["media"][k]["frames"])-1}
                               for k in live]},
                         "reading":page.evaluate("i=>MotionRecipe.reading(i)",index)})
    return reviewed


def check_transitions(page, selected=None):
    return page.evaluate("""selected => {
      const result={}, can=document.createElement('canvas');can.width=120;can.height=68;
      const ctx=can.getContext('2d',{willReadFrequently:true});
      const layer=color=>(g,w,h)=>{g.fillStyle=color;g.fillRect(0,0,w,h)};
      for(const id of selected ?? LineWorldMotion.transitions){
        const counts=[];
        for(let i=0;i<=48;i++){
          LineWorldMotion.transition(ctx,id,i/48,layer('#696969'),layer('#333e48'),{mode:'solid'});
          const d=ctx.getImageData(0,0,120,68).data;
          let pixels=0;for(let j=0;j<d.length;j+=4)if(d[j]===51&&d[j+1]===62&&d[j+2]===72)pixels++;
          counts.push(pixels);
        }
        if(counts[0]!==0||counts.at(-1)!==120*68||counts.some((v,i)=>i&&v<counts[i-1]-1))
          throw Error(id+' invierte el avance o pierde un extremo: '+counts.join(','));
        result[id]=counts;
      }
      return result;
    }""",selected)


def proof_sheet(items,path):
    cols=3;tw,th=320,180
    sheet=Image.new("RGB",(cols*tw,((len(items)+cols-1)//cols)*(th+26)),"#ffffff")
    draw=ImageDraw.Draw(sheet)
    for i,(label,raw) in enumerate(items):
        x=(i%cols)*tw;y=(i//cols)*(th+26)
        with Image.open(io.BytesIO(raw)) as im:
            im.thumbnail((tw,th),Image.Resampling.LANCZOS)
            sheet.paste(im,(x+(tw-im.width)//2,y+(th-im.height)//2))
        draw.text((x+6,y+th+4),label,fill="#333e48")
    path.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(path)


def render(page,plan,out):
    out.parent.mkdir(parents=True,exist_ok=True)
    require(out.suffix.lower() in {".png",".mp4"},"Elige un destino .png o .mp4")
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        candidate=Path(tmp)/("render"+out.suffix.lower())
        decoded=None
        if out.suffix.lower()==".png":
            candidate.write_bytes(image_at(page,plan["frames"]-1))
            with Image.open(candidate) as im:
                require(im.size==(plan["width"],plan["height"]),"Dimensiones de salida distintas")
                im.verify()
        else:
            require(shutil.which("ffmpeg") and shutil.which("ffprobe"),"La exportación MP4 necesita ffmpeg y ffprobe en PATH")
            cmd=["ffmpeg","-v","error","-y","-f","image2pipe","-framerate",str(plan["fps"]),"-c:v","png",
                 "-i","pipe:0","-an","-c:v","libx264","-preset","veryfast","-crf","17","-pix_fmt","yuv420p","-movflags","+faststart",str(candidate)]
            with subprocess.Popen(cmd,stdin=subprocess.PIPE) as process:
                try:
                    for scene in plan["scenes"]:
                        hold=scene["start"]+scene["bridge"]+scene["reveal"]
                        for f in range(scene["start"],hold): process.stdin.write(image_at(page,f,True))
                        if scene["video_assets"]:
                            for f in range(hold,scene["end"]): process.stdin.write(image_at(page,f,True))
                        else:
                            still=image_at(page,hold,True)
                            for _ in range(scene["hold"]): process.stdin.write(still)
                    process.stdin.close()
                    require(process.wait()==0,"FFmpeg no pudo completar el archivo")
                finally:
                    if process.poll() is None: process.kill()
            decoded=verify_movie(candidate,plan,lambda f:image_at(page,f))
        candidate.replace(out)
        return decoded


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--browser",choices=["msedge","chrome","chromium"],default=os.getenv("MOTION_BROWSER"))
    commands=cli.add_subparsers(dest="command",required=True)
    from adapt_motion import add_arguments, run as adapt_request
    add_arguments(commands.add_parser("adapt",help="componer a partir de los datos de un brief nuevo"))
    init=commands.add_parser("init",help="crear una receta editable a partir de un patrón")
    init.add_argument("pattern");init.add_argument("recipe",type=Path)
    for name in ["check","render","verify"]:
        cmd=commands.add_parser(name);cmd.add_argument("recipe",type=Path)
        if name in {"render","verify"}:cmd.add_argument("output",type=Path)
        cmd.add_argument("--report",type=Path)
    all_cmd=commands.add_parser("audit-library",help="validar todos los elementos y transiciones de la versión instalada")
    all_cmd.add_argument("report",type=Path);all_cmd.add_argument("--sheet",type=Path)
    args=cli.parse_args()
    if args.command=="adapt":
        try: adapt_request(args)
        except (ValueError,OSError) as e: cli.exit(2,str(e)+"\n")
        return
    with sync_playwright() as runtime:
        browser=launch(runtime,args.browser)
        try:
            page,defaults,transitions=setup(browser)
            if args.command=="init":
                require(not args.recipe.exists(),"La receta de destino ya existe")
                save_json(args.recipe,example(args.pattern,defaults,transitions));print(args.recipe);return
            fingerprints={f:hashlib.sha256((ROOT/"assets"/f).read_bytes()).hexdigest() for f in SCRIPTS}
            if args.command=="audit-library":
                report={"engine":fingerprints,"transitions":check_transitions(page),"patterns":{}}
                catalog=json.loads((ROOT/"references/patterns.json").read_text(encoding="utf-8"))
                require({p["id"] for p in catalog["patterns"]}==set(transitions)|set(defaults),"El índice y el motor difieren")
                previews=[]
                for key in [*transitions,*defaults]:
                    spec=example(key,defaults,transitions)
                    plan=load(page,spec,ROOT,defaults,transitions)
                    report["patterns"][key]=audit_plan(page,plan)
                    last=plan["scenes"][-1]
                    frame=last["start"]+last["bridge"]//2 if key in transitions else last["end"]-1
                    if args.sheet: previews.append((key,image_at(page,frame)))
                if args.sheet:proof_sheet(previews,args.sheet)
                save_json(args.report,report);print(f"{len(report['patterns'])} patrones verificados");return
            spec=json.loads(args.recipe.read_text(encoding="utf-8-sig"))
            plan=load(page,spec,args.recipe.parent,defaults,transitions)
            protected={args.recipe.resolve(),*((args.recipe.parent/asset_descriptor(p)["path"]).resolve() for p in spec.get("assets",{}).values())}
            if args.command in {"render","verify"}:
                require(args.output.resolve() not in protected,"El destino coincide con un archivo de entrada")
                protected.add(args.output.resolve())
            report_path=args.report or (args.output.with_suffix(".qa.json") if args.command=="render" else None)
            if report_path:
                require(report_path.resolve() not in protected,"El informe requiere su propio archivo")
            report={"engine":fingerprints,"recipe_sha256":hashlib.sha256(args.recipe.read_bytes()).hexdigest(),"fps":plan["fps"],
                    "frames":plan["frames"],"duration_s":plan["frames"]/plan["fps"],"scenes":audit_plan(page,plan)}
            report["transition_audit"]=plan["transition_audit"]
            report["media"]=plan["media"]
            used=sorted({s["transition"] for s in plan["scenes"][1:] if s["transition"]!="cut"})
            report["transition_progress_samples"]={k:len(v) for k,v in check_transitions(page,used).items()}
            if args.command=="render":
                report["decoded"]=render(page,plan,args.output)
            if args.command=="verify":
                require(args.output.suffix.lower()==".mp4" and args.output.is_file(),"verify requiere un MP4 existente")
                report["decoded"]=verify_movie(args.output,plan,lambda f:image_at(page,f))
            if args.command in {"render","verify"}:
                report["output"]=str(args.output);report["output_sha256"]=hashlib.sha256(args.output.read_bytes()).hexdigest()
            if report_path:save_json(report_path,report)
            scene_count=len(plan["scenes"])
            print(f"{scene_count} {'escena' if scene_count==1 else 'escenas'} · {plan['frames']} fotogramas · {report['duration_s']:.2f} s")
        finally:browser.close()


if __name__=="__main__":
    try:main()
    except (ValueError, OSError, BrowserError, subprocess.SubprocessError) as e:
        sys.exit(str(e))
