/* Editable system-design diagrams on the shared 960 x 540 stage. */
(() => {
  "use strict";
  globalThis.LineWorldSystemPatterns = ({unit, ease, ramp, mix, box, dot, line, poly, label}) => {
    // Unit coordinates belong to the whole stage. Nodes keep their bounds as
    // other nodes appear; a path is published in order of distance travelled.
    function stagedNetwork(g, p, labels, c, props, elapsed=p) {
      const amount = time => !time ? 1 : time[1] === time[0] ? Number(p >= time[0]) : ramp(p,time[0],time[1]);
      const nodes = props.nodes.map(n => {
        const move = n.moveFrom;
        const t = move ? amount(move.slice(2)) : 1;
        return {...n, x:960*(move ? mix(move[0],n.x,t) : n.x), y:540*(move ? mix(move[1],n.y,t) : n.y),
          w:n.w*960, h:n.h*540, visible:amount(n.enter),
          selected:(n.active && p>=n.active[0] && (p<n.active[1] || n.active[1]===1)) ||
            props.poseFocus?.some(([id,a,b])=>id===n.id && elapsed>=a && elapsed<b)};
      });
      const byId = new Map(nodes.map(node => [node.id,node]));

      function boundary(n, toward) {
        const dx = toward[0]-n.x, dy = toward[1]-n.y;
        const ratio = n.shape === "circle"
          ? Math.hypot(dx/(n.w/2),dy/(n.h/2))
          : Math.max(Math.abs(dx)/(n.w/2), Math.abs(dy)/(n.h/2));
        return ratio ? [n.x+dx/ratio,n.y+dy/ratio] : [n.x,n.y];
      }
      function edge(e) {
        const from=byId.get(e.from), to=byId.get(e.to);
        const via=(e.via || []).map(([x,y])=>[x*960,y*540]);
        const points=[boundary(from,via[0] || [to.x,to.y]),...via,boundary(to,via.at(-1) || [from.x,from.y])];
        const segments=[];
        let total=0;
        for(let i=1;i<points.length;i++) {
          const a=points[i-1], b=points[i], length=Math.hypot(b[0]-a[0],b[1]-a[1]);
          if(length>0) { segments.push({a,b,length,offset:total}); total+=length; }
        }
        if (!segments.length) return;
        function position(fraction) {
          const distance=unit(fraction)*total;
          const s=segments.find(part => distance <= part.offset+part.length) || segments.at(-1);
          const u=unit((distance-s.offset)/s.length);
          return {x:mix(s.a[0],s.b[0],u), y:mix(s.a[1],s.b[1],u), angle:Math.atan2(s.b[1]-s.a[1],s.b[0]-s.a[0])};
        }
        const visible=amount(e.enter);
        if(visible===0) return;
        const end=position(visible);
        g.save();g.strokeStyle=c.muted;g.lineWidth=2.5;g.lineJoin="round";
        if(e.dashed) g.setLineDash([6,5]);
        g.beginPath();g.moveTo(points[0][0],points[0][1]);
        for(const s of segments) if(s.offset+s.length<visible*total) g.lineTo(s.b[0],s.b[1]);
        g.lineTo(end.x,end.y);g.stroke();g.restore();
        if(e.directed!==false && visible*total>10) {
          const dx=Math.cos(end.angle),dy=Math.sin(end.angle);
          poly(g,[[end.x,end.y],[end.x-11*dx+4.7*dy,end.y-11*dy-4.7*dx],
            [end.x-11*dx-4.7*dy,end.y-11*dy+4.7*dx]],c.muted);
        }
        if(e.token && p>=e.token[0] && p<e.token[1]){
          const t=position(Math.min(visible,amount(e.token)));
          dot(g,t.x,t.y,7,c.paper);dot(g,t.x,t.y,5.3,c.accent);
        }
        if(e.label && visible>=1) {
          const m=position(.5);
          label(g,e.label,m.x,m.y-13,15,c.ink,"center",Math.max(58,Math.min(190,total-15)));
        }
      }

      function drawNode(n) {
        if (!n.visible) return;
        const showLabel=elapsed>=(props.poseLabels?.[n.id] ?? 0);
        const x=n.x-n.w/2,y=n.y-n.h/2,w=n.w,h=n.h;
        const fill=n.selected ? c.accent : c.quiet;
        const ink=n.selected ? c.paper : c.ink;
        g.save();
        try {
          if(n.visible<1){g.beginPath();g.rect(x-2,y-2,(w+4)*n.visible,h+4);g.clip();}
          if(n.shape==="group") {
            box(g,x,y,w,h,n.selected ? c.accent : c.line,8);
            box(g,x+2,y+2,w-4,h-4,c.paper,6);
            if(showLabel) label(g,n.label,x+13,y+15,17,c.muted,"left",w-26,600);
            return;
          }
          if(n.shape==="circle") {
            g.fillStyle=fill;g.beginPath();g.ellipse(n.x,n.y,w/2,h/2,0,0,Math.PI*2);g.fill();
          } else if(n.shape==="server") {
            box(g,x,y,w,h,fill,5);
            const notch=Math.min(12,h*.20);
            line(g,x+9,y+notch,x+w-9,y+notch,n.selected?c.paper:c.neutral,2);
            dot(g,x+12,y+notch/2,2,n.selected?c.paper:c.muted);
          } else if(n.shape==="database") {
            const r=Math.min(10,h*.14);
            box(g,x,y+r,w,h-2*r,fill);
            g.fillStyle=fill;g.beginPath();g.ellipse(n.x,y+h-r,w/2,r,0,0,Math.PI*2);g.fill();
            g.fillStyle=n.selected?c.accent:c.line;g.beginPath();g.ellipse(n.x,y+r,w/2,r,0,0,Math.PI*2);g.fill();
            g.beginPath();g.ellipse(n.x,y+r,w/2-1,r-.5,0,0,Math.PI);g.strokeStyle=n.selected?c.paper:c.neutral;g.lineWidth=1.2;g.stroke();
          } else if(n.shape==="page") {
            const fold=Math.min(w*.16,h*.20,16);
            poly(g,[[x,y],[x+w-fold,y],[x+w,y+fold],[x+w,y+h],[x,y+h]],fill);
            poly(g,[[x+w-fold,y],[x+w,y+fold],[x+w-fold,y+fold]],n.selected?c.paper:c.neutral);
          } else if(n.shape==="person") {
            const r=Math.min(w*.13,h*.15,11), cy=y+h*.19;
            dot(g,n.x,cy,r,n.selected?c.accent:c.muted);
            box(g,n.x-1.7*r,cy+r+2,3.4*r,1.64*r,n.selected?c.accent:c.muted,r*.8);
          } else if(n.shape!=="text") box(g,x,y,w,h,fill,6);
          if(!showLabel) return;
          const outside=n.shape==="text" || n.shape==="person";
          const textY=n.shape==="person"?y+h*.83:n.y+(["server","database","page"].includes(n.shape)?h*.08:0);
          const lines=String(n.label).split("\n");
          const fontSize=Math.min(n.fontSize??23,h*(n.shape==="person"?.30:.58)/Math.max(1,lines.length*.72));
          for(let i=0;i<lines.length;i++){
            label(g,lines[i],n.x,textY+(i-(lines.length-1)/2)*fontSize*1.06,fontSize,
              outside?(n.selected?c.accent:c.ink):ink,"center",w*(n.shape==="circle"?.78:.9),n.selected?700:550);
          }
        } finally {g.restore();}
      }
      nodes.filter(n=>n.shape==="group").forEach(drawNode);
      props.edges.forEach(edge);
      nodes.filter(n=>n.shape!=="group").forEach(drawNode);
    }

    // Sample a curve only up to the shared playhead. Its tangent determines the arrowhead.
    function studyArrow(g, point, fraction, color, width=3, dashed=false, tip=9) {
      if (fraction <= 0) return;
      const stop = unit(fraction);
      const steps = Math.max(2, Math.ceil(55 * stop));
      g.save();
      g.strokeStyle = color;
      g.lineWidth = width;
      g.lineCap = "round";
      if (dashed) g.setLineDash([5, 7]);
      g.beginPath();
      g.moveTo(...point(0));
      for (let i=1; i<=steps; i++) g.lineTo(...point(stop * i / steps));
      g.stroke();
      g.restore();
      const [x,y] = point(stop);
      const [qx,qy] = point(Math.max(0, stop-.009));
      const angle = Math.atan2(y-qy, x-qx);
      const size = Math.min(tip, tip * stop * 9);
      poly(g, [[x,y],
        [x - size*Math.cos(angle-.47), y - size*Math.sin(angle-.47)],
        [x - size*Math.cos(angle+.47), y - size*Math.sin(angle+.47)]], color);
    }

    function studyCurve(start, control, end) {
      return function(t) {
        const u = 1-t;
        return [u*u*start[0] + 2*u*t*control[0] + t*t*end[0],
                u*u*start[1] + 2*u*t*control[1] + t*t*end[1]];
      };
    }

    function ringHandoff(g, p, labels, c, props) {
      const cx=484, cy=283, radius=159;
      function onRing(degrees) {
        const theta=(degrees-90)*Math.PI/180;
        return [cx+radius*Math.cos(theta),cy+radius*Math.sin(theta)];
      }
      const marks=["A","B","C","D","E"];
      const owners=[46,135,226,315,19];
      const keys=[349,97,194,260];
      const keyNames=[props.keyLabel || "K0","K1","K2","K3"];
      const launch=ramp(p,.21,.405), arrival=ramp(p,.024,.135);
      const lastX=196,lastY=378;
      const newPoint=onRing(owners[4]);
      const oldPoint=onRing(owners[0]);
      const keyPoint=onRing(keys[0]);
      const ringPoint=(x,y,text,fill,fg,r=18)=>{
        dot(g,x,y,r+2,c.ink);
        dot(g,x,y,r,fill);
        label(g,text,x,y,17,fg,"center",r*1.7,700);
      };
      label(g,"Nodos",83,112,22,c.muted,"left",134,620);
      labels.slice(0,5).forEach((value,i)=>{
        const y=162+i*54;
        const a=i===4?arrival:1;
        if (!a) return;
        g.save();g.beginPath();g.rect(79,y-22,147,44*a);g.clip();
        box(g,80,y-20,145,40,i===4?c.accent:c.quiet,7);
        label(g,value,92,y,19,i===4?c.paper:c.ink,"left",88,600);
        ringPoint(lastX,y,marks[i],c.paper,c.ink,13);
        g.restore();
      });
      g.beginPath();g.arc(cx,cy,radius,0,Math.PI*2);
      g.lineWidth=3;g.strokeStyle=c.muted;g.stroke();
      const newLink=ramp(p,.64,.85);
      const oldLink=ramp(p,.57,.76);
      studyArrow(g,studyCurve([keyPoint[0]-2,keyPoint[1]-17],
        [cx-9,cy-radius-89],[newPoint[0]-4,newPoint[1]-18]),newLink,c.accent,3);
      studyArrow(g,studyCurve([keyPoint[0]+4,keyPoint[1]+16],
        [cx+3,cy-radius+111],[oldPoint[0]-20,oldPoint[1]-3]),oldLink,c.muted,2,true);
      const cancel=ramp(p,.82,.89);
      if(cancel>0) {
        const x=cx+8,y=cy-radius+65;
        box(g,x-9,y-10,20,20,c.paper,3);
        line(g,x-7,y-7,x-7+14*cancel,y-7+14*cancel,c.accent,4);
        line(g,x+7,y-7,x+7-14*cancel,y-7+14*cancel,c.accent,4);
      }
      owners.slice(0,4).forEach((a,i)=>{
        const [x,y]=onRing(a);
        ringPoint(x,y,marks[i],c.ink,c.paper);
      });
      keys.forEach((a,i)=>{
        const [x,y]=onRing(a);
        ringPoint(x,y,keyNames[i],c.paper,c.ink,17);
      });
      if(launch>0) {
        const path=studyCurve([lastX,lastY],[330,238],newPoint);
        const [x,y]=path(launch);
        ringPoint(x,y,marks[4],c.accent,c.paper);
      }
      label(g,"Claves",733,164,22,c.muted,"left",141,620);
      keyNames.forEach((key,i)=>{
        const y=207+i*45;
        ringPoint(752,y,key,c.paper,c.ink,14);
        const mark=i===0 && cancel>0 ? 4:i;
        label(g,"→ "+(labels[mark] || marks[mark]),777,y,19,
          mark===4?c.accent:c.ink,"left",130,600);
      });
    }

    function bitProbe(g,p,labels,c,props) {
      const bits=props.bits || {size:10,groups:[[1,3,4],[0,4,8],[1,5,8]]};
      const size=bits.size, groups=bits.groups;
      const cell=Math.min(68,734/size), left=(960-size*cell)/2, rowY=267;
      const starts=[[362,103],[601,103],[461,430]];
      const windows=[[.025,.20],[.32,.48],[.645,.844]];
      const high=new Set();
      groups.forEach((indices,i)=>{
        const [begin,end]=windows[i];
        if (p<=begin) return;
        const [x,y]=starts[i],below=i===2;
        label(g,labels[i],x,y,25,i===1?c.accent:c.ink,"center",202,680);
        indices.forEach((index,k)=>{
          const step=(end-begin)*.52/Math.max(1,indices.length-1);
          const part=ramp(p,begin+k*step,end-(indices.length-1-k)*step);
          const tx=left+(index+.5)*cell;
          const ty=below?rowY+52:rowY-28;
          const start=[x+(k-(indices.length-1)/2)*8,y+(below?-17:18)];
          const path=studyCurve(start,[mix(x,tx,.82),mix(start[1],ty,.2)],[tx,ty]);
          studyArrow(g,path,part,below?c.muted:(i===1?c.accent:c.ink),2.4,below,8);
          if (!below && part>=1) high.add(index);
        });
      });
      for(let i=0;i<size;i++) {
        const x=left+i*cell;
        const match=p>=.844&&groups[2].includes(i);
        box(g,x+1,rowY-25,cell-2,50,high.has(i)?c.ink:c.quiet,4);
        if(match) box(g,x+1,rowY+20,cell-2,5,c.accent,2);
        label(g,high.has(i)?"1":"0",x+cell/2,rowY,27,high.has(i)?c.paper:c.ink,"center",cell-8,680);
        label(g,String(i),x+cell/2,rowY+39,15,c.muted,"center",cell-6,550);
      }
      const show=ramp(p,.857,.925);
      if(show>0) {
        const possible=groups[2].every(i=>high.has(i));
        line(g,575,430,575+42*show,430,c.muted,2);
        if(show>.42) {
          box(g,622,410,150,40,possible?c.ink:c.accent,6);
          label(g,possible?"Posible":"Descartado",697,430,19,c.paper,"center",136,640);
        }
      }
    }

    function messageLadder(g,p,labels,c,props,elapsed=p) {
      const msgs=props.exchanges || [
        {from:0,label:"SYN"}, {from:1,label:"SYN + ACK"}, {from:0,label:"ACK"}
      ];
      const left=257, right=704, top=134;
      const lane=[left,right], pitch=Math.min(83,312/msgs.length);
      const lastY=top+27+pitch*msgs.length;
      const start=.065, finish=.885, step=(finish-start)/msgs.length;
      let railEnd=top;
      msgs.forEach((msg,i)=>{
        const a=start+i*step, reach=ramp(p,a-.05,a+.84*step);
        if(reach>0) railEnd=Math.max(railEnd,mix(top,top+38+i*pitch+Math.min(22,pitch*.35),reach));
      });
      lane.forEach((x,i)=>{
        box(g,x-87,80,174,51,c.quiet,8);
        label(g,labels[i],x,105,26,c.ink,"center",151,620);
        if(railEnd>top) line(g,x,top,x,Math.min(lastY,railEnd),c.muted,2);
      });
      msgs.forEach((msg,i)=>{
        const a=start+i*step, progress=ramp(p,a,a+.84*step);
        if(!progress) return;
        const x=lane[msg.from],tx=lane[1-msg.from],y=top+25+i*pitch;
        const slope=Math.min(22,pitch*.35);
        const path=t=>[mix(x,tx,t),y+slope*t];
        studyArrow(g,path,progress,c.ink,2.6,false,11);
        dot(g,x,y,3.5,c.accent);
        if(progress>.47 && elapsed>=(props.poseLabels?.["message-"+(i+1)] ?? 0)) {
          g.save();
          g.font=g.font.replace(/[\d.]+px/,"21px");
          const gap=Math.min(199,g.measureText(msg.label).width+16);
          g.restore();
          box(g,480-gap/2,y+slope/2-16,gap,31,c.paper,2);
          label(g,msg.label,480,y+slope/2,21,c.ink,"center",188,630);
        }
      });
    }

    function detailCallout(g,p,labels,c,props) {
      const parts=props.parts || ["https://","ejemplo.net","/archivo/","plano"];
      const focus=props.focusLabel || "Dirección";
      const zoom=ramp(p,.05,.195), back=ramp(p,.816,.955);
      const s=mix(mix(.12,1,zoom),.63,back);
      const x=mix(mix(399,133,zoom),445,back), y=mix(mix(170,130,zoom),71,back);
      const actorX=mix(mix(201,41,zoom),205,back);
      const actorY=mix(mix(175,385,zoom),219,back);
      const subjectScale=mix(mix(.85,.62,zoom),.92,back);
      g.save();g.translate(actorX,actorY);g.scale(subjectScale,subjectScale);
      dot(g,0,-59,11,c.ink);
      box(g,-16,-44,32,20,c.ink,8);
      label(g,focus,0,0,22,c.ink,"center",138,650);
      line(g,0,16,0,59,c.muted,2);
      box(g,-104,59,208,115,c.ink,7);
      box(g,-101,62,202,109,c.paper,5);
      box(g,-99,64,198,20,c.quiet,4);
      [0,1,2].forEach(i=>dot(g,-88+11*i,74,2.5,c.muted));
      box(g,-46,69,132,10,c.paper,3);
      g.restore();
      if(p<.025) return;
      line(g,actorX+56*subjectScale,actorY-5,x+2,y+205*s,c.muted,2);
      g.save();g.translate(x,y);g.scale(s,s);
      box(g,0,0,697,220,c.ink,9);
      box(g,3,3,691,214,c.paper,7);
      if(s>=.52) label(g,focus,348,38,26,c.ink,"center",633,650);
      // Give each contiguous part a little breathing room while preserving its relative length.
      const widths=parts.map(v=>Math.max(4,Math.min(21,String(v).length)));
      const denom=widths.reduce((a,b)=>a+b,0);
      const times=[.21,.40,.53,.625];
      let partX=27;
      parts.forEach((value,i)=>{
        const w=643*widths[i]/denom,mid=partX+w/2;
        const visible=ramp(p,times[i],times[i]+.067);
        box(g,partX,85,w-2,41,i%2?c.line:c.quiet,3);
        if(s>=.55) label(g,value,mid,105,23,c.ink,"center",w-11,610);
        if(visible>0) {
          line(g,mid,127,mid,127+27*visible,c.muted,2);
          if(visible>.65) {
            dot(g,mid,127,3,c.accent);
            label(g,labels[i],mid,179,20,c.ink,"center",w-6,600);
          }
        }
        partX+=w;
      });
      g.restore();
    }

    // Long division produces remainders downward; the endpoint reads them upward.
    function radixLadder(g, p, labels, c, props) {
      const finiteInteger = (n, fallback, max) => Number.isInteger(n) && n >= 0 && n <= max ? n : fallback;
      const candidate = finiteInteger(props.base, 62, 62);
      const base = candidate >= 2 ? candidate : 62;
      const value = finiteInteger(props.value, Math.min(11157, base ** 5 - 1), base ** 5 - 1);
      const alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
      const rows = [];
      let dividend = value;
      do {
        const quotient = Math.floor(dividend / base);
        const remainder = dividend % base;
        rows.push({ dividend, quotient, remainder, glyph: alphabet[remainder] });
        dividend = quotient;
      } while (dividend > 0);

      const spacing = Math.min(74, 250 / rows.length);
      const originY = 262 - (rows.length - 1) * spacing / 2;
      const frame = {x:75,y:95,w:810,h:350};
      box(g,frame.x,frame.y,frame.w,frame.h,c.line,9);
      box(g,frame.x+2,frame.y+2,frame.w-4,frame.h-4,c.paper,8);
      label(g,labels[0],142,132,21,c.ink,"left",165,600);
      label(g,labels[1],432,132,21,c.ink,"center",143,600);
      if (p >= .65) label(g,labels[2],619,132,21,c.ink,"center",138,600);
      const endpointX = 770;
      line(g,endpointX-66,285,endpointX+64,285,c.line,2);
      let encoded = "";
      rows.forEach(({dividend, quotient, remainder, glyph}, i) => {
        const y = originY + i * spacing;
        const x = 141 + i * 15;
        // Scaffolds are fixed throughout the computation, as in the reference.
        label(g,String(base),x-9,y,19,c.muted,"right",40);
        line(g,x,y-13,x,y+17,c.muted,1.8);
        line(g,x,y+17,x+67,y+17,c.muted,1.8);
        const start = .015 + .46 * i / rows.length;
        const close = start + .46 / rows.length;
        const computing = p>=start && p<close-.056;
        if (i === 0 || p >= start) label(g,String(dividend),x+7,y,23,computing ? c.accent : c.ink,"left",91,650);
        if (i === rows.length-1 && p >= close) label(g,String(quotient),x+23,y+spacing*.64,19,c.muted,"left",60);
        const remainderMove = ramp(p,close-.065,close+.035);
        if (remainderMove > 0) {
          const rx = mix(x+88,432,remainderMove);
          label(g,String(remainder),rx,y,24,remainderMove<1 ? c.accent : c.ink,"center",70,650);
        }
        const reverseIndex = rows.length - 1 - i;
        const decodeStart = .70 + .25 * reverseIndex / rows.length;
        const map = ramp(p,decodeStart,decodeStart+.11/rows.length);
        if (map > 0) {
          label(g,glyph,mix(462,619,map),y,26,c.accent,"center",56,700);
        }
      });
      for (let j=0; j<rows.length; j++) {
        if (p >= .70 + (.25*j+.16)/rows.length) encoded += rows[rows.length-1-j].glyph;
      }
      label(g,encoded,endpointX,260,34,c.accent,"center",137,700);
    }

    // Independent renditions share a lower-left corner and each retains its own input.
    function resolutionFan(g, p, labels, c) {
      const x=348, bottom=442;
      const startY=102, row=45;
      const fills=[c.ink,c.neutral,c.quiet,c.ink,c.neutral,c.quiet,c.accent];
      const originX=161, originY=268;
      for (let i=0; i<7; i++) {
        const start=.035+i*.113;
        const top=startY+i*row;
        const u=ramp(p,start,start+.064);
        if (u>0) line(g,originX+38,originY,mix(originX+38,x,u),mix(originY,top+17,u),c.muted,2.2);
      }
      box(g,originX-36,originY-28,72,56,c.ink,5);
      for (let n=0;n<5;n++) {
        box(g,originX-31+n*13,originY-24,7,4,c.paper);
        box(g,originX-31+n*13,originY+20,7,4,c.paper);
      }
      poly(g,[[originX-8,originY-13],[originX+13,originY],[originX-8,originY+13]],c.paper);
      label(g,labels[0],originX,originY+52,20,c.ink,"center",147,600);
      for (let i=0; i<7; i++) {
        const top=startY+i*row, width=493-i*49;
        const arrive=ramp(p,.067+i*.113,.115+i*.113);
        if (arrive<=0) continue;
        g.save();
        g.beginPath();
        g.rect(x,top,width*arrive,(bottom-top)*arrive);
        g.clip();
        box(g,x,top,width,bottom-top,c.line,7);
        box(g,x+1.5,top+1.5,width-3,bottom-top-3,fills[i],6);
        label(g,labels[i+1],x+14,top+18,20,i===0||i===3||i===6 ? c.light : c.ink,"left",width-28,650);
        g.restore();
      }
    }

    // Refill once; consume exactly one token for each admitted request.
    function tokenGate(g, p, labels, c, props) {
      const count = (n, fallback, lo) => Number.isInteger(n) && n >= lo && n <= 5 ? n : fallback;
      const tokens = count(props.tokens,1,0), requests = count(props.requests,2,1);
      const open = ramp(p,.342,.447);
      const centerX=480, bucketY=mix(264+73*ramp(p,.094,.202),201,open), decisionY=313;
      const admitted=Math.min(tokens,requests);
      function arrow(ax,ay,bx,by,u) {
        if (u<=0) return;
        const x=mix(ax,bx,u), y=mix(ay,by,u), a=Math.atan2(by-ay,bx-ax);
        line(g,ax,ay,x,y,c.muted,2);
        poly(g,[[x,y],[x-8*Math.cos(a)+4*Math.sin(a),y-8*Math.sin(a)-4*Math.cos(a)],[x-8*Math.cos(a)-4*Math.sin(a),y-8*Math.sin(a)+4*Math.cos(a)]],c.muted);
      }
      function capsule(x,y,color) {
        box(g,x-12,y-7,24,14,color,7);
      }
      if (p >= .095) {
        const refillY=bucketY-107;
        const enter=ramp(p,.095,.198);
        const dy=13*(1-enter);
        g.save();
        g.beginPath();
        g.rect(centerX-24,refillY-21+dy,137,81*enter);
        g.clip();
        box(g,centerX-10,refillY-17+dy,20,44,c.ink,8);
        poly(g,[[centerX-21,refillY+19+dy],[centerX+21,refillY+19+dy],[centerX,refillY+42+dy]],c.ink);
        dot(g,centerX,refillY-3+dy,3.6,c.paper);
        dot(g,centerX,refillY+9+dy,3.6,c.paper);
        label(g,labels[1],centerX+18,refillY+5+dy,19,c.ink,"left",94,650);
        g.restore();
      }
      let spent=0;
      const trips=[];
      for (let i=0; i<requests; i++) {
        const start=.49 + i*.42/requests;
        const move=ramp(p,start,start+.36/requests);
        const allowed=i<admitted;
        if (allowed && move>=.48) spent++;
        trips.push({move,allowed});
      }
      const stock=p<.22 ? 0 : tokens-spent;
      // Open rim and tapered walls identify a bucket even at zero stock.
      poly(g,[[424,bucketY-26],[536,bucketY-26],[526,bucketY+30],[434,bucketY+30]],c.ink);
      poly(g,[[428,bucketY-23],[532,bucketY-23],[523,bucketY+27],[437,bucketY+27]],c.paper);
      g.beginPath(); g.ellipse(centerX,bucketY-24,55,8,0,0,2*Math.PI); g.fillStyle=c.ink; g.fill();
      g.beginPath(); g.ellipse(centerX,bucketY-24,51,5.8,0,0,2*Math.PI); g.fillStyle=c.paper; g.fill();
      for(let i=0;i<stock;i++) dot(g,centerX+(i-(stock-1)/2)*15,bucketY+13,5,c.accent);
      if (open <= 0) return;
      arrow(centerX,bucketY+32,centerX,decisionY-44,open);
      arrow(259,decisionY,centerX-80,decisionY,open);
      arrow(centerX+80,decisionY,703,decisionY,open);
      arrow(centerX,decisionY+42,centerX,408,open);
      if (open<.55) return;
      box(g,112,decisionY-37,147,74,c.quiet,7);
      box(g,703,decisionY-37,147,74,c.quiet,7);
      box(g,405,410,150,55,c.quiet,7);
      poly(g,[[centerX,decisionY-42],[centerX+78,decisionY],[centerX,decisionY+42],[centerX-78,decisionY]],c.ink);
      label(g,"≥ 1",centerX,decisionY,27,c.light,"center",84,700);
      label(g,labels[0],185,decisionY-55,20,c.ink,"center",164,600);
      label(g,labels[2],776,decisionY-55,20,c.ink,"center",164,600);
      label(g,labels[3],480,488,20,c.ink,"center",190,600);
      trips.forEach(({move,allowed},i) => {
        const sx=137+(i%3)*37,sy=decisionY+(i>=3 ? 13 : requests>3 ? -12 : 0);
        const rank=allowed?i:i-admitted;
        const dx=(allowed?724:425)+(rank%3)*35,dy=(allowed?decisionY:438)+(rank>=3 ? 12 : -4);
        let x,y;
        if (move<=.48) {
          x=mix(sx,centerX,move/.48); y=mix(sy,decisionY+12,move/.48);
        } else if (allowed) {
          x=mix(centerX,dx,(move-.48)/.52); y=mix(decisionY+12,dy,(move-.48)/.52);
        } else {
          const outbound=(move-.48)/.52;
          x=mix(centerX,dx,ramp(outbound,.65,1)); y=mix(decisionY+12,dy,ramp(outbound,0,.78));
        }
        capsule(x,y,move>.48 && !allowed ? c.muted : c.accent);
      });
    }

    // Populate three priority shelves before revealing how a selector joins them.
    function queueRouter(g, p, labels, c, props) {
      const criteria=Array.isArray(props.criteria) ? props.criteria.slice(0,3) : [];
      const cx=mix(419,385,ramp(p,.025,.23)), cy=302, qx=514;
      const ys=[165,302,438];
      const mergeStart=criteria.length ? .785 : .55;
      const branch=(x1,y1,x2,y2,fraction) => {
        if (fraction>0) line(g,x1,y1,mix(x1,x2,fraction),mix(y1,y2,fraction),c.muted,2.5);
      };
      ys.forEach((y,i) => {
        const start=.045+i*.07, stroke=ramp(p,start,start+.1);
        branch(cx+47,cy,qx-42,y,stroke);
        const merge=ramp(p,mergeStart+i*.017,mergeStart+.096+i*.017);
        branch(qx+44,y,656,cy,merge);
        const arrive=ramp(p,start+.067,start+.15);
        if (arrive<=0) return;
        const n=Math.ceil(arrive*5);
        for (let j=n-1;j>=0;j--) {
          const sx=qx-38+j*3, sy=y-22-j*5;
          box(g,sx,sy,76,42,c.muted,3);
          box(g,sx+1.5,sy+1.5,73,39,c.paper,2);
        }
        label(g,labels[i+1],qx,y,19,c.ink,"center",67,650);
      });
      box(g,cx-49,cy-22,98,44,c.ink,6);
      label(g,labels[0],cx,cy,20,c.light,"center",84,650);
      const input=ramp(p,.30,.375);
      const inputLabel=typeof props.inputLabel === "string" ? props.inputLabel : "";
      if (inputLabel && input>0) {
        branch(169,cy,cx-52,cy,input);
        label(g,inputLabel,166,cy-16,18,c.ink,"center",192,550);
      }
      if (p<mergeStart && criteria.length) {
        criteria.forEach((criterion,i) => {
          const rise=ramp(p,.397+i*.039,.445+i*.039);
          if (rise<=0 || typeof criterion!=="string") return;
          box(g,584,114+i*35,137*rise,29,i===0?c.ink:c.quiet,3);
          if (rise>.94) label(g,criterion,652,128+i*35,15,i===0?c.light:c.ink,"center",124,550);
        });
      }
      const selector=ramp(p,mergeStart+.045,mergeStart+.12);
      if (selector>0) {
        box(g,655,cy-25,100*selector,50,c.accent,6);
        if (selector>.88) label(g,labels[4],705,cy,20,c.light,"center",86,650);
      }
    }
    return Object.freeze({
      "staged-network": stagedNetwork,
      "ring-handoff": ringHandoff,
      "bit-probe": bitProbe,
      "message-ladder": messageLadder,
      "detail-callout": detailCallout,
      "radix-ladder": radixLadder,
      "token-gate": tokenGate,
      "resolution-fan": resolutionFan,
      "queue-router": queueRouter
    });
  };
})();
