#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2", "numpy>=2,<3", "av>=18,<20"]
# ///
"""Compose a weekly market film from dated closes, measured speech and an editable shot sheet."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import wave

from validar import normalize
from publicar import publish

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[3]/"media-use"/"audio"/"scripts"))
from spanish_captions import compose as compose_captions
TOOLS=HERE.parents[2]/"scripts"
FPS=30


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream,"sha256").hexdigest()


def audio_clock(audio,out,transcript=None):
    if (audio/"timeline.json").is_file():
        return audio/"timeline.json"
    info=read(audio/"duraciones.json")
    rate=info["sample_rate"]
    if rate!=48000: raise ValueError("The original segmented recordings must be 48 kHz PCM.")
    dest=out/"audio";dest.mkdir(exist_ok=True)
    scenes=[];cursor=0
    with wave.open(str(dest/"master.wav"),"wb") as master:
        master.setparams((1,2,rate,0,"NONE","not compressed"))
        for index,entry in enumerate(info["scenes"]):
            src=audio/entry["file"]
            if sha(src)!=entry["sha256"]: raise ValueError("The supplied recording differs from its manifest: "+str(src))
            with wave.open(str(src),"rb") as voice:
                if (voice.getframerate(),voice.getnchannels(),voice.getsampwidth())!=(rate,1,2): raise ValueError("Expected original mono PCM.")
                n=voice.getnframes();pcm=voice.readframes(n)
            # Preserve the original film's pause lengths and sentence clock, sample for sample.
            lead=16000 if index==0 else 8000
            tail=40000 if index==len(info["scenes"])-1 else 12000
            end=cursor+lead+math.ceil(n/2000)*2000+tail
            master.writeframesraw(bytes(lead*2));master.writeframesraw(pcm);master.writeframesraw(bytes((end-cursor-lead-n)*2))
            sentences=[]
            for phrase in entry["sentences"]:
                start=cursor+lead+round(phrase["start_s"]*rate);stop=cursor+lead+round(phrase["end_s"]*rate)
                sentences.append({"text":phrase["text"],"absolute_start_sample":start,"absolute_end_sample":stop})
            scenes.append({"id":entry["id"],"start_sample":cursor,"end_sample":end,"sentences":sentences,
                           "absolute_voice_start_sample":cursor+lead,"voice_file":entry["file"],"original_voice_sha256":entry["sha256"]})
            cursor=end
    path=dest/"timeline.json"
    clock={"sample_rate":rate,"voice":info["voice"],"master":{"file":"master.wav","sha256":sha(dest/"master.wav"),
           "samples":cursor,"frames":cursor},"scenes":scenes}
    srt,cues=compose_captions(clock,transcript)
    (dest/"captions.srt").write_text(srt,encoding="utf-8")
    write(dest/"cortes-subtitulos.json",{"masterSha256":clock["master"]["sha256"],"cues":cues})
    write(path,clock)
    return path


def breadth_intervals(data,row,start,stop,end,focus,other):
    series=data["series"]
    prices=[series[key]["values"] for key in ("sp500","nasdaq","oro","btc","tlt")]
    directions=[(values[-1]>values[0])-(values[-1]<values[0]) for values in prices]
    count=max(directions.count(sign) for sign in (-1,0,1))
    def shown(frame):
        progress=row["from"]+(row["to"]-row["from"])*(frame-start)/max(1,stop-start-1)
        return min(count,math.floor(progress*count+1e-8))
    cursor=start
    for frame in range(start+1,stop):
        if shown(frame)==shown(frame-1):continue
        if cursor<frame:yield cursor,frame,[]
        yield frame,frame+1,[focus,other]
        cursor=frame+1
    if cursor<end:yield cursor,end,[]


def spoken_start(expression,phrase,rate,transcript):
    def tokens(text):
        return re.findall(r"[^\W_]+",text.casefold())
    wanted=tokens(expression) if isinstance(expression,str) else []
    scripted=tokens(phrase['text'])
    if not wanted or not any(scripted[i:i+len(wanted)]==wanted for i in range(len(scripted))):
        raise ValueError(f"The spoken cut {expression!r} must occur in its recorded sentence.")
    first,last=(phrase[k]/rate for k in ('absolute_start_sample','absolute_end_sample'))
    timed=[(token,w['start']) for w in transcript['words'] if first<=w['start']<w['end']<=last
           for token in tokens(w['word'])]
    matches=[start for i,(_,start) in enumerate(timed) if [v[0] for v in timed[i:i+len(wanted)]]==wanted]
    if len(matches)!=1:
        raise ValueError(f"Expected one measured occurrence of {expression!r} within its recorded sentence.")
    return math.ceil(matches[0]*FPS)


def plan(timeline,recipe,portrait,data,transcript=None):
    rate=timeline["sample_rate"]
    frames=math.ceil(timeline["master"]["samples"]*FPS/rate)
    phrases=[(scene,i,row) for scene in timeline["scenes"] for i,row in enumerate(scene["sentences"])]
    if [(r["scene"],r["sentence"]) for r in recipe]!=[(s["id"],i) for s,i,_ in phrases]:
        raise ValueError("The visual recipe must name each recorded sentence once and in order.")
    starts=[round((scene["start_sample"] if i==0 else row["absolute_start_sample"])*FPS/rate) for scene,i,row in phrases]
    if any('startOn' in row for row in recipe):
        origin=(transcript or {}).get('origin',{})
        if (origin.get('mediaSha256')!=timeline['master'].get('sha256') or not origin.get('mediaSha256') or
                origin.get('clock')!='seconds-from-first-decoded-sample' or not isinstance(transcript.get('words'),list)):
            raise ValueError('Spoken cuts need word timestamps measured against this master WAV and its sample clock.')
        previous=0
        for word in transcript['words']:
            if (not isinstance(word,dict) or not isinstance(word.get('word'),str) or not word['word'].strip() or
                    not all(type(word.get(k)) in (int,float) and math.isfinite(word[k]) for k in ('start','end')) or
                    not previous<=word['start']<=word['end']<=timeline['master']['samples']/rate):
                raise ValueError('Expected ordered word intervals inside the recorded master.')
            previous=word['end']
        for index,(row,(_,_,phrase)) in enumerate(zip(recipe,phrases)):
            if 'startOn' in row:
                if index==0: raise ValueError('The first shot must cover the beginning of the film.')
                starts[index]=spoken_start(row['startOn'],phrase,rate,transcript)
    shots=[];beats=[];tracks={}
    for row,start,end,(_,_,phrase) in zip(recipe,starts,starts[1:]+[frames],phrases):
        if 'yieldUnit' in row and (row['metric']!='yield' or row['yieldUnit']!='percentage-points'):
            raise ValueError('Use yieldUnit=percentage-points only for a yield shot.')
        if row["view"] not in ("coupon","line","ranking","breadth") or not 0<=row["from"]<row["to"]<=1:
            raise ValueError("Use a supported visual and a progressive range inside [0, 1].")
        if "approxPercent" in row or "spokenApprox" in row:
            bound=row.get("approxPercent"); quote=row.get("spokenApprox")
            if (row["metric"]!="rank" or type(bound) is not int or bound<=0 or not isinstance(quote,str)
                    or not quote.strip() or quote.casefold() not in phrase["text"].casefold()):
                raise ValueError("The rounded comparison needs a positive integer and the exact corresponding quote in the recorded phrase.")
            values=data["series"][row["series"]]["values"]
            magnitude=abs(100*(values[-1]/values[0]-1))
            if not 1e-8 < bound-magnitude <= .1+1e-8:
                raise ValueError("The observed change must be below the spoken approximation by at most 0.1 percentage points.")
        if end-start<10: raise ValueError("The spoken phrase is too short for a readable visual.")
        yields=data["series"]["ust10"]["values"]
        static=row["view"]=="ranking" or row["view"]=="coupon" and yields[0]==yields[-1]
        stop=start if static else start+min(round(2.4*FPS),max(9,round((end-start)*.57)))
        key=f'{row["scene"]}-{row["sentence"]+1}-{row["series"]}'
        if row["view"]=="coupon":
            focus=key+"-precio";other=key+"-rendimiento"
            tracks[focus]={"box":[.43,.52,.55,.25]};tracks[other]={"box":[.43,.27,.55,.23]}
            if portrait:
                tracks[focus]={"box":[.04,.608,.92,.16]};tracks[other]={"box":[.04,.407,.92,.15]}
        else:
            focus=key+("-amplitud" if row["view"]=="breadth" else "-valor")
            other=key+{"breadth":"-variaciones","line":"-fecha"}.get(row["view"],"-escala")
            tracks[focus]={"box":[.42,.235,.555,.492]};tracks[other]={"box":[.42,.73,.555,.12]}
            if portrait:
                tracks[focus]={"box":[.01,.394,.97,.365]};tracks[other]={"box":[.015,.765,.965,.095]}
            if row["view"]=="line":
                tracks[other]={"box":[.015,.765,.965,.105] if portrait else [.42,.73,.555,.14]}
            if row["view"]=="breadth":
                tracks[focus]={"box":[.014,.415,.035,.36] if portrait else [.423,.272,.021,.43]}
                tracks[other]={"box":[.825,.43,.13,.31] if portrait else [.895,.32,.065,.40]}
            elif row["metric"]=="rank":
                order=data.get("orden",["sp500","nasdaq","oro","btc","tlt"])
                index=order.index(row["series"])
                tracks[focus]={"box":[.045,(330+62*index)/844,.91,66/844] if portrait else
                                     [.436,(188+66*index)/720,.53,54/720]}
                tracks[other]={"box":[.045,.135,.91,.11] if portrait else [.04,.34,.36,.20]}
        shot={**row,"start":start,"end":end,"stop":stop,"focus":focus}
        shots.append(shot)
        if row["view"]=="breadth":
            intervals=breadth_intervals(data,row,start,stop,end,focus,other)
        elif static:
            intervals=((start,end,[]),)
        else:
            intervals=((start,stop,[focus,other]),(stop,end,[]))
        for a,b,active in intervals:
            cues=[{"scene":s["id"],"sentence":i} for s,i,phrase in phrases if
                  math.floor(phrase["absolute_start_sample"]*FPS/rate)<b and math.ceil(phrase["absolute_end_sample"]*FPS/rate)>a]
            beats.append({"start":a,"end":b,"focus":focus,"visible":[focus,other],"moving":active,"mode":"motion" if active else "read",
                          "idea":row["idea"],"cut":a==start and a>0,"cues":cues})
    return shots,{"fps":FPS,"frames":frames,"tracks":tracks,"beats":beats}


def run(*cmd):
    subprocess.run(list(map(str,cmd)),check=True)


def generate(args,out):
    data=normalize(read(args.datos))
    recipe=read(args.guion_visual)
    source=args.palabras
    if not source and any('startOn' in row for row in recipe):
        source=args.guion_visual.with_name('palabras-voz.json')
    if source and not source.is_file():
        raise ValueError('Provide --palabras with the word timestamps of the recorded master.')
    transcript=read(source) if source else None
    timeline=audio_clock(args.audio.resolve(),out,transcript)
    portrait=args.formato=="vertical"
    width,height=(390,844) if portrait else (1280,720)
    narration=read(timeline)
    if any('startOn' in row for row in recipe):
        if sha(timeline.parent/narration['master']['file'])!=narration['master']['sha256']:
            raise ValueError('The master WAV differs from its timeline.')
    shots,score=plan(narration,recipe,portrait,data,transcript)
    if transcript: write(out/'palabras-voz.json',transcript)
    write(out/"datos.json",data);write(out/"atencion.json",score)
    write(out/"guion-visual.json",shots)
    payload=json.dumps({"data":data,"shots":shots,"fps":FPS},ensure_ascii=False).replace("<","\\u003c")
    template=(HERE/"escena.html").read_text(encoding="utf-8")
    (out/"escena.html").write_text(template.replace("__PAYLOAD__",payload).replace("__WIDTH__",str(width)).replace("__HEIGHT__",str(height)),encoding="utf-8")
    titles={"intro":"La semana en los mercados","bolsa":"Las bolsas de Estados Unidos","oro":"El oro al contado",
            "btc":"Bitcoin","bonos":"Precio de los bonos y rendimiento del Tesoro"}
    if data.get("sintetico"):
        names={key:s.get("etiqueta",s["nombre"]) for key,s in data["series"].items()}
        titles.update(intro="Balance de prueba",bolsa=names["sp500"]+" y "+names["nasdaq"],
                      oro=names["oro"],btc=names["btc"],bonos=names["tlt"]+" y "+names["ust10"])
    project={"fps":FPS,"width":width,"height":height,"language":"spa","captionMode":"verbatim",
             "audioTimeline":Path(os.path.relpath(timeline,out)).as_posix(),
             "attention":"atencion.json","scenes":[{"id":s["id"],"title":titles.get(s["id"],s["id"]),"html":"escena.html"} for s in narration["scenes"]]}
    write(out/"proyecto.json",project)
    run(sys.executable,TOOLS/"review_attention.py","pre-render",out/"atencion.json","--audio-timeline",timeline,"--report",out/"pre-render.json")
    if args.preflight_only:return timeline
    browser=["--browser",args.browser] if args.browser else []
    run(sys.executable,TOOLS/"compose_narrated.py",out/"proyecto.json","--output",out/"mercados.mp4","--report",out/"composicion.json",*browser)
    run(sys.executable,TOOLS/"review_attention.py","post-export",out/"atencion.json","--audio-timeline",timeline,
        "--video",out/"mercados.mp4","--source-report",out/"composicion.json","--report",out/"post-export.json")
    picks=[round((s["stop"]+s["end"]-1)/2) for s in shots]
    select="+".join(f"eq(n\\,{f})" for f in picks)
    columns=min(3,len(picks))
    rows=math.ceil(len(picks)/columns)
    run("ffmpeg","-v","error","-y","-i",out/"mercados.mp4","-vf","select="+select+f",scale=390:-2:flags=lanczos,tile={columns}x{rows}:color=white",
        "-frames:v","1","-update","1",out/"frases.jpg")
    for index in (0,4,10,12):
        if index<len(picks):
            run("ffmpeg","-v","error","-y","-ss",str(picks[index]/FPS),"-i",out/"mercados.mp4",
                "-frames:v","1","-update","1",out/f"vista-{index}.png")
    run(sys.executable,HERE/"verificar.py","--out",out,"--datos",args.datos,"--audio",args.audio,*browser)

    return timeline


def declared_inputs(args):
    audio=args.audio.resolve()
    paths={args.datos.resolve(),args.guion_visual.resolve()}
    if args.recibo:
        paths.add(args.recibo.resolve())
    marks=args.palabras or args.guion_visual.with_name('palabras-voz.json')
    if marks.exists():paths.add(marks.resolve())
    if (audio/"timeline.json").is_file():
        clock=read(audio/"timeline.json")
        paths.update((audio/name).resolve() for name in
                     ["timeline.json","captions.srt",clock["master"]["file"],
                      *(s.get("voice_file") or s["voice"] for s in clock["scenes"] if s.get("voice_file") or s.get("voice"))])
    else:
        manifest=read(audio/"duraciones.json")
        paths.update((audio/name).resolve() for name in
                     ["duraciones.json","narracion.json",*(s["file"] for s in manifest["scenes"])])
    return paths


def relocate(stage,target,timeline):
    """Commit final locations and hashes for the same validated files."""
    def final(path):
        return target/path.relative_to(stage) if path.is_relative_to(stage) else path
    project=stage/"proyecto.json"
    spec=read(project)
    spec["audioTimeline"]=Path(os.path.relpath(final(timeline),target)).as_posix()
    write(project,spec)
    for report,key in (("pre-render.json","sha256"),("post-export.json","sha256"),("composicion.json","inputs")):
        path=stage/report
        if not path.is_file():continue
        obj=read(path)
        obj[key]={str(final(Path(p))):sha(project) if Path(p)==project else value
                  for p,value in obj[key].items()}
        write(path,obj)


def build_candidate(args,stage,target):
    inputs={p:sha(p) for p in declared_inputs(args) if p.is_file()}
    if args.recibo:
        from cierres import compare_rows, discrepancies
        checks=compare_rows(args.datos,args.recibo)
        problems=discrepancies(checks)
        if problems:
            first=problems[0]
            raise ValueError(f"Cierres sin confirmar con el recibo: {len(problems)}. "
                             f"{first['series']} · {first['date']} · episodio {first.get('episode')} · "
                             f"proveedor {first.get('observed')}.")
        write(stage/"cotejo-fuentes.json",checks)
    timeline=generate(args,stage)
    for path,expected in inputs.items():
        if not path.is_file() or sha(path)!=expected:
            raise ValueError(f"Input changed during rendering: {path}")
    relocate(stage,target,timeline)
    return set(inputs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos",type=Path)
    parser.add_argument("--audio",type=Path)
    parser.add_argument("--recibo",type=Path,help="Cotejar cada observación con este recibo de cierres.py antes del render.")
    parser.add_argument("--ejemplo",action="store_true",help="Render the sourced week and the five original recordings bundled with this plugin.")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--guion-visual",type=Path,default=HERE/"guion-visual.json")
    parser.add_argument("--palabras",type=Path,help="Word timestamps for this master WAV, used by subtitles and startOn cuts.")
    parser.add_argument("--preflight-only",action="store_true")
    parser.add_argument("--formato",choices=("horizontal","vertical"),default="horizontal")
    parser.add_argument("--browser",choices=("msedge","chrome","chromium"))
    args=parser.parse_args()
    if args.ejemplo:
        if args.datos or args.audio:
            parser.error("Use --ejemplo alone or supply your own --datos and --audio.")
        example=HERE/"ejemplo-2026-11-20"
        if not example.is_dir() and (HERE.parents[3]/"MANIFIESTO.json").is_file():
            example=HERE.parents[3]
        if not (example/"datos.json").is_file() or not (example/"voces").is_dir():
            parser.error("The example inputs are missing. Supply --datos and --audio or restore the source package.")
        args.datos=example/"datos.json"
        args.audio=example/"voces"
        if args.recibo is None and (example==HERE/"ejemplo-2026-11-20" or (example/"evidencia/recibo.json").is_file()):
            args.recibo=example/"evidencia/recibo.json"
        if args.palabras is None:
            args.palabras=HERE/"palabras-voz.json"
    elif not args.datos or not args.audio:
        parser.error("Supply --datos and --audio, or use the bundled --ejemplo.")
    target=publish(args.out,args.preflight_only,lambda stage,destination:build_candidate(args,stage,destination))
    print(json.dumps({"published":str(target),"preflight":args.preflight_only},ensure_ascii=False))


if __name__=="__main__":main()
