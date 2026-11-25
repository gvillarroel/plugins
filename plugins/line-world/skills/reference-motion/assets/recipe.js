/* Deterministic scene renderer shared by the command line export and its checks. */
(() => {
  "use strict";
  const engine = globalThis.LineWorldMotion, presets = globalThis.LineWorldPresets;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", {willReadFrequently:true});
  let plan, media = {}, findings, checkText = false, labels = new Set(), occupied = [];
  let keyLabels = new Set(), measured = {}, positions = {};
  function criticalLabels(scene) {
    const p=scene.props;
    if(scene.artifact==="chart-ring") return [engine.percentageLabel(p.value)];
    if(scene.artifact==="disc-endcard") return String(p.detail||"").split("\n").filter(Boolean);
    if(scene.artifact!=="data-chart" || !Number.isInteger(p.highlightIndex)) return [];
    const unit=String(p.unit||"").trim(), idx=p.highlightIndex;
    return [String(p.values[idx])+(unit && !["%","‰","°"].includes(unit)?" ":"")+unit,
            String(p.labels[idx])];
  }
  function addLabels(value) {
    if (Array.isArray(value)) value.forEach(addLabels);
    else if (value && typeof value === "object") {
      for (const [key,v] of Object.entries(value)) {
        if (["title","detail","label","labels","cta","kicker","text","name","items","nodes","cards","guests","value","number","inputs","outputs","edges","keyLabel","focusLabel","inputLabel","exchanges","parts","criteria"].includes(key)) addLabels(v);
      }
    } else if (typeof value === "string" || typeof value === "number")
      String(value).split("\n").forEach(v=>labels.add(v));
  }
  function luminance(rgb) {
    const values=rgb.map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);
    return values[0]*.2126+values[1]*.7152+values[2]*.0722;
  }
  const palette = new Set(["#ffffff","#f7f7f7","#e7e7e7","#cfcfcf","#b5b5b5","#9c9c9c","#828282",
    "#696969","#4f4f4f","#363636","#333e48","#1c1c1c","#000000","#9e1b32","#6d1222","#e8002a"]);

  // Audit painting operations, so antialiasing and pixels from imported images
  // do not get mistaken for unauthorized paint colors.
  const prototype = CanvasRenderingContext2D.prototype;
  for (const name of ["fill","fillRect","fillText","stroke","strokeRect","strokeText","drawImage"]) {
    const original = prototype[name];
    prototype[name] = function(...args) {
      if (findings && this.globalAlpha > 0) {
        const style = name.startsWith("stroke") ? this.strokeStyle : this.fillStyle;
        if (name !== "drawImage" && !palette.has(style)) findings.add("Pintura fuera de la paleta sólida: "+String(style));
        if (this.globalAlpha !== 1) findings.add("Opacidad parcial en "+name);
        if (this.filter && this.filter !== "none") findings.add("Filtro en "+name);
        if (checkText && this.canvas === canvas && /Text$/.test(name) && String(args[0]).trim()) {
          const [label,x,y,limit] = args, m=this.measureText(label);
          const scale = limit && m.width ? Math.min(1,limit/m.width) : 1;
          if (scale < .66) findings.add("Texto comprimido: "+label);
          const a=x-m.actualBoundingBoxLeft*scale, b=x+m.actualBoundingBoxRight*scale;
          const top=y-m.actualBoundingBoxAscent, bottom=y+m.actualBoundingBoxDescent, t=this.getTransform();
          const points=[[a,top],[b,top],[a,bottom],[b,bottom]].map(([px,py])=>t.transformPoint({x:px,y:py}));
          if(labels.has(String(label))) positions[label]=points.map(p=>[p.x,p.y]);
          if (points.some(p=>p.x< -2 || p.x>canvas.width+2 || p.y< -2 || p.y>canvas.height+2))
            findings.add("Texto fuera del encuadre: "+label);
          if (keyLabels.has(String(label))) {
            const ys=points.map(p=>p.y), xs=points.map(p=>p.x);
            const height=Math.max(...ys)-Math.min(...ys);
            measured[label]={x:Math.min(...xs),y:Math.min(...ys),width:Math.max(...xs)-Math.min(...xs),height,
                             mobileInkHeight:height*Math.min(1,390/canvas.width)};
            if (measured[label].mobileInkHeight<7.8) findings.add("Texto clave demasiado pequeño a 390 px: "+label);
          }
          if ((labels.has(String(label)) || keyLabels.has(String(label))) && style && /^#[0-9a-f]{6}$/i.test(style)) {
            const em=Number(this.font.match(/([\d.]+)px/)?.[1]) * Math.hypot(t.c,t.d);
            if(em < canvas.height/50) findings.add("Texto demasiado pequeño a tamaño de entrega: "+label);
            const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
            const box={l:Math.min(...xs),r:Math.max(...xs),t:Math.min(...ys),b:Math.max(...ys),label};
            const area=(box.r-box.l)*(box.b-box.t);
            if(area>0){
              for(const old of occupied){
                const overlap=Math.max(0,Math.min(old.r,box.r)-Math.max(old.l,box.l))*Math.max(0,Math.min(old.b,box.b)-Math.max(old.t,box.t));
                if(overlap>.32*Math.min(area,(old.r-old.l)*(old.b-old.t))) findings.add("Textos superpuestos: "+old.label+" / "+label);
              }
              occupied.push(box);
              const ink=luminance([1,3,5].map(i=>parseInt(style.slice(i,i+2),16)));
              const contrasts=[.15,.35,.5,.65,.85].map(u=>{
                const px=Math.max(0,Math.min(canvas.width-1,Math.round(box.l+(box.r-box.l)*u)));
                const py=Math.max(0,Math.min(canvas.height-1,Math.round((box.t+box.b)/2)));
                const bg=luminance([...this.getImageData(px,py,1,1).data].slice(0,3));
                return (Math.max(bg,ink)+.05)/(Math.min(bg,ink)+.05);
              }).sort((a,b)=>a-b);
              if(contrasts[2] < (em>=canvas.height/30 ? 3 : 4.5)) findings.add("Contraste de lectura bajo: "+label);
            }
          }
        }
      }
      return original.apply(this,args);
    };
  }
  function resolve(value, scene, key) {
    if (["media","mark","slide","background"].includes(key) && Object.hasOwn(media,value)) {
      const asset=media[value];
      if(asset.kind!=="video") return asset;
      return scene.video[value] ||= {...asset,element:null,index:-1};
    }
    if (Array.isArray(value)) return value.map(v=>resolve(v,scene));
    if (value && typeof value === "object")
      return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,resolve(v,scene,k)]));
    return value;
  }
  async function load(config, files) {
    plan=config;canvas.width=config.width;canvas.height=config.height;
    media=Object.create(null);
    await Promise.all(Object.entries(files).map(async ([id,entry])=>{
      const item=typeof entry==="string"?{kind:"image",url:entry}:entry;
      const asset={...item,lineWorldMedia:true,element:null};
      if(item.kind==="image"){
        const image=new Image();image.src=item.url;await image.decode();asset.element=image;
      }
      media[id]=asset;
    }));
    for (const s of plan.scenes) {s.video=Object.create(null);s.inputs=resolve(s.props,s);}
    await document.fonts.ready;
  }
  const lead = .5;
  const mediaOverlays=new Set(["caption-overlay","speaker-id","question-card","insight-band","orbital-caption","guest-grid"]);
  const hasFocusWindow=scene=>scene.artifact==="data-chart" && scene.props.focusHold>0;
  const startsAtZero=scene=>engine.diagrams.includes(scene.artifact) || hasFocusWindow(scene);
  const waitsForJoin=scene=>mediaOverlays.has(scene.artifact) || startsAtZero(scene);
  const timeOrigin=scene=>startsAtZero(scene)?0:lead;
  function paint(g, w, h, scene, time, deferLabels=false) {
    g.save();
    try {
      g.fillStyle="#ffffff";g.fillRect(0,0,w,h);
      presets.drawArtifact(g,scene.artifact,time,scene.inputs,{width:w,height:h,mode:"solid",deferMediaLabels:deferLabels,
        completeGuestNames:scene.artifact==="guest-grid" && scene.bridge>1});
    } finally {g.restore();}
  }
  async function seekScene(scene, local) {
    await Promise.all(Object.entries(scene.video).map(async ([key,item])=>{
      const index=Math.min(item.frames-1,Math.max(0,local));
      if(item.index===index) return;
      const image=new Image();
      image.src=await globalThis.lineWorldFrameData(key,index);
      await image.decode();item.element=image;item.index=index;
    }));
  }
  async function draw(frame) {
    const f=Math.min(plan.frames-1,Math.max(0,Math.floor(frame)));
    const i=plan.scenes.findIndex(s=>s.end>f), s=plan.scenes[i], local=f-s.start;
    ctx.resetTransform();ctx.globalAlpha=1;
    if (i && local<s.bridge) {
      const prev=plan.scenes[i-1];
      await Promise.all([seekScene(s,local),seekScene(prev,prev.end-prev.start-1)]);
      const hidePreviousNames=local>0 && s.bridge>1 && s.artifact==="guest-grid" &&
        (prev.artifact==="speaker-id" || prev.artifact==="guest-grid");
      const from=(g,w,h)=>paint(g,w,h,prev,timeOrigin(prev)+prev.reveal/plan.fps,hidePreviousNames);
      const defer=s.bridge>1 && waitsForJoin(s);
      const intro=startsAtZero(s)?0:timeOrigin(s)+Math.min(s.reveal,local)/plan.fps;
      const to=(g,w,h)=>paint(g,w,h,s,intro,defer);
      const progress=s.bridge===1?1:local/(s.bridge-1);
      engine.transition(ctx,s.transition,progress,from,to,{mode:"solid"});
    } else {
      await seekScene(s,local);
      const advance=s.bridge>1 && !waitsForJoin(s)?s.bridge-1:0;
      const elapsed=Math.min(s.reveal,local-s.bridge+advance)/plan.fps;
      paint(ctx,canvas.width,canvas.height,s,timeOrigin(s)+elapsed);
    }
  }
  async function audit(frame, settled) {
    findings=new Set();checkText=settled;
    labels=new Set();occupied=[];measured=Object.create(null);positions=Object.create(null);keyLabels=new Set();
    if (settled) {
      const scene=plan.scenes.find(s=>s.end>frame);
      addLabels(scene.props);keyLabels=new Set(criticalLabels(scene));
      if(scene.video_assets?.length && scene.props.title)
        for(const line of scene.props.title.split("\n").filter(Boolean)) keyLabels.add(line);
    }
    try {
      await draw(frame);
      const {data}=ctx.getImageData(0,0,canvas.width,canvas.height);
      let min=255,max=0;
      for (let n=0;n<data.length;n+=16) {
        if (data[n+3]!==255) findings.add("Píxeles sin fondo opaco");
        const light=(data[n]+data[n+1]+data[n+2])/3;
        min=Math.min(min,light);max=Math.max(max,light);
      }
      if (max-min<16) findings.add("Fotograma sin contenido distinguible");
      for(const label of keyLabels)
        if(!Object.hasOwn(measured,label)) findings.add("No se dibujó el texto clave: "+label);
      return [...findings];
    } finally {findings=null;checkText=false;}
  }
  async function png(frame, validate=false) {
    if (validate) {
      const errors=await audit(frame,false);
      if (errors.length) throw Error("Fotograma "+frame+": "+errors.join(", "));
    } else await draw(frame);
    return canvas.toDataURL("image/png").split(",")[1];
  }
  async function settled(index) {
    const scene=plan.scenes[index],w=canvas.width,h=canvas.height;
    const t=timeOrigin(scene)+scene.reveal/plan.fps;
    await seekScene(scene,scene.bridge+scene.reveal);
    paint(ctx,w,h,scene,t);const actual=canvas.toDataURL();
    return [.5,2,8].every(extra=>{paint(ctx,w,h,scene,t+extra);return actual===canvas.toDataURL();});
  }
  async function reading(index) {
    const scene=plan.scenes[index],begin=scene.start+scene.bridge, hold=begin+scene.reveal;
    const frames=[hold];
    if(scene.artifact==="chart-ring" || (scene.artifact==="data-chart" && scene.props.focusHold>0))
      for(let i=0;i<8;i++)frames.push(begin+Math.floor(i*scene.reveal/8));
    if(scene.video_assets?.length)
      for(let i=1;i<=4;i++)frames.push(hold+Math.floor(i*(scene.end-1-hold)/4));
    let reference;
    let firstLayout;
    for(const frame of frames) {
      const errors=await audit(frame,true);if(errors.length)throw Error(scene.id+": "+errors.join(", "));
      if(scene.video_assets?.length && frame>=hold){
        const geometry=JSON.stringify(positions);
        if(firstLayout && geometry!==firstLayout) throw Error(scene.id+": se movió un rótulo sobre el vídeo");
        firstLayout=geometry;
      }
      if(!reference) reference=measured;
      else if(JSON.stringify(measured)!==JSON.stringify(reference))
        throw Error(scene.id+": la cifra destacada o su categoría se desplazaron durante la comparación");
    }
    return {preview_width:Math.min(390,canvas.width),frames:frames.sort((a,b)=>a-b),labels:reference,
            ...(firstLayout?{hold_label_positions:JSON.parse(firstLayout)}:{})};
  }
  globalThis.MotionRecipe={load,draw,audit,png,settled,reading,canvas};
})();
