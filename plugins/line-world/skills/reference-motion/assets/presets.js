/* Shared example data and deterministic scene backgrounds for the gallery and generator. */
(() => {
  "use strict";
  const engine=globalThis.LineWorldMotion;
  const art=globalThis.LineWorldDemoArt;
  const media = Object.freeze({
    "@city":art.city(0), "@network":art.network(0), "@host":art.trainCard,
    "@host-close":art.hostClose, "@guest-close":art.guestClose, "@guest":art.guest, "@schedule":art.schedule,
    "@platform":art.platformDoor, "@station-detail":art.stationDetail, "@mark":art.mark
  });
  const data = {
    "speaker-id":{title:"Inés Vidal",detail:"Planificación\nEstación Central",side:"left"},
    "question-card":{title:"¿Dónde cambia\nla línea?"},
    "caption-overlay":{media:"@station-detail",title:"Andén 2"},
    "editorial-split":{media:"@platform",title:"Estación\nCentral",detail:"Andén 2",share:.54},
    "slide-pip":{slide:"@schedule",media:"@host-close"},
    "insight-band":{media:"@network",kicker:"Línea Norte",title:"Central",detail:"Enlace con Ribera",side:"bottom"},
    "dashboard-stack":{beat:3,cards:[
      {title:"Salidas por hora · laborables",values:art.departures,labels:["06 h","10 h","14 h","18 h"],highlightIndex:2},
      {title:"Salidas por hora · fin de semana",values:[4,6,8,6],labels:["06 h","10 h","14 h","18 h"],highlightIndex:2}
    ]},
    "icon-card":{points:[[.12,.82],[.12,.44],[.5,.16],[.88,.44],[.88,.82],[.12,.82],[.12,.59],[.88,.59],[.5,.59],[.5,.82]],title:"Estación Central"},
    "disc-endcard":{title:"N",detail:"Línea Norte  ·  Central",hold:2.6,moveDuration:2.2,enterDuration:.75,finalY:.34},
    "chart-focus":{box:[.54,.22,.13,.51]},
    "corner-card":{title:"Línea Norte"},
    "orbital-caption":{title:"Andén\n2",x:.74,y:.39,delay:1.55},
    "numbered-step":{number:2,title:"Cambiar de andén"},
    "keypoint-list":{items:["Llegada a Central","Cambio de andén","Salida a Ribera"],starts:[0,2.2,4.4],y:.27,spacing:.2},
    "chart-ring":{value:75,label:"Ocupación del andén",duration:2.4,fractional:true},
    "guest-grid":{guests:[{media:"@host-close",name:"Inés Vidal"},{media:"@guest-close",name:"Eva León"}]},
    "type-title":{title:"Estación Central",detail:"Línea Norte"},
    "cta-card":{title:"Línea Norte",detail:"Conexiones desde Central",cta:"Consultar el plano"},
    "brand-slate":{title:"Línea Norte",mark:"@mark"},
    "metric-callout":{value:"12",label:"Salidas por hora",detail:"14 h  ·  Estación Central"},
    "concept-diagram":{title:"Central",nodes:["Andén 1","Vestíbulo","Andén 2"]},
    "circle-window":{media:"@platform",title:"Andén 2",side:"left"},
    "field-packing":{labels:["Posición","Edad","Velocidad","Color"],duration:5},
    "layer-preview":{labels:["Cámara","Sombras","Luz","Acabado"],duration:5},
    "isometric-layers":{labels:["Cámara","Malla","Instancias","Luz","Acabado"],duration:5},
    "module-transfer":{labels:["Destino","Cámara","Malla","Luz","Acabado"],duration:5,
      highlightIndex:1,inputs:["root","tamaño","objetivo"],outputs:["vista","proyección"]},
    "vertex-remap":{labels:["Vértices","Superficie"],duration:5},
    "command-lanes":{labels:["Sombra","Escena","Brillo","Salida"],duration:5},
    "shared-host":{labels:["Web","Escena","Móvil"],duration:5},
    "pivot-rotation":{title:"El recorrido de una aguja",unit:"mm",radius:42,startAngle:25,sweepAngle:140,
      orientation:"compass",pivotLabel:"Eje",pointLabel:"Extremo",duration:6},
    "rigid-rearrangement":{title:"Una banda, dos filas",unit:"cm",duration:6,pieces:[
      {id:"base",label:"A",width:3,height:2,from:[0,0],to:[0,0]},
      {id:"strip",label:"B",width:2,height:1,from:[3,0],to:[3,1]},
      {id:"cap",label:"C",width:2,height:1,from:[5,0],to:[3,0]}]},
    "split-clock":{labels:["Interfaz","Cálculo"],duration:5},
    "object-route":{title:"El recorrido de una muestra",objectLabel:"Ágata azul",
      stops:["Archivo Celeste","Taller Ibis","Sala del Olmo","Archivo Celeste"],duration:8},
    "contact-transfer":{title:"Imprimir un sello",labels:["Palanca","Sello","Papel","Huella de tinta"],
      drive:"lever",effect:"mark",duration:6},
    "trajectory-trace":{title:"Recorrido de una boya",unit:"m",timeUnit:"s",duration:7,samples:[
      {t:0,x:0,y:0},{t:1,x:1,y:2},{t:2,x:2,y:1},{t:4,x:1,y:-1},{t:5,x:0,y:0}]},
    "interval-refinement":{title:"Localizar el punto de medida",unit:"m",duration:7,intervals:[
      {label:"Tramo inicial",low:0,high:1200},{label:"Sector",low:300,high:600},
      {label:"Inspección",low:420,high:480},{label:"Localización final",low:444,high:456}]},
    "pass-strip":{labels:["Sombra","Escena","Brillo","Acabado"],duration:5},
    "import-footprint":{labels:["Iluminación","Instancias","Cámaras"],duration:5},
    "ring-handoff":{"labels":["Norte","Este","Sur","Oeste","Nuevo"],"keyLabel":"K0","duration":6},
    "bit-probe":{"labels":["Lino","Nube","Brisa"],"bits":{"size":10,"groups":[[1,3,4],[0,4,8],[1,5,8]]},"duration":6},
    "message-ladder":{"labels":["Cliente","Servidor"],"exchanges":[{"label":"SYN","from":0},{"label":"SYN + ACK","from":1},{"label":"ACK","from":0}],"duration":6},
    "detail-callout":{"labels":["Esquema","Dominio","Ruta","Recurso"],"parts":["https://","ejemplo.net","/archivo/","plano"],"focusLabel":"Dirección","duration":6},
    "radix-ladder":{"labels":["División","Residuo","Código"],"value":11157,"base":62,"duration":6},
    "token-gate":{"labels":["Solicitudes","Recarga","Admitidas","Descartadas"],"tokens":1,"requests":2,"duration":6},
    "resolution-fan":{"labels":["Original","2160p · 4K","1440p","1080p","720p","480p","360p","240p"],"duration":6},
    "queue-router":{"labels":["Prioridad","Alta","Media","Baja","Selector"],"duration":6},
    "staged-network":{"nodes":[{"id":"ask","label":"Solicitud","x":0.15,"y":0.5,"w":0.2,"h":0.14,"shape":"page"},{"id":"service","label":"Servicio","x":0.48,"y":0.5,"w":0.21,"h":0.14,"shape":"server","enter":[0.12,0.3]},{"id":"index","label":"Índice","x":0.8,"y":0.3,"w":0.19,"h":0.13,"shape":"database","enter":[0.42,0.55]},{"id":"records","label":"Registros","x":0.8,"y":0.7,"w":0.19,"h":0.13,"shape":"database","enter":[0.7,0.82]}],"edges":[{"from":"ask","to":"service","enter":[0.02,0.16],"token":[0.18,0.31]},{"from":"service","to":"index","via":[[0.64,0.5],[0.64,0.3]],"enter":[0.32,0.46],"token":[0.48,0.6]},{"from":"service","to":"records","via":[[0.64,0.5],[0.64,0.7]],"enter":[0.63,0.78],"token":[0.79,0.94]}],"duration":6},
    "data-chart":{title:"Salidas por hora",detail:"Estación Central · Datos de ejemplo",values:art.departures,
      labels:["06 h","10 h","14 h","18 h"],highlightIndex:2,focusHold:3.5,duration:1.5}
  };
  function defaults(id) {
    if(!engine.artifacts.includes(id) && !engine.transitions.includes(id)) throw new RangeError("Patrón desconocido: "+id);
    return structuredClone(data[id] || {});
  }
  function resolveMedia(value) {
    return Object.hasOwn(media,value) ? media[value] : undefined;
  }
  function resolveProps(value, key) {
    if (typeof value==="string" && ["media","mark","slide","background"].includes(key)) return resolveMedia(value) || value;
    if (Array.isArray(value)) return value.map(item=>resolveProps(item));
    if (value && Object.getPrototypeOf(value)===Object.prototype)
      return Object.fromEntries(Object.entries(value).map(([field,item])=>[field,resolveProps(item,field)]));
    return value;
  }
  function drawArtifact(ctx,id,time,props=defaults(id),options={}) {
    const w=options.width ?? ctx.canvas.width, h=options.height ?? ctx.canvas.height;
    const parameters=resolveProps(props);
    const underlay={"speaker-id":"@host","chart-focus":"@schedule","question-card":"@station-detail","orbital-caption":"@network"}[id];
    ctx.save();
    try {
      ctx.fillStyle=options.theme?.paper ?? engine.theme.paper;
      ctx.fillRect(0,0,w,h);
      if (underlay) engine.media(ctx,parameters.background || resolveMedia(underlay),0,0,w,h);
      engine.artifact(ctx,id,time,parameters,options);
    } finally {ctx.restore();}
  }
  globalThis.LineWorldPresets=Object.freeze({defaults,drawArtifact,resolveMedia,mediaTokens:Object.freeze(Object.keys(media))});
})();
