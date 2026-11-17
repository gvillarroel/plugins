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
"""Portable, CPU-only artistic operators; no assets, trained models or repository state."""
from __future__ import annotations

import math
from dataclasses import dataclass

import kornia as K
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter
from scipy.spatial import cKDTree


INK = np.array([[.10,.24,.29],[.69,.38,.25],[.92,.85,.71]],np.float32)


def tensor(a):
    a=np.asarray(a,dtype=np.float32)
    if a.ndim==2:a=a[...,None]
    return torch.from_numpy(np.ascontiguousarray(a)).permute(2,0,1)[None]


def array(t):
    return t.detach()[0].permute(1,2,0).cpu().numpy().astype(np.float32)


def normalize(a):
    lo,hi=np.quantile(a,[.01,.99])
    if hi-lo<1e-6:return np.clip(a,0,1).astype(np.float32)
    return np.clip((a-lo)/(hi-lo),0,1).astype(np.float32)


def blur(t,sigma):
    radius=max(1,min(31,int(math.ceil(2.8*sigma))))
    return K.filters.gaussian_blur2d(t,(2*radius+1,)*2,(float(sigma),)*2,border_type='replicate')


def ink_palette(g):
    p=np.clip(g,0,1)*2
    lo=np.minimum(p.astype(int),1);f=(p-lo)[...,None]
    return INK[lo]*(1-f)+INK[lo+1]*f


def blend(a,b,m):
    if np.ndim(m)==2:m=m[...,None]
    return a*(1-m)+b*m


@dataclass
class Context:
    rgb: np.ndarray
    scale: float
    seed: int
    palette: str

    def __post_init__(self):
        self.h,self.w=self.rgb.shape[:2]
        self.unit=max(.5,min(self.h,self.w)/512*self.scale)
        self.y,self.x=np.mgrid[:self.h,:self.w].astype(np.float32)
        self.rng=np.random.default_rng(self.seed)
        self.t=tensor(self.rgb)
        self.gray=K.color.rgb_to_grayscale(self.t)
        self.g=normalize(array(self.gray)[...,0])
        self.sm=normalize(array(blur(self.gray,max(.5,self.unit)))[...,0])
        grad=K.filters.spatial_gradient(blur(self.gray,max(.5,self.unit)))[0,0].numpy()
        self.gx,self.gy=grad[0],grad[1]
        self.edge=normalize(np.hypot(self.gx,self.gy))
        jxx=array(blur(tensor(self.gx**2),max(.7,3*self.unit)))[...,0]
        jyy=array(blur(tensor(self.gy**2),max(.7,3*self.unit)))[...,0]
        jxy=array(blur(tensor(self.gx*self.gy),max(.7,3*self.unit)))[...,0]
        self.coherence=np.clip(np.sqrt((jxx-jyy)**2+4*jxy**2)/(jxx+jyy+1e-8),0,1)

    def material(self):
        return self.rgb.copy() if self.palette=='source' else ink_palette(self.g)

    def mark_color(self,y,x):
        return self.rgb[y,x]*.72+INK[0]*.28 if self.palette=='source' else INK[0]


def quadtree_regions(rgb,scale=1.):
    """Return a complete nonoverlapping half-open rectangular partition."""
    h,w=rgb.shape[:2];unit=max(.5,min(h,w)/512*scale)
    t=tensor(rgb);gray=K.color.rgb_to_grayscale(t)
    integrals=K.enhance.integral_image(torch.cat((t,gray,gray.square()),1))
    sums=np.pad(array(integrals),((1,0),(1,0),(0,0)))
    regions=[];minimum=max(2,int(round(14*unit)));maximum=max(minimum,int(round(75*unit)))
    def visit(xa,ya,xb,yb):
        count=(xb-xa)*(yb-ya)
        total=sums[yb,xb]-sums[ya,xb]-sums[yb,xa]+sums[ya,xa]
        mean=total[3]/count;variance=max(0.,float(total[4]/count-mean*mean))
        can_split=(xb-xa>minimum or yb-ya>minimum)
        if can_split and (max(xb-xa,yb-ya)>maximum or variance>.0065):
            xm=(xa+xb)//2;ym=(ya+yb)//2
            xs=[(xa,xm),(xm,xb)] if xa<xm<xb else [(xa,xb)]
            ys=[(ya,ym),(ym,yb)] if ya<ym<yb else [(ya,yb)]
            for y0,y1 in ys:
                for x0,x1 in xs:visit(x0,y0,x1,y1)
        else:regions.append((xa,ya,xb,yb,total[:3]/count,float(mean)))
    visit(0,0,w,h)
    return regions


