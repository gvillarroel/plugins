/* Editable, balanced composition. Visible context is explicitly requested only. */
(() => {
const C=LineWorldTheme.colors();
const S=window.STORY,rows=S.rows,stage=d3.select('#stage'),world=d3.select('#world');
const A=LineWorldAttention,M=A.settings(S.attention);
const O={diagram:{x:1920,y:0},data:{x:1920,y:1080},categories:{x:0,y:1080}};
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v)),ease=v=>{v=clamp(v);return v*v*(3-2*v)},mix=(a,b,t)=>a+(b-a)*t;
const at=id=>S.beats.find(b=>b.id===id),local=(t,id)=>t-at(id).start;
const cameraWindows={
  relations:2.6*Math.min(1,at('relations').duration/8),
  travel:at('travel').duration*.85,
  categories:2.7*Math.min(1,at('categories').duration/8),
  overview:3.6*Math.min(1,at('overview').duration/6),
};
const klass=cls=>cls.split(' ').map(c=>['label','small','note','number','quiet'].includes(c)?'world-'+c:c).join(' ');
const text=(g,x,y,value,cls='label')=>g.append('text').attr('x',x).attr('y',y).attr('class',klass(cls)).attr('data-role','data-label').text(value);
const line=(g,x1,y1,x2,y2,color=C.ink)=>g.append('line').attr('x1',x1).attr('y1',y1).attr('x2',x2).attr('y2',y2).attr('stroke',color).attr('stroke-width',LineWorldTheme.lineWidth());
const path=(g,d,cls='ink-line')=>g.append('path').attr('d',d).attr('class',cls);
const shifted=(g,o)=>g.attr('transform',`translate(${o.x} ${o.y})`);
function reveal(p,q){const length=p.node().getTotalLength();p.attr('stroke-dasharray',length+' '+length).attr('stroke-dashoffset',length*(1-clamp(q)));}
function icon(g,id,x,y,size=48){if(S.icons[id])g.append('g').attr('data-lw-icon','monochrome').attr('transform',`translate(${x} ${y}) scale(${size/24})`).html(S.icons[id]);}
function along(points,q){const value=clamp(q)*(points.length-1),i=Math.min(points.length-2,Math.floor(value)),u=ease(value-i);return{x:mix(points[i].x,points[i+1].x,u),y:mix(points[i].y,points[i+1].y,u)};}
function curve(a,b,q){const u=ease(q);return{x:mix(a.x,b.x,u),y:mix(a.y,b.y,u)+Math.sin(u*Math.PI)*100};}
let seed=431;function random(){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;}

const cloud=world.append('g').attr('id','observations').attr('data-content-anchor','observation-field').attr('data-pattern-id','line-world-guided-relations');
const nodes=[{x:340,y:540,label:S.copy.observe,icon:'database'},{x:730,y:245,label:S.copy.select},{x:1160,y:345,label:S.copy.relate,icon:'chart-no-axes-combined'},{x:1550,y:650,label:S.copy.explain,icon:'workflow'},{x:950,y:845,label:S.copy.compare}];
const edges=[[0,1],[1,2],[2,3],[3,4],[4,0],[1,4]];
const cloudEdges=cloud.append('g').selectAll('path').data(edges).join('path').attr('class','ink-line').attr('d',d=>`M${nodes[d[0]].x} ${nodes[d[0]].y} Q960 535 ${nodes[d[1]].x} ${nodes[d[1]].y}`);
const particles=Array.from({length:90},(_,i)=>{const a=random()*Math.PI*2,r=110+random()*330;return{i,x:960+Math.cos(a)*r*1.72,y:540+Math.sin(a)*r*.85,r:2+random()*4,target:nodes[i%5]}});
const dots=cloud.selectAll('.particle').data(particles).join('circle').attr('class','particle')
  .attr('data-motion-id',d=>'observation-'+d.i).attr('r',d=>d.r).attr('fill',C.muted).attr('stroke','none');
const nodeMarks=cloud.selectAll('.concept').data(nodes).join('g').attr('class','concept').attr('transform',d=>`translate(${d.x} ${d.y})`);
nodeMarks.each(function(d){const g=d3.select(this);if(d.icon)icon(g,d.icon,-24,-24);else g.append('circle').attr('r',12).attr('fill',C.ink);text(g,0,-42,d.label).attr('text-anchor','middle')});

