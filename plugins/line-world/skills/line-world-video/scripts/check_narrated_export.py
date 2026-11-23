"""Compare the delivered AAC and timed text against their authored source tracks."""
from contextlib import ExitStack
import json
import math
from pathlib import Path
import subprocess

import numpy as np
from caption_tracks import parse_srt, plain, reading_summary
from check_audio_channels import compare as compare_channels


def cues(text):
    """Preserve cue times, words and reading order across subtitle codecs."""
    return [(row["startMs"],row["endMs"]," ".join(plain(row["text"]).split())) for row in parse_srt(text)]


def pcm(path):
    return subprocess.Popen(["ffmpeg","-v","error","-xerror","-i",str(path),"-map","0:a:0",
        "-ac","1","-ar","8000","-c:a","pcm_s16le","-f","s16le","pipe:1"],stdout=subprocess.PIPE)


def audio_agreement(master,movie,scenes,rate):
    """Accumulate correlations per scene using 1 s blocks independent of film length."""
    results=[]
    with ExitStack() as resources:
        ref=resources.enter_context(pcm(master))
        mix=resources.enter_context(pcm(movie))
        try:
            pos=0
            for scene in scenes:
                end=round(scene["voice"]["end_sample"]*8000/rate)
                sums=np.zeros(3,dtype=np.float64)
                while pos<end:
                    frames=min(8000,end-pos)
                    original=ref.stdout.read(2*frames)
                    encoded=mix.stdout.read(2*frames)
                    if len(original)!=2*frames or len(encoded)!=2*frames:
                        raise ValueError("A voice track ended inside scene "+scene["id"])
                    a=np.frombuffer(original,"<i2").astype(np.float64)
                    b=np.frombuffer(encoded,"<i2").astype(np.float64)
                    sums+=[a@a,b@b,a@b]
                    pos+=frames
                energy_in,energy_out,cross=sums
                if energy_in<=0:
                    ok=energy_out==0
                    correlation=gain=None
                else:
                    correlation=cross/math.sqrt(energy_in*energy_out) if energy_out else 0
                    gain=10*math.log10(energy_out/energy_in) if energy_out else None
                    ok=correlation>=.975 and gain is not None and abs(gain)<=1.5
                results.append({"id":scene["id"],"ok":bool(ok),
                    "correlation":None if correlation is None else round(correlation,6),
                    "levelDifferenceDb":None if gain is None else round(gain,3)})
            # The last AAC packet can contain up to one codec frame of padding.
            for stream in (ref,mix):
                if len(stream.stdout.read(2*801))>2*800:
                    raise ValueError("An audio track runs more than 100 ms past the final voice scene.")
                if stream.wait(): raise ValueError("The final audio track could not be decoded.")
        finally:
            for stream in (ref,mix):
                if stream.poll() is None:
                    stream.kill()
                    stream.wait()
    return results


def verify(movie, master, subtitles, scenes, fps, language, rate, subtitle_language=None):
    metadata=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_chapters",
                                                 "-of","json",str(movie)]))
    audio=[s for s in metadata["streams"] if s["codec_type"]=="audio"]
    subs=[s for s in metadata["streams"] if s["codec_type"]=="subtitle"]
    subtitle_language=subtitle_language or language
    tracks_ok=all(len(rows)==1 and rows[0].get("tags",{}).get("language")==code
                  for rows,code in ((audio,language),(subs,subtitle_language)))
    extracted=subprocess.check_output(["ffmpeg","-v","error","-i",str(movie),"-map","0:s:0","-f","srt","pipe:1"])
    delivered=extracted.decode("utf-8-sig")
    actual=cues(delivered)
    expected=cues(Path(subtitles).read_text(encoding="utf-8-sig"))
    text_ok=len(actual)==len(expected)>0 and all(a[2]==b[2] and abs(a[0]-b[0])<=1 and abs(a[1]-b[1])<=1
            for a,b in zip(actual,expected))
    last_frame=scenes[-1]["end"]
    text_ok=text_ok and all(0<=s<e<=math.ceil(1000*last_frame/fps)+1 and words for s,e,words in actual)
    chapters=metadata.get("chapters",[])
    chapter_ok=len(chapters)==len(scenes) and all(ch.get("tags",{}).get("title")==scene["title"] and
        abs(float(ch["start_time"])-scene["start"]/fps)<=.002 and abs(float(ch["end_time"])-scene["end"]/fps)<=.002
        for ch,scene in zip(chapters,scenes))
    agreement=audio_agreement(master,movie,scenes,rate)
    full_band=compare_channels(master,movie,scenes,rate,audio[0]["channels"] if len(audio)==1 else None)
    return {"ok":bool(tracks_ok and text_ok and chapter_ok and full_band["ok"] and all(s["ok"] for s in agreement)),
            "fullBandChannels":full_band,
            "audio":agreement,"streamLanguagesMatch":tracks_ok,"captionsMatch":bool(text_ok),
            "captionCount":len(actual),"captionReading":reading_summary(parse_srt(delivered)),
            "audioLanguage":language,"subtitleLanguage":subtitle_language,"chapterClockMatches":chapter_ok}