def regions_lab(c):
    h,w=c.h,c.w
    smooth=blur(c.t,max(.5,c.unit*1.3))
    lab=K.color.rgb_to_lab(smooth)
    ratio=min(1.,64/max(h,w))
    size=(max(1,round(h*ratio)),max(1,round(w*ratio)))
    small=F.interpolate(lab,size=size,mode='bilinear',align_corners=False)
    units=torch.tensor([100.,80.,80.])
    data=small[0].permute(1,2,0).reshape(-1,3)/units
    k=min(7,len(data))
    indices=c.rng.choice(len(data),size=k,replace=False)
    centers=data[torch.from_numpy(indices)].clone()
    for _ in range(9):
        labels=torch.cdist(data,centers).argmin(1)
        for j in range(k):
            if (labels==j).any():centers[j]=data[labels==j].mean(0)
    # Canonical labels and duplicate removal make flat inputs a single region.
    values=centers.numpy();order=np.lexsort((values[:,2],values[:,1],values[:,0]));unique=[]
    for item in values[order]:
        if not any(np.allclose(item,prior,rtol=0,atol=1e-5) for prior in unique):unique.append(item)
    centers=torch.from_numpy(np.asarray(unique,dtype=np.float32));k=len(centers)
    full=lab[0].permute(1,2,0).reshape(-1,3)/units
    ids=torch.cat([torch.cdist(full[start:start+65536],centers).argmin(1)
                   for start in range(0,len(full),65536)]).reshape(h,w)
    rebuilt=(centers[ids]*units).permute(2,0,1)[None]
    flat=array(K.color.lab_to_rgb(rebuilt))
    labels=ids.numpy()
    if c.palette=='ink':flat=ink_palette(c.sm)
    return labels,flat,k


def resample(c,rgb,x,y):
    if c.w==1:x=np.zeros_like(x)
    if c.h==1:y=np.zeros_like(y)
    return array(K.geometry.transform.remap(tensor(rgb),torch.as_tensor(x,dtype=torch.float32)[None],
        torch.as_tensor(y,dtype=torch.float32)[None],align_corners=True,padding_mode='reflection'))


def quadtree_engraving(c):
    out=np.broadcast_to(INK[2],c.rgb.shape).copy();leaves=quadtree_regions(c.rgb,c.scale)
    for xa,ya,xb,yb,mean,g in leaves:
        xx=c.x[ya:yb,xa:xb];yy=c.y[ya:yb,xa:xb]
        ix=(xa+xb-1)//2;iy=(ya+yb-1)//2
        angle=math.atan2(c.gy[iy,ix],c.gx[iy,ix])+math.pi/2
        phase=(xx*np.cos(angle)+yy*np.sin(angle))/max(2.,6*c.unit)%1
        tone=c.sm[ya:yb,xa:xb]*.65+g*.35
        marks=(phase<np.clip((1-tone)*.86,.025,.97)).astype(np.float32)
        if g<.3:
            cross=(xx*np.cos(angle+1.1)+yy*np.sin(angle+1.1))/max(2.,8*c.unit)%1
            marks=np.maximum(marks,(cross<(1-tone)*.32).astype(np.float32))
        mark=mean*.60+INK[0]*.40 if c.palette=='source' else INK[0]
        patch=blend(out[ya:yb,xa:xb],mark,marks*.94)
        if min(xb-xa,yb-ya)>3:
            patch[0,:]=INK[1]*.4+INK[2]*.6;patch[:,0]=INK[1]*.4+INK[2]*.6
        out[ya:yb,xa:xb]=patch
    out=out*.88+ink_palette(c.g)*.12
    return out,{'regions':len(leaves),'partition':'rectangular half-open bounds','line_pitch_px':max(2.,6*c.unit)}


