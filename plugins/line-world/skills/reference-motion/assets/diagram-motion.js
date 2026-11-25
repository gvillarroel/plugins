/* Source-timed diagram studies. A single normalized clock drives all connected figures. */
(() => {
  "use strict";
  const unit = value => Math.min(1, Math.max(0, value));
  const ease = value => { const t = unit(value); return t * t * (3 - 2 * t); };
  const ramp = (p, start, end) => ease((p - start) / (end - start));
  const mix = (a, b, t) => a + (b - a) * t;

  function box(g, x, y, w, h, fill, radius=0) {
    if (w <= 0 || h <= 0) return;
    g.fillStyle = fill;
    g.beginPath();
    g.roundRect(x, y, w, h, Math.min(radius, w/2, h/2));
    g.fill();
  }
  function dot(g, x, y, radius, fill) {
    if (radius <= 0) return;
    g.fillStyle = fill;
    g.beginPath();
    g.arc(x, y, radius, 0, 2*Math.PI);
    g.fill();
  }
  function line(g, x1, y1, x2, y2, color, width=2) {
    if (width <= 0) return;
    g.strokeStyle = color;
    g.lineWidth = width;
    g.beginPath();
    g.moveTo(x1, y1);
    g.lineTo(x2, y2);
    g.stroke();
  }
  function poly(g, points, color) {
    g.fillStyle = color;
    g.beginPath();
    points.forEach(([x,y], i) => i ? g.lineTo(x, y) : g.moveTo(x,y));
    g.closePath();
    g.fill();
  }
  const fonts = new WeakMap();
  function label(g, value, x, y, size, fill, align="left", maxWidth=Infinity, weight=500) {
    if (!value || size <= 0 || maxWidth <= 0) return;
    const family = fonts.get(g) || "Arial, sans-serif";
    g.font = weight + " " + size + "px " + family;
    const measured = g.measureText(value).width;
    if (measured > maxWidth) g.font = weight + " " + (size * maxWidth / measured) + "px " + family;
    g.textAlign = align;
    g.textBaseline = "middle";
    g.fillStyle = fill;
    g.fillText(value, x, y);
  }
  function fieldPacking(g, p, labels, c) {
    const split = ramp(p, .17, .33);
    const x = mix(218, 50, split);
    const y = mix(105, 100, split);
    const w = mix(524, 379, split);
    const h = mix(308, 265, split);
    const previewX = mix(996, 515, split);
    const previewY = 100;
    const colors = [c.accent, c.neutral, c.ink, c.muted];
    const fields = [
      { first: 0, count: 12 }, { first: 12, count: 4 },
      { first: 16, count: 12 }, { first: 32, count: 12 },
    ];
    function fieldY(i) { return y + 72 + i * (h - 107) / 3; }
    function cell(index) {
      return [previewX + 2 + (index % 16) * 24.3, 348 + Math.floor(index / 16) * 24.3];
    }

    // Field identity is stationary in the left panel while its byte copies leave.
    box(g, x, y, w, h, c.quiet, 10);
    for (let i = 0; i < 4; i++) {
      const arrive = ramp(p, .016 * i, .064 + .02 * i);
      g.save();
      const fy = fieldY(i);
      if (i > 0) {
        g.beginPath();
        g.rect(x+19,fy-21,(w-38)*arrive,48);
        g.clip();
      }
      label(g, labels[i], x + 30, fy, 27, c.ink, "left", w - 118, 550);
      if (i < 3) line(g, x + 30, fy + 24, x + w - 30, fy + 24, c.line, 1);
      box(g, x + w - 56, fy - 7, 14, 14, colors[i], 2);
      g.restore();
    }
    if (split <= 0) return;

    const previewW = 389;
    const previewH = 218;
    box(g, previewX, previewY, previewW, previewH, c.ink, 9);
    for (let i = 0; i < 48; i++) {
      const [cx, cy] = cell(i);
      box(g, cx, cy, 20, 20, c.quiet, 2);
    }

    const flights = [];
    fields.forEach(({ first, count }, field) => {
      const sourceX = x + w - 49;
      const sourceY = fieldY(field);
      for (let i = 0; i < count; i++) {
        const start = .30 + field * .081 + i * .0044;
        const u = ramp(p, start, start + .17);
        if (u <= 0) continue;
        const [cx, cy] = cell(first + i);
        const tx = cx + 10;
        const ty = cy + 10;
        // A low control point makes bytes fall first and then settle horizontally.
        const bx = (1-u)*(1-u)*sourceX + 2*(1-u)*u*(sourceX+10) + u*u*tx;
        const by = (1-u)*(1-u)*sourceY + 2*(1-u)*u*(ty+8) + u*u*ty;
        const size = mix(8, 20, u);
        flights.push({bx, by, size, paint:colors[field]});
      }
    });
    flights.forEach(({bx,by,size,paint}) => box(g,bx-size/2,by-size/2,size,size,paint,2));

    const output = ramp(p,.736,.83);
    if (output > 0) {
      g.save();
      g.beginPath();
      g.rect(previewX + 3, previewY + 3, previewW - 6, previewH - 6);
      g.clip();
      for (let i = 0; i < Math.ceil(72*output); i++) {
        const drift = (p-.736) * 2.1;
        const u = ((i * .61803398875 + drift * (.05 + (i%3)*.024)) % 1 + 1) % 1;
        const v = ((i * .754877666 + Math.cos(i*.7+drift*3)*.045) % 1 + 1) % 1;
        const px = previewX + 8 + (previewW - 16)*u;
        const py = previewY + 9 + (previewH - 18)*v;
        dot(g, px, py, i%5 === 0 ? 3.8 : 1.6 + .45 * (i%3), i%4 === 0 ? c.paper : (i%3 ? c.neutral : c.accent));
      }
      g.restore();
    }
  }

  function layerPreview(g, p, labels, c) {
    const reframe = ramp(p, .04, .22);
    const stackX = mix(287, 82, reframe);
    const stackW = mix(385, 324, reframe);
    const baseY = 355;
    const ceiling = baseY - 18 - 39 - 4 * 49 * ramp(p, .22, .40);
    const previewX = mix(990, 454, reframe);
    const viewport = { x: previewX, y: 114, w: 439, h: 261 };
    const starts = [.392,.454,.518,.582];
    const levels = starts.map(t => ramp(p, t, t+.072));
    const siding = ramp(p, .68, .75) * (1-ramp(p, .80, .89));

    box(g, stackX, baseY, stackW, 73, c.quiet, 5);
    label(g, "WebGPU", stackX+stackW/2, baseY + 37, 28, c.ink, "center", stackW - 30, 650);
    box(g, stackX, baseY - 12, stackW, 9, c.accent, 2);
    const topLabels = ["Bucle", "Pases", "Shaders"];
    topLabels.forEach((v,i) => {
      const bw = (stackW - 8)/3;
      const chipX = stackX + i*(bw+4);
      box(g,chipX,ceiling,bw,34,c.quiet,3);
      label(g,v,chipX+bw/2,ceiling+17,17,c.ink,"center",bw-8,550);
    });
    if (reframe <= 0) return;

    for (let i = 0; i < 4; i++) {
      if (levels[i] <= 0) continue;
      const reveal = levels[i];
      const rowY = baseY - 18 - (i+1)*49;
      g.save();
      g.beginPath();
      g.rect(stackX,rowY,stackW*reveal,45);
      g.clip();
      const isLead = i === 3;
      const fill = isLead ? c.accent : [c.neutral, c.quiet, c.neutral][i];
      box(g, stackX, rowY + 6*(1-reveal), stackW, 44, fill, 3);
      label(g, labels[i], stackX+18, rowY+22+6*(1-reveal), 23, isLead ? c.light : c.ink, "left", stackW-34, 550);
      g.restore();
    }
    if (siding > 0) {
      g.save();
      const y = baseY - 18 - 4*49;
      g.beginPath();
      g.rect(stackX, y, stackW*siding, 194);
      g.clip();
      box(g,stackX,y,stackW,194,c.ink,3);
      label(g,"Motor",stackX+stackW/2,y+97,32,c.light,"center",stackW-40,600);
      g.restore();
    }

    // This original pavilion holds the same camera pose as shading is assembled.
    const {x,y,w,h} = viewport;
    g.save();
    g.translate(x,y);
    g.beginPath();
    g.roundRect(0,0,w,h,9);
    g.clip();
    box(g,0,0,w,h,c.quiet);
    const plate = ramp(p,.28,.41);
    const pyramid = [[219,70],[163,171],[275,171]];
    poly(g,pyramid,c.ink);
    g.beginPath();
    g.rect(0,0,w*plate,h);
    g.clip();
    box(g,0,0,w,h,c.quiet);
    const floor = [[20,185],[226,78],[423,172],[215,254]];
    poly(g,floor,c.line);
    function prism(cx,cy,rise,radius,front,right,roof) {
      const rightP=[cx+radius,cy], nose=[cx,cy+radius*.47], leftP=[cx-radius,cy];
      poly(g, [leftP,nose,[nose[0],nose[1]-rise],[leftP[0],leftP[1]-rise]],front);
      poly(g, [nose,rightP,[rightP[0],rightP[1]-rise],[nose[0],nose[1]-rise]],right);
      poly(g, [[cx-radius,cy-rise],[cx,cy-rise-radius*.47],[cx+radius,cy-rise],[cx,cy-rise+radius*.47]],roof);
    }
    const towers = [[143,151,61,28],[226,125,77,30],[303,158,54,26],[206,193,33,35]];
    g.save();
    g.beginPath();
    g.rect(0,0,w*levels[1],h);
    g.clip();
    towers.forEach(([ox,oy,rise,r]) => {
      const shift = rise*.62;
      poly(g,[[ox-r,oy],[ox,oy+r*.47],[ox+shift+4,oy+r*.47+17],[ox-r+shift,oy+15]],c.neutral);
    });
    g.restore();
    towers.forEach(([ox,oy,rise,r],i) => {
      prism(ox,oy,rise,r,c.neutral,c.muted,c.paper);
      if (levels[2] > 0) {
        g.save();
        g.beginPath();
        g.rect(0,0,w*levels[2],h);
        g.clip();
        prism(ox,oy,rise,r,i===1 ? c.accent : c.neutral,c.ink,c.paper);
        g.restore();
      }
    });
    if (levels[3] > 0) {
      g.save();
      g.beginPath();
      g.rect(0,0,w*levels[3],h);
      g.clip();
      line(g,38,192,213,258,c.paper,2);
      for (let i=0;i<5;i++) {
        const sx=62+i*28, sy=181+i*11;
        dot(g,sx,sy,2.5,c.accent);
      }
      g.restore();
    }
    g.restore();

  }
  // Front, side and top use the same projected axes as the receiving socket.
  function slab(g, x, y, w, d, h, name, selected, c) {
    const slope = .34;
    const a = [x, y], b = [x+w, y+w*slope], e = [x+d, y-d*.5], f = [b[0]+d, b[1]-d*.5];
    const down = v => [v[0], v[1]+h];
    poly(g, [a,b,down(b),down(a)], selected ? c.accent : c.quiet);
    poly(g, [b,f,down(f),down(b)], selected ? c.ink : c.neutral);
    poly(g, [a,e,f,b], selected ? c.accent : c.line);
    line(g, a[0],a[1],b[0],b[1], c.paper, 1.7);
    g.save();
    g.transform(1,slope,0,1,x+13,y+13*slope);
    label(g,name,0,h*.51,Math.min(20,h*.6), selected ? c.paper : c.ink,"left",w-26,600);
    g.restore();
  }

  function isometricLayers(g, p, labels, c) {
    const layout = ramp(p,.09,.37);
    const x = mix(368,128,layout);
    const y = 301;
    const step = 47;
    const floor = ramp(p,.17,.37);
    if (floor > 0) {
      g.save();
      g.translate(703,399);
      g.scale(floor,floor);
      const outline = [[-155,-13],[-59,-61],[158,12],[62,60]];
      poly(g,outline,c.muted);
      poly(g,outline.map(([a,b])=>[a*.96,b*.94]),c.paper);
      poly(g,[[-115,-12],[-57,-41],[113,16],[55,44]],c.quiet);
      g.restore();
    }
    for (let i=0; i<labels.length-1; i++) {
      slab(g,x,y-i*step,156,61,step-1,labels[i],false,c);
    }
    const travel = ramp(p,.39,.82);
    const lift = 56*Math.sin(Math.PI*travel);
    const activeY = y - (labels.length - 1)*step;
    slab(g,mix(x,590,travel),mix(activeY,340,travel)-lift,
      mix(156,179,travel),mix(61,67,travel),step-1,labels.at(-1),true,c);
  }

  function moduleTransfer(g, p, labels, c, props) {
    const focus = props.highlightIndex ?? 1;
    const left = 48, top = 82, rowX = 521, rowY = 90, rowW = 358, rowH = 48, gap = 17;
    box(g,left,top,421,364,c.quiet,9);
    box(g,left+3,top+3,415,358,c.paper,7);
    const route = ramp(p,.16,.52);
    for (let i=0; i<labels.length; i++) {
      const y = rowY+i*(rowH+gap);
      if (i===focus) {
        box(g,rowX,y,rowW,rowH,c.line,4);
        box(g,rowX+2,y+2,rowW-4,rowH-4,c.paper,3);
        g.save();
        g.setLineDash([4,6]);
        line(g,rowX+12,y+rowH/2,rowX+rowW-12,y+rowH/2,c.line,2);
        g.restore();
      } else {
        box(g,rowX,y,rowW,rowH,c.quiet,4);
        label(g,labels[i],rowX+18,y+rowH/2,24,c.ink,"left",rowW-40);
      }
    }
    const x = mix(rowX,left+16,route), y = mix(rowY+focus*(rowH+gap),top+17,route);
    box(g,x,y,rowW,rowH,c.accent,4);
    label(g,labels[focus],x+18,y+rowH/2,24,c.paper,"left",rowW-40,600);
    // Two columns are dependent on the arrival of the selected module.
    const columns = [
      {title:"Entradas", x:left+20, items:props.inputs ?? ["root","tamaño","objetivo"], start:.55},
      {title:"Salidas", x:left+218, items:props.outputs ?? ["vista","proyección"], start:.71}
    ];
    for (const col of columns) {
      const open = ramp(p,col.start,col.start+.16);
      if (!open) continue;
      label(g,col.title,col.x,top+109,22,c.muted,"left",157,600);
      col.items.forEach((item,i) => {
        const by = top+155+i*42;
        if (open < (i+.3)/col.items.length) return;
        dot(g,col.x+5,by,4,c.accent);
        label(g,item,col.x+18,by,20,c.ink,"left",155);
      });
    }
  }

  function sharedHost(g, p, labels, c) {
    const zoom = ramp(p,.26,.47);
    const topology = ramp(p,.73,.96);
    const centralWidth = mix(207,144,zoom);
    const cx = 480, cy = mix(262,135,topology);
    const cardW = mix(centralWidth,137,topology), cardH = mix(mix(230,168,zoom),59,topology);
    const adapterW = 255, adapterH = mix(150,95,topology);
    const top = cy-cardH/2;
    const leftOpen = ramp(p,.27,.47), rightOpen = ramp(p,.48,.67);
    const adapterY = mix(262,355,topology);
    const centers = [mix(192,247,topology), mix(768,713,topology)];
    function adapter(side, open) {
      if (!open) return;
      const s = side ? 1 : -1;
      const center = centers[side];
      const innerX = center - s*adapterW/2;
      const portX = cx + s*cardW/2;
      const cable = ramp(open,0,.23);
      const unfold = ramp(open,.23,1);
      for (const offset of [-19,25]) {
        const py = cy+offset*(1-topology);
        const endX = mix(portX,mix(innerX,center,topology),cable);
        const endY = mix(py,adapterY-adapterH/2,topology);
        line(g,portX,py,endX,py,c.muted,2);
        line(g,endX,py,endX,endY,c.muted,2);
      }
      const width = adapterW*unfold;
      if (width <= 0) return;
      const mid = innerX + s*width/2;
      box(g,mid-width/2,adapterY-adapterH/2,width,adapterH,c.quiet,6);
      if (width>90) label(g,labels[side?2:0],mid,adapterY-mix(26,0,topology),27,c.ink,"center",width-18,600);
      if (unfold>.65 && topology<.60) {
        label(g,side?"useScene(…)":"web.host(…)",mid,adapterY+19,19,c.muted,"center",width-25);
      }
    }
    adapter(0,leftOpen);adapter(1,rightOpen);
    box(g,cx-cardW/2,top,cardW,cardH,c.ink,7);
    label(g,labels[1],cx,top+mix(30,cardH/2,topology),27,c.paper,"center",cardW-18,600);
    const ports = ramp(p,.07,.25)*(1-topology);
    if (ports > .03) {
      g.save();
      g.beginPath();g.rect(cx-cardW/2,top+51,cardW,Math.max(0,cardH-57));g.clip();
      ["root","surface"].forEach((name,i) => {
        const slot = i ? Math.min(1,Math.max(0,ports*2-1)) : Math.min(1,ports*2);
        const y=cy+(i?25:-19);
        if (slot>0) {
          box(g,cx-(cardW-32)*slot/2,y-15,(cardW-32)*slot,30,c.accent,2);
          if (slot>.75) label(g,name,cx,y,18,c.paper,"center",cardW-40,600);
        }
      });
      g.restore();
    }
  }
  function passStrip(g, p, labels, c) {
    const x = 50, w = 860, top = 36, viewportH = 211;
    const lighting = ramp(p,.07,.17);
    const lamps = ramp(p,.17,.26);
    // The upper result holds its camera, even when attention moves down to the frame.
    g.save();
    g.beginPath();
    g.roundRect(x,top,w,viewportH,7);
    g.clip();
    box(g,x,top,w,viewportH,c.quiet);
    box(g,x,top+140,w,71,c.line);
    const postXs = [178, 378, 578, 778];
    const archTop = top + 43, baseline = top + 171;
    for (let i=0;i<3;i++) {
      const left=postXs[i], right=postXs[i+1], cx=(left+right)/2;
      box(g,left,archTop,right-left,baseline-archTop,c.neutral);
      g.fillStyle=c.ink;
      g.beginPath();
      g.moveTo(left+18,baseline);
      g.lineTo(left+18,archTop+97);
      g.bezierCurveTo(left+18,archTop+6,right-18,archTop+6,right-18,archTop+97);
      g.lineTo(right-18,baseline);
      g.closePath();
      g.fill();
      if (lighting>0) {
        g.save();
        g.beginPath();
        g.rect(left+18,archTop+14,(right-left-36)*lighting,baseline-archTop-13);
        g.clip();
        poly(g,[[left+18,baseline],[left+49,baseline-29],[left+96,baseline-23],[left+69,baseline]],c.muted);
        g.restore();
      }
      if (lamps>0) {
        line(g,cx,archTop+37,cx,archTop+55,c.muted,2);
        const radius=5+7*lamps;
        dot(g,cx,archTop+59,radius,c.accent);
        dot(g,cx,archTop+59,3+2*lamps,c.paper);
      }
    }
    postXs.forEach(px => {
      box(g,px-7,archTop+16,14,baseline-archTop-14,c.quiet);
      box(g,px-12,archTop+8,24,10,c.muted);
      box(g,px-14,baseline-4,28,8,c.muted);
    });
    box(g,postXs[0]-16,archTop-9,632,15,c.muted);
    box(g,postXs[0]-20,baseline+4,640,5,c.muted);
    g.restore();

    const stage = [0.32,.43,.54,.65];
    const progresses=stage.map(start=>ramp(p,start,start+.088));
    const submitted=ramp(p,.76,.84);
    const focused=submitted>0 ? -1 : stage.findLastIndex(start=>p>=start);
    const stripY=263, stripH=40, startW=116, endW=120;
    const segmentW=(w-startW-endW-15)/4;
    const segmentXs=stage.map((_,i)=>x+startW+3+i*(segmentW+3));
    const endX=x+w-endW;
    if (p>.25) {
      const intro=ramp(p,.25,.32);
      g.save();
      g.beginPath();
      g.rect(x,stripY,startW*intro,stripH);
      g.clip();
      box(g,x,stripY,startW,stripH,c.ink,3);
      label(g,"Encoder",x+startW/2,stripY+stripH/2,22,c.paper,"center",startW-10,600);
      g.restore();
    }
    for (let i=0;i<4;i++) {
      if (progresses[i]<=0) continue;
      const sx=segmentXs[i];
      const active=focused===i;
      g.save();
      g.beginPath();
      g.rect(sx,stripY,segmentW*progresses[i],stripH);
      g.clip();
      box(g,sx,stripY,segmentW,stripH,active ? c.accent : c.neutral,3);
      label(g,labels[i],sx+segmentW/2,stripY+stripH/2,22,active ? c.paper : c.ink,"center",segmentW-12,600);
      g.restore();
    }
    if (submitted>0) {
      g.save();
      g.beginPath();
      g.rect(endX,stripY,endW*submitted,stripH);
      g.clip();
      box(g,endX,stripY,endW,stripH,c.accent,3);
      label(g,"Submit",endX+endW/2,stripY+stripH/2,22,c.paper,"center",endW-12,650);
      g.restore();
    }

    const codeY=325, codeH=176;
    box(g,x,codeY,w,codeH,c.quiet,6);
    for (let i=0;i<4;i++) {
      const rowY=codeY+25+i*41;
      const active=focused===i;
      if (active) box(g,x+1,rowY-14,5,28,c.accent,1);
      label(g,labels[i]+".record(frame)",x+24,rowY,23,active ? c.accent : c.ink,"left",w*.48,active ? 650 : 500);
      const annotate=ramp(p,.79+i*.032,.85+i*.032);
      if (annotate>0) {
        const ruleX=x+w*.50, end=x+w*.71;
        line(g,ruleX,rowY,mix(ruleX,end,annotate),rowY,c.neutral,1.6);
        if (annotate>.95) {
          dot(g,end,rowY,3,c.muted);
          label(g,labels[i],end+14,rowY,22,c.ink,"left",w*.25,550);
        }
      }
    }
  }
  function importFootprint(g, p, labels, c, props = {}) {
    // The source's light cells were counted in three individual frames. Shared
    // indices deliberately remain shared rather than partitioning the bundle.
    const data = props.footprint || {
      total: 212, unit: 'kB',
      groups: [
        [0,1,2,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,40,41,43,62,126,127,128,129,130,131,133,171,172,173,174,175],
        [1,2,7,14,40,41,42,43,60,61,126,127,128,129,130,133,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,164,170],
        [2,3,4,5,6,7,8,16,17,18,19,20,21,22,23,24,25,26]
      ]
    };
    const take = p < 0.60 ? 0 : p < 0.79 ? 1 : 2;
    const selected = new Set(data.groups[take]);
    const counting = p >= 0.27, breakdown = p >= 0.44;
    const zoom = ramp(p, 0.255, 0.44);
    const columns = Math.min(data.total, Math.ceil(Math.sqrt(data.total * 2.64)));
    const rows = Math.ceil(data.total / columns);
    const finalPitch = Math.min(624 / columns, 221 / rows, 82);
    const pitch = mix(174, finalPitch, zoom);
    const finalX = 66 + (624 - finalPitch * columns) / 2;
    const finalY = 64 + (221 - finalPitch * rows) / 2;
    const originX = mix(111, finalX, zoom), originY = mix(100, finalY, zoom);
    const gap = pitch * 0.145;

    box(g, 48, 44, 864, 297, c.line, 10);
    box(g, 50, 46, 860, 293, c.paper, 9);
    g.save();
    g.beginPath(); g.rect(63, 60, 628, breakdown ? 232 : 271); g.clip();
    for (let index = 0; index < data.total; index++) {
      const x = originX + (index % columns) * pitch;
      const y = originY + Math.floor(index / columns) * pitch;
      const ink = breakdown && selected.has(index) ? c.accent : counting ? c.neutral : c.quiet;
      box(g, x, y, pitch - gap, pitch - gap, ink);
    }
    g.restore();
    if (breakdown) {
      const readoutY = 315, readout = String(selected.size) + ' ' + data.unit;
      box(g, 72, readoutY - 7, 14, 14, c.accent);
      label(g, labels[take], 99, readoutY, 20, c.ink, 'left', 360, 600);
      label(g, readout, 681, readoutY, 21, c.accent, 'right', 210, 650);
    }

    // An original small viewport keeps the right-hand framing static while
    // the left-hand camera pulls back. It encodes no part of the byte count.
    box(g, 705, 72, 190, 231, c.quiet, 4);
    label(g, 'GPU', 721, 101, 20, c.muted, 'left', 95, 650);
    box(g, 720, 121, 160, 106, c.paper);
    poly(g, [[720,208],[766,152],[792,188],[817,161],[880,213],[880,227],[720,227]], c.neutral);
    poly(g, [[720,218],[756,191],[784,205],[822,181],[866,205],[880,204],[880,227],[720,227]], c.muted);
    line(g, 720, 237, 880, 237, c.line, 1.5);

    box(g, 48, 353, 864, 143, c.quiet, 10);
    const statement = counting ? "import * as kit from 'kit'" : "import * as frames from 'kit/frames'";
    label(g, statement, 72, mix(420, 397, zoom), 27, c.ink, 'left', 806);
    if (counting) {
      label(g, String(data.total) + ' ' + data.unit, 72, 456, 40, c.ink, 'left', 270, 650);
      label(g, 'minificado · gzip', 357, 460, 19, c.muted, 'left', 430);
    }
  }
  function vertexRemap(g, p, labels, c) {
    // The 15 by 25 parameter grid has 14 by 24 cells and two triangles per cell.
    const columns = 15, rows = 25;
    const left = 280, right = 438, top = 67, bottom = 246;
    const sample = (row, col) => {
      const u = col / (columns - 1), v = row / (rows - 1);
      const angle = u * Math.PI * 2 - Math.PI / 2;
      const tier = (3 * v) % 1;
      const radius = (1 - v) * (1 - 0.54 * tier) * 57;
      return [687 + Math.cos(angle) * radius, 244 - v * 183 + Math.sin(angle) * radius * 0.21];
    };
    box(g, 48, 42, 864, 242, c.line, 9);
    box(g, 50, 44, 860, 238, c.paper, 8);
    box(g, 48, 300, 864, 197, c.quiet, 9);
    label(g, String(columns * rows), 72, 116, 48, c.ink, 'left', 154, 650);
    label(g, labels[0], 74, 148, 20, c.muted, 'left', 176);
    const surface = ramp(p, 0.65, 0.91);
    if (surface > 0) {
      label(g, String((columns - 1) * (rows - 1) * 2), 72, 211, 42, c.ink, 'left', 154, 650);
      label(g, 'triángulos', 74, 240, 20, c.muted);
    }
    for (let col = 0; col < columns; col++) {
      const x = mix(left, right, col / (columns - 1));
      line(g, x, top, x, bottom, c.quiet, 1);
    }
    for (let row = 0; row < rows; row++) {
      const y = mix(bottom, top, row / (rows - 1));
      line(g, left, y, right, y, c.quiet, 1);
    }
    label(g, 'u', (left + right) / 2, bottom + 19, 15, c.muted, 'center');
    label(g, 'v', left - 15, (top + bottom) / 2 + 5, 15, c.muted, 'center');
    const route = ramp(p, 0.15, 0.22);
    if (route > 0) {
      const endpoint = mix(463, 578, route);
      line(g, 463, 162, endpoint, 162, c.neutral);
      poly(g, [[endpoint, 162], [endpoint - 8, 158], [endpoint - 8, 166]], c.muted);
      label(g, 'f (u, v)', 519, 144, 18, c.ink, 'center');
    }
    // Paint the back of each ring before its front. The seam uses both u endpoints.
    const sectors = Array.from({ length: columns - 1 }, (_, col) => col)
      .sort((a, b) => Math.sin((a + 0.5) * 2 * Math.PI / (columns - 1) - Math.PI / 2)
        - Math.sin((b + 0.5) * 2 * Math.PI / (columns - 1) - Math.PI / 2));
    for (let row = 0; row < Math.floor(surface * (rows - 1) + 1e-7); row++) {
      for (const col of sectors) {
        const a = sample(row, col), b = sample(row, col + 1);
        const d = sample(row + 1, col), e = sample(row + 1, col + 1);
        poly(g, [a, b, d], c.accent);
        poly(g, [b, e, d], c.accent);
        line(g, b[0], b[1], d[0], d[1], c.neutral, 0.8);
        line(g, a[0], a[1], b[0], b[1], c.paper, 0.8);
      }
    }
    for (let row = 0; row < rows; row++) {
      const v = row / (rows - 1);
      for (let col = 0; col < columns; col++) {
        const u = col / (columns - 1);
        const launch = 0.25 + v * 0.235 + u * 0.026;
        const travel = ramp(p, launch, launch + 0.115);
        const [destinationX, destinationY] = sample(row, col);
        const x = mix(mix(left, right, u), destinationX, travel);
        const y = mix(mix(bottom, top, v), destinationY, travel);
        const filled = surface > 0 && v <= surface;
        dot(g, x, y, filled ? 1.38 : 1.85, filled ? c.paper : travel > 0 && travel < 1 ? c.accent : c.ink);
      }
    }
    const codeX = 78, secondY = 394;
    label(g, labels[1] + ' (u, v)', codeX, 351, 23, c.ink, 'left', 760, 600);
    if (p >= 0.13 && p < 0.68) box(g, 62, secondY - 21, 4, 61, c.accent, 2);
    label(g, 'θ = 2πu', codeX + 20, secondY, 21, c.muted);
    label(g, '(x, y, z) = (r(v) cos θ, h × v, r(v) sin θ)', codeX + 20, 435, 21, c.ink, 'left', 780);
    if (surface > 0) {
      box(g, 62, 451, 4, 28, c.accent, 2);
      label(g, '2 × 14 × 24 = 672', codeX + 20, 473, 19, c.ink);
    }
  }

  function commandLanes(g, p, labels, c) {
    const spread = ramp(p, 0.29, 0.37);
    const result = ramp(p, 0.54, 0.65);
    const compare = ramp(p, 0.79, 0.88);
    const top = mix(173, 83, spread), bottom = mix(368, 464, spread);
    const busX = 890, laneX = 467;
    const ys = [157, 235, mix(270, 313, spread), 391];
    box(g, 52, top, 383, bottom - top, c.line, 10);
    box(g, 54, top + 2, 379, bottom - top - 4, c.paper, 9);
    box(g, busX, mix(204, 137, spread), 20, mix(133, 274, spread), c.muted, 2);
    label(g, 'GPU', busX + 10, mix(187, 120, spread), 18, c.ink, 'center', 80, 650);
    const ops = ['beginPass', 'viewport', 'pipeline', 'bind', 'draw', 'end'];
    const fractions = [0.19, mix(0.94, 0.67, compare), 0.38, 0.28];
    const active = p > 0.65;
    for (let row = 0; row < 4; row++) {
      const expansion = row === 2 ? 1 : spread;
      if (expansion <= 0) continue;
      if (row !== 2 && (ys[row] < top + 25 || ys[row] > bottom - 25)) continue;
      const y = ys[row], selected = row === 1 && active;
      const strip = row === 2 ? mix(53, 30, spread) : 30 * spread;
      const laneWidth = (busX - laneX) * expansion;
      const textX = row === 2 ? mix(78, 82, spread) : 82;
      const textSize = row === 2 ? mix(32, 22, spread) : 22;
      if (selected) {
        box(g, 56, y - 21, 5, 41, c.accent, 2);
        box(g, 66, y - 20, 355, 40, c.quiet, 4);
      }
      label(g, labels[row] + '.record()', textX, y + 7, textSize, selected ? c.accent : c.ink, 'left', 337, selected ? 650 : 500);
      line(g, 435, y, laneX, y, c.neutral, 2);
      box(g, laneX, y - strip / 2, laneWidth, strip, c.quiet, 2);
      g.save();
      g.beginPath(); g.rect(laneX, y - strip / 2, laneWidth, strip); g.clip();
      if (p < 0.55) {
        if (row === 2 && spread < 0.85) {
          const step = 156, speed = 2850;
          for (let n = 0; n < ops.length; n++) {
            const x = laneX - 110 + speed * p - n * step;
            box(g, x, y - 17, 117, 34, c.neutral, 4);
            label(g, ops[n], x + 58.5, y + 6, 16, c.ink, 'center', 109, 600);
          }
        } else {
          const step = 13, start = (p - 0.32) * 3500;
          for (let n = 0; n < 31; n++) {
            const x = laneX + start - n * step - row * 26;
            box(g, x, y - 7, 5 + (n % 3) * 2, 14, n % 3 ? c.neutral : c.muted);
          }
        }
      }
      if (result > 0) {
        const w = laneWidth * fractions[row] * result;
        box(g, busX - w, y - strip / 2, w, strip, selected ? c.accent : c.muted, 2);
        if (selected) label(g, compare > 0.5 ? 'toon' : 'PBR', busX - w + 12, y + 6, 17, c.paper, 'left', w - 20, 600);
      }
      g.restore();
    }
  }

  function splitClock(g, p, labels, c) {
    const origin = 210, pitch = 82, top = 212, bottom = 337;
    const boxW = 39, period = 8;
    box(g, 51, 57, 860, 59, c.quiet, 8);
    label(g, 'render (', 73, 95, 25, c.ink);
    label(g, 'worker', 166, 95, 25, c.accent, 'left', 130, 650);
    label(g, ')', 253, 95, 25, c.ink);
    label(g, labels[0], 52, top + 38, 21, c.ink, 'left', 132, 600);
    label(g, labels[1], 52, bottom + 38, 21, c.ink, 'left', 132, 600);
    box(g, origin - 11, top, 710, 67, c.quiet, 4);
    box(g, origin - 11, bottom, 710, 67, c.quiet, 4);
    const overrun = ramp(p, 0.66, 0.78);
    for (let i = 0; i < period; i++) {
      const x = origin + pitch * i;
      const first = ramp(p, -0.028 + i * 0.014, 0.011 + i * 0.014);
      const second = ramp(p, 0.30 + i * 0.013, 0.37 + i * 0.013);
      if (first > 0) box(g, x + 6, top + 8, 25 * first, 51, c.muted, 2);
      // A longer worker frame absorbs the fifth dispatch; the UI keeps every beat.
      const dispatched = i === 4 ? 1 - overrun : 1;
      if (first * dispatched > 0) box(g, x, top + 8, 3 * first * dispatched, 51, c.ink);
      if (second * dispatched > 0) {
        const reach = (bottom - (top + 59)) * second * dispatched;
        line(g, x + 1.5, top + 59, x + 1.5, top + 59 + reach, c.neutral, 1.5);
      }
      const duration = i === 3 ? boxW + pitch * overrun : boxW * dispatched;
      if (second * duration > 0) box(g, x, bottom + 8, duration * second, 51, c.accent, 2);
    }
    label(g, 'vsync', origin - 2, top - 14, 16, c.muted);
  }
  function intervalRefinement(g, p, unused, c, props) {
    const input = props.intervals;
    const outward = input[1].low < input[0].low || input[1].high > input[0].high;
    const steps = outward ? input.slice().reverse() : input, root = steps[0], left = 66, right = 894;
    if (outward) p = 1-p;
    const phase = unit(p) * (steps.length - 1);
    const i = Math.min(steps.length - 2, Math.floor(phase));
    const local = phase - i, parent = steps[i], child = steps[i + 1];
    const select = ramp(local, .13, .42), zoom = ramp(local, .52, .84);
    const low = mix(parent.low, child.low, zoom), high = mix(parent.high, child.high, zoom);
    const x = (v, a, b) => left + (right - left) * ((v-a)/(b-a));
    const fmt = v => Number(v.toPrecision(15)).toLocaleString("es-ES", {maximumSignificantDigits:15});
    const range = s => fmt(s.low) + " – " + fmt(s.high) + " " + props.unit;
    const active = select > 0 ? child : parent;
    label(g, props.title, left, 62, 31, c.ink, "left", right-left, 650);
    label(g, root.label, left, 136, 21, c.muted, "left", 390);
    label(g, range(root), right, 136, 22, c.ink, "right", 402);
    box(g, left, 162, right-left, 15, c.quiet, 2);
    const a = x(low,root.low,root.high), b = x(high,root.low,root.high);
    box(g, a, 162, b-a, 15, c.accent);
    line(g, a, 157, a, 183, c.accent, 2);
    line(g, b, 157, b, 183, c.accent, 2);
    line(g, a, 190, left, 284, c.line);
    line(g, b, 190, right, 284, c.line);
    box(g, left, 289, right-left, 48, i > 0 && select === 0 ? c.accent : c.quiet, 3);
    const l = x(child.low,low,high), r = x(child.high,low,high);
    if (select > 0) {
      box(g,l,289,(r-l)*select,48,c.accent);
      line(g,l,282,l,344,c.ink,2);
      line(g,l+(r-l)*select,282,l+(r-l)*select,344,c.ink,2);
    }
    if (zoom === 0 || zoom === 1) {
      const axis = zoom === 0 ? parent : child;
      label(g,fmt(axis.low),left,365,22,c.ink,"left",386);
      label(g,fmt(axis.high),right,365,22,c.ink,"right",386);
    }
    label(g,active.label,left,449,30,c.ink,"left",388,620);
    label(g,range(active),right,449,30,c.accent,"right",414,650);
  }

  function trajectoryTrace(g, p, unused, c, props) {
    const data = props.samples, first = data[0], last = data[data.length-1];
    const time = mix(first.t, last.t, p);
    const extent = key => [Math.min(...data.map(s=>s[key])), Math.max(...data.map(s=>s[key]))];
    const [xmin,xmax] = extent("x"), [ymin,ymax] = extent("y");
    // Both views use the same vertical projection. The plan preserves aspect ratio.
    const scale = Math.min(xmax > xmin ? 295/(xmax-xmin) : Infinity,
                           ymax > ymin ? 210/(ymax-ymin) : Infinity);
    const k = Number.isFinite(scale) ? scale : 1;
    const px = s => 242 + (s.x-(xmin+(xmax-xmin)/2))*k;
    const py = s => 286 - (s.y-(ymin+(ymax-ymin)/2))*k;
    const tx = s => 532 + 350*((s.t-first.t)/(last.t-first.t));
    const fmt = v => Number(v.toPrecision(4)).toLocaleString("es-ES",{maximumSignificantDigits:4});
    let j = data.findIndex(s=>s.t>time);
    if (j < 0) j = data.length;
    const prev = data[j-1], next = data[j] || prev;
    const f = prev === next ? 0 : unit((time-prev.t)/(next.t-prev.t));
    const current = {t:time, x:mix(prev.x,next.x,f), y:mix(prev.y,next.y,f)};
    label(g,props.title,56,61,32,c.ink,"left",850,650);
    label(g,"Posición ("+props.unit+")",56,135,26,c.ink,"left",360,600);
    label(g,"Altura ("+props.unit+")",510,135,26,c.ink,"left",374,600);
    box(g,54,170,373,230,c.quiet,5);
    line(g,532,172,532,403,c.muted); line(g,532,403,883,403,c.muted);
    const ticks = py({y:ymin})-py({y:ymax})>32 ? [ymin,ymax] : [ymin];
    for (const y of ticks) {
      const yy=py({y});
      line(g,528,yy,885,yy,c.line,1);
      label(g,fmt(y),518,yy,18,c.muted,"right",72);
    }
    const span = (a,b,x,color,width) => line(g,x(a),py(a),x(b),py(b),color,width);
    for (let i=1;i<j;i++) {
      span(data[i-1],data[i],px,c.ink,3);
      span(data[i-1],data[i],tx,c.ink,3);
    }
    span(prev,current,px,c.ink,3); span(prev,current,tx,c.ink,3);
    g.save(); g.setLineDash([4,7]);
    line(g,px(current),py(current),tx(current),py(current),c.muted,1.5);
    g.restore();
    for (const x of [px,tx]) dot(g,x(current),py(current),7,c.accent);
    label(g,fmt(first.t),532,428,20,c.muted,"left",112);
    label(g,fmt(last.t),882,428,20,c.muted,"right",112);
    label(g,"Tiempo ("+props.timeUnit+")",707,431,20,c.ink,"center",160);
    label(g,"y = "+fmt(current.y)+" "+props.unit,56,476,25,c.ink,"left",380,600);
    label(g,"t = "+fmt(time)+" "+props.timeUnit,882,476,25,c.ink,"right",380,600);
  }

  const renderers = Object.freeze({
    "trajectory-trace":trajectoryTrace,
    "interval-refinement":intervalRefinement,
    "pass-strip":passStrip, "import-footprint":importFootprint,
    "field-packing":fieldPacking, "layer-preview":layerPreview, "isometric-layers":isometricLayers,
    "module-transfer":moduleTransfer, "vertex-remap":vertexRemap, "command-lanes":commandLanes,
    "shared-host":sharedHost, "split-clock":splitClock
  });
  const tools = Object.freeze({unit,ease,ramp,mix,box,dot,line,poly,label});
  let systems;
  function draw(g, id, time, props, options) {
    const w = options.width, h = options.height;
    const scale = Math.min(w/960,h/540);
    fonts.set(g,options.theme.font);
    g.save();
    try {
      box(g,0,0,w,h,options.theme.paper);
      g.translate((w-960*scale)/2,(h-540*scale)/2);
      g.scale(scale,scale);
      let render = renderers[id];
      if (!render) {
        systems ??= globalThis.LineWorldSystemPatterns?.(tools);
        render = systems?.[id];
        if (!render) throw new Error("Load systems-motion.js before drawing " + id);
      }
      const elapsed=unit(time/(props.duration ?? 5));
      let pose=elapsed;
      if (props.poseClock) {
        const clock=props.poseClock;
        const right=clock.findIndex(mark=>mark[0]>=elapsed);
        if (right<=0) pose=right===0 ? clock[0][1] : 1;
        else {
          const [a,from]=clock[right-1], [b,to]=clock[right];
          pose=mix(from,to,(elapsed-a)/(b-a));
        }
      }
      render(g,pose,props.labels,options.theme,props,elapsed);
    } finally { g.restore(); }
  }
  globalThis.LineWorldDiagrams = Object.freeze({draw});
})();
