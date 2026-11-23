# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.61.0", "Pillow>=10,<13"]
# ///
"""Exercise the installed motion catalogue on actual source media and encoded MP4s."""
import argparse
import copy
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

import generate_motion as generator


ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"assets/review-media.json"
RECEIPT_VERSION=1


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def write_json(path, document):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,delete=False) as f:
        json.dump(document,f,indent=2,ensure_ascii=False)
        f.write("\n")
        temp=Path(f.name)
    try:
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def fixtures(directory,download):
    metadata=json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name,record in metadata.items():
        path=directory/name
        if path.is_file() and digest(path)==record["sha256"]:
            continue
        if path.exists():
            raise ValueError(f"Source differs from the published fixture: {path}")
        if not download:
            raise ValueError(f"Missing {name}. Run fetch-media before reviewing the catalogue.")
        directory.mkdir(parents=True,exist_ok=True)
        request=Request(record["download"],headers={"User-Agent":"LineWorld-Catalogue-QA"})
        with tempfile.TemporaryDirectory(dir=directory) as d:
            staged=Path(d)/name
            with urlopen(request,timeout=35) as source,staged.open("wb") as out:
                while chunk:=source.read(128*1024):
                    out.write(chunk)
            if digest(staged)!=record["sha256"]:
                raise ValueError(f"Upstream media changed: {name}. Review the source before updating its digest.")
            os.replace(staged,path)
    return metadata


def scene(kind,defaults):
    p=copy.deepcopy(defaults[kind])
    collins_face=[.346,.129,.1875,.1875]
    # The stock gallery supplies original artwork; replace its stand-ins where an
    # identifiable individual, a real still or real camera footage is called for.
    overrides={
        "speaker-id":{"background":"collins","title":"Eileen Collins","detail":"Astronauta"},
        "question-card":{"background":"coffee","title":"¿Dónde está la taza?"},
        "caption-overlay":{"media":"garden","title":"Flores en movimiento"},
        "editorial-split":{"media":"coffee","title":"Café","detail":"Fotografía"},
        "slide-pip":{"media":"collins","presenter":"Eileen Collins","faceBox":collins_face},
        "insight-band":{"media":"garden","kicker":"","title":"Flores","detail":"Se abre la corola"},
        "orbital-caption":{"background":"coffee","title":"Asa","x":.224,"y":.70,"anchor":[.369,.718],"delay":.72},
        "guest-grid":{"guests":[{"media":"collins","name":"Eileen Collins","faceBox":collins_face},
                                {"media":"johnson","name":"Katherine Johnson","faceBox":[.229,.203,.511,.338]}]},
        "circle-window":{"media":"garden","title":"Jardín"},
    }
    p.update(overrides.get(kind,{}))
    return {"id":kind,"artifact":kind,"props":p}


def make_recipe(typ,name,defaults,folder,destination=None):
    required={
        "collins":{"path":"portrait-collins.png","focal":[.44,.25],"fit":"cover"},
        "johnson":{"path":"portrait-johnson.jpg","focal":[.50,.36],"fit":"cover"},
        "coffee":{"path":"coffee.png","focal":[.47,.53],"fit":"cover"},
        "garden":{"path":"garden.mp4","in_s":.25,"out_s":4.75,"fit":"cover"},
    }
    if typ=="element":
        rows=[scene(name,defaults)]
    else:
        kind=destination or "caption-overlay"
        outgoing="speaker-id" if kind!="speaker-id" else "editorial-split"
        rows=[scene(outgoing,defaults),scene(kind,defaults)]
        rows[1]["transition"]={"id":name,"reason":"Comparar el encuadre de salida con la entrada del siguiente elemento."}
    def tokens(item):
        if isinstance(item,list):
            for v in item: yield from tokens(v)
        if isinstance(item,dict):
            for k,v in item.items():
                if k in ("media","slide","mark","background") and isinstance(v,str):
                    yield v
                else:
                    yield from tokens(v)
    used=set(tokens(rows)) & set(required)
    assets={key:{**required[key],"path":str(folder/required[key]["path"])} for key in sorted(used)}
    return {"version":1,"width":640,"height":360,"fps":24,"assets":assets,"scenes":rows}


