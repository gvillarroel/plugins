/* Seekable Canvas 2D components. Load as a classic script, including from file://. */
(() => {
  "use strict";
  const clamp = x => Math.max(0, Math.min(1, x));
  const ease = x => { x = clamp(x); return x * x * (3 - 2 * x); };
  const phase = (time, start, seconds) => seconds > 0 ? ease((time - start) / seconds) : Number(time >= start);
  // The default Line World colorset1 on a white field. Photographs and caller-supplied
  // painting callbacks keep their original colors. Fractional coverage on glyph and
  // path edges is canvas antialiasing, never a translucent graphic surface.
  const theme = {paper:"#ffffff", light:"#ffffff", ink:"#333e48", accent:"#9e1b32",
    muted:"#696969", neutral:"#b5b5b5", quiet:"#e7e7e7", line:"#cfcfcf", font:"Arial, sans-serif"};
  const transitions = ["cut", "dissolve", "tint-bridge", "iris-fill", "iris-close", "shutter-close", "step-blocks", "band-pass", "push-down", "push-left"];
  const diagrams = Object.freeze(["field-packing", "layer-preview", "isometric-layers", "module-transfer",
    "vertex-remap", "command-lanes", "shared-host", "split-clock", "pass-strip", "import-footprint", "contact-transfer", "object-route",
    "ring-handoff", "bit-probe", "message-ladder", "detail-callout", "radix-ladder", "token-gate", "resolution-fan", "queue-router", "staged-network", "interval-refinement", "trajectory-trace", "rigid-rearrangement", "pivot-rotation"]);
  const artifacts = ["speaker-id", "question-card", "caption-overlay", "editorial-split", "slide-pip", "insight-band", "dashboard-stack", "icon-card", "disc-endcard", "chart-focus", "corner-card", "orbital-caption", "numbered-step", "keypoint-list", "chart-ring",
    "guest-grid", "type-title", "cta-card", "brand-slate", "metric-callout", "concept-diagram", "circle-window", "data-chart", ...diagrams];
  const isolated = new WeakMap();

  function saved(ctx, draw) {
    ctx.save();
    try { draw(); } finally { ctx.restore(); }
  }
  function rect(ctx, x, y, w, h, color) {
    ctx.fillStyle = color; ctx.fillRect(x, y, w, h);
  }
  function disc(ctx, x, y, r, color) {
    ctx.beginPath(); ctx.arc(x, y, Math.max(0, r), 0, 2 * Math.PI);
    ctx.fillStyle = color; ctx.fill();
  }
  function clip(ctx, drawPath, drawLayer) {
    saved(ctx, () => { ctx.beginPath(); drawPath(); ctx.clip(); drawLayer(); });
  }
  function text(ctx, value, x, y, size, color, options = {}) {
    if (!(size > 0) || value == null || value === "") return;
    const family = options.font || theme.font, weight = options.weight || 400;
    const lines = String(value).split("\n");
    ctx.font = weight + " " + size + "px " + family;
    if (options.width > 0) {
      const longest = Math.max(...lines.map(line => ctx.measureText(line).width));
      if (longest > options.width) size *= options.width / longest;
    }
    const leading = options.leading || 1.16;
    if (options.height > 0) size = Math.min(size,options.height / (1+(lines.length-1)*leading));
    ctx.font = weight + " " + size + "px " + family;
    ctx.textAlign = options.align || "left"; ctx.textBaseline = "middle"; ctx.fillStyle = color;
    const gap = size * leading;
    const draw = () => lines.forEach((line,i) => ctx.fillText(line,x,y+(i-(lines.length-1)/2)*gap));
    const reveal = options.reveal ?? 1;
    if (reveal >= 1) draw();
    else if (reveal > 0) {
      const band = lines.length*gap + size*.5;
      // Uncover the type in place; already-visible areas keep their exact fill.
      clip(ctx, () => ctx.rect(x-ctx.canvas.width,y-band/2,2*ctx.canvas.width,band*reveal),draw);
    }
  }
  function solidPaint(ctx, value, fallback) {
    if (typeof value !== "string") return fallback;
    ctx.save();
    ctx.fillStyle = fallback;
    ctx.fillStyle = value;
    const parsed = ctx.fillStyle;
    ctx.restore();
    // Canvas normalizes opaque CSS named, rgb, hsl and hex colors to six-digit sRGB.
    return /^#[0-9a-f]{6}$/i.test(parsed) ? parsed : fallback;
  }
  function resolveTheme(ctx, options={}) {
    if (!options.theme) return theme;
    const colors = {...theme};
    for (const token of Object.keys(theme)) {
      if (token === "font") colors.font = options.theme.font || theme.font;
      else if (options.theme[token]) colors[token] = solidPaint(ctx,options.theme[token],theme[token]);
    }
    return colors;
  }
  function foreground(fill, c) {
    const luminance = hex => {
      const rgb = [1,3,5].map(offset => parseInt(hex.slice(offset,offset+2),16)/255)
        .map(v => v <= .04045 ? v / 12.92 : ((v+.055)/1.055)**2.4);
      return rgb[0]*.2126 + rgb[1]*.7152 + rgb[2]*.0722;
    };
    const l = luminance(fill);
    const contrast = color => {const other = luminance(color);return (Math.max(l,other)+.05)/(Math.min(l,other)+.05);};
    return contrast(c.ink) >= contrast(c.light) ? c.ink : c.light;
  }
  function inBox(ctx, source, x, y, w, h, faceBox) {
    if (!source || w <= 0 || h <= 0) return;
    clip(ctx, () => ctx.rect(x, y, w, h), () => {
      ctx.translate(x, y);
      if (typeof source === "function") { source(ctx, w, h); return; }
      const item = source.lineWorldMedia ? source.element : source;
      if (!item) return;
      const iw = item.videoWidth || item.naturalWidth || item.width;
      const ih = item.videoHeight || item.naturalHeight || item.height;
      if (!(iw > 0 && ih > 0)) return;
      if (faceBox) {
        const [left, top, width, height] = faceBox;
        const scale = Math.min(.70*h/(height*ih),.64*w/(width*iw));
        const centerX = (left + width/2)*iw*scale;
        const centerY = (top + height/2)*ih*scale;
        rect(ctx,0,0,w,h,theme.quiet);
        ctx.drawImage(item, w/2-centerX, h/2-centerY, iw*scale, ih*scale);
        return;
      }
      const contain=source.fit==="contain", s=(contain?Math.min:Math.max)(w/iw,h/ih);
      const [fx,fy]=source.focal || [.5,.5];
      const align=(size,scaled,focus)=>contain?(size-scaled)/2:
          Math.min(0,Math.max(size-scaled,size/2-focus*scaled));
      if(contain) rect(ctx,0,0,w,h,theme.paper);
      ctx.drawImage(item,align(w,iw*s,fx),align(h,ih*s,fy),iw*s,ih*s);
    });
  }
  function composite(ctx, source, w, h, opacity) {
    if (opacity <= 0) return;
    let target = isolated.get(ctx);
    if (!target || target.width !== w || target.height !== h) {
      target = document.createElement("canvas"); target.width = w; target.height = h;
      isolated.set(ctx, target);
    }
    const other = target.getContext("2d");
    other.clearRect(0, 0, w, h);
    inBox(other, source, 0, 0, w, h);
    saved(ctx, () => { ctx.globalAlpha *= opacity; ctx.drawImage(target, 0, 0, w, h); });
  }
  function sampleTrack(progress, keys) {
    const i = keys.findIndex(([position]) => position >= progress);
    if (i <= 0) return keys[i === 0 ? 0 : keys.length - 1][1];
    const [a, v] = keys[i - 1], [b, next] = keys[i];
    return v + (next - v) * (progress - a) / (b - a);
  }
  function transition(ctx, id, progress, from, to, options = {}) {
    if (!transitions.includes(id)) throw new RangeError("Unknown transition: " + id);
    if (!Number.isFinite(progress)) throw new TypeError("progress must be finite");
    const p = clamp(progress), w = options.width || ctx.canvas.width, h = options.height || ctx.canvas.height;
    const c = resolveTheme(ctx,options), reference = options.mode === "reference";
    const layer = src => inBox(ctx, src, 0, 0, w, h);
    if (p === 0 || p === 1 || id === "cut") {
      layer(p === 1 || (id === "cut" && p >= .5) ? to : from); return;
    }
    saved(ctx, () => {
      if (id !== "push-left" && id !== "push-down" && id !== "iris-close") layer(from);
      switch (id) {
        case "dissolve": {
          if (reference) {composite(ctx,to,w,h,p);break;}
          // Solid adaptation: the diagonal reveal advances once. There is no
          // checkerboard shimmer and the two complete images never crossfade.
          const slant=.20*w, right=(w+slant)*ease(p);
          clip(ctx,()=>{
            ctx.moveTo(-slant,0);ctx.lineTo(right,0);ctx.lineTo(right-slant,h);ctx.lineTo(-slant,h);ctx.closePath();
          },()=>layer(to));break;
        }
        case "tint-bridge":
          if (!reference) {
            const band=.045*w, edge=(w+band)*ease(p);
            clip(ctx,()=>ctx.rect(0,0,Math.max(0,edge-band),h),()=>layer(to));
            rect(ctx,Math.max(0,edge-band),0,Math.min(band,edge),h,c.accent);
            break;
          }
          if (p < .5) {
            ctx.globalAlpha *= ease(p*2); rect(ctx,0,0,w,h,c.accent);
          } else {
            rect(ctx,0,0,w,h,c.accent); composite(ctx,to,w,h,ease((p-.5)*2));
          }
          break;
        case "iris-fill":
        case "iris-close": {
          const closing = id === "iris-close";
          const x = w*((options.x ?? .5) + (closing ? 0 : (options.drift ?? -.025)*p)), y = h*(options.y ?? .5);
          const radius = Math.hypot(Math.max(x,w-x), Math.max(y,h-y));
          const amount = closing ? 1-ease(p) : sampleTrack(p,[[0,0],[.125,.044],[.25,.122],[.375,.226],[.5,.36],[.625,.507],[.75,.663],[.875,.82],[1,1]]);
          if (closing) layer(to);
          clip(ctx, () => ctx.arc(x,y,radius*amount,0,Math.PI*2), () => layer(closing ? from : to)); break;
        }
        case "shutter-close": {
          const seam = clamp(options.y ?? 150/360);
          const top = h*seam*sampleTrack(p,[[0,0],[4/18,0],[6/18,.22],[9/18,.66],[13/18,.92],[17/18,1],[1,1]]);
          const bottom = h*(1-seam)*sampleTrack(p,[[0,0],[1/18,.029],[3/18,.176],[6/18,.643],[9/18,.852],[13/18,.957],[17/18,.995],[1,1]]);
          clip(ctx, () => { ctx.rect(0,0,w,top); ctx.rect(0,h-bottom,w,bottom); }, () => layer(to)); break;
        }
        case "push-left": {
          const offset = Math.round(ease(p)*w);
          inBox(ctx,from,-offset,0,w,h); inBox(ctx,to,w-offset,0,w,h); break;
        }
        case "push-down": {
          const y = Math.round(ease(p)*h);
          inBox(ctx,from,0,y,w,h); inBox(ctx,to,0,y-h,w,h); break;
        }
        case "step-blocks": {
          // Leave the outgoing plane visible behind each staggered strip.
          if (reference) rect(ctx,0,0,w,h,c.light);
          clip(ctx, () => {
            for (let i=0;i<5;i++) {
              const reveal = phase(p, .07+i*.085, .55);
              ctx.rect(0, Math.floor(h*i/5), w*reveal, Math.ceil(h/5)+1);
            }
          }, () => layer(to)); break;
        }
        case "band-pass": {
          const band = reference ? .85 : .08;
          const front = Math.min(1,ease(p)*(1+band))*h;
          const back = Math.max(0,ease(p)*(1+band)-band)*h;
          clip(ctx, () => ctx.rect(0,0,w,back), () => layer(to));
          rect(ctx,0,back,w,front-back,c.accent); break;
        }
      }
    });
  }
  // Keep comparable bars together in groups of two or three. Previously
  // drawn bars stay in place while the next measurements arrive.
  function barGroup(index, count) {
    const groups=Math.ceil(count/3);
    if (groups<=1) return 0;
    const short=Math.floor(count/groups), longGroups=count%groups;
    const longBars=(short+1)*longGroups;
    return index<longBars ? Math.floor(index/(short+1)) : longGroups+Math.floor((index-longBars)/short);
  }
  const barGroupPause=.25;
  const percentNumber=new Intl.NumberFormat("es",{useGrouping:false,maximumSignificantDigits:17});
  const percentageLabel=value=>percentNumber.format(value)+" %";

  function chart(ctx, w, h, series, c=theme, options={}) {
    rect(ctx,0,0,w,h,c.paper);
    const entries=(series || []).map((value,index)=>({value,index})).filter(item=>Number.isFinite(item.value));
    if (!entries.length) return;
    const values=entries.map(item=>item.value);
    const [low,high]=options.domain || [Math.min(0,...values),Math.max(0,...values)];
    const span=high-low||1, step=w*.85/entries.length, plotTop=h*(options.unit ? .24 : .12);
    const plotBottom=h*(options.labels?.length ? .77 : .88), plotHeight=plotBottom-plotTop;
    const baseline=plotTop+plotHeight*(high===low?1:high/span);
    if(options.unit) text(ctx,options.unit,.07*w,.08*h,.088*h,c.muted,{font:c.font,width:.84*w});
    entries.forEach(({value,index},i) => {
      const progress=options.barProgress ? options.barProgress(i,entries.length) : (options.progress??1);
      const x=w*.075+(i+.5)*step, top=baseline-plotHeight*value/span*progress;
      rect(ctx,x-.3*step,Math.min(top,baseline),step*.6,Math.abs(top-baseline),index===options.highlightIndex?c.accent:c.neutral);
      if (options.labels?.length) {
        if(progress>.96)
          text(ctx,String(value),x,top+(value<0?.05:-.05)*h,.084*h,c.ink,{font:c.font,align:"center",width:.95*step});
        text(ctx,options.labels[index],x,.94*h,.078*h,c.ink,{font:c.font,align:"center",width:.95*step});
      }
    });
  }
  function lineIcon(ctx, x, y, size, points, progress, color) {
    if (!points || points.length<2) return;
    const lengths = points.slice(1).map(([px,py],i) => Math.hypot(px-points[i][0],py-points[i][1]));
    let left = clamp(progress) * lengths.reduce((sum,len)=>sum+len,0);
    ctx.beginPath(); ctx.moveTo(x+points[0][0]*size, y+points[0][1]*size);
    for (let i=0;i<lengths.length && left>0;i++) {
      const [ax,ay]=points[i], [bx,by]=points[i+1], t=Math.min(1,left/(lengths[i]||1));
      ctx.lineTo(x+(ax+(bx-ax)*t)*size,y+(ay+(by-ay)*t)*size); left-=lengths[i];
    }
    ctx.strokeStyle=color; ctx.lineWidth=size*.022; ctx.lineJoin="round"; ctx.lineCap="round"; ctx.stroke();
  }

  // 'time' is elapsed scene time in seconds. 'props' contains user content.
  function artifact(ctx, id, time, props = {}, options = {}) {
    if (!artifacts.includes(id)) throw new RangeError("Unknown artifact: " + id);
    if (!Number.isFinite(time)) throw new TypeError("time must be finite");
    if (time < 0) return;
    const w=options.width || ctx.canvas.width, h=options.height || ctx.canvas.height, c=resolveTheme(ctx,options);
    if (diagrams.includes(id)) {
      if (!globalThis.LineWorldDiagrams) throw new Error("Load diagram-motion.js before drawing " + id);
      saved(ctx, () => globalThis.LineWorldDiagrams.draw(ctx,id,time,props,{width:w,height:h,theme:c}));
      return;
    }
    const reference=options.mode==="reference";
    const paint=(value,fallback)=>solidPaint(ctx,value,fallback);
    const title=props.title || "", detail=props.detail || "", mid={align:"center",font:c.font};
    const label=(value,x,y,size,color,opts={})=>text(ctx,value,x*w,y*h,size*h,color,{font:c.font,...opts});
    const media=()=>inBox(ctx, props.media,0,0,w,h);
    saved(ctx, () => {
      switch(id) {
        case "speaker-id": {
          if(options.deferMediaLabels) break;
          const x=(props.side==="left"?.05:.53)*w, y=.655*h;
          const visible=Number.isFinite(props.exitAt)?1-phase(time,props.exitAt,props.exitDuration??.55):1;
          const width=.42*w, height=.30*h, intro=phase(time,-.02,.45);
          clip(ctx,()=>ctx.rect(x,y,width,height*visible),()=>{
            if (!reference) rect(ctx,x,y,width*intro,height,c.paper);
            rect(ctx,x,y,.006*w,height*intro,reference?c.light:c.accent);
            const ink=reference?c.light:c.ink;
            text(ctx,title,x+.02*w,.735*h,.080*h,ink,{weight:650,width:width-.04*w,font:c.font,reveal:phase(time,.14,.33)});
            const lines=String(detail).split("\n");
            const roleSize=Math.min(.064,.142/Math.max(2,lines.length));
            text(ctx,detail,x+.02*w,.853*h,roleSize*h,ink,
              {width:width-.04*w,height:.178*h,font:c.font,reveal:phase(time,.59,.40)});
          });break;
        }
        case "question-card": {
          if(options.deferMediaLabels) break;
          const portrait=h>w, u=phase(time,0,.62), x=(portrait?.055:.05)*w, y=(portrait?.77:.68)*h;
          const bw=(portrait?.89:.40)*w, bh=(portrait?.155:.21)*h, fill=paint(props.fill,c.paper);
          clip(ctx,()=>ctx.rect(x,y,bw*u,bh),()=>{
            rect(ctx,x,y,bw,bh,fill);rect(ctx,x,y,.005*w,bh,c.accent);
            if(!portrait || u>=1)
              text(ctx,title,x+.022*w,y+bh*.5,.046*h,foreground(fill,c),{font:c.font,weight:600,width:bw-.05*w,height:bh*.78});
          });break;
        }
        case "caption-overlay": {
          media();
          if(options.deferMediaLabels) break;
          const rows=String(title).split("\n");
          const size=Math.min(.069*h,.23*h/(rows.length*1.18));
          ctx.font="600 "+size+"px "+c.font;
          const bw=Math.min(.86*w,Math.max(...rows.map(line=>ctx.measureText(line).width))+.06*w);
          const bh=rows.length*size*1.18+.052*h, x=(w-bw)/2;
          const subjectY=props.media?.focal?.[1]??.5;
          const position=props.position || (props.media?.lineWorldMedia ? (subjectY>.60?"top":"bottom") : "center");
          const y=position==="bottom"?h-bh-.065*h:position==="top"?.065*h:(h-bh)/2;
          const fill=paint(props.scrim,c.paper);
          rect(ctx,x,y,bw*phase(time,0,.46),bh,fill);
          if(time>=.46)
            text(ctx,title,w/2,y+bh/2,size,foreground(fill,c),{...mid,weight:600,width:bw-.04*w,height:bh-.035*h});
          break;
        }
        case "editorial-split": {
          rect(ctx,0,0,w,h,reference?c.accent:c.paper);
          const share=Math.min(.78,Math.max(.18,props.share??.5)), x=w*(1-share*phase(time,0,props.moveDuration??1.2));
          inBox(ctx,props.media,x,0,w*share,h);
          const available=w*(1-share-.10), entry=phase(time,.12,.65);
          label(title,.055,.45,.074,reference?c.light:c.ink,{weight:650,width:available,height:.27*h,reveal:entry});
          label(detail,.055,.66,.04,reference?c.light:c.muted,{width:available,height:.14*h,reveal:entry}); break;
        }
        case "slide-pip": {
          const portrait=h>w;
          const box=reference?[.858,.049,.122,.126]:portrait?[.70,.055,.25,.22]:[.74,.08,.20,.20];
          const [x,y,bw,bh]=props.box || box;
          rect(ctx,0,0,w,h,c.paper);
          if(!props.presenter) {
            inBox(ctx,props.slide,0,0,w,h);
            inBox(ctx,props.media,w*x,h*y,w*bw,h*bh,props.faceBox);
            break;
          }
          const entry=portrait?[.14,.13,.72,.52]:[.52,.13,.42,.74];
          const progress=phase(time,1.40,.78);
          const interpolate=(start,end)=>start+progress*(end-start);
          if(time<1.40) label(props.presenter,portrait?.50:.07,portrait?.735:.50,portrait?.061:.078,c.ink,
            {align:portrait?"center":"left",weight:650,width:(portrait?.78:.42)*w,height:.24*h});
          if(progress>=1) {
            const reveal=phase(time,2.18,.40);
            clip(ctx,()=>ctx.rect(0,0,w,h*reveal),()=>inBox(ctx,props.slide,0,0,w,h));
          }
          inBox(ctx,props.media,w*interpolate(entry[0],x),h*interpolate(entry[1],y),
            w*interpolate(entry[2],bw),h*interpolate(entry[3],bh),props.faceBox);
          break;
        }
        case "insight-band": {
          media(); if(options.deferMediaLabels) break;
          const bottom=props.side==="bottom", y=bottom?.69:0;
          const fill=paint(props.fill,reference?c.accent:c.paper), ink=foreground(fill,c), enter=phase(time,0,.64);
          rect(ctx,0,y*h,w,.31*h,fill);
          const kicker=Boolean(props.kicker);
          if(kicker) label(props.kicker,.055,y+.064,.052,ink,{width:.89*w,reveal:enter});
          label(title,.055,y+(kicker?.150:detail?.109:.155),.076,ink,
            {weight:650,width:.89*w,height:.105*h,reveal:enter});
          label(detail,.055,y+(kicker?.245:.220),.062,ink,
            {width:.89*w,height:.085*h,reveal:enter}); break;
        }
        case "dashboard-stack": {
          rect(ctx,0,0,w,h,c.paper);
          const cards=props.cards||[],beat=props.beat??2.8;
          const portrait=h>w, columns=portrait?1:Math.max(1,Math.ceil(Math.sqrt(cards.length)));
          const rows=Math.ceil(cards.length/columns);
          const cellW=.92/columns, cellH=.84/Math.max(1,rows);
          const domains=new Map();
          for(const item of cards) {
            if(item.media || !Array.isArray(item.values)) continue;
            const key=item.unit||"", previous=domains.get(key)||[0,0];
            domains.set(key,[Math.min(previous[0],...item.values),Math.max(previous[1],...item.values)]);
          }
          let nextStart=0;
          cards.forEach((item,i)=>{
            const groups=item.media ? 1 : Math.max(1,Math.ceil((item.values?.length??0)/3));
            const groupSeconds=Math.max(groups>1?.8:0,Math.min(.9,beat*.28));
            const start=nextStart;
            nextStart+=Math.max(beat,groups*groupSeconds+(groups-1)*barGroupPause+.4);
            if(time<start)return;
            const arrive=phase(time,start,groupSeconds);
            const x=(.04+(i%columns)*cellW)*w, y=(.13+Math.floor(i/columns)*cellH)*h;
            const cw=w*(cellW-.035), ch=h*(cellH-(portrait?.17*cellH:.11));
            text(ctx,item.title,x,y-h*.033,h*.036,c.ink,{font:c.font,width:cw});
            const params={...item,domain:domains.get(item.unit||""),progress:arrive};
            if(groups>1) params.barProgress=(i,n)=>phase(time,start+barGroup(i,n)*(groupSeconds+barGroupPause),groupSeconds);
            inBox(ctx,item.media||((sub,sw,sh)=>chart(sub,sw,sh,item.values,c,params)),x,y,cw,ch);
          }); break;
        }
        case "icon-card": {
          rect(ctx,0,0,w,h,c.paper);
          if (reference) rect(ctx,0,h*.91,w,h*.09,c.accent);
          const right=props.side==="right", ix=w*(right?.67:.10), tx=right?.08:.47;
          const size=Math.min(.43*h,.32*w);
          lineIcon(ctx,ix,h>w?.53*h-size/2:.27*h,size,props.points,phase(time,0,.84),c.accent);
          rect(ctx,w*tx,h*.28,.075*w*phase(time,0,.40),h*.009,c.accent);
          label(title,tx,.53,.077,c.ink,{weight:650,width:.44*w,height:.5*h,reveal:phase(time,.12,.68)}); break;
        }
        case "disc-endcard": {
          const fill=paint(props.fill,reference?c.accent:c.paper),face=paint(props.discFill,reference?c.light:c.accent);
          rect(ctx,0,0,w,h,fill);
          const hold=props.hold??(reference?1.45:2.4),move=props.moveDuration??(reference?.47:1.4);
          const settle=phase(time,hold,move),enter=phase(time,0,props.enterDuration??.70);
          const scale=Math.min(h,.44*w/.31);
          const r=scale*(.31-.115*settle)*enter,cy=h*(.50+((props.finalY??.34)-.5)*settle);
          if(r>0){disc(ctx,w*.5,cy,r,face);
            if(props.mark) inBox(ctx,props.mark,w*.5-r*.67,cy-r*.43,r*1.34,r*.86);
            else text(ctx,title,w*.5,cy,r*.55,foreground(face,c),{...mid,weight:650,width:r*1.53,height:r*1.2});}
          label(detail,.5,.76,props.detailScale??.052,foreground(fill,c),{...mid,width:.8*w,height:.16*h,reveal:phase(time,hold+move*.78,.55)});break;
        }
        case "chart-focus": {
          const box=props.box||[.18,.26,.49,.40];
          const pad=(props.padding??.055)*h;
          const x=Math.max(1,box[0]*w-pad),y=Math.max(1,box[1]*h-pad);
          const bw=Math.min(w-1,(box[0]+box[2])*w+pad)-x,bh=Math.min(h-1,(box[1]+box[3])*h+pad)-y;
          ctx.strokeStyle=c.accent;ctx.lineWidth=.006*h;
          ctx.setLineDash([2*(bw+bh),2*(bw+bh)]);
          ctx.lineDashOffset=2*(bw+bh)*(1-phase(time,0,.8));
          ctx.strokeRect(x,y,bw,bh);break;
        }
        case "corner-card": {
          rect(ctx,0,0,w,h,reference?c.accent:c.paper);
          rect(ctx,0,0,.13*w,.18*h,reference?c.ink:c.quiet);
          rect(ctx,.90*w,.79*h,.10*w,.21*h,reference?c.ink:c.quiet);
          rect(ctx,.032*w,.88*h,.07*w,.12*h,reference?c.light:c.neutral);
          rect(ctx,.27*w,.40*h,.005*w,.18*h,reference?c.light:c.accent);
          label(title,.30,.49,.072,reference?c.light:c.ink,{weight:600,width:.58*w,height:.34*h});break;
        }
        case "orbital-caption": {
          if(options.deferMediaLabels) break;
          const cx=w*(props.x??.72), cy=h*(props.y??.40);
          if(props.anchor) {
            const [ax,ay]=[props.anchor[0]*w,props.anchor[1]*h];
            const delay=props.delay??2;
            const travel=phase(time,0,Math.max(.35,delay));
            const scale=Math.min(h,1.05*w);
            const radius=.122*scale, dx=cx-ax, dy=cy-ay;
            const distance=Math.hypot(dx,dy), length=Math.max(0,distance-radius);
            const fraction=length*travel/(distance||1);
            const endX=ax+dx*fraction, endY=ay+dy*fraction;
            for(const [ink,width] of [[c.paper,.017],[c.ink,.007]]) {
              ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(endX,endY);
              ctx.strokeStyle=ink;ctx.lineWidth=width*scale;ctx.lineCap="round";ctx.stroke();
            }
            disc(ctx,ax,ay,.018*scale,c.paper);
            disc(ctx,ax,ay,.010*scale,c.accent);
            const entry=phase(time,Math.max(.35,delay),.45), r=entry*radius;
            if(r>0) {
              const fill=paint(props.fill,c.paper);
              disc(ctx,cx,cy,r,fill);
              ctx.strokeStyle=c.ink;ctx.lineWidth=.005*scale;ctx.stroke();
              text(ctx,title,cx,cy,.069*scale,foreground(fill,c),{...mid,weight:650,
                width:1.72*radius,height:1.40*radius,reveal:entry});
            }
            break;
          }
          const delay=props.delay??2.0, travel=phase(time,0,Math.max(.35,delay));
          const r=h*.18*phase(time,delay,.68), x0=.12*w, y0=.70*h;
          const arc = u => [x0+(cx-x0)*u,y0+(cy-y0)*u+.13*h*Math.sin(Math.PI*u)];
          ctx.beginPath();ctx.moveTo(x0,y0);
          for(let i=1;i<=40;i++) ctx.lineTo(...arc(travel*i/40));
          ctx.strokeStyle=c.muted;ctx.lineWidth=Math.max(1,.0025*h);ctx.stroke();
          disc(ctx,...arc(travel),.013*h,c.accent);
          if(r>0){
            const face=paint(props.fill,c.paper);
            disc(ctx,cx,cy,r,face);ctx.strokeStyle=c.muted;ctx.lineWidth=.0025*h;ctx.stroke();
            text(ctx,title,cx,cy,r*.33,foreground(face,c),{...mid,width:r*1.62,height:r*1.4});
          }break;
        }
        case "numbered-step": {
          rect(ctx,0,0,w,h,c.paper);
          const scale=Math.min(h,.16*w/.22), x=.22*w,y=.48*h,r=.22*scale;
          ctx.beginPath();ctx.arc(x,y,r,-Math.PI/2,-Math.PI/2+Math.PI*1.86*phase(time,0,.56));
          ctx.lineWidth=.009*scale;ctx.strokeStyle=c.ink;ctx.stroke();
          ctx.font="600 "+r*1.37+"px "+c.font;ctx.textAlign="center";ctx.textBaseline="middle";
          ctx.lineWidth=.004*scale;ctx.strokeStyle=c.accent;ctx.strokeText(String(props.number??1),x,y);
          label(title,.40,.50,.071,c.ink,{width:.54*w,height:.48*h,weight:600,reveal:phase(time,.10,.65)}); break;
        }
        case "keypoint-list": {
          const items=props.items||[], x=props.x??.11, top=props.y??.28;
          const spacing=Math.min(props.spacing??.16,(.91-top)/Math.max(1,items.length-1));
          items.forEach((item,i)=>saved(ctx,()=>{
            const p=phase(time,props.starts?.[i]??i*(props.beat??1.5),.60);
            const y=top+i*spacing;
            const isObject=item && typeof item==="object";
            disc(ctx,w*x,h*y,h*.009*p,isObject&&item.accent?c.accent:c.neutral);
            label(isObject?item.text:item,x+.032,y,Math.min(.052,spacing*.7),isObject&&item.accent?c.accent:c.ink,
              {width:w*(1-x-.09),height:h*spacing*.85,weight:600,reveal:p});
          }));break;
        }
        case "chart-ring": {
          const progress=phase(time,0,props.duration??1.8), val=clamp((props.value??0)/100);
          const scale=Math.min(h,.43*w/.241);
          const x=w*.5,y=h*(props.label?.44:.5),r=.22*scale, fractional=props.fractional??!reference;
          ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.strokeStyle=paint(props.track,c.quiet);ctx.lineWidth=.042*scale;ctx.stroke();
          ctx.beginPath();ctx.arc(x,y,r,-Math.PI/2,-Math.PI/2-Math.PI*2*(fractional?val:1)*progress,true);ctx.strokeStyle=paint(props.fill,c.accent);ctx.stroke();
          if(val>0) {
            const angle=-Math.PI/2-Math.PI*2*(fractional?val:1)*progress;
            const guideRadius=r+.045*scale;
            disc(ctx,x+guideRadius*Math.cos(angle),y+guideRadius*Math.sin(angle),.012*scale,c.ink);
          }
          text(ctx,percentageLabel(props.value??0),x,y,.13*scale,c.ink,{...mid,weight:650,width:1.62*r,height:.84*r});
          label(props.label,.5,.77,.045,c.ink,{...mid,width:.80*w,height:.13*h});break;
        }
        case "guest-grid": {
          rect(ctx,0,0,w,h,c.paper);
          const guests=(props.guests || []).slice(0,4);
          const videos=guests.filter(({media})=>media?.kind==="video" || media?.tagName==="VIDEO").length;
          const fixedNames=options.completeGuestNames || guests.length+videos>3;
          const columns=Math.min(2,guests.length);
          const rows=Math.ceil(guests.length/2);
          const gap=.009*w;
          const cellWidth=(.88*w-gap*(columns-1))/Math.max(1,columns);
          const cellHeight=Math.min(.86*h/Math.max(1,rows)-gap/2,cellWidth*.93);
          const top=(h-rows*cellHeight-(rows-1)*gap)/2;
          guests.forEach((guest,index)=>{
            const row=Math.floor(index/2);
            const rowCount=Math.min(columns,guests.length-row*2);
            const x=(w-cellWidth*rowCount-gap*(rowCount-1))/2+(index%2)*(cellWidth+gap);
            const y=top+row*(cellHeight+gap);
            rect(ctx,x,y,cellWidth,cellHeight,c.quiet);
            const band=Math.min(.129*h,.29*cellHeight);
            inBox(ctx,guest.media,x,y,cellWidth,cellHeight-band,guest.faceBox);
            if(!guest.name) return;
            const nameReveal=fixedNames?1:phase(time,0,.6);
            saved(ctx,()=>{
              clip(ctx,()=>ctx.rect(x,y+cellHeight-band,cellWidth*nameReveal,band),()=>{
                rect(ctx,x,y+cellHeight-band,cellWidth,band,c.paper);
                if(options.deferMediaLabels) return;
                text(ctx,guest.name,x+.035*cellWidth,y+cellHeight-band/2,band*.65,c.ink,
                  {font:c.font,weight:650,width:.93*cellWidth,height:.85*band});
              });
            });
          });
          break;
        }
        case "type-title": {
          rect(ctx,0,0,w,h,c.paper);
          label(title,.5,detail?.45:.5,.090,c.ink,{...mid,weight:650,width:.84*w,height:.27*h,reveal:phase(time,0,.74)});
          label(detail,.5,.65,.069,c.muted,{...mid,width:.84*w,height:.14*h,reveal:phase(time,.40,.60)});
          break;
        }
        case "cta-card": {
          const fill=reference?c.accent:c.paper, ink=foreground(fill,c);
          rect(ctx,0,0,w,h,fill);
          const entry=phase(time,0,.70);
          label(title,.5,.34,.077,ink,{...mid,weight:650,width:.84*w,height:.17*h,reveal:entry});
          label(detail,.5,.50,.067,ink,{...mid,width:.84*w,height:.14*h,reveal:entry});
          if(props.cta) {
            label(props.cta,.5,.69,.071,reference?c.light:c.accent,{...mid,weight:650,width:.82*w,height:.14*h,reveal:phase(time,.42,.74)});
          }
          break;
        }
        case "brand-slate": {
          rect(ctx,0,0,w,h,c.paper);
          const mark=props.mark;
          if(!mark) {
            label(title,.5,.5,.093,c.ink,{...mid,weight:700,width:.76*w});
            break;
          }
          let mw=.48*w,mh=.44*h;
          const cy=(title?.41:.5)*h;
          if(typeof mark!=="function"){
            const iw=mark.videoWidth || mark.naturalWidth || mark.width;
            const ih=mark.videoHeight || mark.naturalHeight || mark.height;
            if(iw>0 && ih>0){const scale=Math.min(mw/iw,mh/ih);mw=iw*scale;mh=ih*scale;}
          }
          inBox(ctx,mark,(w-mw)/2,cy-mh/2,mw,mh);
          label(title,.5,.72,.05,c.ink,{...mid,weight:600,width:.76*w});
          break;
        }
        case "metric-callout": {
          rect(ctx,0,0,w,h,c.paper);
          if(props.media) inBox(ctx,props.media,0,0,w*.46,h);
          const x=props.media?.73:.50;
          const tw=(props.media?.46:.85)*w;
          label(props.value,x,.44,.15,c.accent,{...mid,weight:650,width:tw,height:.23*h,reveal:phase(time,0,.80)});
          label(props.label,x,.62,.065,c.ink,{...mid,weight:650,width:tw,height:.125*h,reveal:phase(time,.24,.68)});
          label(detail,x,.76,.067,c.muted,{...mid,width:tw,height:.15*h,reveal:phase(time,.38,.68)});
          break;
        }
        case "concept-diagram": {
          rect(ctx,0,0,w,h,c.paper);
          const nodes=props.nodes || [],cx=.50*w,cy=.50*h;
          const centerRadius=Math.min(.150*h,.13*w);
          function nodeLabel(value,x,y,r,ink){
            const size=Math.min(.071*h,.56*r),limit=1.69*r;
            ctx.font="600 "+size+"px "+c.font;
            const lines=String(value??"").split("\n").flatMap(paragraph=>{
              const rows=[""];
              for(const word of (paragraph.match(/\S+\s+\d+(?=\s|$)|\S+/g)||[])){
                const last=rows.length-1;
                const candidate=rows[last]?rows[last]+" "+word:word;
                if(rows[last] && ctx.measureText(candidate).width>limit) rows.push(word);
                else rows[last]=candidate;
              }
              return rows;
            });
            text(ctx,lines.join("\n"),x,y,Math.min(size,1.38*r/lines.length),ink,
              {...mid,weight:600,width:limit,leading:1.03});
          }
          const centers=nodes.map((node,i)=>{
            const a=2*Math.PI*i/nodes.length-Math.PI/2;
            return {x:cx+Math.cos(a)*.33*w,y:cy+Math.sin(a)*.33*h,node};
          });
          centers.forEach(({x,y,node},i)=>{
            const dx=x-cx,dy=y-cy,distance=Math.hypot(dx,dy);
            const separation=Math.min(...centers.map((other,j)=>i===j?Infinity:Math.hypot(x-other.x,y-other.y)));
            const radius=Math.min(.153*h,.13*w,separation*.45,distance-centerRadius-.017*h);
            if(radius<=0) return;
            const start=.28+.70*i;
            const edge=phase(time,start,.32);
            if(edge<=0) return;
            const leading=centerRadius/distance, end=(distance-radius)/distance;
            const head=leading+(end-leading)*edge;
            ctx.beginPath();ctx.moveTo(cx+leading*dx,cy+leading*dy);ctx.lineTo(cx+head*dx,cy+head*dy);
            ctx.strokeStyle=c.muted;ctx.lineWidth=.005*h;ctx.stroke();
            const grow=phase(time,start+.32,.38);
            if(grow>0) disc(ctx,x,y,radius*grow,c.quiet);
            if(grow>=1) nodeLabel(node,x,y,radius,c.ink);
          });
          disc(ctx,cx,cy,centerRadius,c.accent);
          nodeLabel(title,cx,cy,centerRadius,foreground(c.accent,c));
          break;
        }
        case "circle-window": {
          rect(ctx,0,0,w,h,c.paper);
          const side=props.side || (title?"left":"center");
          const x=w*(side==="left"?.28:side==="right"?.72:.5);
          const y=h*.5, radius=Math.min(.32*h,.26*w);
          const visible=radius*phase(time,0,.92);
          clip(ctx,()=>ctx.arc(x,y,visible,0,2*Math.PI),()=>{
            rect(ctx,x-radius,y-radius,2*radius,2*radius,c.accent);
            inBox(ctx,props.media,x-radius,y-radius,2*radius,2*radius);
          });
          if(title) label(title,side==="right"?.28:.72,.5,.072,c.ink,{...mid,weight:650,width:.42*w});
          break;
        }
        case "data-chart": {
          rect(ctx,0,0,w,h,c.paper);
          const showLabels=!options.deferMediaLabels;
          if(showLabels) {
            label(title,.10,detail?.097:.13,.065,c.ink,{weight:650,width:.80*w});
            if(detail) label(detail,.10,.174,.048,c.muted,{width:.80*w});
          }
          const entries=(props.values || []).map((value,i)=>({value,label:props.labels?.[i],index:i}))
            .filter(item=>Number.isFinite(item.value));
          if(!entries.length) break;
          const values=entries.map(item=>item.value);
          const low=Math.min(0,...values),high=Math.max(0,...values);
          const plotTop=detail?.34:.25, span=high-low||1, plotHeight=(.75-plotTop)*h, left=.10*w;
          const base=plotTop*h+plotHeight*(high===low?1:high/span);
          const slot=.80*w/entries.length;
          const grow=props.duration??1.25, focusHold=props.focusHold??0;
          const focusIndex=entries.findIndex(item=>item.index===(props.highlightIndex??props.activeIndex));
          const advancing=entries.length-Number(focusHold>0 && focusIndex>=0);
          const numericLabel=(value)=>{
            const unit=String(props.unit||"").trim();
            return String(value)+(unit && !["%","‰","°"].includes(unit)?" ":"")+unit;
          };
          ctx.beginPath();ctx.moveTo(left,base);ctx.lineTo(w*.90,base);
          ctx.strokeStyle=c.muted;ctx.lineWidth=.003*h;ctx.stroke();
          entries.forEach(({value,label:category},i)=>{
            const x=left+(i+.5)*slot, focus=i===focusIndex;
            const rank=i-Number(focusHold>0 && focusIndex>=0 && i>focusIndex);
            const start=focusHold+barGroup(rank,advancing)*(grow+barGroupPause);
            const p=phase(time,start,grow);
            // Keep the selected observation and scale fixed while admitting its peers.
            const visible=focusHold ? (focus?1:p) : 1;
            if(visible<=0)return;
            const barH=value/span*plotHeight*(focusHold?1:p), barW=.64*slot*visible;
            rect(ctx,x-barW/2,Math.min(base,base-barH),barW,Math.abs(barH),focus?c.accent:c.neutral);
            if(!showLabels)return;
            const valueReveal=focusHold ? Number(focus || p>=.82) :
              (advancing>3 ? Number(p>=1) : phase(time,grow,.48));
            text(ctx,numericLabel(value),x,base-barH+(value<0?.043:-.043)*h,focusHold?.067*h:.055*h,c.ink,
              {...mid,weight:600,width:.91*slot,reveal:valueReveal});
            if(!focusHold || focus || p>=.34)
              text(ctx,category,x,.865*h,focusHold?.058*h:.054*h,c.ink,{...mid,width:.92*slot});
          });
          break;
        }
      }
    });
  }
  globalThis.LineWorldMotion = Object.freeze({transition,artifact,media:inBox,chart,percentageLabel,resolveTheme,diagrams,transitions:Object.freeze(transitions),artifacts:Object.freeze(artifacts),theme:Object.freeze(theme)});
})();
