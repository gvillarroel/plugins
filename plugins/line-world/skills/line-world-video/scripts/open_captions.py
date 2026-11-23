"""Create an MP4 with open captions in a separate band below its entire picture."""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import zlib
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from caption_tracks import extract


DEFAULT_FONT=Path(__file__).resolve().parents[1]/"assets"/"fonts"/"space-grotesk.ttf"


def output(*cmd):
    return subprocess.check_output(cmd, stderr=subprocess.PIPE)


def probe(movie):
    return json.loads(output("ffprobe","-v","error","-show_streams","-show_chapters","-of","json",str(movie)))


NUMBERS=set(("cero un uno una dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince "
             "dieciséis diecisiete dieciocho diecinueve veinte treinta cuarenta cincuenta sesenta setenta ochenta "
             "noventa cien ciento doscientos trescientos cuatrocientos quinientos seiscientos setecientos "
             "ochocientos novecientos mil millón millones").split())


def number(word):
    return bool(re.search(r"\d",word) or word in NUMBERS or word.startswith("veinti") or
                (word.endswith("cientas") and word.removesuffix("cientas")+"cientos" in NUMBERS))


def safe_breaks(words, spanish=True):
    normal=[w.casefold().strip("¿¡.,:;?!()") for w in words]
    protected=set()
    for i in range(1,len(words)):
        prev,cur=normal[i-1],normal[i]
        if (spanish and number(prev) and number(cur)) or (re.search(r"\d",prev) and re.search(r"\d",cur)):
            protected.add(i)
        if spanish and cur in {"y","coma"} and i+1<len(words) and number(prev) and number(normal[i+1]):
            protected.update((i,i+1))
        if spanish and cur=="por" and i+1<len(words) and number(prev) and normal[i+1]=="ciento":
            protected.update((i,i+1))
        if cur in {"%","€","$"} and number(prev):
            protected.add(i)
    return [i for i in range(1,len(words)) if i not in protected]


def layout(cue,font_file,w,h,preferred,minimum,spanish=True):
    words=cue["text"].split()
    allowed=safe_breaks(words,spanish)
    original=cue["text"].splitlines()
    original_cut=len(original[0].split()) if len(original)==2 else None
    guard=max(10,round(w*.028))
    for px in range(preferred,minimum-1,-1):
        font=ImageFont.truetype(str(font_file),px)
        if px==preferred:
            missing=font.getmask("\u0378")
            signature=(missing.size,bytes(missing))
            for ch in set("".join(words)):
                mask=font.getmask(ch)
                if (mask.size,bytes(mask))==signature:
                    raise ValueError(f"El subtítulo {cue['cue']} necesita el carácter {ch!r}. Usa --font con cobertura de ese idioma.")
        plans=[(None,[" ".join(words)])]+[(i,[" ".join(words[:i])," ".join(words[i:])]) for i in allowed]
        candidates=[]
        for cut,lines in plans:
            if spanish and cut and cut!=original_cut and words[cut-1].casefold() in {
                    "al","del","de","los","las","la","el","que","y","por","un","una","en","a"}:
                continue
            widths=[font.getlength(line) for line in lines]
            if max(widths)<=w-2*guard:
                criteria=(0 if cut==original_cut else 1,len(lines),max(widths)-min(widths))
                candidates.append((criteria,lines))
        if not candidates:
            continue
        lines=min(candidates,key=lambda candidate:candidate[0])[1]
        strip=Image.new("L",(w,h),32)
        paint=ImageDraw.Draw(strip)
        ascent,descent=font.getmetrics()
        step=ascent+descent+round(px*.12)
        anchors=[i*step for i in range(len(lines))]
        line_boxes=[paint.textbbox((w/2,y),t,font=font,anchor="ms") for y,t in zip(anchors,lines)]
        top=min(b[1] for b in line_boxes)
        bottom=max(b[3] for b in line_boxes)
        offset=round((h-bottom+top)/2)-top
        if offset+top<4:
            continue
        boxes=[]
        for y,t in zip(anchors,lines):
            where=(w/2,y+offset)
            paint.text(where,t,font=font,fill=250,anchor="ms")
            boxes.append(list(paint.textbbox(where,t,font=font,anchor="ms")))
        assert " ".join(lines)==" ".join(words)
        return strip, dict(lines=lines,fontPx=px,boxes=boxes)
    raise ValueError(f"El subtítulo {cue['cue']} excede dos líneas a {minimum} px. Divide ese subtítulo en el origen.")


