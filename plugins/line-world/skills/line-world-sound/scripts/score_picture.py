"""Score a measured narration with frame-anchored Earshot cues and a voice-only comparator."""
import argparse
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile

import numpy as np


ENGINE_PATH = Path(__file__).resolve().parents[2] / "media-use/audio/scripts/scene_audio.py"
SPEC = importlib.util.spec_from_file_location("scene_audio", ENGINE_PATH)
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)
RATE = engine.RATE


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def frame_sample(frame, fps):
    if type(frame) is not int or frame < 0 or fps <= 0:
        raise ValueError("A cue needs a nonnegative whole frame and positive fps.")
    return round(Fraction(frame*RATE,1)/fps)


def clean_narration(timeline, directory, voices):
    if timeline["sample_rate"] != RATE:
        raise ValueError("Use the measured 48 kHz scene timeline.")
    pcm = np.zeros(timeline["master"]["samples"], np.float32)
    sentences = []
    for scene in timeline["scenes"]:
        if scene.get("voice_file"):
            path = voices / scene["voice_file"]
            start, expected = scene["absolute_voice_start_sample"], scene["original_voice_sha256"]
        else:
            path = directory / scene["voice"]
            start = scene["start_sample"] + round(scene["voice_start_s"]*RATE)
            expected = scene["voice_sha256"]
        if engine.checksum(path) != expected:
            raise ValueError("Voice stem digest differs for "+scene["id"])
        stem = engine.read_audio(path)
        if start < scene["start_sample"] or start+len(stem) > scene["end_sample"]:
            raise ValueError("Voice exceeds its scene: "+scene["id"])
        pcm[start:start+len(stem)] = stem
        sentences += scene["sentences"]
    return pcm, sentences


def make_bank(cues, work):
    ids = [row["id"] for row in cues]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,48}", k) for k in ids):
        raise ValueError("Each cue needs a unique lowercase ID.")
    spec = {"sounds":[{"name":c["id"],"sound":c["sound"],"seed":c["seed"]} for c in cues]}
    if any(type(c["seed"]) is not int for c in cues):
        raise ValueError("Each take needs an explicit integer seed.")
    write(work/"earshot.json", spec)
    folder = work/"takes"
    engine.command(["earshot","make","--spec",str(work/"earshot.json"),"-o",str(folder),"--format","wav"])
    made = read(folder/"manifest.json")["sounds"]
    if [(r["name"], r["sound"], r["ok"]) for r in made] != [(c["id"], c["sound"], True) for c in cues]:
        raise ValueError("Earshot did not produce the requested clean designs.")
    return {r["name"]:folder/r["file"] for r in made}


def picture_change(video, frame, fps, roi):
    probe = json.loads(engine.command(["ffprobe","-v","error","-select_streams","v:0","-show_entries",
                    "stream=width,height,avg_frame_rate","-of","json",str(video)]).stdout)["streams"][0]
    if Fraction(probe["avg_frame_rate"]) != fps or frame < 1:
        raise ValueError("A before/after comparison needs the source frame rate and a previous frame.")
    w,h = probe["width"],probe["height"]
    x,y,right,bottom = roi or (0,0,w,h)
    if not 0 <= x < right <= w or not 0 <= y < bottom <= h:
        raise ValueError("Invalid pixel rectangle [left, top, right, bottom].")
    selector = f"select=eq(n\\,{frame-1})+eq(n\\,{frame})"
    raw = engine.command(["ffmpeg","-v","error","-i",str(video),"-map","0:v:0","-vf",selector,
                         "-frames:v","2","-fps_mode","passthrough","-pix_fmt","rgb24","-f","rawvideo","-"]).stdout
    pair = np.frombuffer(raw,np.uint8).reshape(2,h,w,3)[:,y:bottom,x:right].astype(np.int16)
    return round(float((np.max(np.abs(pair[1]-pair[0]),axis=2) > 16).mean()),6)