STRESS = {
    "12-landscape-iris-clip": (12, 640, 360, "iris-fill", "caption-overlay", 1.0,
        "Iris mínimo desde retrato; el texto espera al cambio y deja ver el clip.", True),
    "12-portrait-push-photo": (12, 360, 640, "push-down", "guest-grid", 1.0,
        "Cambio vertical mínimo hacia dos retratos del mismo tamaño facial.", False),
    "24-landscape-cut-data": (24, 640, 360, "cut", "data-chart", None,
        "Corte de un fotograma con categoría, valor y ventana de foco fijos.", False),
    "24-portrait-band-clip": (24, 360, 640, "band-pass", "insight-band", None,
        "Franja móvil con lectura y metraje continuo en 9:16.", True),
    "30-portrait-shutter-data": (30, 360, 640, "shutter-close", "data-chart", 1.0,
        "Cierre mínimo desde foto; cuatro categorías y el foco se leen tras el cambio.", True),
    "30-landscape-push-photo": (30, 640, 360, "push-left", "editorial-split", None,
        "Reparto del cuadro entre texto y fotografía real con FPS de entrega.", False),
    "60-landscape-dissolve-clip": (60, 640, 360, "dissolve", "insight-band", 1.0,
        "Interpolación densa a 60 fps de un clip nativo a 29,97 fps.", True),
    "60-portrait-cut-diagram": (60, 360, 640, "cut", "concept-diagram", None,
        "Corte de un fotograma y revelado sucesivo de enlaces y nodos.", False),
}


PORTRAIT_EXAMPLES = {
    "join-cut--question-card",
    "join-cut--dashboard-stack",
    "join-cut--numbered-step",
    "join-cut--slide-pip",
    "join-cut--chart-focus",
    "join-cut--circle-window",
    "join-dissolve--guest-grid",
    "join-tint-bridge--editorial-split",
    "join-iris-fill--caption-overlay",
    "join-iris-close--orbital-caption",
    "join-shutter-close--data-chart",
    "join-shutter-close--speaker-id",
    "join-step-blocks--icon-card",
    "join-band-pass--insight-band",
    "join-push-down--disc-endcard",
    "join-push-left--chart-ring",
}


def portrait_recipe(spec):
    width,height=390,844
    spec.update(width=width,height=height)
    scene=spec["scenes"][-1]
    props=scene["props"]
    if scene["artifact"]=="chart-focus":
        props.update(box=[.538,.398,.124,.402],padding=.014)
    if scene["artifact"]=="orbital-caption":
        # The coffee fixture and the original point were inspected at 640 × 360.
        # Project the same feature of the 600 × 400 photo after the portrait crop.
        fx,fy=spec["assets"]["coffee"]["focal"]
        source=(221.4,285.575)
        scale=max(width/600,height/400)
        x=min(0,max(width-600*scale,width/2-fx*600*scale))
        y=min(0,max(height-400*scale,height/2-fy*400*scale))
        anchor=[(x+source[0]*scale)/width,(y+source[1]*scale)/height]
        props.update(anchor=anchor,x=anchor[0]+.25,y=anchor[1]-.015)


def production_cases(suite, defaults, transitions, folder):
    if suite=="stress":
        for case,(fps,w,h,transition,destination,seconds,purpose,keep) in STRESS.items():
            spec=make_recipe("join",transition,defaults,folder,destination)
            spec.update(fps=fps,width=w,height=h)
            if seconds is not None:
                spec["scenes"][-1]["transition"]["seconds"]=seconds
            spec["scenes"][-1]["transition"]["reason"]=purpose
            yield case,spec,keep
        return
    cases=([("join",t,e) for t in transitions for e in defaults] if suite in {"matrix","portrait"} else
           [("element",n,None) for n in defaults]+[("transition",n,None) for n in transitions])
    for typ,name,destination in cases:
        case=typ+"-"+name+("--"+destination if destination else "")
        spec=make_recipe(typ,name,defaults,folder,destination)
        keep=True
        if suite=="portrait":
            portrait_recipe(spec)
            keep=case in PORTRAIT_EXAMPLES
        yield case,spec,keep