def prepare(movie,font=DEFAULT_FONT,language=None):
    info=probe(movie)
    videos=[s for s in info["streams"] if s["codec_type"]=="video"]
    if len(videos)!=1:
        raise ValueError("Se necesita una única pista de imagen.")
    track=extract(movie,language)
    if not track or not track["cues"]:
        raise ValueError("El archivo necesita una pista de subtítulos de texto con al menos un intervalo.")
    v=videos[0]
    w,h=v["width"],v["height"]
    if (v.get("sample_aspect_ratio","1:1") not in {"1:1","N/A"} or w%2 or h%2 or
            any(s.get("rotation",0)%360 for s in v.get("side_data_list",[]))):
        raise ValueError("La salida admite cuadros sin rotación con píxel cuadrado y dimensiones pares.")
    if v.get("color_transfer") in {"smpte2084","arib-std-b67"} or v.get("pix_fmt") not in {"yuv420p","yuvj420p"}:
        raise ValueError("Se necesita SDR YUV 4:2:0 de ocho bits.")
    fps=Fraction(v["avg_frame_rate"])
    frames=int(v["nb_frames"])
    time_base=Fraction(v["time_base"])
    timestamps=output("ffprobe","-v","error","-select_streams","v:0","-show_entries",
                      "packet=pts","-of","csv=p=0",str(movie))
    pts=sorted(int(i) for i in timestamps.splitlines() if i)
    if len(pts)!=frames or any(abs(t*time_base*fps-i)>Fraction(1,1000) for i,t in enumerate(pts)):
        raise ValueError("Se requiere cadencia constante con inicio en cero; los PTS del archivo no la confirman.")
    rows=[dict(cue=n,**cue) for n,cue in enumerate(track["cues"],1)]
    band=2*round(max(50,h*.15 if w>=h else h*.128)/2)
    if h<=band or w<64:
        raise ValueError("La imagen es demasiado pequeña para reservar una franja legible.")
    ph=h-band
    pw=2*round(w*ph/h/2)
    left=2*((w-pw)//4)  # Chroma samples in yuv420p start on even positions.
    portrait=w<h
    preferred=max(16,round(w*(.054 if portrait else .027)))
    minimum=max(14,round(w*(.043 if portrait else .020)))
    blank=bytes([32])*(w*band)
    bands=[zlib.compress(blank,1)]
    timeline=[0]*frames
    manifest=[]
    previous_end=0
    for row in rows:
        if row["startMs"]<previous_end:
            raise ValueError(f"El subtítulo {row['cue']} se solapa con el anterior.")
        previous_end=row["endMs"]
        start=math.ceil(Fraction(row["startMs"],1000)*fps)
        end=math.ceil(Fraction(row["endMs"],1000)*fps)
        if not (0<=start<end<=frames):
            raise ValueError(f"El subtítulo {row['cue']} queda fuera de los PTS de imagen o carece de un cuadro.")
        strip,details=layout(row,font,w,band,preferred,minimum,spanish=track["language"] in {"spa","es"})
        idx=len(bands)
        bands.append(zlib.compress(strip.tobytes(),1))
        timeline[start:end]=[idx]*(end-start)
        manifest.append(dict(**row,**details,firstFrame=start,endFrameExclusive=end))
    plan=dict(width=w,height=h,picture=[left,0,pw,ph],band=[0,ph,w,band],fps=str(fps),
              color={k:v[k] for k in ("color_range","color_space","color_transfer","color_primaries")
                     if v.get(k) not in {None,"unknown"}},
              frames=frames,fontFile=font.name,fontSha256=hashlib.sha256(font.read_bytes()).hexdigest(),
              language=track["language"],cues=manifest)
    return plan,bands,timeline


def encode(movie,destination,font=DEFAULT_FONT,language=None):
    if destination.exists():
        raise FileExistsError(f"La salida ya existe: {destination}. Elige una ruta nueva.")
    if not destination.parent.is_dir():
        raise ValueError("La carpeta de salida debe existir.")
    plan,bands,timeline=prepare(movie,font,language)
    w,h=plan["width"],plan["height"]
    x,_,pw,ph=plan["picture"]
    band=plan["band"][3]
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix=".franja-") as tmp:
        path=Path(tmp)/"abierto.mp4"
        graph=(f"[0:v:0]scale={pw}:{ph}:flags=lanczos,setsar=1,pad={w}:{ph}:{x}:0:white[img];"
               "[1:v:0]scale=in_range=full:out_range=limited,format=yuv420p[bar];"
               "[img][bar]vstack=inputs=2:shortest=1[out]")
        tag={"color_range":"-color_range","color_space":"-colorspace","color_transfer":"-color_trc",
             "color_primaries":"-color_primaries"}
        color=[arg for key,value in plan["color"].items() for arg in (tag[key],value)]
        cmd=["ffmpeg","-nostdin","-v","error","-threads","2","-i",str(movie),"-f","rawvideo",
             "-pixel_format","gray","-video_size",f"{w}x{band}","-framerate",plan["fps"],"-i","pipe:0",
             "-filter_complex_threads","1","-filter_complex",graph,"-map","[out]","-map","0:a?",
             "-map_chapters","0","-map_metadata","0","-c:v","libx264","-threads","2","-preset","veryfast",
             "-crf","15","-pix_fmt","yuv420p",*color,"-fps_mode","passthrough","-c:a","copy",
             "-movflags","+faststart",str(path)]
        # Keep diagnostics on disk only during the subprocess; never fill its stderr pipe.
        with (Path(tmp)/"encoder.log").open("wb+") as log:
            process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
            try:
                previous=None
                for idx in timeline:
                    if idx!=previous:
                        pixels=zlib.decompress(bands[idx])
                        previous=idx
                    process.stdin.write(pixels)
            except BrokenPipeError:
                pass
            finally:
                process.stdin.close()
                code=process.wait()
            if code:
                log.seek(0)
                raise RuntimeError(log.read().decode(errors="replace")[-2000:])
        rendered=probe(path)
        source=probe(movie)
        streams=rendered["streams"]
        if (next(int(v["nb_frames"]) for v in streams if v["codec_type"]=="video")!=plan["frames"]
                or rendered["chapters"]!=source["chapters"] or any(s["codec_type"]=="subtitle" for s in streams)):
            raise ValueError("La copia no conservó los cuadros/capítulos o incluye otra pista de subtítulos.")
        # Publish exclusively even when another process creates the name mid-render.
        if os.name=="nt":
            path.rename(destination)  # Windows rename is exclusive, including on exFAT.
        else:
            os.link(path,destination)
    return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("movie",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--font",type=Path,default=DEFAULT_FONT)
    parser.add_argument("--language",help="Subtítulos por código de idioma del MP4, por ejemplo spa o eng. Por omisión usa la pista predeterminada.")
    args=parser.parse_args()
    try:
        plan=encode(args.movie.resolve(),args.output.resolve(),args.font.resolve(),args.language)
    except (OSError,KeyError,ValueError,RuntimeError,ZeroDivisionError,subprocess.SubprocessError) as err:
        parser.exit(2,f"{err}\n")
    print(json.dumps({"output":str(args.output),"frames":plan["frames"],"picture":plan["picture"],
                      "band":plan["band"],"language":plan["language"],"cues":len(plan["cues"])},ensure_ascii=False))


if __name__=="__main__":
    main()
