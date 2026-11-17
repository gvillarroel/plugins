#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["torch==2.15.0", "kornia==0.9.0", "numpy>=2,<3", "pillow>=11,<14", "scipy>=1.14,<2"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Apply portable Kornia artistic techniques or build a local comparison gallery."""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.metadata
import json
import math
import os
import platform
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy.ndimage import distance_transform_edt
import torch

from techniques import TECHNIQUES, apply


def parse_color(value):
    value=value.lstrip('#')
    if len(value)!=6 or any(c not in '0123456789abcdefABCDEF' for c in value):
        raise ValueError('Background must contain six hexadecimal RGB digits, optionally prefixed by #.')
    return tuple(bytes.fromhex(value))


def load_image(path,max_edge=1024):
    path=Path(path).resolve()
    if not path.is_file():raise ValueError(f'Input image does not exist: {path}')
    if max_edge<0:raise ValueError('Max edge must be zero or positive.')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    with Image.open(path) as image:
        original_size=list(image.size);original_mode=image.mode
        if image.mode in ('I','F') or image.mode.startswith('I;16'):
            raise ValueError('High-depth integer and floating-point images are unsupported; explicitly tone-map to an 8-bit image first.')
        frame_count=int(getattr(image,'n_frames',1));image.seek(0)
        icc_present=bool(image.info.get('icc_profile'))
        corrected=ImageOps.exif_transpose(image).convert('RGBA')
        oriented_size=list(corrected.size)
        if max_edge and max(corrected.size)>max_edge:
            ratio=max_edge/max(corrected.size)
            size=tuple(max(1,round(n*ratio)) for n in corrected.size)
            corrected=corrected.resize(size,Image.Resampling.LANCZOS)
        rgba=np.asarray(corrected,dtype=np.uint8).copy()
    source={'file':path.name,'sha256':digest,'original_size':original_size,'oriented_size':oriented_size,
            'output_size':[rgba.shape[1],rgba.shape[0]],'original_mode':original_mode,
            'has_transparency':bool((rgba[...,3]<255).any()),'exif_orientation':'applied before resizing',
            'frame_count':frame_count,'frame_index':0,'motion_policy':'first frame only; animation is not preserved',
            'color_policy':{'working_encoding':'8-bit Pillow RGBA','icc_profile_present':icc_present,
                            'icc_conversion_applied':False,'conversion':'Pillow mode conversion; not ICC-managed or calibrated for print'},
            'resize_policy':'downscale only, preserve aspect ratio with nearest integer dimensions'}
    return rgba,source


def processing_support(rgb,alpha):
    """Fill invisible RGB from nearest nonzero-alpha pixels without changing alpha."""
    visible=alpha>0
    if visible.all() or not visible.any():return rgb.copy()
    nearest=distance_transform_edt(~visible,return_distances=False,return_indices=True)
    result=rgb.copy();result[~visible]=rgb[nearest[0][~visible],nearest[1][~visible]]
    return result


def compose(rgba,keys,*,seed=0,strength=1.,scale=1.,palette=None,background=None):
    original=rgba[...,:3].astype(np.float32)/255
    alpha=rgba[...,3].copy();current=original.copy();stages=[]
    for index,key in enumerate(keys):
        stage_seed=int.from_bytes(hashlib.sha256(f'{seed}:{index}:{key}'.encode()).digest()[:8],'big')%(2**63)
        support=processing_support(current,alpha)
        styled,stage=apply(support,key,seed=stage_seed,scale=scale,palette=palette,strength=1.)
        current=np.clip(current*(1-strength)+styled*strength,0,1).astype(np.float32)
        stage['parameters']['strength']=strength
        stages.append(stage)
    if not np.isfinite(current).all():raise ValueError('Composition produced nonfinite pixels.')
    if background is not None:
        color=np.array(background,dtype=np.float32)/255
        current=current*(alpha[...,None]/255)+color*(1-alpha[...,None]/255)
        output_alpha=np.full_like(alpha,255)
        alpha_policy='flattened onto the explicitly supplied background after artistic processing'
    else:
        output_alpha=alpha
        alpha_policy='anchored: EXIF-corrected/resized input alpha preserved exactly; RGB may be spatially transformed'
    rgb8=np.rint(np.clip(current,0,1)*255).astype(np.uint8)
    result=np.concatenate((rgb8,output_alpha[...,None]),2)
    weights=alpha.astype(np.float32)/255
    visible_difference=float((np.abs(current-original)*weights[...,None]).sum()/max(1.,weights.sum()*3))
    validation={'finite_rgb':True,'width':result.shape[1],'height':result.shape[0],
                'rgb_standard_deviation':float(current.std()),'visible_mean_absolute_difference':visible_difference,
                'alpha_matches_processed_source':bool(np.array_equal(output_alpha,alpha)) if background is None else None,
                'pixel_sha256':hashlib.sha256(result.tobytes()).hexdigest()}
    return result,stages,validation,alpha_policy