def moments(plan):
    last=plan["scenes"][-1]
    start,reveal=last["start"],last["bridge"]+last["reveal"]
    if len(plan["scenes"])>1:
        return [max(0,start-1),start+last["bridge"]//2,start+reveal,last["end"]-1]
    return [start,start+max(0,reveal//2),start+reveal,last["end"]-1]


def sample_sheet(movie, times, target, fps, size):
    w,h=size
    scale=min(320/w,320/h)
    tw,th=round(w*scale),round(h*scale)
    sheet=Image.new("RGB",(len(times)*tw,th+27),"white")
    draw=ImageDraw.Draw(sheet)
    for i,frame in enumerate(times):
        raw=subprocess.check_output(["ffmpeg","-v","error","-ss",f"{frame/fps:.8f}","-i",str(movie),
            "-map","0:v:0","-frames:v","1","-vf",f"scale={tw}:{th}:flags=area","-f","image2pipe","-c:v","png","pipe:1"])
        with Image.open(io.BytesIO(raw)) as tile:
            sheet.paste(tile,(i*tw,0))
        draw.text((i*tw+6,th+4),f"f{frame}  {frame/fps:.2f}s",fill="#333e48")
    sheet.save(target,quality=92)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError):
        return {}


def matches_file(path, sha):
    return bool(sha) and path.is_file() and digest(path)==sha


def link_or_copy(source, target):
    with tempfile.TemporaryDirectory(prefix=".link-",dir=target.parent) as folder:
        staged=Path(folder)/target.name
        try:
            os.link(source,staged)
            method="hardlink"
        except OSError:
            shutil.copyfile(source,staged)
            method="copy"
        staged.replace(target)
    return method


def stage_assets(spec, directory, metadata):
    for asset in spec["assets"].values():
        source=Path(asset["path"])
        local=directory/"media"/source.name
        local.parent.mkdir(parents=True,exist_ok=True)
        if local.exists() and not matches_file(local,metadata[source.name]["sha256"]):
            raise ValueError(f"Case contains a modified source asset: {local}")
        if not local.exists():
            link_or_copy(source,local)
        asset["path"]="media/"+source.name


def retrospectively_verify(page, base, spec, plan, reviewed, sources):
    rejected=[]
    stages=[scene["reading_frame_sha256"] for scene in reviewed]
    attempted=set()
    for source in sources:
        candidate=source/base.name
        old=read_json(candidate/"review.json")
        sha=old.get("sha256")
        if not sha or sha in attempted or read_json(candidate/"recipe.json")!=spec:
            continue
        old_stages=[scene.get("reading_frame_sha256") for scene in old.get("scenes",[])]
        if old_stages!=stages:
            continue
        movie=candidate/"example.mp4"
        if not matches_file(movie,sha):
            continue
        attempted.add(sha)
        try:
            decoded=generator.verify_movie(movie,plan,lambda index:generator.image_at(page,index))
        except (ValueError,subprocess.CalledProcessError) as error:
            rejected.append({"source":str(candidate),"sha256":sha,"reason":str(error)})
            continue
        if matches_file(movie,sha):
            return movie,sha,decoded,rejected
    return None,None,None,rejected


def run_case(page,defaults,transitions,case,spec,out,engine,metadata,keep,sheet_needed,sources,verify_only):
    base=out/case
    base.mkdir(parents=True,exist_ok=True)
    report_path=base/"review.json"
    movie,sheet=base/"example.mp4",base/"frames.jpg"
    with tempfile.TemporaryDirectory(prefix=".case-",dir=out) as tmp:
        stage_assets(spec,base,metadata)
        inputs={"engine":engine,"spec":spec}
        cache_key=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
        old=read_json(report_path)
        if (old.get("inputs")==cache_key and read_json(base/"recipe.json")==spec and old.get("movie_retained")==keep
                and bool(old.get("sheet_sha256"))==sheet_needed
                and (not keep or matches_file(movie,old.get("sha256")))
                and (not sheet_needed or matches_file(sheet,old.get("sheet_sha256")))):
            return old,"receipt"
        write_json(base/"recipe.json",spec)
        plan=generator.load(page,spec,base,defaults,transitions,memory_clips=engine["clip_cache"]=="memory")
        reviewed=generator.audit_plan(page,plan)
        if keep and sources:
            precedent,sha,decoded,rejected=retrospectively_verify(page,base,spec,plan,reviewed,sources)
        else:
            precedent,sha,decoded,rejected=None,None,None,[]
        retained=movie if keep else Path(tmp)/"example.mp4"
        if precedent:
            method=link_or_copy(precedent,retained)
            if not matches_file(retained,sha):
                raise ValueError(f"Source changed between validation and retention: {precedent}")
            proof={"method":method,"source":str(precedent),"compared_every_frame":True}
        elif verify_only:
            return None,"needs-render"
        else:
            decoded=generator.render(page,plan,retained)
            proof={"method":"fresh-render","compared_every_frame":True}
        sampled=moments(plan)
        if sheet_needed:
            sample_sheet(retained,sampled,sheet,plan["fps"],(plan["width"],plan["height"]))
        result={"case":case,"inputs":cache_key,"sha256":digest(retained),"movie_retained":keep,
                "sheet_sha256":digest(sheet) if sheet_needed else None,"verification":proof,
                "fps":plan["fps"],"size":[plan["width"],plan["height"]],"sourceMedia":plan["media"],
                "scenes":reviewed,"transitions":plan["transition_audit"],"decoded":decoded,
                "sampledFrames":sampled,"rejectedCandidates":rejected}
    write_json(report_path,result)
    return result,proof["method"]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=["fetch-media","review"])
    p.add_argument("--media-dir",type=Path,required=True)
    p.add_argument("--out",type=Path)
    p.add_argument("--browser",choices=["msedge","chrome","chromium"])
    p.add_argument("--suite",choices=["catalogue","matrix","portrait","stress"],default="catalogue")
    p.add_argument("--only",action="append",help="Run a named case. Repeat to review several cases.")
    p.add_argument("--reuse-from",type=Path,action="append",default=[],
                   help="Revalidate an existing recipe and MP4 against the present engine before linking.")
    p.add_argument("--verify-only",action="store_true",help="Record pending cases without encoding a new movie.")
    p.add_argument("--compact",action="store_true",
                   help="Create sheets for --keep-sheet cases and the retained stress or portrait exemplars. "
                        "Existing sheets are preserved.")
    p.add_argument("--keep-sheet",action="append",default=[],help="Retain a named contact sheet in compact mode.")
    p.add_argument("--reserve-mib",type=int,default=16,help="Suspend the run before free space drops below this threshold.")
    args=p.parse_args()
    directory=args.media_dir.resolve()
    metadata=fixtures(directory,args.command=="fetch-media")
    if args.command=="fetch-media":
        print(f"{len(metadata)} source assets verified")
        return
    if not args.out: p.error("review requires --out")
    out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    if args.reserve_mib<0: p.error("--reserve-mib must be nonnegative")
    sources=[path.resolve() for path in args.reuse_from if path.resolve()!=out]
    if args.verify_only and not sources: p.error("--verify-only requires a --reuse-from directory distinct from --out")
    if any(not source.is_dir() for source in sources): p.error("Every --reuse-from path must be an existing directory")
    engine_files=[*(ROOT/"assets"/name for name in generator.SCRIPTS),
                  *(ROOT/"scripts"/name for name in ("generate_motion.py","motion_recipe.py","verify_movie.py")),MANIFEST]
    fingerprint={path.relative_to(ROOT).as_posix():digest(path) for path in engine_files}
    runner_path=Path(__file__).resolve()
    runner={"path":runner_path.relative_to(ROOT).as_posix(),"sha256":digest(runner_path)}
    portrait=args.suite=="portrait"
    browser_args=["--disable-gpu-shader-disk-cache","--disk-cache-size=1048576"] if portrait else None
    with sync_playwright() as runtime:
        browser=generator.launch(runtime,args.browser,args=browser_args)
        try:
            page,defaults,transitions=generator.setup(browser)
            registry={p["id"] for p in json.loads((ROOT/"references/patterns.json").read_text(encoding="utf-8"))["patterns"]}
            if set(transitions)|set(defaults)!=registry: raise ValueError("Pattern registry differs from the rendering engine")
            named_cases={name:(spec,keep) for name,spec,keep in production_cases(args.suite,defaults,transitions,directory)}
            requested=set(args.only or named_cases)
            unknown=(requested | set(args.keep_sheet))-named_cases.keys()
            if unknown: raise ValueError(f"Unknown cases: {', '.join(sorted(unknown))}")
            engine={"files":fingerprint,"browser":browser.version,"browser_args":browser_args,
                    "clip_cache":"memory" if portrait else "disk","receipt_version":RECEIPT_VERSION,"runner":runner,
                    **{name:subprocess.check_output([name,"-version"],text=True).splitlines()[0]
                       for name in ("ffmpeg","ffprobe")}}
            engine_sha=hashlib.sha256(json.dumps(engine,sort_keys=True).encode()).hexdigest()
            rendered=[]
            failures=[]
            waiting=[]
            report_name=("partial-"+args.only[0] if len(args.only)==1 else "partial-selected") if args.only else args.suite
            index=out/(report_name+".json")

            def checkpoint(stop=None):
                covered={row["case"] for row in rendered}
                write_json(index,{"suite":args.suite,"complete":len(covered)==len(named_cases),
                    "elements":list(defaults),"transitions":transitions,"cases":rendered,"expected":len(named_cases),
                    "requested":len(requested),"pending":sorted(requested-covered),
                    "requires_render":waiting,"failed":failures,"stop":stop,"sourceMedia":metadata,"engine":engine,
                    "engine_sha256":engine_sha,
                    "runner":runner})

            for case,(spec,keep) in named_cases.items():
                if case not in requested: continue
                if shutil.disk_usage(out).free < args.reserve_mib*1024**2:
                    status=f"Reservados {args.reserve_mib} MiB libres antes de {case}"
                    checkpoint(status)
                    print(status,flush=True)
                    return 2
                sheet=case in args.keep_sheet or (keep and (args.suite in {"stress","portrait"} or not args.compact))
                try:
                    result,method=run_case(page,defaults,transitions,case,spec,out,engine,metadata,
                                           keep,sheet,sources,args.verify_only)
                except (ValueError,subprocess.CalledProcessError,OSError) as error:
                    failures.append({"case":case,"error":str(error)})
                    print(f"{case}: {error}",flush=True)
                    if getattr(error,"errno",None)==errno.ENOSPC:
                        checkpoint(str(error))
                        return 2
                else:
                    if result:
                        rendered.append({"case":case,"frames":result["decoded"]["frames"],"sha256":result["sha256"],
                                         "fps":result["fps"],"size":result["size"],"movie_retained":result["movie_retained"],
                                         "verification":result["verification"]["method"]})
                        print(f"{len(rendered)}/{len(requested)} {case} {result['decoded']['frames']} {method}",flush=True)
                    else:
                        waiting.append(case)
                        print(f"{case}: requiere render",flush=True)
                finally:
                    generator.release_video_frames(page)
                checkpoint()
            return int(bool(failures))
        finally:
            browser.close()


if __name__=="__main__":
    raise SystemExit(main())
