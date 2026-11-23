# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow>=10,<13"]
# ///
"""Record a native Codex bitmap and check its identity, alpha, and placement in a rendered film."""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageChops, ImageColor


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def need(test, reason):
    if not test:
        raise ValueError(reason)


def pixels(image):
    # Pillow 12 supplies a non-deprecated alternative to getdata.
    return image.get_flattened_data() if hasattr(image,"get_flattened_data") else image.getdata()


def examine(image_path, alpha_policy, minimum_near_opaque=None):
    with Image.open(image_path) as bitmap:
        bitmap.load()
        w,h = bitmap.size
        channel = bitmap.convert("RGBA").getchannel("A")
        alpha = channel.histogram()
        clear, opaque = alpha[0],alpha[255]
        partial = w*h-clear-opaque
        near_opaque = sum(alpha[250:])
        near_fraction = near_opaque/(opaque+partial) if opaque+partial else 0
        need(alpha_policy in ("opaque","cutout"),"alpha must be opaque or cutout")
        if alpha_policy=="cutout":
            need(clear and opaque+partial,"Cutout requires both transparent and visible pixels")
        else:
            need(opaque==w*h,"Opaque asset has transparent pixels")
        if minimum_near_opaque is not None:
            need(alpha_policy=="cutout" and type(minimum_near_opaque) in (int,float) and 0<=minimum_near_opaque<=1,
                 "Minimum near-opaque fraction requires a cutout and a number between zero and one")
            need(near_fraction>=minimum_near_opaque,
                 f"Cutout has {near_fraction:.2%} near-opaque visible pixels at alpha ≥250, expected {minimum_near_opaque:.2%}")
        rgb = bitmap.convert("RGB")
        perimeter = Counter()
        border = [(0,0,w,1)]
        if h>1: border.append((0,h-1,w,h))
        if h>2:
            border.append((0,1,1,h-1))
            if w>1: border.append((w-1,1,w,h-1))
        perimeter_alpha = Counter()
        for box in border:
            perimeter.update(pixels(rgb.crop(box)))
            perimeter_alpha.update(pixels(channel.crop(box)))
        color, common = perimeter.most_common(1)[0]
        return {"size":[w,h],"format":bitmap.format,"mode":bitmap.mode,"transparent_pixels":clear,
                "partially_visible_pixels":partial,"opaque_pixels":opaque,
                "alpha_detail":{"maximum":channel.getextrema()[1],"visible_bounds":channel.getbbox(),
                                "near_opaque_cutoff":250,"near_opaque_pixels":near_opaque,
                                "near_opaque_fraction_of_visible":round(near_fraction,6),
                                "transparent_perimeter_fraction":round(perimeter_alpha[0]/sum(perimeter_alpha.values()),6)},
                "border":{"rgb_values":len(perimeter),"most_common_rgb":list(color),
                          "most_common_fraction":round(common/sum(perimeter.values()),6)}}


def media_tokens(value):
    if isinstance(value,dict):
        for key,part in value.items():
            if key in ("media","background","mark","slide") and isinstance(part,str):
                yield part
            else:
                yield from media_tokens(part)
    if isinstance(value,list):
        for part in value:
            yield from media_tokens(part)


def inspect_frame(movie, sample):
    frame=sample["frame"]
    need(type(frame) is int and frame>=0,"Frame index must be a non-negative integer")
    result=subprocess.run(["ffmpeg","-v","error","-nostdin","-i",str(movie),"-map","0:v:0","-vf",
                           f"select=eq(n\\,{frame})","-frames:v","1","-c:v","png","-f","image2pipe","-"],
                          capture_output=True,check=True)
    need(result.stdout,f"No decoded frame {frame}")
    with Image.open(io.BytesIO(result.stdout)) as image:
        x1,y1,x2,y2=sample["rect"]
        need(0<=x1<x2<=1 and 0<=y1<y2<=1,"Invalid normalized frame rectangle")
        rect=(math.floor(x1*image.width),math.floor(y1*image.height),math.ceil(x2*image.width),math.ceil(y2*image.height))
        region=image.convert("RGB").crop(rect)
    tolerance=sample.get("tolerance",3)
    threshold=sample["min_fraction"]
    need(type(tolerance) is int and 0<=tolerance<=255 and 0<=threshold<=1,"Invalid pixel comparison tolerance")
    target=ImageColor.getrgb(sample["rgb"])
    difference=ImageChops.difference(region,Image.new("RGB",region.size,target))
    r,g,b=difference.split()
    errors=ImageChops.lighter(r,ImageChops.lighter(g,b)).histogram()
    fraction=sum(errors[:tolerance+1])/sum(errors)
    need(fraction>=threshold,f"{sample['label']}: only {fraction:.2%} of pixels match, expected {threshold:.2%}")
    return {**sample,"matched_fraction":round(fraction,6),"pixel_bounds":list(rect)}


