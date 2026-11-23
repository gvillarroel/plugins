"""Compare each delivered audio channel and each scheduled effect against the measured master at its sample rate."""
from contextlib import ExitStack
import math
from pathlib import Path
import subprocess
import wave

import numpy as np


def master_clock(path):
    """Return channels, sample rate and samples per channel for a lossless master."""
    with Path(path).open("rb") as source:
        if source.read(4) != b"fLaC":
            source.seek(0)
            with wave.open(source, "rb") as wav:
                return wav.getnchannels(), wav.getframerate(), wav.getnframes()
        header = source.read(4)
        info = source.read(34)
    # The mandatory first FLAC block carries the exact sample count, including
    # a short last frame. A duration rounded to milliseconds would lose it.
    if len(header) != 4 or header[0] & 0x7f or int.from_bytes(header[1:], "big") != 34 or len(info) != 34:
        raise ValueError("The FLAC master has no complete STREAMINFO block.")
    clock = int.from_bytes(info[10:18], "big")
    rate = clock >> 44
    channels = ((clock >> 41) & 7) + 1
    samples = clock & ((1 << 36) - 1)
    if not rate:
        raise ValueError("The FLAC master has no sample rate.")
    if not samples:
        # A non-seekable encoder may leave the total unset. Decode in bounded
        # blocks without writing a WAV or loading a long master into memory.
        with decoder(path, rate) as proc:
            size = sum(len(block) for block in iter(lambda: proc.stdout.read(262144), b""))
            if proc.wait() or not size or size % (2 * channels):
                raise ValueError("The FLAC master has no complete decoded sample clock.")
        samples = size // (2 * channels)
    return channels, rate, samples


def decoder(path, rate):
    return subprocess.Popen(["ffmpeg","-v","error","-xerror","-nostdin","-i",str(path),"-map","0:a:0",
        "-ar",str(rate),"-c:a","pcm_s16le","-f","s16le","pipe:1"],stdout=subprocess.PIPE)


def moments(a,b):
    return np.stack([np.einsum("ij,ij->j",x,y) for x,y in ((a,a),(b,b),(a,b))])


def metrics(sums, count):
    rows=[]
    for energy, delivered, product in sums.T:
        # Permit very quiet codec residue in an otherwise silent channel.
        if energy/count <= (32768*10**(-80/20))**2:
            ok=delivered/count <= (32768*10**(-70/20))**2
            rows.append({"ok":bool(ok),"silent":True,"correlation":None,"levelDifferenceDb":None})
        else:
            correlation=product/math.sqrt(energy*delivered) if delivered else 0
            level=10*math.log10(delivered/energy) if delivered else None
            rows.append({"ok":bool(correlation>=.975 and level is not None and abs(level)<=1.5),
                         "silent":False,"correlation":round(float(correlation),6),
                         "levelDifferenceDb":None if level is None else round(level,3)})
    return rows


def compare(master, movie, scenes, rate, delivered_channels):
    count, source_rate, samples = master_clock(master)
    if source_rate != rate or samples != scenes[-1]["voice"]["end_sample"]:
        raise ValueError("The master sample clock differs from its timeline.")
    result={"ok":False,"sampleRate":rate,"sourceChannels":count,"deliveredChannels":delivered_channels,"scenes":[]}
    if delivered_channels!=count:
        result["error"]="The delivered channel count differs from the master."
        return result
    with ExitStack() as stack:
        original=stack.enter_context(decoder(master,rate))
        output=stack.enter_context(decoder(movie,rate))
        try:
            pos=0
            for scene in scenes:
                start=pos
                end=scene["voice"]["end_sample"]
                events=[]
                for idx,event in enumerate(scene["voice"].get("effects",[])):
                    a=event.get("absolute_start_sample")
                    duration=event.get("duration_s")
                    if type(a) is not int or type(duration) not in (int,float) or not math.isfinite(duration):
                        raise ValueError(f"Effect {idx+1} in {scene['id']} has no measured interval.")
                    b=a+round(duration*rate)
                    if not start<=a<b<=end:
                        raise ValueError(f"Effect {idx+1} exceeds scene {scene['id']}.")
                    events.append((event.get("sound") or event.get("file") or str(idx+1),a,b,np.zeros((3,count))))
                sums=np.zeros((3,count))
                while pos<end:
                    n=min(rate,end-pos)
                    size=2*n*count
                    ref=original.stdout.read(size)
                    enc=output.stdout.read(size)
                    if len(ref)!=size or len(enc)!=size:
                        raise ValueError("An audio channel ended inside scene "+scene["id"])
                    a=np.frombuffer(ref,"<i2").astype(np.float64).reshape(n,count)
                    b=np.frombuffer(enc,"<i2").astype(np.float64).reshape(n,count)
                    sums+=moments(a,b)
                    for _,left,right,acc in events:
                        lo=max(0,left-pos)
                        hi=min(n,right-pos)
                        if hi>lo:
                            acc+=moments(a[lo:hi],b[lo:hi])
                    pos+=n
                channels=metrics(sums,end-start)
                effects=[{"name":name,"startSample":lo,"endSample":hi,"channels":metrics(acc,hi-lo)}
                         for name,lo,hi,acc in events]
                passed=all(c["ok"] for c in channels) and all(c["ok"] for e in effects for c in e["channels"])
                result["scenes"].append({"id":scene["id"],"ok":passed,"channels":channels,"effects":effects})
            for proc,limit in ((original, 0), (output, math.ceil(rate*.1)*count*2)):
                if len(proc.stdout.read(limit+1))>limit or proc.wait():
                    raise ValueError("The audio decode exceeded the measured film or did not finish.")
        finally:
            for proc in (original,output):
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
    result["ok"]=all(scene["ok"] for scene in result["scenes"])
    return result