const diagram=shifted(world.append('g').attr('id','diagram'),O.diagram);
const diagramAsset=diagram.append('g').attr('id','producer-diagram').attr('transform','translate(200 270)');
let diagramPorts=[],diagramFocus=-2;
if(S.diagramSvg){
  diagramAsset.html(S.diagramSvg);diagramAsset.selectAll('.node rect,.node circle,.node ellipse,.node polygon').attr('data-lw-surface','item');LineWorldTheme.finish(diagramAsset.node());diagramAsset.select('svg').attr('width',1520).attr('height',540).style('width','1520px').style('height','540px').style('overflow','visible');
  const inverse=stage.node().getScreenCTM().inverse();
  diagramAsset.selectAll('.node').each(function(){const circle=this.querySelector('circle'),radius=circle?+circle.getAttribute('r'):0;const point=new DOMPoint(0,-radius).matrixTransform(this.getScreenCTM()).matrixTransform(inverse);diagramPorts.push({x:point.x,y:point.y})});
}else{
  [S.copy.observe,S.copy.select,S.copy.compare,S.copy.explain].forEach((name,i)=>{const x=100+i*440;diagramAsset.append('circle').attr('cx',x).attr('cy',270).attr('r',12).attr('fill',C.ink);text(diagramAsset,x,330,name).attr('text-anchor','middle');if(i<3)path(diagramAsset,`M${x+24} 270L${x+410} 270`,'guide-line').attr('marker-end','url(#arrow)');diagramPorts.push({x:O.diagram.x+200+x,y:540})});
}
if(diagramPorts.length<2)diagramPorts=[{x:2220,y:540},{x:3540,y:540}];

const data=shifted(world.append('g').attr('id','data-island').attr('data-pattern-id','line-world-table-focus'),O.data);
const tableX=130,tableY=205,rowGap=Math.min(150,600/rows.length);
const table=data.append('g').attr('id','table').attr('transform',`translate(${tableX} ${tableY})`);
text(table,0,0,S.copy.entity,'small quiet');text(table,390,0,S.copy.before,'small quiet').attr('text-anchor','end');text(table,590,0,S.copy.after,'small quiet').attr('text-anchor','end');
line(table,0,30,650,30,C.line);
const tableRows=table.selectAll('.table-row').data(rows).join('g').attr('class','table-row').attr('data-row-id',d=>d.id).attr('transform',(d,i)=>`translate(0 ${78+i*rowGap})`);
tableRows.append('text').attr('class','world-label row-label').text(d=>d.label);
tableRows.append('text').attr('x',390).attr('class','world-number before-value').attr('text-anchor','end').text(d=>d.before);
tableRows.append('text').attr('x',590).attr('class','world-number after-value').attr('text-anchor','end').text(d=>d.after);
tableRows.append('line').attr('x1',0).attr('x2',650).attr('y1',30).attr('y2',30).attr('stroke',C.quiet).attr('stroke-width',1);
const rowRules=tableRows.append('line').attr('x1',-25).attr('x2',650).attr('y1',30).attr('y2',30)
  .attr('class','row-focus').attr('stroke',C.red).attr('stroke-width',2.5);
const unitNote=S.unit+(S.dataStatus==='synthetic'?' · '+S.copy.synthetic:'');
text(table,0,rows.length*rowGap+90,unitNote,'small quiet');
const chart=data.append('g').attr('id','paired-chart').attr('transform','translate(1040 205)');
line(chart,0,-8,36,-8,C.line);text(chart,48,0,S.copy.before,'small quiet');line(chart,190,-8,226,-8,C.ink);text(chart,238,0,S.copy.after,'small quiet');
const maximum=d3.max(rows,d=>Math.max(d.before,d.after))||1,x=d3.scaleLinear().domain([0,maximum*1.1]).range([0,690]);
const pairY=index=>58+index*rowGap;
const pairs=chart.selectAll('.pair').data(rows).join('g').attr('class','pair').attr('data-row-id',d=>d.id).attr('transform',(d,i)=>`translate(0 ${pairY(i)})`);
pairs.append('rect').attr('class','before-bar').attr('height',8).attr('fill',C.line).attr('width',d=>x(d.before));
pairs.append('rect').attr('class','after-bar').attr('y',20).attr('height',8).attr('fill',C.secondary).attr('width',d=>x(d.after));
pairs.append('text').attr('class','world-small chart-value').attr('x',d=>x(d.after)+16).attr('y',32).text(d=>d.after);
line(chart,0,rows.length*rowGap+56,690,rows.length*rowGap+56,C.line).attr('class','pair-axis');
[0,maximum/2,maximum].forEach(v=>{const px=x(v);line(chart,px,rows.length*rowGap+56,px,rows.length*rowGap+65,C.line);text(chart,px,rows.length*rowGap+102,d3.format('~g')(v),'small quiet').attr('text-anchor','middle')});
const delta=text(chart,0,0,'','small').attr('id','data-delta').attr('data-role','data-value').style('fill',C.red);
const comparisonPoint=chart.append('circle').attr('data-motion-id','before-to-after').attr('r',5).attr('fill',C.red);

