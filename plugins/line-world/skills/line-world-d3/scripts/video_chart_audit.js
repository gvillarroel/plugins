() => {
  const root=document.querySelector("#stage"), data=window.VIDEO_DATA;
  const elements=sel=>Array.from(root.querySelectorAll(sel));
  const frame=root.getBoundingClientRect();
  const boxes=elements("text").map(e=>{
    const b=e.getBoundingClientRect(), m=e.getScreenCTM();
    return {text:e.textContent,b,size:parseFloat(getComputedStyle(e).fontSize)*Math.hypot(m.a,m.b)};
  });
  const outside=boxes.filter(({b})=>b.left<frame.left-.5||b.top<frame.top-.5||b.right>frame.right+.5||b.bottom>frame.bottom+.5).map(d=>d.text);
  const overlaps=[];
  for(let i=0;i<boxes.length;i++) for(let j=i+1;j<boxes.length;j++){
    const a=boxes[i].b,b=boxes[j].b;
    if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)
      overlaps.push([boxes[i].text,boxes[j].text]);
  }
  const allowed=new Set(["none","rgb(255, 255, 255)","rgb(51, 62, 72)","rgb(158, 27, 50)","rgb(105, 105, 105)","rgb(207, 207, 207)"]);
  const solidPaint=elements("rect,path,circle,line,text").filter(el=>!el.closest("defs")).every(el=>{
    const style=getComputedStyle(el);
    return +style.opacity===1 && +style.fillOpacity===1 && +style.strokeOpacity===1
      && (style.fill==="none"||allowed.has(style.fill)||el.tagName==="line") && allowed.has(style.stroke);
  });
  const consistent=values=>values.length<2||Math.max(...values)-Math.min(...values)<1e-6*Math.max(1,...values.map(Math.abs));
  let values=[],scale=true,validMarks=true,calendarSpacing=true,visibleNumbers=true;
  if(data.kind==="time-series"){
    const circles=elements(".observation"), missing=elements(".missing");
    const points=new Map(circles.map(e=>[e.dataset.date,{value:+e.dataset.value,x:+e.getAttribute("cx"),y:+e.getAttribute("cy")}]));
    for(const e of missing) points.set(e.dataset.date,{value:null,x:e.getBBox().x+e.getBBox().width/2});
    const ordered=data.observations.map(d=>points.get(d.date));
    values=ordered.map(d=>d?.value);
    const ySlopes=[], xSlopes=[];
    const present=ordered.filter(d=>d && d.value!==null);
    for(let i=1;i<present.length;i++) if(present[i].value!==present[0].value)
      ySlopes.push((present[i].y-present[0].y)/(present[i].value-present[0].value));
    for(let i=1;i<ordered.length;i++) if(ordered[i] && ordered[0]){
      const days=(Date.parse(data.observations[i].date)-Date.parse(data.observations[0].date))/86400000;
      xSlopes.push((ordered[i].x-ordered[0].x)/days);
    }
    scale=consistent(ySlopes)&&ySlopes.every(s=>s<0);
    calendarSpacing=consistent(xSlopes)&&xSlopes.every(s=>s>0);
    const segments=data.observations.filter((d,i)=>d.value!==null&&(i===0||data.observations[i-1].value===null)).length;
    const moves=(root.querySelector(".trend")?.getAttribute("d")||"").match(/M/g)||[];
    validMarks=ordered.every(Boolean)&&circles.length+missing.length===data.observations.length&&moves.length===segments;
  } else {
    const texts=elements(".source-value"), marks=elements(".mark");
    values=texts.map(e=>e.hasAttribute("data-value")?JSON.parse(e.dataset.value):+e.textContent);
    if(texts.some(e=>e.hasAttribute("data-value"))){
      const parts=new Intl.NumberFormat(data.locale||"en").formatToParts(12345.6);
      const separator=type=>parts.find(p=>p.type===type)?.value;
      const localDigits=new Intl.NumberFormat(data.locale||"en",{useGrouping:false});
      visibleNumbers=texts.every((e,i)=>{
        let s=e.textContent.replace(/[\u061c\u200e\u200f]/g,"").replace("−","-");
        if(values[i]===null) return s===((data.locale||"en").toLowerCase().startsWith("es")?"Sin dato":"No data");
        if(separator("group")) s=s.split(separator("group")).join("");
        if(separator("decimal")) s=s.replace(separator("decimal"),".");
        for(let n=0;n<10;n++) s=s.split(localDigits.format(n)).join(String(n));
        return Number(s)===values[i];
      });
    }
    const slopes=[], zeros=[];
    for(let i=0;i<data.records.length;i++){
      const d=data.records[i], mark=marks[i], line=mark?.querySelector(".value-mark");
      if(!mark||mark.dataset.entityId!==d.id||((d.value===null)!==(!line))){validMarks=false;continue}
      if(!line) continue;
      const x1=+line.getAttribute("x1"), x2=+line.getAttribute("x2");
      zeros.push(x1);
      if(d.value!==0) slopes.push((x2-x1)/d.value);
      else if(Math.abs(x2-x1)>1e-6) validMarks=false;
    }
    scale=consistent(zeros)&&consistent(slopes)&&slopes.every(s=>s>0);
  }
  return {outside,overlaps,values,scale,validMarks,calendarSpacing,solidPaint,visibleNumbers,
    minFontPx:Math.min(...boxes.map(b=>b.size)),unitsVisible:boxes.some(b=>b.text===data.unit)};
}