def place(cue, path, sentences, fps, samples, mode):
    index=cue.get("protect_sentence")
    if type(index) is not int or not 1<=index<=len(sentences):
        raise ValueError("protect_sentence identifies a one-based spoken sentence.")
    phrase=sentences[index-1]
    if not cue["term"].strip() or cue["term"].casefold() not in phrase["text"].casefold():
        raise ValueError("The protected term must occur in the specified sentence.")
    if cue["use"] not in ("play","silence") or not cue["reason"].strip() or not cue["silence"].strip():
        raise ValueError("Declare play/silence, the purpose and the silent alternative.")
    audio = engine.read_audio(path)
    peak = engine.numeric(cue["peak_dbfs"], "peak_dbfs", -55, -10)
    normalized = abs(audio)/max(abs(audio))*10**(peak/20)
    active = np.flatnonzero(normalized >= 10**(-50/20))
    if not len(active):
        raise ValueError("Cue never exceeds the declared -50 dBFS onset gate.")
    anchors={"onset":int(active[0]), "peak":int(np.argmax(normalized))}
    anchor=anchors[cue["anchor"]]
    picture=frame_sample(cue["frame"],fps)
    offset=cue.get("offset_ms",0)
    if abs(offset)>500/float(fps):
        raise ValueError("The sound anchor would miss its picture by more than half a frame.")
    start=picture+round(offset*RATE/1000)-anchor
    if start<0 or start+len(audio)>samples:
        raise ValueError("Anchored take falls outside the recording.")
    a,b=phrase["absolute_start_sample"],phrase["absolute_end_sample"]
    protected_overlap=int(np.count_nonzero((start+active >= a)&(start+active < b)))
    enabled = mode=="audition" or (mode=="edit" and cue["use"]=="play")
    if enabled and mode!="audition" and protected_overlap:
        raise ValueError(cue["id"]+": audible effect overlaps the protected phrase; move, lower or silence it.")
    row={"id":cue["id"],"sound":cue["sound"],"seed":cue["seed"],"fileSha256":engine.checksum(path),
         "decision":cue["use"],"enabled":enabled,"frame":cue["frame"],"pictureSample":picture,
         "startSample":start,"sourceAnchorSample":anchor,"anchoredSample":start+anchor,"gateDbfs":-50,
         "sourcePeakSample":anchors["peak"],"candidatePeakMinusPictureMs":round((start+anchors["peak"]-picture)*1000/RATE,3),
         "lastSampleAboveGate":start+int(active[-1]),"protectedSentence":phrase["text"],"term":cue["term"],
         "protectedStartSample":a,"protectedEndSample":b,"candidateOverlapAboveGateSamples":protected_overlap,
         "candidateEndToSpeechMs":round((a-start-int(active[-1])-1)*1000/RATE,3),
         "reason":cue["reason"],"silentAlternative":cue["silence"]}
    return row, {"file":str(path),"at_s":start/RATE,"peak_dbfs":peak}


