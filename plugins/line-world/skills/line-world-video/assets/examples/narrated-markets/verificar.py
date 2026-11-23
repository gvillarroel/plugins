#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2", "numpy>=2,<3"]
# ///
"""Cross-check market readouts, measured narration and decoded MP4 reading poses."""
import argparse
import base64
from collections import Counter
from datetime import date,timedelta
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import wave

import numpy as np
from playwright.sync_api import Error as BrowserError, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[3]/"scripts"))
from caption_tracks import extract as extract_captions


def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def require(condition,message):
    if not condition:raise ValueError(message)
def sha(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def number(n):return ("−" if n<0 else "")+f"{abs(n):,.2f}".replace(",","!").replace(".",",").replace("!",".")
def pct(n):return ("−" if n<0 else "+" if n>0 else "")+number(abs(n))+" %"
def direction(s):
    first,last=s["values"][0],s["values"][-1]
    return (last>first)-(last<first)


def percentage_point_labels(first,last):
    delta=round(Decimal(str(last))-Decimal(str(first)),8)
    magnitude=abs(delta).normalize()
    def decimal_es(value,digits):
        return f'{value:,.{digits}f}'.replace(',','!').replace('.',',').replace('!','.')
    bps=(magnitude*100).normalize()
    value=decimal_es(magnitude,max(2,-magnitude.as_tuple().exponent))
    headline='Sin cambio' if not delta else ('Bajó ' if delta<0 else 'Subió ')+value
    unit='0 puntos porcentuales' if not delta else 'punto porcentual' if magnitude==1 else 'puntos porcentuales'
    equivalent=decimal_es(bps,max(0,-bps.as_tuple().exponent))+(' punto básico' if bps==1 else ' puntos básicos')
    return headline,unit,equivalent


def audio_samples(path):
    return np.frombuffer(subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-map","0:a:0","-ac","1",
                         "-ar","8000","-f","s16le","-"]),dtype="<i2").astype(float)


