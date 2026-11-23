#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2", "numpy>=2,<3", "av>=18,<20"]
# ///
"""Generate, render and verify the narrated circuit from the measured audio project."""
import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import wave

from playwright.sync_api import Error as BrowserError, sync_playwright


HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[2]/"scripts"
FPS = 30
WIDTH, HEIGHT = 1280, 720


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def domain(left,top,right,bottom):
    return [left/WIDTH, top/HEIGHT, (right-left)/WIDTH, (bottom-top)/HEIGHT]


def plan(narration):
    rate=narration["sample_rate"]
    scenes=narration["scenes"]
    if [s["id"] for s in scenes] != ["interruptor","bobina"] or any(len(s["sentences"])!=2 for s in scenes):
        raise ValueError("Use the two-scene switch-and-coil episode and its four recorded sentences.")
    switch=next(e for e in scenes[0]["effects"] if e["sound"]=="switch/light")
    close=round(switch["absolute_start_sample"]*FPS/rate)
    if abs(close/FPS-switch["absolute_start_sample"]/rate)>.5/FPS:
        raise ValueError("The switch must land within half a delivery frame of its audio cue.")
    count=math.ceil(narration["master"]["samples"]*FPS/rate)
    spoken=[(s["id"],i,d) for s in scenes for i,d in enumerate(s["sentences"])]
    def sample(index,field):
        return spoken[index][2]["absolute_"+field+"_sample"]*FPS/rate

    edges={"close":close,"established":round(min(sample(0,"end")-.5*FPS,close+1.2*FPS)),
           "flow":round(sample(1,"start")),"flowEnd":round(sample(1,"end")),
           "magnet":round(sample(2,"start")),
           "magnetEnd":round(sample(2,"start")+(sample(2,"end")-sample(2,"start"))*.67),
           "open":round(sample(3,"start")),"opened":round(sample(3,"start")+.95*FPS)}
    tracks={
        "palanca":{"box":domain(263,177,424,283),"meaning":"El contacto móvil cierra o abre el único corte del circuito."},
        "abertura":{"box":domain(426,177,453,283),"meaning":"Las dos marcas miden visualmente el hueco entre contactos."},
        "ida":{"box":domain(455,242,607,284),"meaning":"Sentido de la corriente hacia la bobina por el conductor superior."},
        "retorno":{"box":domain(146,510,602,552),"meaning":"La misma corriente regresa al polo negativo por la rama inferior."},
        "bobina":{"box":domain(589,290,655,508),"meaning":"La marca sigue las espiras del símbolo, de arriba hacia abajo."},
        "campo":{"box":domain(763,225,1234,430),"meaning":"Una única línea cerrada del campo enlaza el interior y el exterior de la bobina."}}
    definitions=[
        (edges["close"]+1,"palanca",["palanca","abertura"],"Se reduce el hueco hasta que los contactos se tocan con el clic."),
        (edges["established"]+1,"ida",["ida","retorno","campo"],"Al cerrarse el camino aparecen la corriente convencional y el campo."),
        (edges["flow"],"palanca",[],"Los contactos permanecen unidos y el recorrido está completo."),
        (edges["flowEnd"]+1,"ida",["ida","retorno"],"La corriente sale de la placa positiva por arriba y retorna a la negativa por abajo."),
        (edges["magnet"],"bobina",[],"El conductor de la derecha atraviesa las espiras."),
        (edges["magnetEnd"]+1,"campo",["bobina","campo"],"La corriente de la bobina crea un campo con líneas que se cierran."),
        (edges["open"],"campo",[],"La línea vuelve por fuera después de pasar por el interior."),
        (edges["opened"]+1,"palanca",["palanca","ida","campo"],"La apertura interrumpe el recorrido y desaparece el campo creado por la corriente."),
        (count,"palanca",[],"Tras la apertura, el circuito de corriente continua queda sin corriente sostenida.")]
    beats=[]
    start=0
    for end,focus,moving,idea in definitions:
        if end<=start:
            raise ValueError("The measured voice does not leave enough time for the explanatory poses.")
        cues=[{"scene":scene,"sentence":index} for scene,index,row in spoken
              if math.floor(row["absolute_start_sample"]*FPS/rate)<end and math.ceil(row["absolute_end_sample"]*FPS/rate)>start]
        beats.append({"start":start,"end":end,"focus":focus,"moving":moving,"mode":"motion" if moving else "read","idea":idea,"cues":cues})
        start=end
    return {"fps":FPS,"frames":count,"tracks":tracks,"beats":beats},edges