const history=data.append('g').attr('id','history-chart').attr('transform','translate(1040 205)').attr('data-pattern-id','line-world-linked-history');
const historyPlotWidth=650,historyLabelGap=20,historyRightEdge=1920-1040-48;
const hmax=(d3.max(rows.flatMap(d=>d.trend))||1)*1.13,hx=d3.scaleLinear().domain([0,rows[0].trend.length-1]).range([0,historyPlotWidth]),hy=d3.scaleLinear().domain([0,hmax]).range([610,45]);
const historyAxis=line(history,0,610,historyPlotWidth,610,C.line);
line(history,0,45,0,610,C.line);
[0,hmax/2,hmax].forEach(v=>text(history,-20,hy(v)+8,d3.format('.0f')(v),'small quiet').attr('text-anchor','end'));
text(history,0,665,'1','small quiet');
const historyLastTick=text(history,historyPlotWidth,665,''+rows[0].trend.length,'small quiet').attr('text-anchor','end');
const historyAxisTitle=text(history,historyPlotWidth/2,715,S.copy.observations,'small quiet').attr('text-anchor','middle');
text(history,-20,10,S.unit,'small quiet').attr('text-anchor','end');
const lineGen=d3.line().x((d,i)=>hx(i)).y(d=>hy(d)).curve(d3.curveMonotoneX);
const histories=history.selectAll('.history-path').data(rows).join('path').attr('class','ink-line history-path').attr('data-row-id',d=>d.id).attr('d',d=>lineGen(d.trend));
const historyPaths=histories.nodes().map(path=>({path,length:path.getTotalLength()}));
const historyLabels=history.selectAll('.history-label').data(rows).join('text')
  .attr('class','world-small history-label').attr('data-row-id',d=>d.id)
  .attr('x',historyPlotWidth+historyLabelGap).attr('y',d=>hy(d.trend.at(-1))+7).text(d=>d.label+' · '+d3.format('~g')(d.trend.at(-1)));
const historyPoint=history.append('circle').attr('data-motion-id','selected-history-reading').attr('r',7).attr('fill',C.red);