def waveform_checks(wet,dry,rows,cues,fps,mode,encoded):
    for row,cue in zip(rows,cues):
        a,b=row["protectedStartSample"],row["protectedEndSample"]
        d,v=dry[a:b],wet[a:b]
        gain=float(d@v/(d@d))
        residual=v-gain*d
        ratio=float(np.sqrt(np.mean(residual**2)/(np.mean((gain*d)**2)+1e-24)))
        metrics={"phraseResidualDbRelative":round(20*np.log10(max(ratio,1e-10)),2),
                 "phraseCorrelation":round(float(np.corrcoef(d,v)[0,1]),8)}
        if row["enabled"]:
            lo=max(0,row["startSample"]-RATE//100);hi=min(len(wet),row["lastSampleAboveGate"]+RATE//100)
            env=abs(wet[lo:hi]-gain*dry[lo:hi])
            above=np.flatnonzero(env>=10**(-50/20))
            if not len(above):raise ValueError("Effect undetectable in final audio.")
            detected=lo+(int(above[0]) if cue["anchor"]=="onset" else int(env.argmax()))
            metrics.update(measuredMixSample=detected,mixMinusPictureMs=round((detected-row["pictureSample"])*1000/RATE,3))
            if abs(metrics["mixMinusPictureMs"])>500/float(fps):raise ValueError("Rendered cue misses its visual frame.")
        if mode!="audition" and (ratio>(.025 if encoded else .01) or metrics["phraseCorrelation"]<(.9995 if encoded else .9999)):
            raise ValueError(row["id"]+": the protected voice differs from the voice-only mix.")
        if encoded:row["aac"]=metrics
        else:row.update(metrics)


def render(recipe, timeline_path, out, voices=None, video=None, mode="edit"):
    data=read(recipe); timeline=read(timeline_path); fps=Fraction(str(data["fps"]))
    out.mkdir(parents=True,exist_ok=True)
    pcm, sentences=clean_narration(timeline,timeline_path.parent,voices or timeline_path.parent)
    cues=data["cues"]
    if not cues:
        raise ValueError("Add at least one candidate, even for a silent edit.")
    with tempfile.TemporaryDirectory(prefix="score-",dir=out) as tmp:
        work=Path(tmp).resolve(); files=make_bank(cues,work)
        engine.save_audio(work/"narration.wav",pcm)
        marks=[{"text":s["text"],"start_s":s["absolute_start_sample"]/RATE,"end_s":s["absolute_end_sample"]/RATE} for s in sentences]
        scene={"id":"mix","file":"narration.wav","lead_s":0,"tail_s":0,"text":" ".join(s["text"] for s in sentences),"marks":marks,"effects":[]}
        spec={"scenes":[scene],"target_lufs":data.get("target_lufs",-18)}
        engine.build(spec,work,work/"dry",work,None)
        rows=[]
        for cue in cues:
            row,effect=place(cue, files[cue["id"]], sentences, fps, len(pcm), mode)
            if video:
                row["changedPixelsFraction"]=picture_change(video,cue["frame"],fps,cue.get("roi"))
                if row["enabled"] and mode!="audition" and row["changedPixelsFraction"]<=0:
                    raise ValueError(cue["id"]+": the selected picture region did not change on the declared frame.")
            rows.append(row)
            if row["enabled"]:scene["effects"].append(effect)
        wet_timeline=engine.build(spec,work,work/"wet",work,None)
        dry=engine.read_audio(work/"dry/master.wav").astype(float)
        wet=engine.read_audio(work/"wet/master.wav").astype(float)
        if len(wet)!=len(pcm):raise ValueError("Mix duration changed.")
        waveform_checks(wet,dry,rows,cues,fps,mode,False)
        master=work/"wet/master.wav"
        raw=json.loads(engine.command(["earshot","measure",str(master),"--light","--json"]).stdout)
        if raw["clipped_samples"] or raw["true_peak_dbtp"]> -1.5:
            raise ValueError("The delivered master has too little peak headroom.")
        report={"ok":True,"mode":mode,"sampleRate":RATE,"fps":str(fps),"samples":len(pcm),
                "masterSha256":engine.checksum(master),"voiceOnlySha256":engine.checksum(work/"dry/master.wav"),
                "mix":{**wet_timeline["master"],"file":"mezcla.wav"},"earshot":{k:raw.get(k) for k in ("duration","true_peak_dbtp","clipped_samples")},
                "cues":rows}
        if video:
            preview=work/"muxed.mp4";reference=work/"dry.m4a"
            engine.command(["ffmpeg","-v","error","-i",str(video),"-i",str(master),"-map","0:v:0","-map","1:a:0",
                            "-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart",str(preview)])
            engine.command(["ffmpeg","-v","error","-i",str(work/"dry/master.wav"),"-c:a","aac","-b:a","192k",str(reference)])
            encoded=engine.read_audio(preview).astype(float)
            baseline=engine.read_audio(reference).astype(float)
            waveform_checks(encoded,baseline,rows,cues,fps,mode,True)
            stats=engine.meters(preview)
            if stats["true_peak_dbtp"]>-1.5:raise ValueError("Encoded audio exceeded the true peak ceiling.")
            report["encoded"]={"codec":"AAC-LC","bitrate":192000,"sourcePictureSha256":engine.checksum(video),**stats}
        for src,name in ((master,"mezcla.wav"),(work/"dry/master.wav","solo-voz.wav")):
            shutil.copyfile(src,work/name);(work/name).replace(out/name)
        write(work/"qa.json",report);(work/"qa.json").replace(out/"qa.json")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("recipe",type=Path);p.add_argument("--timeline",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True);p.add_argument("--voices",type=Path)
    p.add_argument("--video",type=Path);p.add_argument("--mode",choices=("edit","audition","silence"),default="edit")
    a=p.parse_args();r=render(a.recipe,a.timeline,a.out,a.voices,a.video,a.mode)
    print(json.dumps({"ok":r["ok"],"cues":len(r["cues"]),"sha256":r["masterSha256"]}))