def region_hatching(c):
    labels,flat,k=regions_lab(c)
    angle=labels*(math.pi/max(1,k))+.12
    pitch=max(2.,7*c.unit)
    phase=(c.x*np.cos(angle)+c.y*np.sin(angle))/pitch%1
    mark=(phase<np.clip((1-c.sm)*.60,.025,.80)).astype(np.float32)
    border=(maximum_filter(labels,3)!=minimum_filter(labels,3)).astype(np.float32)
    out=blend(flat*.84+INK[2]*.16,INK[0],mark*.60*(1-border))
    out=blend(out,INK[2],border*.54)
    return out,{'lab_regions':k,'line_pitch_px':pitch,'kmeans_iterations':9,'canonical_region_order':'L,a,b ascending; duplicate centers removed'}


def ink_strata(c):
    pitch=max(3.,66*c.unit);coordinate=c.y+.16*c.x
    bands=np.floor(coordinate/pitch).astype(int)
    shift=((bands%3)-1)*7*c.unit
    shifted=resample(c,c.material(),c.x+shift,c.y)
    gray=K.color.rgb_to_grayscale(tensor(shifted));g=normalize(array(gray)[...,0])
    stamp=(g<.54).astype(np.float32)
    stamp=array(K.morphology.closing(tensor(stamp),torch.ones(3,3)))[...,0]
    screen_pitch=max(2.,9*c.unit)
    phase=(c.x*.84+c.y*.54)/screen_pitch%1
    screen=(phase<np.clip(1-g,.04,.96)).astype(np.float32)
    gate=(bands%2).astype(np.float32)
    out=np.broadcast_to(INK[2],c.rgb.shape).copy()
    stamp_color=shifted*.64+INK[1]*.36 if c.palette=='source' else INK[1]
    line_color=shifted*.60+INK[0]*.40 if c.palette=='source' else INK[0]
    out=blend(out,stamp_color,stamp*(1-gate)*.90)
    out=blend(out,line_color,screen*gate*.97)
    contour=normalize(array(K.filters.sobel(gray))[...,0])
    out=blend(out,INK[2],contour**1.35*.72)
    reserve=(coordinate%pitch<max(.7,2.2*c.unit)).astype(np.float32)
    out=blend(out,INK[2],reserve)
    return out,{'band_pitch_px':pitch,'oblique_slope':.16,'source_offsets_px':[-7*c.unit,0,7*c.unit],
                'stencil_threshold':.54,'screen_pitch_px':screen_pitch,'contour_reserve':.72,
                'alternating_materials':['closed ink stamp','line screen']}


def linked_cells(c):
    aa=2;image=Image.new('RGB',(c.w*aa,c.h*aa),tuple((INK[2]*255).astype(int)))
    draw=ImageDraw.Draw(image);leaves=quadtree_regions(c.rgb,c.scale)
    centers=np.array([[(xa+xb)/2,(ya+yb)/2] for xa,ya,xb,yb,_,_ in leaves])
    for xa,ya,xb,yb,mean,g in leaves:
        width=xb-xa;height=yb-ya
        fill=mean*.65+INK[0]*.35 if c.palette=='source' else INK[0]
        pad=min(width,height)*.035
        rect=((xa+pad)*aa,(ya+pad)*aa,(xb-pad)*aa,(yb-pad)*aa)
        draw.rounded_rectangle(rect,radius=max(0,min(width,height)*.12*aa),fill=tuple(np.rint(np.clip(fill,0,1)*255).astype(int)))
        inset=.15+.28*(1-g)
        if min(width,height)>3:
            hole=((xa+width*inset)*aa,(ya+height*inset)*aa,(xb-width*inset)*aa,(yb-height*inset)*aa)
            draw.rounded_rectangle(hole,radius=min(width,height)*.07*aa,fill=tuple((INK[2]*255).astype(int)))
    links=set()
    if len(centers)>1:
        tree=cKDTree(centers)
        for i,p in enumerate(centers):
            _,near=tree.query(p,k=min(4,len(centers)))
            xa,ya,xb,yb,_,_=leaves[i]
            ix=min(c.w-1,int(p[0]));iy=min(c.h-1,int(p[1]));angle=math.atan2(c.gy[iy,ix],c.gx[iy,ix])+math.pi/2
            for j in np.atleast_1d(near)[1:]:
                delta=centers[int(j)]-p;distance=np.linalg.norm(delta)
                if distance<max(xb-xa,yb-ya)*1.9 and abs(np.dot(delta/(distance+1e-6),[math.cos(angle),math.sin(angle)]))>.83:
                    links.add(tuple(sorted((i,int(j)))))
        for i,j in sorted(links):
            draw.line([tuple(centers[i]*aa),tuple(centers[j]*aa)],fill=tuple((INK[1]*255).astype(int)),width=max(1,round(c.unit*aa)))
    return np.asarray(image.resize((c.w,c.h),Image.Resampling.LANCZOS),np.float32)/255,{'cells':len(leaves),'links':len(links),'cavity_control':'local luminance'}