def runtime_metadata():
    engine=Path(__file__).with_name('techniques.py')
    return {'python':platform.python_version(),
            'packages':{name:importlib.metadata.version(name) for name in ('torch','kornia','numpy','Pillow','scipy')},
            'engine_sha256':hashlib.sha256(engine.read_bytes()).hexdigest(),
            'executor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def stable_id(source,keys,options,runtime):
    value={'source_sha256':source['sha256'],'techniques':keys,'options':options,'runtime':runtime}
    digest=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return 'kat-'+digest[:20]


def relative(path,parent):
    try:return Path(os.path.relpath(Path(path).resolve(),Path(parent).resolve())).as_posix()
    except ValueError as error:raise ValueError('Image and report must be on the same volume for portable relative paths.') from error


def check_targets(source,targets,overwrite=False):
    source=Path(source).resolve();resolved=[Path(p).resolve() for p in targets]
    if len(set(resolved))!=len(resolved):raise ValueError('Output artifact paths overlap.')
    for target in resolved:
        if target==source or (target.exists() and os.path.samefile(target,source)):
            raise ValueError('The input image must never be overwritten, including through an alias or with --overwrite.')
        if target.exists() and target.is_dir():raise ValueError(f'An output path is a directory: {target}')
        if target.exists() and not overwrite:raise ValueError(f'Output exists; pass --overwrite to replace it: {target}')
        for parent in target.parents:
            if parent.exists() and not parent.is_dir():raise ValueError(f'An output parent is not a directory: {parent}')


def write_image(path,image,overwrite):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('wb' if overwrite else 'xb') as handle:
        image.save(handle,format='PNG')


def write_text(path,value,overwrite):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w' if overwrite else 'x',encoding='utf-8',newline='\n') as handle:handle.write(value)


def write_json(path,value,overwrite):
    write_text(path,json.dumps(value,ensure_ascii=False,indent=2)+'\n',overwrite)


def source_preview(rgba,background):
    if background is None:return Image.fromarray(rgba,'RGBA')
    alpha=rgba[...,3:4].astype(np.float32)/255
    rgb=rgba[...,:3]*alpha+np.array(background)*(1-alpha)
    out=np.concatenate((np.rint(rgb).astype(np.uint8),np.full_like(rgba[...,3:4],255)),2)
    return Image.fromarray(out,'RGBA')


def make_contact(source,images,names):
    items=[('Source',source)]+list(zip(names,images))
    cellw=250;cellh=225;columns=min(3,len(items));rows=math.ceil(len(items)/columns)
    sheet=Image.new('RGBA',(columns*cellw,rows*cellh),(247,247,247,255));draw=ImageDraw.Draw(sheet)
    for index,(name,image) in enumerate(items):
        preview=image.copy();preview.thumbnail((cellw-16,cellh-42),Image.Resampling.LANCZOS)
        x=(index%columns)*cellw+(cellw-preview.width)//2
        y=(index//columns)*cellh+8+(cellh-42-preview.height)//2
        sheet.alpha_composite(preview,(x,y))
        draw.text(((index%columns)*cellw+8,(index//columns)*cellh+cellh-28),name,fill=(28,28,28,255))
    return sheet.convert('RGB')


def gallery_html(source,outputs):
    cards=[]
    for item in outputs:
        name=' + '.join(item['techniques']);esc=html.escape
        cards.append(f'''<article id="{esc(item['id'])}"><h2>{esc(name)}</h2>
<img class="checker" src="{esc(item['image'])}" alt="{esc(name)} artistic result" loading="lazy">
<details><summary>Compare source</summary><img class="checker" src="source.png" alt="Source image" loading="lazy"></details>
<p><a href="{esc(item['image'])}" download>PNG</a> · <a href="{esc(item['report'])}">Report</a></p></article>''')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kornia artistic studies</title><style>
*{box-sizing:border-box}body{margin:0;background:#f7f7f7;color:#1c1c1c;font:16px/1.5 system-ui,sans-serif}
main{max-width:1440px;margin:auto;padding:24px}h1{font-size:1.7rem}h2{font-size:1rem;overflow-wrap:anywhere}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(270px,100%),1fr));gap:20px}
article{min-width:0;background:#ffffff;padding:14px;border:1px solid #cfcfcf}img{display:block;width:100%;height:auto;max-height:420px;object-fit:contain}
.checker{background:repeating-conic-gradient(#e7e7e7 0% 25%,#f7f7f7 0% 50%) 50%/16px 16px}
summary{margin:10px 0;cursor:pointer}a{color:#9e1b32}header{max-width:900px;margin-bottom:24px}header img{max-height:260px;object-position:left}
@media(max-width:480px){main{padding:12px}.grid{gap:12px}}
</style><main><header><h1>Kornia artistic studies</h1><p>Local comparison gallery. These are digital techniques, not physically produced prints or materials.</p>
<img class="checker" src="source.png" alt="Processed source image"><p>''' + html.escape(source['file']) + ''' · ''' + str(source['output_size'][0])+' × '+str(source['output_size'][1]) + ''' pixels</p></header><section class="grid">'''+'\n'.join(cards)+'''</section></main></html>'''


def execute(args):
    if args.input is None:raise ValueError('An input image is required.')
    if args.seed<0 or args.seed>=2**63:raise ValueError('Seed must be in [0, 2**63).')
    if not math.isfinite(args.strength) or not 0<=args.strength<=1:raise ValueError('Strength must be between zero and one.')
    if not math.isfinite(args.scale) or args.scale<=0:raise ValueError('Scale must be finite and positive.')
    background=parse_color(args.background) if args.background is not None else None
    batch=args.output_dir is not None
    if batch:
        if args.output or args.technique or args.report:raise ValueError('Batch mode uses --output-dir and --techniques, without -o, --technique or --report.')
        if not args.techniques:raise ValueError('Batch mode requires --techniques KEY,KEY or --techniques all.')
        keys=list(TECHNIQUES) if args.techniques=='all' else [v.strip() for v in args.techniques.split(',') if v.strip()]
        if not keys or len(set(keys))!=len(keys):raise ValueError('Batch technique keys must be nonempty and unique.')
        directory=Path(args.output_dir).resolve()
        image_paths=[directory/'images'/f'{i:03d}-{key}.png' for i,key in enumerate(keys,1)]
        report_paths=[p.with_suffix('.json') for p in image_paths]
        targets=image_paths+report_paths+[directory/name for name in ('source.png','manifest.json','contact-sheet.png','gallery.html')]
    else:
        if args.techniques:raise ValueError('--techniques is for batch mode; use repeatable --technique for a composition.')
        keys=args.technique or []
        if not args.output or not keys:raise ValueError('Single mode requires -o result.png and at least one --technique.')
        image_paths=[Path(args.output).resolve()]
        if image_paths[0].suffix.lower()!='.png':raise ValueError('The exact single output path must end in .png.')
        report_paths=[Path(args.report).resolve() if args.report else image_paths[0].with_suffix('.json')]
        targets=image_paths+report_paths
    unknown=[key for key in keys if key not in TECHNIQUES]
    if unknown:raise ValueError('Unknown technique keys: '+', '.join(unknown))
    check_targets(args.input,targets,args.overwrite)
    rgba,source=load_image(args.input,args.max_edge)
    runtime=runtime_metadata()
    options={'seed':args.seed,'strength':args.strength,'scale':args.scale,'palette':args.palette,
             'max_edge':args.max_edge,'background':('#'+bytes(background).hex()) if background else None}
    groups=[[key] for key in keys] if batch else [keys]
    results=[];images=[]
    for index,group in enumerate(groups):
        pixels,stages,validation,alpha_policy=compose(rgba,group,seed=args.seed,strength=args.strength,scale=args.scale,palette=args.palette,background=background)
        result={'schema_version':1,'id':stable_id(source,group,options,runtime),'techniques':group,'runtime':runtime,
                'source':{**source,'alpha_policy':alpha_policy,'transparent_rgb_support':'nearest nonzero-alpha RGB values are used only while processing'},
                'options':options,'stages':stages,'validation':validation}
        base=directory if batch else report_paths[index].parent
        result['image']=relative(image_paths[index],base)
        result['report']=relative(report_paths[index],base)
        results.append(result);images.append(Image.fromarray(pixels,'RGBA'))
    # All deterministic validations and target checks happen before the first write.
    for image,path,report_path,result in zip(images,image_paths,report_paths,results):
        write_image(path,image,args.overwrite)
        per_image=dict(result)
        per_image['image']=relative(path,report_path.parent)
        per_image['report']=report_path.name
        write_json(report_path,per_image,args.overwrite)
    if batch:
        preview=source_preview(rgba,background)
        manifest={'schema_version':1,'source':results[0]['source'],'options':options,'runtime':runtime,'outputs':results,
                  'source_image':'source.png','contact_sheet':'contact-sheet.png','gallery':'gallery.html'}
        write_image(directory/'source.png',preview,args.overwrite)
        write_image(directory/'contact-sheet.png',make_contact(preview,images,keys),args.overwrite)
        write_text(directory/'gallery.html',gallery_html(source,results),args.overwrite)
        write_json(directory/'manifest.json',manifest,args.overwrite)
        return manifest
    return results[0]


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',nargs='?',help='Input image; EXIF is applied and aspect ratio is preserved.')
    p.add_argument('-o','--output',help='Exact single PNG output path.')
    p.add_argument('--technique',action='append',help='Ordered composition stage; repeat to combine techniques.')
    p.add_argument('--output-dir',help='Batch output directory.')
    p.add_argument('--techniques',help='Comma-separated independent batch techniques, or all.')
    p.add_argument('--list',action='store_true',help='List the ten techniques in default collection order.')
    p.add_argument('--seed',type=int,default=0)
    p.add_argument('--max-edge',type=int,default=1024,help='Downscale only; 0 keeps the original dimensions.')
    p.add_argument('--strength',type=float,default=1.,help='Per-stage blend strength from 0 to 1.')
    p.add_argument('--scale',type=float,default=1.,help='Positive multiplier of isotropic short-edge style units.')
    p.add_argument('--palette',choices=['source','ink'],help='Default: source, except the three monochrome techniques use ink.')
    p.add_argument('--background',help='Optional #RRGGBB flattening background; otherwise alpha is preserved.')
    p.add_argument('--report',help='Single-output JSON path; defaults to output.with_suffix(.json).')
    p.add_argument('--overwrite',action='store_true',help='Replace planned output artifacts; never replace the input.')
    return p


def main(argv=None):
    p=parser();args=p.parse_args(argv)
    if args.list:
        for key,(_,default,_,_) in TECHNIQUES.items():print(f'{key}\tdefault palette: {default}')
        return 0
    try:
        torch.set_num_threads(min(4,os.cpu_count() or 1))
        result=execute(args)
    except (ValueError,OSError,RuntimeError) as error:
        print(f'Error: {error}',file=sys.stderr);return 2
    print(json.dumps({'status':'ok','id':result.get('id'),'outputs':len(result.get('outputs',[])) or 1},ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
