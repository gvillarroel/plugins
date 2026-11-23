# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3", "Pillow>=11,<13"]
# ///
"""Check that a specific label is visible in the delivered picture while its words are heard."""
import argparse
from bisect import bisect_left, bisect_right
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
from caption_tracks import write_atomic
from frame_notes import digest, finite_number, movie_clock, read


def audio_clock(media):
    details = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "a:0", "-read_intervals", "%+#8",
        "-show_entries", "frame=best_effort_timestamp_time:stream=sample_rate,channels,channel_layout",
        "-of", "json", str(media)]))
    if not details.get("frames"):
        raise ValueError("The first audio stream has no decoded samples.")
    return float(details["frames"][0]["best_effort_timestamp_time"]), details["streams"][0]


def pcm_hash(media):
    return subprocess.check_output(["ffmpeg", "-v", "error", "-xerror", "-i", str(media),
        "-map", "0:a:0", "-c:a", "pcm_s32le", "-f", "hash", "-hash", "sha256", "-"], text=True).strip()


def span(row, offset, clock):
    words = row.get("heard")
    if not isinstance(words, list) or not words or not all(isinstance(w,dict) and
            finite_number(w.get("start")) and finite_number(w.get("end")) and
            0 <= w["start"] <= w["end"] for w in words):
        raise ValueError("The matched expression needs measured word intervals.")
    if any(a["end"] > b["start"] for a,b in zip(words, words[1:])):
        raise ValueError("Word intervals run backwards.")
    start, end = words[0]["start"] + offset, words[-1]["end"] + offset
    if start >= end:
        raise ValueError("The spoken expression has no measured duration.")
    first_picture, last_picture = clock["pts"][0], clock["pictureEnd"]
    uncovered = [[a,b] for a,b in ((start,min(end,first_picture)), (max(start,last_picture),end)) if a < b]
    first = max(0,bisect_right(clock["pts"], start)-1)
    stop = bisect_left(clock["pts"], end)
    if end <= first_picture or start >= last_picture:
        first = stop
    return start, end, first, stop, uncovered


