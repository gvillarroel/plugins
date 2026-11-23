/* Flat, time-independent source plates. All coordinates use a 960 × 540 field. */
(() => {
  "use strict";
  const width = 960, height = 540;
  const palette = Object.freeze({
    paper:"#ffffff", ink:"#333e48", gray:"#696969", line:"#828282",
    muted:"#b5b5b5", light:"#cfcfcf", quiet:"#e7e7e7", red:"#9e1b32"
  });
  const font = '"Segoe UI", Arial, sans-serif';

  function plate(paint) {
    return (ctx, w, h) => {
      ctx.save();
      try {
        ctx.fillStyle = palette.paper;
        ctx.fillRect(0,0,w,h);
        const scale = Math.min(w / width, h / height);
        ctx.translate((w-width*scale)/2,(h-height*scale)/2);
        ctx.scale(scale,scale);
        paint(ctx);
      } finally { ctx.restore(); }
    };
  }
  function line(ctx, points, color=palette.line, weight=2) {
    ctx.beginPath();
    ctx.lineJoin="round"; ctx.lineCap="round";
    points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
    ctx.strokeStyle=color; ctx.lineWidth=weight; ctx.stroke();
  }
  function shape(ctx, points, color) {
    ctx.beginPath();
    points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
    ctx.closePath(); ctx.fillStyle=color; ctx.fill();
  }
  function block(ctx,x,y,w,h,color,radius=0) {
    ctx.fillStyle=color;
    if (!radius) {ctx.fillRect(x,y,w,h); return;}
    ctx.beginPath(); ctx.roundRect(x,y,w,h,radius); ctx.fill();
  }
  function dot(ctx,x,y,r,color) {
    ctx.fillStyle=color; ctx.beginPath(); ctx.arc(x,y,r,0,2*Math.PI); ctx.fill();
  }
  function type(ctx,value,x,y,size,color=palette.ink,align="left",weight=500) {
    ctx.font=weight+" "+size+"px "+font; ctx.fillStyle=color;
    ctx.textAlign=align; ctx.textBaseline="middle"; ctx.fillText(value,x,y);
  }

  // Exterior and network share the Central station point. Changing representation
  // answers a spatial question without changing the selected stop.
  function drawStation(ctx,labels) {
    line(ctx,[[102,176],[244,124],[710,124],[854,176]],palette.line,3);
    line(ctx,[[105,176],[852,176]],palette.light,3);
    for(const x of [200,760]) {
      line(ctx,[[x,176],[x,350]],palette.light,5);
      line(ctx,[[x-38,176],[x,205],[x+38,176]],palette.muted,2);
    }
    for(const [a,b] of [[156,348],[354,586],[592,804]]) {
      const body=[
        [a,326],[a,270],[a+18,249],[b-27,249],[b,272],[b,326]
      ];
      shape(ctx,body,palette.quiet);
      for(let x=a+29;x<b-42;x+=49) block(ctx,x,267,33,21,palette.muted,4);
      dot(ctx,a+39,329,10,palette.gray); dot(ctx,b-41,329,10,palette.gray);
    }
    block(ctx,465,265,30,54,palette.red,3);
    block(ctx,471,271,18,17,palette.paper,2);
    line(ctx,[[103,346],[854,346]],palette.ink,3);
    block(ctx,103,349,751,23,palette.quiet);
    if(labels) {
      line(ctx,[[482,249],[482,218]],palette.red,2);
      dot(ctx,482,246,7,palette.red);
      type(ctx,"Central",482,199,26,palette.ink,"center",620);
      type(ctx,"Andén 2",482,408,21,palette.gray,"center");
    }
  }
  const station=plate(ctx=>drawStation(ctx,true));
  const stationDetail=plate(ctx=>{
    ctx.translate(-145,-55);ctx.scale(1.3,1.3);drawStation(ctx,false);
  });
  const route = plate(ctx => {
    const branch=[[212,383],[302,383],[447,249],[576,249],[680,152],[805,152]];
    const main=[[94,304],[204,304],[279,246],[482,246],[619,246],[717,307],[865,307]];
    line(ctx,branch,palette.light,7); line(ctx,main,palette.gray,6);
    line(ctx,[[279,246],[482,246]],palette.red,6);
    for(const [x,y] of [[204,304],[302,383],[619,246],[680,152],[717,307],[805,152]]) {
      dot(ctx,x,y,6,palette.muted);
    }
    for(const [x,y] of [[94,304],[865,307]]) {
      dot(ctx,x,y,10,palette.gray);dot(ctx,x,y,5,palette.paper);
    }
    dot(ctx,482,246,16,palette.red);dot(ctx,482,246,6,palette.paper);
    type(ctx,"Central",482,202,26,palette.ink,"center",620);
    type(ctx,"Talleres",94,341,20,palette.gray,"center");
    type(ctx,"Ribera",863,345,20,palette.gray,"center");
  });
  const trainCard=plate(ctx=>{
    // A portrait silhouette is sufficient for inspecting a nameplate.
    const x=550;
    ctx.translate(x,275);ctx.scale(1.45,1.45);ctx.translate(-x,-275);
    shape(ctx,[[x-174,438],[x-159,396],[x-122,357],[x-50,324],[x+51,324],[x+135,359],[x+169,406],[x+178,438]],palette.muted);
    block(ctx,x-34,285,68,58,palette.light,9);
    ctx.beginPath();ctx.ellipse(x,238,67,77,0,0,Math.PI*2);ctx.fillStyle=palette.quiet;ctx.fill();
    shape(ctx,[[x-67,243],[x-64,194],[x-40,160],[x-5,145],[x+39,154],[x+66,185],[x+68,218],[x+44,196],[x+8,197],[x-29,208],[x-48,237]],palette.gray);
    line(ctx,[[x-38,242],[x-10,242],[x-7,253],[x-32,253],[x-38,242],[x-9,242],[x+7,242],[x+36,242],[x+32,253],[x+10,253],[x+7,242]],palette.ink,2.2);
    line(ctx,[[x-5,278],[x+10,278]],palette.gray,2);
    line(ctx,[[x-47,328],[x,356],[x+45,328]],palette.paper,4);
    block(ctx,x+62,373,30,19,palette.red,2);
  });
  const departures = Object.freeze([6,9,12,8]);
  function platformDoor(ctx,w,h) {
    ctx.save();
    ctx.fillStyle=palette.paper;ctx.fillRect(0,0,w,h);
    const size=Math.min(w,h);
    ctx.translate((w-size)/2,(h-size)/2);ctx.scale(size/100,size/100);
    block(ctx,-12,24,124,49,palette.quiet);
    block(ctx,36,36,28,37,palette.red,2);
    block(ctx,41,40,18,13,palette.paper,1.5);
    block(ctx,4,37,21,15,palette.muted,2);
    block(ctx,75,37,21,15,palette.muted,2);
    dot(ctx,18,74,4,palette.gray);dot(ctx,82,74,4,palette.gray);
    line(ctx,[[-8,80],[108,80]],palette.line,1.3);
    ctx.restore();
  }
  const guest=plate(ctx=>{
    const x=480;
    ctx.translate(x,275);ctx.scale(1.45,1.45);ctx.translate(-x,-275);
    shape(ctx,[[x-168,434],[x-147,368],[x-48,327],[x+46,327],[x+142,365],[x+168,434]],palette.light);
    block(ctx,x-31,279,62,62,palette.muted,7);
    ctx.fillStyle=palette.quiet;ctx.beginPath();ctx.ellipse(x,238,60,75,0,0,Math.PI*2);ctx.fill();
    shape(ctx,[[x-61,257],[x-68,220],[x-52,170],[x-16,146],[x+38,155],[x+78,200],[x+71,300],[x+43,314],[x+51,229],[x+24,204],[x-11,200],[x-41,225]],palette.ink);
    line(ctx,[[x-35,241],[x-21,241]],palette.gray,3);
    line(ctx,[[x+6,241],[x+19,241]],palette.gray,3);
    line(ctx,[[x-16,275],[x-2,277],[x+8,274]],palette.gray,2);
    line(ctx,[[x-43,331],[x-3,365],[x+42,331]],palette.gray,3);
  });
  function closePortrait(source,x,y) {
    return (ctx,w,h)=>{
      ctx.save();
      try {
        const scale=Math.max(w/415,h/330);
        ctx.translate(w/2-x*scale,h/2-y*scale);
        ctx.scale(scale,scale);
        source(ctx,width,height);
      } finally {ctx.restore();}
    };
  }
  const hostClose=closePortrait(trainCard,550,252), guestClose=closePortrait(guest,480,252);
  const landscapeSchedule=plate(ctx=>{
    const baseline=375, scale=18, origins=[175,360,545,730], hours=["06 h","10 h","14 h","18 h"];
    type(ctx,"Salidas por hora",105,88,24,palette.ink,"left",620);
    line(ctx,[[102,baseline],[860,baseline]],palette.line,2);
    departures.forEach((value,i)=>{
      const x=origins[i], top=baseline-value*scale;
      block(ctx,x,top,76,baseline-top,i===2?palette.red:palette.muted);
      type(ctx,value,x+38,top-22,28,i===2?palette.red:palette.ink,"center",620);
      type(ctx,hours[i],x+38,baseline+35,27,palette.ink,"center");
    });
  });
  function schedule(ctx,w,h) {
    if(w>=h) {
      landscapeSchedule(ctx,w,h);
      return;
    }
    const left=.10*w,right=.90*w,slot=(right-left)/departures.length,base=.73*h;
    const tallest=Math.max(...departures),plotHeight=.30*h,barWidth=.62*slot;
    const hours=["06 h","10 h","14 h","18 h"];
    block(ctx,0,0,w,h,palette.paper);
    type(ctx,"Salidas por hora",left,.33*h,.057*w,palette.ink,"left",620);
    line(ctx,[[left,base],[right,base]],palette.line,.004*w);
    departures.forEach((value,i)=>{
      const center=left+(i+.5)*slot,top=base-plotHeight*value/tallest;
      const emphasized=i===2;
      block(ctx,center-barWidth/2,top,barWidth,base-top,emphasized?palette.red:palette.muted);
      type(ctx,value,center,top-.045*w,.052*w,emphasized?palette.red:palette.ink,"center",620);
      type(ctx,hours[i],center,.778*h,.047*w,palette.ink,"center");
    });
  }
  function mark(ctx,w,h) {
    const size=Math.min(w,h),x=w/2,y=h/2;
    ctx.save();
    line(ctx,[[x-size*.31,y+size*.17],[x-size*.08,y+size*.17],[x+size*.13,y-size*.13],[x+size*.30,y-size*.13]],palette.gray,size*.055);
    dot(ctx,x-size*.08,y+size*.17,size*.073,palette.red);
    ctx.restore();
  }
  globalThis.LineWorldDemoArt = Object.freeze({
    city:()=>station, network:()=>route, trainCard, guest, hostClose, guestClose, schedule,
    platformDoor, stationDetail, mark, departures, palette
  });
})();