def verify(out,original_audio,original_data,browser_channel=None):
    project=read(out/"proyecto.json");data=read(out/"datos.json");series=data["series"]
    w,h=project["width"],project["height"]
    shots=read(out/"guion-visual.json")
    tracks=read(out/"atencion.json")["tracks"]
    timeline=(out/project["audioTimeline"]).resolve()
    narration=read(timeline);master=timeline.parent/narration["master"]["file"];movie=out/"mercados.mp4"
    src=read(original_data)
    a,b=(date.fromisoformat(src[k]) for k in ("inicio","fin"))
    calendar={d.day:d.isoformat() for d in (a+timedelta(days=i) for i in range((b-a).days+1))}
    for key,original in src["series"].items():
        observations=original.get("observaciones",[])
        raw=original["values"] if "values" in original else [row["valor"] for row in observations]
        factor={"porcentaje":1,"fraccion":100,"puntos_basicos":.01}[original.get("escala_tasa","porcentaje")]
        expected=[Decimal(str(v))*Decimal(str(factor)) for v in raw]
        require(expected==[Decimal(str(v)) for v in series[key]["values"]],f"{key}: converted levels differ")
        if "fechas" in original:dated=[date.fromisoformat(d).isoformat() for d in original["fechas"]]
        elif observations:dated=[date.fromisoformat(row["fecha"]).isoformat() for row in observations]
        else:dated=[calendar[d] for d in original.get("dias",src.get("dias",[]))]
        require(dated==series[key]["fechas"],f"{key}: copied dates differ")
        copied=series[key].get("observaciones",[])
        require(len(copied)==len(observations),f"{key}: number of declared observations changed")
        for before,after in zip(observations,copied):
            require(before.get("cierre")==after.get("cierre"),f"{key}: declared closing time changed")
    calculated={}
    for key,s in series.items():
        first,last=s["values"][0],s["values"][-1]
        rate=s["tipo"]=="rendimiento"
        calculated[key]={"start":first,"end":last,"change":round((last-first)*100 if rate else 100*(last/first-1),2),
                         "unit":"pb" if rate else "%","sourceUrls":s.get("fuentes",[])}
    voices=[]
    with wave.open(str(master),"rb") as merged:
        for scene in narration["scenes"]:
            if "original_voice_sha256" not in scene:continue
            path=original_audio/scene["voice_file"]
            require(sha(path)==scene["original_voice_sha256"],"The original voice digest differs.")
            with wave.open(str(path),"rb") as orig:
                n=orig.getnframes();merged.setpos(scene["absolute_voice_start_sample"])
                require(merged.readframes(n)==orig.readframes(n),scene["id"]+": master changed the original PCM")
            voices.append({"id":scene["id"],"sha256":sha(path),"identicalPcmSamples":n})
    expected=[s["text"] for scene in narration["scenes"] for s in scene["sentences"]]
    blocks=extract_captions(movie,"spa")["cues"]
    words=" ".join(cue["text"] for cue in blocks)
    require(words.split()==" ".join(expected).split(),"Encoded subtitles differ from narration.")
    m,a=audio_samples(master),audio_samples(movie)
    correlations=[]
    for scene in narration["scenes"]:
        i,j=(round(scene[k]*8000/narration["sample_rate"]) for k in ("start_sample","end_sample"))
        j=min(j,len(m),len(a));corr=float(np.corrcoef(m[i:j],a[i:j])[0,1])
        require(corr>.98,scene["id"]+": the AAC differs from the source waveform")
        correlations.append(round(corr,6))
    reading_frames={round((s["stop"]+s["end"]-1)/2) for s in shots}
    editorial_frames=set()
    for shot in shots:
        start,stop,end=(shot[k] for k in ("start","stop","end"))
        if shot["view"]=="breadth":
            editorial_frames.update(start+round((stop-start-1)*part/4) for part in range(5))
        if shot["view"]=="line":
            editorial_frames.add(min(start+project["fps"]//2,end-1))
        if shot["metric"] in ("rank","yield"):
            editorial_frames.update((start,end-1))
    picks=sorted(reading_frames|editorial_frames)
    source_images=[];poses=[]
    with sync_playwright() as rt:
        try:browser=rt.chromium.launch(channel=browser_channel) if browser_channel else rt.chromium.launch()
        except BrowserError as e:
            if browser_channel or os.name!="nt" or "Executable doesn't exist" not in str(e):raise
            browser=rt.chromium.launch(channel="msedge")
        page=browser.new_page(viewport={"width":w,"height":h})
        page.goto((out/"escena.html").as_uri())
        page.evaluate("""()=>{const ctx=document.querySelector('canvas').getContext('2d'),original=ctx.fillText.bind(ctx);
          window.drawn=[];ctx.fillText=(s,x,y,...rest)=>{const m=ctx.measureText(s);
          drawn.push({s,x,y,font:parseFloat(ctx.font.match(/(\\d+(?:\\.\\d+)?)px/)[1]),color:ctx.fillStyle,
            box:[x-m.actualBoundingBoxLeft,y-m.actualBoundingBoxAscent,x+m.actualBoundingBoxRight,y+m.actualBoundingBoxDescent]});
          original(s,x,y,...rest)}}""")
        for fno in picks:
            shot=next(s for s in shots if s["start"]<=fno<s["end"])
            rows=page.evaluate("frame=>{drawn=[];renderAt(0,frame);return drawn}",fno)
            texts=[r["s"] for r in rows]
            if shot["view"]=="breadth":
                ids=["sp500","nasdaq","oro","btc","tlt"]
                counts=Counter(direction(series[k]) for k in ids)
                n=max(counts.values())
                labels={-1:"Bajas",1:"Alzas",0:"Sin cambio"}
                leaders=[label for sign,label in labels.items() if counts[sign]==n]
                hero="Empate" if len(leaders)>1 else f"{n} de {len(ids)}"
                if hero=="Empate":
                    require(" y ".join(leaders)+f" · {n} de {len(ids)} por grupo" in texts,
                            "The overview must name both equally frequent directions.")
                else:
                    verb={"Alzas":"subieron","Bajas":"bajaron","Sin cambio":"quedaron sin cambio"}[leaders[0]]
                    require("referencias "+verb in texts,"The opening must identify the counted direction.")
                require(not any(t.startswith("Filas señaladas") or re.search(r"\b\d+\s*/\s*\d+\b",t) for t in texts),
                        "The overview shows a second count.")
                require(all(r["color"]!="#9e1b32" for r in rows if r["s"] in ["Bitcoin",pct(calculated["btc"]["change"])]),
                        "The overview highlights Bitcoin during the broad-market sentence.")
            elif shot["view"]=="coupon":
                rate_direction=direction(series["ust10"]);price_direction=direction(series["tlt"])
                question=("¿Por qué bajan?" if rate_direction>0 else "¿Por qué suben?") if rate_direction*price_direction<0 else "¿Y su precio?"
                hero=question if shot["metric"]=="question" else "Cupón fijo"
                if shot["metric"]!="question":
                    discount={-1:"Un tipo de descuento menor",0:"El descuento se mantiene.",1:"Un tipo de descuento mayor"}
                    require(discount[rate_direction] in texts,"The coupon example must match the observed yield direction.")
            else:
                line=calculated[shot["series"]]
                if shot["metric"]=="level":
                    hero=number(line["end"])
                    closing=date.fromisoformat(series[shot["series"]]["fechas"][-1])
                    month=("ene","feb","mar","abr","may","jun","jul","ago","sept","oct","nov","dic")[closing.month-1]
                    require(any(t.startswith(f"Cierre del {closing.day} {month} · ") for t in texts),
                            "The closing price must identify its observed date and unit beside the headline.")
                elif shot["metric"]=="yield":
                    bps=round((Decimal(str(line["end"]))-Decimal(str(line["start"])))*100,6)
                    magnitude=format(abs(bps).normalize(),"f").replace(".",",")
                    hero=("−" if bps<0 else "+" if bps>0 else "")+magnitude+" pb"
                    if shot.get('yieldUnit')=='percentage-points':
                        hero,unit,equivalent=percentage_point_labels(line['start'],line['end'])
                        require(unit in texts and equivalent in texts,'Missing full percentage-point or basis-point label.')
                        if w==390:
                            require(all(r['font']>=24 for r in rows if r['s'] in (hero,unit)),
                                    'The complete mobile yield headline must retain at least 24 px type.')
                    if not data.get("sintetico"):
                        require(not any("TLT" in t or "20 años" in t for t in texts),
                                "The yield plate identifies the wrong instrument.")
                        if shot.get("yieldUnit")=="percentage-points":
                            require("Rendimiento anual del Tesoro a 10 años" in texts,
                                    "The yield plate must identify the ten-year series beside the closing levels.")
                elif shot["metric"]=="rank":
                    selected=shot["series"]
                    sign=direction(series[selected])
                    compared=(series[key] for key in ("sp500","nasdaq","oro","btc","tlt"))
                    moves=(abs(s["values"][-1]/s["values"][0]-1) for s in compared if direction(s)==sign)
                    magnitude=abs(line["end"]/line["start"]-1)
                    rank=1+sum(move>magnitude for move in moves)
                    hero="Sin cambio" if sign==0 else ("Mayor " if rank==1 else f"{rank}.ª mayor ")+("caída" if sign<0 else "alza")
                    exact=pct(line["change"])
                    selected_rows=[r for r in rows if r["s"]==exact and r["color"]=="#9e1b32"]
                    require(len(selected_rows)==1,"The selected row must highlight its observed percent once.")
                    x,y,rw,rh=tracks[shot["focus"]]["box"]
                    x1,y1,x2,y2=selected_rows[0]["box"]
                    require(x*w<=x1<=x2<=(x+rw)*w and y*h<=y1<=y2<=(y+rh)*h,
                            "The declared ranking focus must contain the observed percent in its own row.")
                    if shot.get("approxPercent"):
                        require(hero+" entre las cinco referencias" in texts,"Missing the ordinal for the ranked move.")
                        hero=f"Casi el {shot['approxPercent']} %"
                else:hero=pct(line["change"])
            require(hero in texts,f"Frame {fno}: missing verified readout {hero}")
            if data.get("sintetico"):
                require(any("DATOS SINTÉTICOS" in s for s in texts),"Missing visible synthetic attribution")
            require(all(r["box"][0]>=-.5 and r["box"][2]<=w+.5 and r["box"][1]>=-.5 and r["box"][3]<=h+.5 for r in rows),
                    f"Frame {fno}: text outside viewport")
            if w<600:require(min(r["font"] for r in rows)>=13,"Phone typography below 13 px")
            # Reserve two default player lines at both native delivery sizes.
            caption_top=h-2*math.ceil(.061*min(w,h))
            require(all(row["box"][3]<=caption_top for row in rows),
                    f"Frame {fno}: a label crosses the subtitle band at y={caption_top}")
            overlaps=[]
            for i,left in enumerate(rows):
                for right in rows[i+1:]:
                    b1,b2=left["box"],right["box"]
                    if min(b1[2],b2[2])-max(b1[0],b2[0])>1 and min(b1[3],b2[3])-max(b1[1],b2[1])>1:overlaps.append((left["s"],right["s"]))
            require(not overlaps,f"Frame {fno}: overlapping visible labels {overlaps}")
            source_images.append(base64.b64decode(page.locator("canvas").evaluate("c=>c.toDataURL('image/png').split(',')[1]")))
            poses.append({"frame":fno,"focus":shot["focus"],"readout":hero,"minimumFontPx":min(r["font"] for r in rows)})
        browser.close()
    downw,downh=(195,422) if w==390 else (320,180)
    scale=f"scale={downw}:{downh}:flags=area"
    target=subprocess.check_output(["ffmpeg","-v","error","-i",str(movie),"-map","0:v:0","-vf","select="+
        "+".join(f"eq(n\\,{k})" for k in picks)+","+scale,"-fps_mode","passthrough","-pix_fmt","rgb24","-f","rawvideo","-"])
    source=subprocess.check_output(["ffmpeg","-v","error","-f","image2pipe","-c:v","png","-i","-","-vf",scale,
        "-pix_fmt","rgb24","-f","rawvideo","-"],input=b"".join(source_images))
    stride=downw*downh*3
    require(len(target)==len(source)==stride*len(poses),"A reading frame was missing from the decoded MP4")
    for i,pose in enumerate(poses):
        sl=slice(i*stride,(i+1)*stride)
        decoded=np.frombuffer(target[sl],np.uint8).reshape(downh,downw,3)
        corners=np.concatenate([patch.reshape(-1,3) for patch in (
            decoded[:3,:3],decoded[-3:,:3],decoded[:3,-3:],decoded[-3:,-3:])])
        pose["whiteCornerMinimum"]=int(corners.min())
        require(pose["whiteCornerMinimum"]>=248,"A decoded white background corner changed colour.")
        delta=np.abs(decoded.reshape(-1).astype(int)-np.frombuffer(source[sl],np.uint8))
        pose["meanAbsEncodedRgbError"]=round(float(delta.mean()),3)
        pose["fractionOver40"]=round(float((delta>40).mean()),5)
        require(delta.mean()<4 and (delta>40).mean()<.015,f"Decoded frame {pose['frame']} differs from the authored scene.")
    attention=read(out/"post-export.json");require(attention["ok"],"Post-export attention audit failed")
    return {"ok":True,"mp4Sha256":sha(movie),"viewport":[w,h],"fps":project["fps"],"frames":attention["frames"],
            "secondsReviewed":len(attention["seconds"]),"renderedPoses":[p for p in poses if p["frame"] in reading_frames],
            "editorialPoses":[p for p in poses if p["frame"] in editorial_frames],"benchmarks":calculated,
            "previousClose":data["inicio"],"currentClose":data["fin"],"originalVoices":voices,"aacWaveformCorrelations":correlations,
            "spokenSentences":len(expected),"encodedSubtitleCues":len(blocks),"peakMovingRegions":max(
                p.get("peakSimultaneous",0) for sec in attention["seconds"] for p in sec["beats"])}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--datos",type=Path,required=True);p.add_argument("--audio",type=Path,required=True)
    p.add_argument("--browser",choices=("msedge","chrome","chromium"))
    args=p.parse_args();report=verify(args.out.resolve(),args.audio,args.datos,args.browser)
    (args.out/"verificacion.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"ok":True,"poses":len(report["renderedPoses"]),"sha256":report["mp4Sha256"]}))