def verify_source(html, audio, folder, score, edges, browser_channel):
    with sync_playwright() as runtime:
        try:
            browser=runtime.chromium.launch(channel=browser_channel) if browser_channel else runtime.chromium.launch()
        except BrowserError as exc:
            if browser_channel or os.name!="nt" or "Executable doesn't exist" not in str(exc):
                raise
            browser=runtime.chromium.launch(channel="msedge")
        try:
            page=browser.new_page(viewport={"width":WIDTH,"height":HEIGHT})
            page.goto(html.as_uri())
            samples=[page.evaluate("f=>renderAt(0,f)",frame) for frame in range(0,score["frames"],FPS)]
            before=page.evaluate("f=>renderAt(0,f)",edges["close"]-1)
            closed=page.evaluate("f=>renderAt(0,f)",edges["close"])
            corrected=page.evaluate("f=>renderAt(0,f)",edges["opened"])
            assert before["gap"]>0 and abs(closed["gap"])<1e-8 and corrected["gap"]>60
            assert closed["tip"]==[410,263] and corrected["fieldLength"]==0
            page.evaluate("renderAt(8.54)")
            a=page.locator("canvas").screenshot()
            page.evaluate("renderAt(1.90)")
            page.evaluate("renderAt(8.54)")
            assert a==page.locator("canvas").screenshot(), "Seeking changed the picture"
            for name,frame in (("contacto",edges["close"]),("campo",edges["magnetEnd"]),("abierto",edges["opened"])):
                page.evaluate("f=>renderAt(0,f)",frame)
                page.locator("canvas").screenshot(path=str(folder/("fuente-"+name+".png")))
        finally:
            browser.close()
    with wave.open(str(audio/"master.wav"),"rb") as stream:
        rate=stream.getframerate()
        pcm=array("h",stream.readframes(rate//2))
    if sys.byteorder=="big":
        pcm.byteswap()
    onset=next(i for i,value in enumerate(pcm) if abs(value)>=104)
    cue=edges["close"]/FPS
    assert abs(onset/rate-cue)<=.5/FPS, "The switch sound and contact are more than half a delivery frame apart"
    return {"fps":FPS,"frames":score["frames"],"sourceSha256":digest(html),"masterSha256":digest(audio/"master.wav"),
            "perSecond":samples,"contact":{"firstClosedFrame":edges["close"],"seconds":cue,"previousGapPixels":before["gap"],
            "closedGapPixels":closed["gap"],"measuredAudioOnsetSeconds":onset/rate,
            "scheduledEffectSeconds":read(audio/"timeline.json")["scenes"][0]["effects"][0]["at_s"],
            "offsetMilliseconds":1000*(cue-onset/rate),"threshold":"-50 dBFS before narration"},
            "openedGapPixels":corrected["gap"],"repeatSeek":True}


def run(*arguments):
    subprocess.run([str(a) for a in arguments],check=True)


def verify_encoded(film, audio, edges, score):
    first=edges["close"]
    # This patch is immediately left of the fixed contact. A burgundy blade
    # fills it only once the air gap has closed, including after H.264 encoding.
    crop="crop=8:6:392:260"
    raw=subprocess.check_output(["ffmpeg","-v","error","-i",str(film),"-map","0:v:0",
        "-vf",f"select=lte(n\\,{first+1}),{crop}","-fps_mode","passthrough","-pix_fmt","rgb24","-f","rawvideo","-"])
    counts=[]
    for start in range(0,len(raw),8*6*3):
        rgb=raw[start:start+8*6*3]
        counts.append(sum(r>95 and r-g>35 and r-b>35 for r,g,b in zip(rgb[::3],rgb[1::3],rgb[2::3])))
    if len(counts)!=first+2 or next((i for i,n in enumerate(counts) if n>=24),None)!=first:
        raise ValueError(f"Decoded blade contact does not coincide with frame {first}: {counts}")
    rate=audio["sample_rate"]
    pcm=array("h")
    pcm.frombytes(subprocess.check_output(["ffmpeg","-v","error","-i",str(film),"-map","0:a:0",
        "-t","0.5","-ac","1","-ar",str(rate),"-f","s16le","-"]))
    if sys.byteorder=="big": pcm.byteswap()
    onset=next(i for i,value in enumerate(pcm) if abs(value)>=104)
    error=first/FPS-onset/rate
    if abs(error)>.5/FPS:
        raise ValueError("Switch closure and the decoded AAC click are over half a frame apart.")
    probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_chapters","-show_format",
                                         "-of","json",str(film)]))
    streams={s["codec_type"]:s for s in probe["streams"]}
    if int(streams["video"]["nb_frames"])!=score["frames"] or len(probe["chapters"])!=2:
        raise ValueError("Unexpected frame or chapter count.")
    if not all(streams[k].get("tags",{}).get("language")=="spa" for k in ("audio","subtitle")):
        raise ValueError("The exported soundtrack and captions must be identified as Spanish.")
    subtitles=subprocess.check_output(["ffmpeg","-v","error","-i",str(film),"-map","0:s:0",
                                       "-f","srt","-"]).decode("utf-8-sig")
    actual=[text.strip() for text in re.findall(r"-->[^\n]*\n(.*?)(?:\r?\n\s*\r?\n|$)",subtitles,re.S)]
    expected=[sentence["text"] for scene in audio["scenes"] for sentence in scene["sentences"]]
    if actual!=expected:
        raise ValueError("The four spoken sentences must match the final embedded captions.")
    boundary=round(audio["scenes"][0]["end_sample"]*FPS/rate)
    consecutive=subprocess.check_output(["ffmpeg","-v","error","-i",str(film),"-map","0:v:0","-vf",
        f"select=between(n\\,{boundary-1}\\,{boundary}),scale=320:180:flags=area","-fps_mode","passthrough",
        "-pix_fmt","rgb24","-f","rawvideo","-"])
    size=320*180*3
    if len(consecutive)!=2*size:
        raise ValueError("Missing frames at the audio chapter boundary.")
    changed=sum(abs(a-b)>16 for a,b in zip(consecutive[:size],consecutive[size:]))/size
    if changed>.001:
        raise ValueError("The steady circuit has a visible cut at the narration chapter boundary.")
    return {"ok":True,"mp4Sha256":digest(film),"frames":score["frames"],"fps":FPS,
            "seconds":float(probe["format"]["duration"]),"chapters":[c["tags"]["title"] for c in probe["chapters"]],
            "spokenSentencesVerified":len(actual),"chapterBoundaryFrame":boundary,"changedFractionAtChapterBoundary":changed,
            "firstClosedFrame":first,"firstClosedFrameSeconds":first/FPS,"redPixelsInContactPatch":counts,
            "encodedClickSample":onset,"encodedClickSeconds":onset/rate,"audioSampleRate":rate,
            "audioThresholdDbfs":-50,"pictureMinusClickMilliseconds":error*1000}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio",type=Path,required=True,help="Directory with timeline.json, master.wav and captions.srt")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--browser",choices=("chromium","chrome","msedge"))
    parser.add_argument("--preflight-only",action="store_true")
    args=parser.parse_args()
    audio,out=args.audio.resolve(),args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    if audio==out or out.is_relative_to(HERE):
        parser.error("Use a separate output directory.")
    timeline=audio/"timeline.json"
    for src in (timeline,audio/"master.wav",audio/"captions.srt"):
        if not src.is_file(): parser.error("Missing "+str(src))
    recorded=read(timeline)
    score,edges=plan(recorded)
    write(out/"atencion.json",score)
    clock={k:score[k] for k in ("fps","frames","beats")}
    clock["edges"]=edges
    html=out/"escena.html"
    html.write_text((HERE/"escena.html").read_text(encoding="utf-8").replace("__CLOCK__",json.dumps(clock,ensure_ascii=False).replace("<","\\u003c")),encoding="utf-8")
    project={"fps":FPS,"width":WIDTH,"height":HEIGHT,"language":"spa","audioTimeline":Path(os.path.relpath(timeline,out)).as_posix(),
             "attention":"atencion.json","scenes":[{"id":"interruptor","title":"El interruptor cierra el circuito","html":html.name},
             {"id":"bobina","title":"El campo de la bobina","html":html.name}]}
    write(out/"proyecto.json",project)
    write(out/"fuente.json",verify_source(html,audio,out,score,edges,args.browser))
    review=TOOLS/"review_attention.py"
    compose=TOOLS/"compose_narrated.py"
    run(sys.executable,review,"pre-render",out/"atencion.json","--audio-timeline",timeline,"--report",out/"pre-render.json")
    if args.preflight_only:
        return
    film=out/"circuito.mp4"
    browser=["--browser",args.browser] if args.browser else []
    run(sys.executable,compose,out/"proyecto.json","--output",film,"--report",out/"composicion.json",*browser)
    run(sys.executable,review,"post-export",out/"atencion.json","--audio-timeline",timeline,"--video",film,"--report",out/"post-export.json")
    write(out/"verificacion-mp4.json",verify_encoded(film,recorded,edges,score))
    # Original decoded frames, including the two sides of the exact switch contact.
    for name,frame in (("contacto-anterior",edges["close"]-1),("contacto",edges["close"]),("campo",edges["magnetEnd"]),("abierto",edges["opened"])):
        run("ffmpeg","-v","error","-y","-i",film,"-vf",f"select=eq(n\\,{frame})","-frames:v","1","-update","1",out/("mp4-"+name+".png"))
    run("ffmpeg","-v","error","-y","-i",film,"-vf",f"select=not(mod(n\\,{FPS})),scale=390:-2:flags=lanczos,tile=4x4",
        "-frames:v","1","-update","1",out/"segundo-a-segundo.jpg")


if __name__=="__main__":
    main()

