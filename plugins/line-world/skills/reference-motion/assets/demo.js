/* One pass per preview. The gallery and exported scripts share the same artwork and presets. */
(() => {
  "use strict";
  const engine=globalThis.LineWorldMotion, presets=globalThis.LineWorldPresets;
  const $=id=>document.getElementById(id);
  const canvas=$("stage"), ctx=canvas.getContext("2d",{willReadFrequently:true});
  const query=new URLSearchParams(location.search);
  const referenceById=new Map(LineWorldReferences.patterns.map(item=>[item.id,item]));
  const ids=[...engine.transitions,...engine.artifacts];
  const labels={transitions:"Transición",artifacts:"Elemento gráfico"};
  const artNotes={
    "cut":"Pasa de la estación a su ubicación en la red. El punto de Central queda en el mismo lugar.",
    "dissolve":"Una frontera diagonal sustituye la vista del andén por la red, manteniendo los dos dibujos en color sólido.",
    "tint-bridge":"Una franja de color acompaña el paso del andén a la red de transporte.",
    "iris-fill":"El círculo que parte de Central abre su posición en el plano de la red.",
    "iris-close":"El plano del andén se recoge en un círculo para mostrar la red que lo rodea.",
    "shutter-close":"Dos franjas descubren el nuevo plano y se encuentran por encima de la mitad.",
    "step-blocks":"Las franjas descubren el plano por etapas y en una sola dirección.",
    "band-pass":"Una banda descendente descubre la red detrás del andén.",
    "push-down":"El plano de la red entra desde arriba y desplaza al andén.",
    "push-left":"La red entra desde la derecha y desplaza la vista del andén.",
    "guest-grid":"Las dos participantes conservan su nombre y su posición durante la conversación.",
    "type-title":"El nombre de la estación y la línea quedan centrados en el campo de lectura.",
    "cta-card":"Una acción de consulta cierra el recorrido por la estación.",
    "brand-slate":"El símbolo y el nombre de la línea forman una placa sobre blanco.",
    "metric-callout":"La franja de las 14 h registra 12 salidas por hora.",
    "concept-diagram":"El vestíbulo y los dos andenes comparten la estación como referencia.",
    "circle-window":"El recorte circular sitúa el andén junto a su identificación.",
    "data-chart":"La barra de las 14 h permanece en su lugar mientras aparecen las otras tres franjas a la misma escala.",
    "chart-ring":"El arco recorre tres cuartas partes del círculo para indicar un 75 % de ocupación.",
    "orbital-caption":"El punto guía llega a una llamada circular que identifica el andén.",
    "disc-endcard":"El disco se sostiene, asciende y cede espacio al nombre de la línea.",
    "caption-overlay":"El identificador del andén se apoya en un campo opaco sobre la vista de la estación."
  };
  const extendedHolds={"dashboard-stack":13,"keypoint-list":12,"disc-endcard":10,"data-chart":12};
  const transitionDuration={cut:0,dissolve:2.4,"tint-bridge":2.4,"iris-fill":2.2,"iris-close":2.2,
    "shutter-close":2.2,"step-blocks":2.6,"band-pass":2.4,"push-down":2.4,"push-left":2.4};
  const arrival=2.5, finalRead=3.5;
  const clamp=(value,start,end)=>Math.min(end,Math.max(start,value));
  const kindOf=id=>engine.transitions.includes(id)?"transitions":"artifacts";
  const label=id=>referenceById.get(id)?.label || id;
  const decimal=t=>Number(t).toLocaleString("es",{maximumFractionDigits:3});
  let active="",group="transitions",seconds=0,running=false,request=0,clockOrigin=0,poster=false;

  function timing(id) {
    if(kindOf(id)==="artifacts") return {duration:extendedHolds[id]||8,delay:.6,rate:.8};
    const reading=$("pace").value!=="source";
    const move=id==="cut"?0:reading?transitionDuration[id]:referenceById.get(id).duration_s;
    return {duration:arrival+move+finalRead,start:arrival,move};
  }
  function fraction(t,start,movement) {
    return movement===0?Number(t>=start):clamp((t-start)/movement,0,1);
  }
  function paint(t) {
    if(!Number.isFinite(Number(t))) throw new TypeError("El tiempo debe ser un número finito.");
    const plan=timing(active);
    seconds=clamp(Number(t),0,plan.duration);
    ctx.setTransform(1,0,0,1,0,0);
    if(group==="transitions") {
      const p=fraction(seconds,plan.start,plan.move);
      const from=presets.resolveMedia("@city"),to=presets.resolveMedia("@network");
      engine.transition(ctx,active,p,from,to,{x:482/960,y:active==="shutter-close"?150/360:246/540});
    } else {
      presets.drawArtifact(ctx,active,Math.max(0,(seconds-plan.delay)*plan.rate));
    }
    $("seek").max=String(plan.duration);$("seek").value=String(seconds);
    $("clock").textContent=decimal(seconds)+" / "+decimal(plan.duration)+" s";
    return {pattern:active,seconds,duration:plan.duration};
  }
  function playLabel(symbol,name) {
    $("play-icon").textContent=symbol;$("play-name").textContent=name;
  }
  function stop() {
    cancelAnimationFrame(request);running=false;
    playLabel("▶",seconds>=timing(active).duration?"Repetir":"Reproducir");
  }
  function renderAt(t) {
    poster=false;stop();
    const state=paint(t);
    playLabel("▶",state.seconds>=state.duration?"Repetir":"Reproducir");
    return state;
  }
  function play() {
    if(running){stop();return;}
    if(poster || seconds>=timing(active).duration)paint(0);
    poster=false;running=true;clockOrigin=performance.now()-seconds*1000;
    playLabel("Ⅱ","Pausar");
    function tick(now) {
      if(!running)return;
      paint((now-clockOrigin)/1000);
      if(seconds>=timing(active).duration){stop();return;}
      request=requestAnimationFrame(tick);
    }
    request=requestAnimationFrame(tick);
  }
  function refreshList() {
    const needle=$("filter").value.trim().toLocaleLowerCase("es");
    const matching=engine[group].filter(id=>(id+" "+label(id)).toLocaleLowerCase("es").includes(needle));
    $("list").replaceChildren();
    for(const id of matching) {
      const row=document.createElement("li"), button=document.createElement("button");
      button.type="button";button.textContent=label(id);button.dataset.pattern=id;
      button.setAttribute("aria-current",String(active===id));button.addEventListener("click",()=>select(id));
      row.append(button);$("list").append(row);
    }
    $("empty").hidden=Boolean(matching.length);
    for(const key of Object.keys(labels))$(key).setAttribute("aria-pressed",String(group===key));
  }
  function example(id) {
    const intro='const ctx = document.querySelector("canvas").getContext("2d");\n';
    const name=JSON.stringify(id),plan=timing(id);
    if(kindOf(id)==="transitions") {
      const start=decimalCode(plan.start);
      const progress=plan.move===0?'Number(seconds >= '+start+')':'Math.max(0, Math.min(1, (seconds - '+start+') / '+decimalCode(plan.move)+'))';
      const y=id==="shutter-close"?"150 / 360":"246 / 540";
      return intro+'const from = LineWorldPresets.resolveMedia("@city");\nconst to = LineWorldPresets.resolveMedia("@network");\n\nfunction renderAt(seconds) {\n  const p = '+progress+';\n  LineWorldMotion.transition(ctx, '+name+', p, from, to,\n                             {x: 482 / 960, y: '+y+'});\n}\nrenderAt('+decimalCode(plan.start+plan.move/2)+');';
    }
    const props=JSON.stringify(presets.defaults(id),null,2);
    return intro+'const props = '+props+';\n\nfunction renderAt(seconds) {\n  const elapsed = Math.max(0, (seconds - '+decimalCode(plan.delay)+') * '+decimalCode(plan.rate)+');\n  LineWorldPresets.drawArtifact(ctx, '+name+', elapsed, props);\n}\nrenderAt('+decimalCode(plan.duration*.75)+');';
  }
  function decimalCode(value){return Number(value.toFixed(3)).toString();}
  function stamp(value) {
    const ms=Math.round(Math.max(0,Number(value)||0)*1000);
    const fraction=String(ms%1000).padStart(3,"0").replace(/0+$/,"");
    return Math.floor(ms/60000)+":"+String(Math.floor(ms/1000)%60).padStart(2,"0")+(fraction?","+fraction:"");
  }
  function refs(id) {
    const list=$("refs");list.replaceChildren();
    for(const source of referenceById.get(id).sources) {
      const row=document.createElement("li"),a=document.createElement("a"),note=document.createElement("small"),time=document.createElement("span");
      a.href=source.url;a.target="_blank";a.rel="noopener noreferrer";a.textContent=source.video_title;
      note.textContent=source.observation;
      const window=source.end_s>source.start_s;time.className="ref-time";
      time.textContent=(window?"Ventana observada · ":"Muestra fija · ")+stamp(source.start_s)+(window?"–"+stamp(source.end_s):"");
      row.append(time,a,note);list.append(row);
    }
  }
  function select(id,t,saveURL=true) {
    if(!ids.includes(id))throw new RangeError("Patrón desconocido: "+id);
    active=id;group=kindOf(id);stop();
    const plan=timing(id),entry=referenceById.get(id);
    $("title").textContent=label(id);$("kind").textContent=labels[group];
    $("description").textContent=artNotes[id] || entry.mechanism;
    $("pace-control").hidden=group!=="transitions"||id==="cut";
    $("timing").textContent=group==="transitions"
      ? (plan.move>0?"Movimiento de "+decimal(plan.move)+" s":"Corte directo")+" · lectura final de "+decimal(finalRead)+" s"
      : "Vista de "+decimal(plan.duration)+" s";
    $("snippet").textContent=example(id);$("mobile").value=id;$("copy").textContent="Copiar";
    canvas.setAttribute("aria-label","Vista previa de "+label(id));
    refreshList();refs(id);
    poster=t===undefined && group==="artifacts";
    const state=paint(t??(poster?plan.duration*.75:0));
    playLabel("▶",state.seconds>=plan.duration?"Repetir":"Reproducir");
    if(saveURL) {
      const url=new URL(location.href);url.searchParams.set("pattern",id);url.searchParams.delete("t");
      try {history.replaceState(null,"",url);} catch {/* Some file viewers disable History API. */}
    }
    return state;
  }
  for(const key of Object.keys(labels)) {
    const optgroup=document.createElement("optgroup");optgroup.label=key==="transitions"?"Transiciones":"Elementos";
    for(const id of engine[key]) {
      const option=document.createElement("option");option.value=id;option.textContent=label(id);optgroup.append(option);
    }
    $("mobile").append(optgroup);
    $(key).addEventListener("click",()=>{if(group!==key){$("filter").value="";select(engine[key][0]);}});
  }
  $("mobile").addEventListener("change",e=>select(e.target.value));
  $("pace").addEventListener("change",()=>select(active,0,false));
  $("filter").addEventListener("input",refreshList);
  $("play").addEventListener("click",play);
  $("seek").addEventListener("input",e=>renderAt(e.target.value));
  $("copy").addEventListener("click",async()=>{
    const selection=getSelection(),range=document.createRange();
    range.selectNodeContents($("snippet"));selection.removeAllRanges();selection.addRange(range);
    if(document.execCommand("copy")){$("copy").textContent="Copiado";selection.removeAllRanges();return;}
    $("copy").textContent="Código seleccionado";
    try{await navigator.clipboard.writeText($("snippet").textContent);$("copy").textContent="Copiado";selection.removeAllRanges();}
    catch{/* The selection is available for native copy. */}
  });
  if(query.get("render")==="1") document.body.classList.add("render");
  if(query.get("pace")==="source") $("pace").value="source";
  const initial=ids.includes(query.get("pattern"))?query.get("pattern"):"iris-fill";
  const at=query.has("t")&&Number.isFinite(Number(query.get("t")))?Number(query.get("t")):undefined;
  select(initial,at,false);
  globalThis.renderAt=renderAt;
  globalThis.LineWorldDemo=Object.freeze({
    select,renderAt,ids:Object.freeze(ids),timing,defaults:presets.defaults,drawArtifact:presets.drawArtifact,
    get duration(){return timing(active).duration;},get pattern(){return active;},get time(){return seconds;},get canvas(){return canvas;}
  });
})();