const categories=shifted(world.append('g').attr('id','categories').attr('data-pattern-id','line-world-category-expansion'),O.categories);
const positive=rows.filter(d=>d.after>0),root=d3.hierarchy({children:positive.map(d=>({name:d.label,value:d.after,id:d.id}))}).sum(d=>d.value||0);d3.treemap().size([1920,1080]).paddingInner(0).round(true)(root);
const leaves=positive.length?root.leaves():[];
const categoryPair=rows.length===2&&leaves.length===2;
const cells=categories.append('g').selectAll('.cell').data(leaves).join('g').attr('class','cell').attr('data-row-id',d=>d.data.id);
if(categoryPair){
  // A single span keeps both shares directly comparable in the short reading hold.
  const left=160,right=1760,split=left+(right-left)*leaves[0].value/root.value;
  const paint=(d,i)=>i===1?C.red:C.secondary;
  const center=(d,i)=>i===0?clamp((left+split)/2,440,800):clamp((split+right)/2,1120,1480);
  cells.append('rect').attr('x',(d,i)=>i===0?left:split).attr('y',580)
    .attr('width',(d,i)=>i===0?split-left:right-split).attr('height',48).attr('fill',paint)
    .attr('data-color-role',(d,i)=>i===0?'secondary-highlight':'primary-highlight')
    .attr('data-encoding','quantity').attr('data-value',d=>d.value);
  cells.append('text').attr('x',center).attr('y',400).attr('text-anchor','middle')
    .attr('class','world-label').style('font-size','min(48px, calc(38px * var(--lw-font-scale)))').text(d=>d.data.name);
  cells.append('text').attr('x',center).attr('y',526).attr('text-anchor','middle')
    .attr('class','world-number').style('font-size','min(100px, calc(90px * var(--lw-font-scale)))').style('fill',paint).text(d=>d.value);
  text(categories,960,716,S.copy.after+' · '+unitNote,'small quiet').attr('text-anchor','middle')
    .style('font-size','calc(28px * var(--lw-font-scale))');
}else{
  cells.attr('transform',d=>`translate(${d.x0} ${d.y0})`);
  cells.append('rect').attr('width',d=>d.x1-d.x0).attr('height',d=>d.y1-d.y0).attr('fill',C.white).attr('stroke',C.line).attr('stroke-width',2).attr('data-lw-surface','group');
  cells.append('text').attr('x',28).attr('y',48).attr('class','world-label').style('fill',(d,i)=>i?C.ink:C.red).text(d=>d.data.name);
  cells.append('text').attr('x',28).attr('y',99).attr('class','world-number').style('fill',(d,i)=>i?C.ink:C.red).text(d=>d.value);
  cells.append('text').attr('x',28).attr('y',d=>d.y1-d.y0-28).attr('class','world-small').style('fill',C.secondary).text(unitNote);
  if(!leaves.length)text(categories,960,540,'0 '+S.unit,'number').attr('text-anchor','middle');
}
let categoryTarget=leaves.length?{x:O.categories.x+(leaves.at(-1).x0+leaves.at(-1).x1)/2,y:O.categories.y+(leaves.at(-1).y0+leaves.at(-1).y1)/2}:{x:960,y:1620};
const firstTablePort={x:O.data.x+tableX-40,y:O.data.y+tableY+78};
const bridge=path(world,`M${nodes.at(-1).x} ${nodes.at(-1).y}C1680 1050 1820 480 ${diagramPorts[0].x} ${diagramPorts[0].y}M${diagramPorts.at(-1).x} ${diagramPorts.at(-1).y}C3900 860 2370 940 ${firstTablePort.x} ${firstTablePort.y}M${O.data.x+90} 1910C1850 2130 1820 2120 1730 1860`,'guide-line').style('stroke',C.muted).attr('stroke-dasharray','3 13').attr('data-layout-allow-overlap','');
const guide=world.append('g').attr('id','attention-dot');guide.append('circle').attr('r',M.baseRadius+3).attr('fill',C.white);guide.append('circle').attr('r',M.baseRadius).attr('fill',A.PRIMARY_RED);
const context=text(stage,130,84,'','note').attr('id','context-label').attr('data-role','requested-context');
let currentState=null;
const motionWindows=[];
const registerMotion=(element,id,start,end,kind,mode,scope)=>{if(!element||end<=start)return;element.setAttribute('data-focus-motion-source',id);motionWindows.push({id,source:`[data-focus-motion-source="${id}"]`,scope,kind,start,end,mode});};
registerMotion(diagramAsset.node().querySelector('path.flowchart-link,.edgePath path,path.guide-line'),'linked-flow',at('relations').start+cameraWindows.relations+.1,at('relations').end-.45,'diagram','trace','#producer-diagram');
pairs.select('.after-bar').each(function(d,i){const span=(at('compare').duration-2)/rows.length;registerMotion(this,'linked-bar-'+d.id,at('compare').start+2+i*span,at('compare').start+2+(i+1)*span,'chart','pulse','#paired-chart');});
histories.each(function(d,i){if(!i)return;const span=at('history').duration/rows.length;registerMotion(this,'linked-history-'+d.id,at('history').start+i*span,at('history').start+(i+1)*span,'chart','trace','#history-chart');});
if(leaves.length)registerMotion(cells.filter((d,i)=>i===leaves.length-1).select('rect').node(),'linked-category',at('categories').start+cameraWindows.categories,at('categories').end-.45,'chart','trace','#categories');
window.FOCUS_PLAN={windows:motionWindows};
const focusMotion=LineWorldFocusMotion.attach(stage.node(),motionWindows);