def hex_halftone(c):
    aa=2;image=Image.new('RGB',(c.w*aa,c.h*aa),tuple((INK[2]*255).astype(int)));draw=ImageDraw.Draw(image)
    radius=max(1.5,8*c.unit);pitchx=radius*1.5;pitchy=radius*math.sqrt(3);cells=0
    for column,x in enumerate(np.arange(-radius,c.w+radius,pitchx)):
        for y in np.arange(-radius,c.h+radius,pitchy)+(column%2)*pitchy/2:
            ix=int(np.clip(x,0,c.w-1));iy=int(np.clip(y,0,c.h-1))
            r=radius*math.sqrt(np.clip(1-c.sm[iy,ix],.025,.98))
            points=[((x+r*math.cos(j*math.pi/3))*aa,(y+r*math.sin(j*math.pi/3))*aa) for j in range(6)]
            fill=c.mark_color(iy,ix)
            draw.polygon(points,fill=tuple(np.rint(np.clip(fill,0,1)*255).astype(int)));cells+=1
    return np.asarray(image.resize((c.w,c.h),Image.Resampling.LANCZOS),np.float32)/255,{'hex_radius_px':radius,'cells':cells,'coverage':'radius proportional to sqrt(1-luminance)'}


def flow_stitch(c):
    aa=2;image=Image.new('RGB',(c.w*aa,c.h*aa),tuple((INK[2]*255).astype(int)));draw=ImageDraw.Draw(image)
    pitch=max(2,round(7*c.unit));count=0
    for y in range(pitch//2,c.h,pitch):
        for x in range(pitch//2,c.w,pitch):
            angle=math.atan2(c.gy[y,x],c.gx[y,x])+math.pi/2
            length=(1.4+3.6*(1-c.sm[y,x]))*c.unit
            dx=math.cos(angle)*length;dy=math.sin(angle)*length
            nx=-math.sin(angle)*c.unit*.65;ny=math.cos(angle)*c.unit*.65
            px=x+c.rng.uniform(-.35,.35)*c.unit;py=y+c.rng.uniform(-.35,.35)*c.unit
            fill=tuple(np.rint(np.clip(c.mark_color(y,x),0,1)*255).astype(int))
            for sign in (-1,1):
                draw.line([((px-dx+sign*nx)*aa,(py-dy+sign*ny)*aa),((px+dx+sign*nx)*aa,(py+dy+sign*ny)*aa)],fill=fill,width=max(1,round(c.unit*aa)))
            draw.line([((px-nx)*aa,(py-ny)*aa),((px+nx)*aa,(py+ny)*aa)],fill=fill,width=max(1,round(c.unit*aa)))
            count+=1
    return np.asarray(image.resize((c.w,c.h),Image.Resampling.LANCZOS),np.float32)/255,{'stitch_pitch_px':pitch,'stitches':count,'orientation':'smoothed image-gradient tangent; not optical flow'}


def hybrid_mezzotint(c):
    random=c.rng.random((c.h,c.w),dtype=np.float32)
    fine=normalize(array(blur(tensor(random),max(.35,.55*c.unit)))[...,0])
    coarse=normalize(array(blur(tensor(random),max(.7,2.3*c.unit)))[...,0])
    density=np.clip(1-c.sm,0,1)
    stochastic=(fine<density*.95).astype(np.float32)
    matrix=np.array([[0,2],[3,1]],np.float32)
    for _ in range(2):matrix=np.block([[4*matrix,4*matrix+2],[4*matrix+3,4*matrix+1]])
    matrix=(matrix+.5)/64
    pixel=max(1,round(c.unit))
    threshold=matrix[(c.y.astype(int)//pixel)%8,(c.x.astype(int)//pixel)%8]
    ordered=(threshold<density).astype(np.float32)
    marks=ordered*c.coherence+stochastic*(1-c.coherence)
    reserve=np.clip((c.edge-.28)*2.3,0,1)
    reserve=array(K.morphology.dilation(tensor(reserve),torch.ones(3,3)))[...,0]
    base=ink_palette(c.g) if c.palette=='ink' else c.rgb*.62+INK[2]*.38
    out=blend(base,INK[0],marks*.64*(1-reserve*.76))
    out=blend(out,INK[1],reserve*(.25+.50*coarse)*.75)
    return out,{'grain_sigmas_px':[max(.35,.55*c.unit),max(.7,2.3*c.unit)],'ordered_matrix':[8,8],
                'hybrid_gate':'structure-tensor coherence','contour_reserve':True}


def contour_strata(c):
    g=normalize(array(blur(c.gray,max(.5,4*c.unit)))[...,0]);phase=g*7;bands=np.floor(phase)
    length=np.hypot(c.gx,c.gy)+.01
    dx=-c.gy/length;dy=c.gx/length
    shift=np.sin(bands*2.35)*11*c.unit
    moved=resample(c,c.material(),c.x+dx*shift,c.y+dy*shift)
    out=blend(moved,c.material(),np.clip(.18+c.edge*.45,0,.68))
    rim=np.exp(-((phase-np.round(phase))/.055)**2)
    return blend(out,INK[2],rim*.38),{'levels':7,'maximum_tangent_shift_px':11*c.unit,'alpha_policy':'anchored separately from warped RGB'}


def directional_glass(c):
    ux=(c.x-(c.w-1)/2)/max(1,min(c.w,c.h)/2);vy=(c.y-(c.h-1)/2)/max(1,min(c.w,c.h)/2)
    angle=.32*np.sin(ux*2.7)+.26*np.cos(vy*2.4)
    pitch=max(3.,31*c.unit);phase=(c.x*np.cos(angle)+c.y*np.sin(angle))%pitch/pitch
    shift=(np.sin((phase-.5)*math.pi)*.5-(phase-.5))*pitch*1.7
    out=resample(c,c.material(),c.x+np.cos(angle)*shift,c.y+np.sin(angle)*shift)
    highlight=np.exp(-((phase-.22)/.026)**2);shade=np.exp(-((phase-.78)/.07)**2)
    out=out*(1-shade[...,None]*.10)+highlight[...,None]*.065
    return out,{'reed_pitch_px':pitch,'director':'analytic smoothly varying field','alpha_policy':'anchored separately from warped RGB'}


def cell_facets(c):
    cell=max(4,round(57*c.unit));mx=c.x.copy();my=c.y.copy();labels=np.full((c.h,c.w),-1,np.int32)
    shade=np.ones((c.h,c.w),np.float32);number=0
    for y in range(0,c.h,cell):
        for x in range(0,c.w,cell):
            x1=min(c.w,x+cell);y1=min(c.h,y+cell)
            yy=c.y[y:y1,x:x1];xx=c.x[y:y1,x:x1]
            local=(xx-x)/max(1,x1-x)+(yy-y)/max(1,y1-y)>1
            for side in (0,1):
                mask=local==side
                dx=c.rng.uniform(-1,1)*6*c.unit;dy=c.rng.uniform(-1,1)*6*c.unit
                mx[y:y1,x:x1][mask]+=dx;my[y:y1,x:x1][mask]+=dy
                labels[y:y1,x:x1][mask]=number
                shade[y:y1,x:x1][mask]=.88+.17*c.rng.random();number+=1
    out=resample(c,c.material(),mx,my)*shade[...,None]
    borders=(maximum_filter(labels,3)!=minimum_filter(labels,3)).astype(np.float32)
    out=blend(out,INK[2],borders*.42)
    return out,{'cell_size_px':cell,'triangular_facets':number,'refraction_range_px':6*c.unit}


TECHNIQUES = {
    'quadtree-engraving':(quadtree_engraving,'ink',['color.rgb_to_grayscale','enhance.integral_image','filters.spatial_gradient'],['half-open adaptive partition','directional line rasterization']),
    'region-hatching':(region_hatching,'source',['color.rgb_to_lab','color.lab_to_rgb','filters.gaussian_blur2d'],['seeded CIELAB k-means','regional hatching']),
    'ink-strata':(ink_strata,'source',['color.rgb_to_grayscale','geometry.transform.remap','morphology.closing','filters.sobel'],['oblique alternating stamp/screen bands','local registration offsets','clean boundary reserves']),
    'linked-cells':(linked_cells,'source',['enhance.integral_image','filters.spatial_gradient'],['adaptive hollow cells','orientation-linked cell graph']),
    'hex-halftone':(hex_halftone,'ink',['color.rgb_to_grayscale','filters.gaussian_blur2d'],['hexagonal area coverage','antialiased polygon rasterization']),
    'flow-stitch':(flow_stitch,'source',['filters.spatial_gradient','filters.gaussian_blur2d'],['gradient-tangent paired stitches','digital thread appearance; no physical embroidery']),
    'hybrid-mezzotint':(hybrid_mezzotint,'ink',['filters.gaussian_blur2d','filters.spatial_gradient','morphology.dilation'],['seeded correlated grain','contour reserves']),
    'contour-strata':(contour_strata,'source',['filters.gaussian_blur2d','filters.spatial_gradient','geometry.transform.remap'],['isoluminance strata','tangential RGB displacement']),
    'directional-glass':(directional_glass,'source',['geometry.transform.remap'],['regional analytic lens field','graphic refraction and highlights; not physical glass']),
    'cell-facets':(cell_facets,'source',['geometry.transform.remap'],['seeded triangular cell maps','facet shading and seams']),
}


def apply(rgb,key,*,seed=0,scale=1.,palette=None,strength=1.):
    if key not in TECHNIQUES:raise ValueError(f'Unknown technique: {key}')
    if rgb.ndim!=3 or rgb.shape[2]!=3 or min(rgb.shape[:2])<1:raise ValueError('Expected a nonempty HxWx3 RGB array.')
    if not np.isfinite(rgb).all():raise ValueError('Input RGB contains nonfinite values.')
    function,default,native,custom=TECHNIQUES[key]
    resolved=palette or default
    if resolved not in ('source','ink'):raise ValueError('Palette must be source or ink.')
    if not math.isfinite(scale) or scale<=0:raise ValueError('Scale must be finite and positive.')
    if not math.isfinite(strength) or not 0<=strength<=1:raise ValueError('Strength must be between zero and one.')
    if not 0<=seed<2**63:raise ValueError('Seed must be in [0, 2**63).')
    c=Context(np.clip(rgb,0,1).astype(np.float32),scale,seed,resolved)
    styled,parameters=function(c)
    if not np.isfinite(styled).all():raise ValueError(f'{key} produced nonfinite RGB values.')
    out=np.clip(c.rgb*(1-strength)+styled*strength,0,1).astype(np.float32)
    return out,{'technique':key,'seed':seed,'palette':resolved,
                'parameters':{**parameters,'scale':scale,'style_unit_px':c.unit,'strength':strength},
                'native_operations':native,'custom_operations':custom}
