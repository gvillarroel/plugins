"""Attach a measured voice recording to a verified visual export without re-encoding the picture."""
import hashlib
import json
import math
import subprocess


def metadata(path, stream):
    out=subprocess.check_output(["ffprobe","-v","error","-select_streams",stream,"-show_entries",
        "stream=codec_name,duration,nb_frames,avg_frame_rate,start_time","-of","json",str(path)])
    rows=json.loads(out)["streams"]
    if not rows: raise ValueError(f"Falta la pista {stream} en {path.name}.")
    return rows[0]


def picture_hash(path):
    return subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-map","0:v:0",
        "-c","copy","-f","streamhash","-hash","sha256","-"],text=True).strip()


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda:f.read(1024*1024),b""): h.update(data)
    return h.hexdigest()


def attach(movie, receipt, narration, request_dir):
    source=(request_dir/narration["audio"]).resolve(strict=True)
    voice=metadata(source,"a:0")
    visual=metadata(movie,"v:0")
    voice_length=float(voice.get("duration","nan"))
    length=float(visual["duration"])
    if not math.isfinite(voice_length) or abs(voice_length-narration["duration_s"])>.08 or voice_length>length+.04:
        raise ValueError("La duración de la grabación debe coincidir con su reloj de menciones.")
    out=movie.with_name("narrated.mp4")
    subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(movie),"-i",str(source),"-map","0:v:0",
                    "-map","1:a:0","-c:v","copy","-c:a","aac","-ar","48000","-b:a","144k",
                    "-af","apad","-t",str(length),"-movflags","+faststart",str(out)],check=True)
    packets=picture_hash(out); sound=metadata(out,"a:0")
    if packets!=picture_hash(movie) or metadata(out,"v:0")["nb_frames"]!=visual["nb_frames"]:
        raise ValueError("El mux cambió los fotogramas de la película.")
    if abs(float(sound["duration"])-length)>.08 or abs(float(sound.get("start_time","0")))>.04:
        raise ValueError("El audio exportado no ocupa la línea de tiempo prevista.")
    qa=json.loads(receipt.read_text(encoding="utf-8"))
    qa["narration"]={"audio_sha256":digest(source),"audio_duration_s":voice_length,
        "encoded_audio_duration_s":float(sound["duration"]),"unchanged_video_stream":packets,
        "visual_export_sha256":qa["output_sha256"]}
    qa["output_sha256"]=digest(out)
    out.replace(movie)
    receipt.write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