function camera(t){
  let c={x:960,y:540,z:1};
  const move=(id,target,duration)=>{if(t>=at(id).start){const q=ease(local(t,id)/duration);c={x:mix(c.x,target.x,q),y:mix(c.y,target.y,q),z:mix(c.z,target.z,q)}}};
  move('relations',{x:2880,y:540,z:1},cameraWindows.relations);
  move('travel',{x:2880,y:1620,z:1},cameraWindows.travel);
  move('categories',{x:960,y:1620,z:1},cameraWindows.categories);
  move('overview',{x:1920,y:1080,z:.5},cameraWindows.overview);return c;
}
window.renderAt=function(seconds,options={}){
  const t=clamp(+seconds||0,0,S.duration-.000001),c=camera(t),pan=options.pan||[0,0],beat=S.beats.find(b=>t>=b.start&&t<b.end)?.id;
  world.attr('transform',`translate(${960-c.x*c.z+pan[0]} ${540-c.y*c.z+pan[1]}) scale(${c.z})`);
  const cloudT=t*(7/at('cloud').duration);
  const sampleProgress=d=>d.i<nodes.length?ease(A.serialProgress(cloudT,d.i,nodes.length,.45,6.3)):0;
  dots.attr('cx',d=>mix(d.x,d.target.x+28,sampleProgress(d)))
    .attr('cy',d=>mix(d.y,d.target.y+18,sampleProgress(d)));
  cloudEdges.each(function(d,i){reveal(d3.select(this),A.serialProgress(cloudT,i,edges.length,1.22,6.82));});
  const relationT=local(t,'relations')*(8/at('relations').duration);
  const nativeNodes=diagramAsset.selectAll('g.node').nodes(),nativeIndex=beat==='relations'?Math.min(nativeNodes.length-1,Math.max(0,Math.floor((relationT-2.2)/Math.max(1,5.8/nativeNodes.length)))):-1;if(nativeIndex!==diagramFocus){LineWorldTheme.focus(diagramAsset.node(),nativeNodes[nativeIndex]||null);diagramFocus=nativeIndex;}
  const compareT=local(t,'compare'),span=(at('compare').duration-2)/rows.length;
  let selected=clamp(Math.floor((compareT-2)/span),0,rows.length-1),mode='compare';
  if(t>=at('history').start){selected=clamp(Math.floor(local(t,'history')/(at('history').duration/rows.length)),0,rows.length-1);mode='history'}
  const row=rows[selected],rowY=78+selected*rowGap;
  rowRules.attr('visibility',(d,i)=>i===selected&&compareT>=.5?'visible':'hidden');
  tableRows.select('.row-label').style('fill',(d,i)=>i===selected?C.red:C.ink);
  pairs.select('.after-bar').attr('fill',(d,i)=>i===selected?C.red:C.secondary);
  const comparePhase=(compareT-2-selected*span)/span,progress=ease((comparePhase-.12)/.52);
  // Move above the lower row's readout; descend only at the true endpoint.
  comparisonPoint.attr('cx',mix(x(row.before),x(row.after),ease(progress/.75)))
    .attr('cy',pairY(selected)+4+20*ease((progress-.75)/.25))
    .attr('visibility',beat==='compare'&&compareT>=2?'visible':'hidden');
  const historyT=local(t,'history'),historyMode=historyT>=0,historySpan=at('history').duration/rows.length;
  chart.attr('display',historyMode?'none':null);history.attr('display',historyMode?null:'none');
  histories.style('stroke',(d,i)=>i===selected?C.red:C.line);
  historyLabels.attr('visibility',(d,i)=>i===selected?'visible':'hidden');
  const reading=historyPaths[selected],phaseInHistory=(historyT-selected*historySpan)/historySpan;
  const endpoint=reading.path.getPointAtLength(reading.length*ease((phaseInHistory-.1)/.68));
  historyPoint.attr('cx',endpoint.x).attr('cy',endpoint.y);
  const change=row.after-row.before;
  delta.attr('y',pairY(selected)+63)
    .attr('visibility',mode==='compare'&&compareT>=1.5?'visible':'hidden')
    .text(`${change>0?'+':''}${d3.format('~g')(change)} ${S.unit}`);
  const catActual=local(t,'categories');
  const cameraSpan=cameraWindows[beat],moving=Boolean(cameraSpan&&local(t,beat)<cameraSpan);
  bridge.attr('visibility',moving?'visible':'hidden');
  let dot={x:mix(360,nodes[0].x,ease(cloudT/3)),y:mix(360,nodes[0].y,ease(cloudT/3))};
  if(cloudT>=4)dot=along(nodes,(cloudT-4)/2.4);
  if(t>=at('relations').start)dot=relationT<2.2?curve(nodes.at(-1),diagramPorts[0],relationT/2.2):along(diagramPorts,(relationT-2.2)/5.2);
  if(t>=at('travel').start)dot=curve(diagramPorts.at(-1),firstTablePort,local(t,'travel')/cameraWindows.travel);
  if(compareT>=0)dot={x:O.data.x+tableX-40,y:O.data.y+tableY+rowY};
  if(t>=at('categories').start)dot=curve({x:O.data.x+tableX-40,y:O.data.y+tableY+rowY},categoryTarget,catActual/cameraWindows.categories);
  if(t>=at('overview').start)dot=curve(categoryTarget,{x:1920,y:1080},local(t,'overview')/cameraWindows.overview);
  const activeBeat=at(beat),phase=((t-activeBeat.start)/activeBeat.duration*rows.length)%1;
  const travelProgress=moving||beat==='travel'||beat==='overview'?clamp(local(t,beat)/cameraSpan):null;
  const guideRadius=A.radius(M,{phase,travel:travelProgress});
  if(beat==='cloud')dot.x-=guideRadius+24;
  guide.attr('transform',`translate(${dot.x} ${dot.y})`);guide.select('circle:first-child').attr('r',guideRadius+3);guide.select('circle:last-child').attr('r',guideRadius).attr('fill',A.PRIMARY_RED);
  const requestedContext=S.presentation?.contextLabels?.[beat]||'';context.text(requestedContext).attr('opacity',requestedContext?ease(local(t,beat)/.35):0);
  const figureMotion=A.solidFocus(stage.node(),focusMotion.render(t));
  currentState={seconds:t,beat,selectedRowId:row.id,before:row.before,after:row.after,mode,camera:c,dot,palette:S.palette,contextLabel:requestedContext,layout:'balanced-four-islands',guideRadius,guideColor:A.PRIMARY_RED,figureMotion};return currentState;
};
window.snapshot=()=>({...currentState});window.renderAt(0);
window.ready=document.fonts.ready.then(()=>{
 // Reserve room for the widest complete endpoint label using the loaded font.
 const historyDisplay=history.attr('display');
 history.attr('display',null);
 const widestHistoryLabel=d3.max(historyLabels.nodes(),label=>label.getBBox().width);
 const historyEnd=Math.min(historyPlotWidth,historyRightEdge-historyLabelGap-widestHistoryLabel);
 hx.range([0,historyEnd]);
 historyAxis.attr('x2',historyEnd);
 historyLastTick.attr('x',historyEnd);
 historyAxisTitle.attr('x',historyEnd/2);
 historyLabels.attr('x',historyEnd+historyLabelGap);
 histories.attr('d',d=>lineGen(d.trend));
 historyPaths.forEach(reading=>{reading.length=reading.path.getTotalLength();});
 history.attr('display',historyDisplay);
 if(categoryPair){
   // Preserve the full reading in each half, including long labels in a larger project theme.
   const readings=cells.selectAll('text');
   for(const className of ['world-label','world-number']){
     const peers=readings.filter('.'+className);
     const widest=d3.max(peers.nodes(),element=>element.getComputedTextLength());
     if(widest>640)peers.style('font-size',640/widest*parseFloat(getComputedStyle(peers.node()).fontSize)+'px');
   }
 }
 if(leaves.length){
   const target=cells.filter((d,i)=>i===leaves.length-1).select('.world-number').node();
   const box=element=>{
     const bounds=element.getBBox(),leaf=element.__data__;
     const x=O.categories.x+bounds.x+(categoryPair?0:leaf.x0);
     const y=O.categories.y+bounds.y+(categoryPair?0:leaf.y0);
     return {x0:x,y0:y,x1:x+bounds.width,y1:y+bounds.height};
   };
   const value=box(target);
   if(categoryPair){
     // The guide arrives from the right; keep the whole dot on the approach side of the digits.
     categoryTarget={x:value.x1+M.focusRadius+18,y:(value.y0+value.y1)/2};
   }else{
     categoryTarget=A.clearPort(value,{x0:O.categories.x+24,y0:O.categories.y+24,x1:O.categories.x+1896,y1:O.categories.y+1056},cells.selectAll('text').nodes().map(box),M.focusRadius+5);
   }
 }
 return renderAt(currentState.seconds);
});
})();
