duration => {
  const snapshot=window.renderAt(0);
  if(!Array.isArray(snapshot.tracks)) return {supported:false};
  const cues=window.VIDEO_DATA.focusCues;
  const perSecond=[], issues=[], trackIds=new Set(), everMoving=new Set();
  let peak=0;
  const sample=t=>{
    const state=window.renderAt(t);
    const geometry=new Map([...document.querySelectorAll("[data-motion-track]")].map(e=>[e.dataset.motionTrack,e.outerHTML]));
    for(const track of state.tracks) trackIds.add(track.id);
    const active=state.tracks.filter(d=>d.active).map(d=>d.id);
    const {width,height}=document.querySelector("#stage").getBoundingClientRect();
    const point=state.focusPoint||[];
    const cue=cues?.find(c=>c.start<=t && (t<c.end || t===duration && c.end===t));
    if(cues){
      const selected=[...document.querySelectorAll(".record")].filter(row=>
        getComputedStyle(row.querySelector(".source-label")).fill==="rgb(158, 27, 50)").map(row=>row.dataset.entityId);
      const visible=[...document.querySelectorAll("[data-motion-track]")].filter(e=>getComputedStyle(e).visibility!=="hidden");
      if(cue ? state.selectedId!==cue.target || selected.length!==1 || selected[0]!==cue.target || visible.length!==2 :
          state.selectedId!==null || selected.length || visible.length || active.length || state.phase!=="reading")
        issues.push({t,problem:"rendered emphasis differs from the measured row cue",target:cue?.target??null,selected});
    }
    if((!cues || cue) && (!state.selectedId||point.length!==2||!point.every(Number.isFinite)||point[0]<0||point[0]>width||point[1]<0||point[1]>height))
      issues.push({t,problem:"missing or offscreen focus"});
    if(state.phase==="reading"?active.length!==0:active.length<2||active.length>3)
      issues.push({t,problem:"invalid simultaneous motion count",active});
    return {state,active,geometry};
  };
  for(let t=0;t<duration;t+=.125){
    const a=sample(t), b=sample(Math.min(duration,t+.012));
    const changes=[...a.geometry].filter(([k,v])=>b.geometry.get(k)!==v).map(([k])=>k);
    peak=Math.max(peak,changes.length);
    changes.forEach(id=>everMoving.add(id));
    if(a.state.selectedId===b.state.selectedId && a.state.phase===b.state.phase
       && a.active.join()===b.active.join() && (changes.length!==a.active.length||changes.some(id=>!a.active.includes(id))))
      issues.push({t,problem:"visible geometry does not match declared tracks",changes,active:a.active});
    if(changes.length>3) issues.push({t,problem:"too many changing track geometries",changes});
  }
  for(const cue of cues||[]){
    if(cue.start>0) sample(cue.start-.000001);
    const a=sample(cue.start), b=sample(cue.start+Math.min(.01,(cue.end-cue.start)*.15));
    const changed=[...a.geometry].filter(([id,geometry])=>b.geometry.get(id)!==geometry).map(([id])=>id);
    if(changed.length!==2) issues.push({t:cue.start,problem:"measured row emphasis did not move both marks"});
    changed.forEach(id=>everMoving.add(id));
    peak=Math.max(peak,changed.length);
    sample(cue.end-.000001);
    sample(cue.end);
  }
  const times=Array.from({length:Math.ceil(duration)},(_,i)=>i);times.push(duration);
  for(const seconds of times){
    const {state,active}=sample(seconds);
    perSecond.push({seconds,focus:state.selectedId,point:state.focusPoint,phase:state.phase,moving:active,tracks:state.tracks});
  }
  return {supported:true,perSecond,peak,tracks:[...trackIds],seenMoving:[...everMoving],issues,ok:!issues.length&&everMoving.size>=2};
}
