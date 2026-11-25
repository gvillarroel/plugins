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
  let numericTimeSpacing=true,timeUnitVisible=true;
  let values=[],scale=true,validMarks=true,calendarSpacing=true,visibleNumbers=true;
  if(data.kind==="time-series"){
    const circles=elements(".observation"), missing=elements(".missing");
    const numericTime=data.timeUnit!==undefined, key=numericTime?"t":"date";
    const points=new Map(circles.map(e=>[e.dataset[key],{value:+e.dataset.value,x:+e.getAttribute("cx"),y:+e.getAttribute("cy")}]));
    for(const e of missing) points.set(e.dataset[key],{value:null,x:e.getBBox().x+e.getBBox().width/2});
    const ordered=data.observations.map(d=>points.get(String(d[key])));
    values=ordered.map(d=>d?.value);
    const ySlopes=[];
    const present=ordered.filter(d=>d && d.value!==null);
    for(let i=1;i<present.length;i++) if(present[i].value!==present[0].value)
      ySlopes.push((present[i].y-present[0].y)/(present[i].value-present[0].value));
    scale=consistent(ySlopes)&&ySlopes.every(s=>s<0);
    const coordinates=data.observations.map(d=>numericTime ? d.t : Date.parse(d.date));
    const start=coordinates[0],span=coordinates.at(-1)-start;
    const firstX=ordered[0]?.x,lastX=ordered.at(-1)?.x;
    const spacing=lastX>firstX && ordered.every((point,i)=>{
      const expected=firstX+(coordinates[i]-start)/span*(lastX-firstX);
      return point && Math.abs(point.x-expected)<.01;
    });
    if(numericTime){
      numericTimeSpacing=spacing;
      timeUnitVisible=root.querySelector(".last-date")?.textContent.startsWith(data.timeUnit+" · ")===true;
    } else calendarSpacing=spacing;
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
        if(data.encoding==="paired-change"){
          const fmt=new Intl.NumberFormat(data.locale||"en",{maximumSignificantDigits:21});
          const missing=(data.locale||"en").startsWith("es")?"Sin dato":"No data";
          const show=v=>v==null?missing:(Math.abs(v)>0 && Math.abs(v)<1e-8?v.toExponential():fmt.format(v)).replace(/^-/,"−");
          return e.textContent===show(data.records[i].before)+" → "+show(data.records[i].after);
        }
        let s=e.textContent.replace(/[\u061c\u200e\u200f]/g,"").replace("−","-");
        if(values[i]===null) return s===((data.locale||"en").toLowerCase().startsWith("es")?"Sin dato":"No data");
        if(data.encoding==="rate-comparison"){
          if(!s.endsWith(" %")) return false;
          s=s.slice(0,-2);
        }
        if(separator("group")) s=s.split(separator("group")).join("");
        if(separator("decimal")) s=s.replace(separator("decimal"),".");
        for(let n=0;n<10;n++) s=s.split(localDigits.format(n)).join(String(n));
        return Number(s)===values[i];
      });
    }
    const slopes=[], zeros=[];
    for(let i=0;i<data.records.length;i++){
      const d=data.records[i], mark=marks[i], line=mark?.querySelector(".value-mark");
      if(data.encoding==="paired-change"){
        if(!mark || mark.dataset.entityId!==d.id){validMarks=false;continue}
        const cx=el=>+el.getAttribute("cx"), link=mark.querySelector(".pair-link");
        if(!!link!==(d.before!=null && d.after!=null)) validMarks=false;
        for(const role of ["before","after"]){
          const dot=mark.querySelector("."+role);
          if(!!dot!==(d[role]!=null)){validMarks=false;continue}
          if(!dot) continue;
          const origin=elements(".zero")[0];
          if(!origin){validMarks=false;continue}
          const zero=+origin.getAttribute("x1");
          if(d[role]!==0) slopes.push((cx(dot)-zero)/d[role]);
          else if(Math.abs(cx(dot)-zero)>1e-6) validMarks=false;
          if(link && Math.abs(cx(dot)-Number(link.getAttribute(role==="before"?"x1":"x2")))>1e-6)
            validMarks=false;
        }
        continue;
      }
      if(data.encoding==="rate-comparison"){
        const num=new Intl.NumberFormat(data.locale||"en",{maximumSignificantDigits:21});
        const missing=(data.locale||"en").startsWith("es")?"Sin dato":"No data";
        const show=v=>v==null?missing:num.format(v);
        if(!elements(".source-label")[i]?.textContent.endsWith(show(d.numerator)+" / "+show(d.denominator)))
          validMarks=false;
      }
      if(!mark||mark.dataset.entityId!==d.id||((d.value===null)!==(!line))){validMarks=false;continue}
      if(!line) continue;
      const x1=+line.getAttribute("x1"), x2=+line.getAttribute("x2");
      zeros.push(x1);
      if(d.value!==0) slopes.push((x2-x1)/d.value);
      else if(Math.abs(x2-x1)>1e-6) validMarks=false;
    }
    scale=consistent(zeros)&&consistent(slopes)&&slopes.every(s=>s>0);
  }
  return {outside,overlaps,values,scale,validMarks,calendarSpacing,numericTimeSpacing,timeUnitVisible,solidPaint,visibleNumbers,
    minFontPx:Math.min(...boxes.map(b=>b.size)),unitsVisible:boxes.some(b=>b.text===data.unit)};
}