def verify(manifest, movie=None):
    spec=json.loads(manifest.read_text(encoding="utf-8-sig"))
    root=manifest.resolve().parent
    need(spec.get("version")==1 and spec.get("tool")=="Codex ImageGen","Unknown generation record")
    need(spec["operation"] in ("generate","edit") and all(isinstance(spec.get(k),str) and spec[k].strip()
         for k in ("generation_id","purpose")),"Missing generation identity or purpose")
    img=root/spec["image"]
    prompt=root/spec["prompt"]
    need(digest(img)==spec["sha256"],"Original bitmap checksum mismatch")
    need(digest(prompt)==spec["prompt_sha256"] and prompt.read_text(encoding="utf-8-sig").strip(),"Prompt changed or empty")
    references=spec.get("references",[])
    need(references or spec["operation"]=="generate","An edit must identify its original reference")
    for ref in references:
        need(digest(root/ref["file"])==ref["sha256"],"Edited source reference checksum mismatch")
    result={"tool":spec["tool"],"operation":spec["operation"],"generation_id":spec["generation_id"],
            "sha256":spec["sha256"],"prompt_sha256":spec["prompt_sha256"],
            **examine(img,spec["alpha"],spec.get("minimum_near_opaque"))}
    if "recipe" in spec:
        path=root/spec["recipe"]
        recipe=json.loads(path.read_text(encoding="utf-8-sig"))
        key=spec["asset_id"]
        asset=recipe["assets"][key]
        selected=asset["path"] if isinstance(asset,dict) else asset
        need((path.parent/selected).resolve()==img.resolve(),"Recipe references another bitmap")
        scenes=[s["id"] for s in recipe["scenes"] if key in set(media_tokens(s["props"]))]
        need(scenes,"Bitmap is declared but never drawn in the recipe")
        result["integration"]={"recipe_sha256":digest(path),"asset_id":key,"scenes":scenes}
    if "composition_report" in spec or spec.get("movie_samples"):
        need(movie and movie.is_file(),"Movie is required to verify the composition or its declared samples")
        movie_sha=digest(movie)
        result["movie"]={"sha256":movie_sha,"samples":[inspect_frame(movie,s) for s in spec.get("movie_samples",[])]}
        if "composition_report" in spec:
            path=root/spec["composition_report"]
            composed=json.loads(path.read_text(encoding="utf-8-sig"))
            need(composed.get("ok") and composed.get("published") and composed.get("candidateSha256")==movie_sha,
                 "Composition report does not certify this published movie")
            need(composed.get("inputs",{}).get(str(img.resolve()))==spec["sha256"],
                 "Composition report did not record the original bitmap path and digest")
            result["movie"]["composition_report_sha256"]=digest(path)
    return result


def write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,mode="w",encoding="utf-8",delete=False) as stream:
        temporary=Path(stream.name)
        json.dump(data,stream,ensure_ascii=False,indent=2)
        stream.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cmds=cli.add_subparsers(dest="action",required=True)
    add=cmds.add_parser("record",help="write a portable record of the original image and exact prompt")
    for name in ("image","prompt","manifest"):
        add.add_argument(name,type=Path)
    add.add_argument("--operation",choices=["generate","edit"],default="generate")
    add.add_argument("--generation-id",required=True)
    add.add_argument("--purpose",required=True)
    add.add_argument("--alpha",choices=["opaque","cutout"],required=True)
    add.add_argument("--min-near-opaque",type=float,help="Minimum fraction of visible cutout pixels at alpha 250 or higher")
    add.add_argument("--reference",action="append",type=Path,default=[])
    check=cmds.add_parser("verify",help="verify a record and its optional recipe and movie witnesses")
    check.add_argument("manifest",type=Path)
    check.add_argument("--movie",type=Path)
    check.add_argument("--report",type=Path)
    args=cli.parse_args()
    try:
        if args.action=="record":
            need(not args.manifest.exists(),"Generation record already exists")
            need(args.reference or args.operation=="generate","Supply the original with --reference for an edit")
            need(args.purpose.strip() and args.generation_id.strip(),"Generation ID and purpose cannot be blank")
            need(args.prompt.read_text(encoding="utf-8-sig").strip(),"Prompt is empty")
            examine(args.image,args.alpha,args.min_near_opaque)
            rel=lambda p: Path(os.path.relpath(p.resolve(),args.manifest.resolve().parent)).as_posix()
            data={"version":1,"tool":"Codex ImageGen","operation":args.operation,"generation_id":args.generation_id,
                  "purpose":args.purpose,"image":rel(args.image),"sha256":digest(args.image),"prompt":rel(args.prompt),
                  "prompt_sha256":digest(args.prompt),"alpha":args.alpha,
                  "references":[{"file":rel(p),"sha256":digest(p)} for p in args.reference]}
            if args.min_near_opaque is not None: data["minimum_near_opaque"]=args.min_near_opaque
            write(args.manifest,data)
            print(args.manifest)
        else:
            data=verify(args.manifest,args.movie)
            if args.report:
                # A report cannot replace the inputs whose hashes it certifies.
                spec=json.loads(args.manifest.read_text(encoding="utf-8-sig"))
                inputs=[args.manifest,args.movie] + [args.manifest.parent/spec[k]
                    for k in ("image","prompt","recipe","composition_report") if k in spec]
                inputs.extend(args.manifest.parent/r["file"] for r in spec.get("references",[]))
                need(args.report.resolve() not in {p.resolve() for p in inputs if p},"Report path collides with an input")
                write(args.report,data)
            print(json.dumps(data,ensure_ascii=False))
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as err:
        cli.exit(1,f"codex_image_asset: {err}\n")


if __name__=="__main__":
    main()