def inspect_plate(video, reference, box, first, stop):
    x, y, width, height = box
    with Image.open(reference) as image:
        if image.size != (width, height) or image.format != "PNG":
            raise ValueError("The reference must be a native-size PNG of the indicated crop.")
        if image.convert("RGBA").getchannel("A").getextrema()[0] != 255:
            raise ValueError("The text plate reference needs an opaque background.")
        target = np.asarray(image.convert("RGB"), dtype=np.int16)
    background = np.median(target.reshape(-1, 3), axis=0)
    ink = int(np.count_nonzero(np.any(np.abs(target-background) > 40, axis=2)))
    if ink < 12:
        raise ValueError("The reference crop must contain distinct ink for a figure or label.")
    command = ["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-map", "0:v:0", "-an",
               "-vf", f"trim=start_frame={first}:end_frame={stop},format=rgb24,crop={width}:{height}:{x}:{y}",
               "-fps_mode", "passthrough", "-threads", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    ranges = []
    worst = {"frame":first, "pixels":0, "localPixels":0}
    size = width*height*3
    with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
        try:
            for index in range(first, stop):
                raw = proc.stdout.read(size)
                if len(raw) != size:
                    raise ValueError("The decoded crop ended before the matched words.")
                frame = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
                changed = np.any(np.abs(target-frame) > 32, axis=2)
                count = int(changed.sum())
                local = 0
                if count:
                    # A missing sign or decimal can occupy a few neighboring
                    # pixels while the rest of a long number remains intact.
                    summed = np.pad(changed, ((1,0),(1,0))).cumsum(0).cumsum(1)
                    h, w = min(6,height), min(6,width)
                    local = int((summed[h:,w:]-summed[:-h,w:]-summed[h:,:-w]+summed[:-h,:-w]).max())
                if count > worst["pixels"] or (count == worst["pixels"] and local > worst["localPixels"]):
                    worst = {"frame":index, "pixels":count, "localPixels":local}
                if count > max(3, ink*.02) or local >= 8:
                    if ranges and ranges[-1][1] == index:
                        ranges[-1][1] = index + 1
                    else:
                        ranges.append([index, index+1])
            if proc.stdout.read(1) or proc.wait():
                raise ValueError("The crop decoder returned an unexpected frame count or error.")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    return {"status":"revisar" if ranges else "coincide", "comparedFrames":stop-first,
            "inkPixels":ink, "differingFrameRanges":ranges, "worst":worst}


def audit(video, plan_path, speech_path, speech_media, report_path):
    plan, speech = read(plan_path), read(speech_path)
    if not isinstance(plan,dict) or plan.get("version") != 1 or not isinstance(plan.get("plates"),list) or not plan["plates"]:
        raise ValueError("Provide at least one spoken fact and its verified text plate.")
    if not isinstance(speech,dict) or not isinstance(speech.get("checks"),list):
        raise ValueError("Provide the speech report from check_spoken_facts.py.")
    source = (speech_media or video).resolve()
    protected = {p.resolve() for p in (video, plan_path, speech_path, source)}
    references = []
    ids = set()
    for plate in plan["plates"]:
        if not isinstance(plate,dict) or not isinstance(plate.get("fact"),str) or not plate["fact"].strip() or plate["fact"] in ids:
            raise ValueError("Each plate needs a unique spoken fact.")
        ids.add(plate["fact"])
        if not isinstance(plate.get("reference"),str) or not plate["reference"].strip():
            raise ValueError("Provide the verified PNG crop for each spoken fact.")
        reference = (plan_path.parent / plate["reference"]).resolve()
        references.append(reference)
        protected.add(reference)
    if report_path.resolve() in protected:
        raise ValueError("The report must be distinct from all inputs.")
    hashes = {path:digest(path) for path in protected}
    origin = speech.get("origin",{})
    if (origin.get("mediaSha256") != hashes[source] or origin.get("audioStream") != "a:0" or
            origin.get("clock") != "seconds-from-first-decoded-sample" or
            origin.get("method") not in ("human-listening","unprompted-asr")):
        raise ValueError("The listening report must identify the supplied recording and decoded-sample clock.")
    audio_start, audio_format = audio_clock(video)
    shared_pcm = None
    if source != video.resolve():
        shared_pcm = pcm_hash(source)
        if audio_format != audio_clock(source)[1] or shared_pcm != pcm_hash(video):
            raise ValueError("The recorded audio differs between these two edits.")
    clock = movie_clock(video)
    offset = audio_start-clock["timestampOrigin"]
    expressions = {r["id"]:r for r in speech["checks"]}
    results = []
    for plate, reference in zip(plan["plates"], references):
        if hashes[reference] != plate.get("sha256"):
            raise ValueError(f"{plate['fact']}: the reference PNG has changed.")
        box = plate.get("box")
        if (not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box) or
                min(box[:2]) < 0 or min(box[2:]) <= 0 or box[0]+box[2] > clock["width"] or box[1]+box[3] > clock["height"]):
            raise ValueError(f"{plate['fact']}: use an in-picture box [x,y,width,height] in native pixels.")
        expression = expressions.get(plate["fact"])
        if expression is None:
            raise ValueError(f"Unknown spoken fact: {plate['fact']}")
        row = {"fact":plate["fact"], "box":box, "referenceSha256":hashes[reference]}
        if expression.get("status") != "coincide":
            results.append({**row, "status":"revisar", "reason":"No independent word match", "comparedFrames":0})
            continue
        start,end,first,stop,uncovered = span(expression, offset, clock)
        row.update(matched=expression["matched"], mediaInterval=[start,end], frameRange=[first,stop])
        if first < stop:
            row.update(inspect_plate(video,reference,box,first,stop))
        else:
            row["comparedFrames"] = 0
        if uncovered:
            row.update(status="revisar", reason="Words extend beyond the displayed picture",
                       uncoveredMediaIntervals=uncovered)
        results.append(row)
    if any(digest(path)!=sha for path,sha in hashes.items()):
        raise ValueError("A review input changed during decoding.")
    result = {"version":1, "ok":all(r["status"]=="coincide" for r in results), "checks":results,
              "videoSha256":hashes[video.resolve()], "speechMediaSha256":hashes[source],
              "speechReportSha256":hashes[speech_path.resolve()], "planSha256":hashes[plan_path.resolve()],
              "sharedDecodedPcm":shared_pcm, "audioStartInPictureClock":offset}
    write_atomic(report_path,json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("video",type=Path)
    cli.add_argument("plan",type=Path)
    cli.add_argument("--speech-report",type=Path,required=True)
    cli.add_argument("--speech-media",type=Path,help="Original recording if the same audio accompanies a new picture")
    cli.add_argument("--report",type=Path,required=True)
    args = cli.parse_args()
    try:
        report = audit(args.video,args.plan,args.speech_report,args.speech_media,args.report)
    except (ValueError, OSError, KeyError, IndexError, TypeError, subprocess.SubprocessError) as error:
        cli.exit(2,str(error)+"\n")
    print(f"{len(report['checks'])} placas: {'coincide' if report['ok'] else 'revisar'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
