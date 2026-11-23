"""Read and export the timed words of a delivered video, preserving text, line breaks and milliseconds."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from bisect import bisect_right
from itertools import zip_longest
from tempfile import NamedTemporaryFile


STAMP = r"(\d+):([0-5]\d):([0-5]\d)[,.](\d{3})"
TIMING = re.compile(rf"{STAMP}\s+-->\s+{STAMP}(?:\s+.*)?")
STYLE = re.compile(r"</?(?:b|i|u|font)(?:\s+[^>]*)?>", re.IGNORECASE)


def milliseconds(parts):
    hours, minutes, seconds, fraction = map(int, parts)
    return ((hours*60 + minutes)*60 + seconds)*1000 + fraction


def parse_srt(text):
    result = []
    text = text.lstrip("\ufeff").replace("\r\n","\n").replace("\r","\n").strip()
    if not text:
        return result
    for index, block in enumerate(re.split(r"\n[ \t]*\n+",text),1):
        lines = block.splitlines()
        if lines[0].strip().isdigit():
            lines = lines[1:]
        match = TIMING.fullmatch(lines[0].strip()) if lines else None
        if not match:
            raise ValueError(f"Subtitle block {index} has an unreadable time interval.")
        start, end = milliseconds(match.groups()[:4]), milliseconds(match.groups()[4:])
        body = "\n".join(lines[1:]).strip()
        if end <= start or not body:
            raise ValueError(f"Subtitle block {index} needs text and a positive duration.")
        if result and start < result[-1]["startMs"]:
            raise ValueError(f"Subtitle block {index} is out of chronological order.")
        result.append({"startMs":start, "endMs":end, "text":body})
    return result


def plain(text):
    return html.unescape(STYLE.sub("", text))


def reading_summary(rows):
    total = sum(row["endMs"]-row["startMs"] for row in rows)
    lengths, speeds, lines = [], [], []
    for row in rows:
        words = plain(row["text"])
        lengths.append(len(" ".join(words.split())))
        speeds.append(lengths[-1]*1000/(row["endMs"]-row["startMs"]))
        lines.extend(len(line) for line in words.splitlines())
    summary={"cueCount":len(rows), "maxLines":max((len(row["text"].splitlines()) for row in rows),default=0),
            "longestLineCharacters":max(lines,default=0), "peakCharactersPerSecond":round(max(speeds,default=0),2),
            "meanCharactersPerSecond":round(sum(lengths)*1000/total,2) if total else 0}
    if rows:
        fastest=max(range(len(rows)),key=speeds.__getitem__)
        summary["fastestCue"]={"number":fastest+1,"startMs":rows[fastest]["startMs"],"endMs":rows[fastest]["endMs"]}
    return summary


def words(text):
    # Keep signs, decimal separators, units and currency symbols. Ignore case and ordinary sentence punctuation.
    clean=unicodedata.normalize("NFC",plain(text)).casefold().replace("−","-")
    return re.findall(r"\d+(?:[.,]\d+)*|[^\W\d_]+|[^\w\s.,:;¡!¿?…«»“”\"'()]",clean)


def compare_speech(rows, scenes, rate, tolerance_ms=100):
    """Compare wording and the measurable boundaries of spoken phrases, including phrases split across cues."""
    if type(rate) is not int or rate<=0:
        raise ValueError("The voice timeline needs a positive integer sample rate.")
    phrases=[]
    expected=[]
    for scene in scenes:
        for i,phrase in enumerate(scene.get("sentences",[])):
            tokens=words(phrase["text"]) if isinstance(phrase.get("text"),str) else []
            if not tokens:
                return {"available":False,"ok":False,"reason":"Missing recorded phrase text."}
            first,end=phrase.get("absolute_start_sample"),phrase.get("absolute_end_sample")
            if type(first) is not int or type(end) is not int or not 0<=first<end:
                return {"available":False,"ok":False,"reason":"Missing measured phrase boundaries."}
            phrases.append({"scene":scene["id"],"sentence":i,"firstWord":len(expected),"endWord":len(expected)+len(tokens),
                            "startMs":round(1000*first/rate),"endMs":round(1000*end/rate)})
            expected.extend(tokens)
    if not phrases:
        return {"available":False,"ok":False,"reason":"The timeline contains no measured spoken text."}
    actual=[]
    spans=[]
    for row in rows:
        tokens=words(row["text"])
        spans.append((len(actual), len(actual)+len(tokens)))
        actual.extend(tokens)
    mismatch=next((i for i,(a,b) in enumerate(zip_longest(expected,actual)) if a!=b),None)
    report={"available":True,"textMatches":mismatch is None,"clockMatches":None,"phrases":len(phrases),
            "expectedWords":len(expected),"subtitleWords":len(actual),"toleranceMs":tolerance_ms,"issues":[]}
    if mismatch is not None:
        cue=next((i+1 for i,(a,b) in enumerate(spans) if a<=mismatch<b),None)
        report["issues"].append({"code":"wording","word":mismatch+1,"cue":cue,
            "expected":" ".join(expected[max(0,mismatch-3):mismatch+5]),"delivered":" ".join(actual[max(0,mismatch-3):mismatch+5])})
    else:
        starts=[p["firstWord"] for p in phrases]
        for n,((first,end),row) in enumerate(zip(spans,rows),1):
            if first==end:
                report["issues"].append({"code":"missing-words","cue":n})
                continue
            a,b=phrases[bisect_right(starts,first)-1],phrases[bisect_right(starts,end-1)-1]
            # For an interior break the recording only proves the enclosing phrase's boundaries.
            sound_start,sound_end=a["startMs"],b["endMs"]
            start_error=row["startMs"]-sound_start
            end_error=row["endMs"]-sound_end
            if (start_error < -tolerance_ms or end_error > tolerance_ms or
                    first==a["firstWord"] and abs(start_error)>tolerance_ms or
                    end==b["endWord"] and abs(end_error)>tolerance_ms):
                report["issues"].append({"code":"phrase-clock","cue":n,"firstScene":a["scene"],"firstSentence":a["sentence"],
                    "lastScene":b["scene"],"lastSentence":b["sentence"],"cueMs":[row["startMs"],row["endMs"]],
                    "measuredPhraseMs":[sound_start,sound_end]})
        report["clockMatches"]=not report["issues"]
    report["ok"]=not report["issues"]
    return report


def write_atomic(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    with NamedTemporaryFile("w",dir=path.parent,delete=False,encoding="utf-8",newline="\n") as stream:
        temporary=Path(stream.name)
        try:
            stream.write(text)
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def languages(spec):
    shared = spec.get("language", "spa")
    pair = spec.get("audioLanguage", shared), spec.get("subtitleLanguage", shared)
    if any(not isinstance(value,str) or not re.fullmatch("[a-z]{3}",value) for value in pair):
        raise ValueError("Use a three-letter lowercase ISO 639-2 code for each MP4 track, e.g. spa or eng.")
    return pair


def extract(video, language=None):
    metadata = json.loads(subprocess.check_output(["ffprobe","-v","error","-threads","1","-select_streams","s","-show_entries",
        "stream=index,codec_name:stream_tags=language:stream_disposition=default","-of","json",str(video)]))
    streams = metadata.get("streams",[])
    if language:
        streams = [stream for stream in streams if stream.get("tags",{}).get("language")==language]
        if not streams:
            raise ValueError(f"Missing subtitle track with language {language}.")
    text_codecs={"mov_text", "subrip", "webvtt", "ass", "ssa", "text"}
    available=[stream for stream in streams if stream.get("codec_name") in text_codecs]
    if not available:
        if language:
            raise ValueError("The selected subtitle stream does not contain decodable timed text.")
        return None
    selected=max(available,key=lambda stream:stream.get("disposition",{}).get("default",0))
    encoded=subprocess.check_output(["ffmpeg","-v","error","-nostdin","-copyts","-threads","1","-vn","-an","-dn","-i",str(video),"-map",f"0:{selected['index']}",
                                     "-f","srt","pipe:1"])
    rows=parse_srt(encoded.decode("utf-8-sig"))
    return {"index":selected["index"],"language":selected.get("tags",{}).get("language","und"),
            "default":bool(selected.get("disposition",{}).get("default")),
            "candidates":[{"index":stream["index"], "language":stream.get("tags",{}).get("language","und"),
                           "default":bool(stream.get("disposition",{}).get("default"))} for stream in available],
            "cues":[{**row,"text":plain(row["text"])} for row in rows], "reading":reading_summary(rows)}


def compare_authored_srt(rows, path):
    """Compare the selected stream's displayed text, line breaks and absolute millisecond clock."""
    source = path.read_bytes()
    expected = parse_srt(source.decode("utf-8-sig"))
    if not expected:
        raise ValueError("The authored SRT has no subtitle cues.")
    differences = []
    for number, (reference, actual) in enumerate(zip_longest(expected, rows), 1):
        if reference is not None:
            reference = {**reference, "text": plain(reference["text"])}
        if reference != actual:
            differences.append({"cue": number, "expected": reference, "actual": actual})
    return {"sha256": hashlib.sha256(source).hexdigest(), "expectedCues": len(expected),
            "extractedCues": len(rows), "differences": differences, "ok": not differences}


def webvtt(rows):
    def stamp(ms):
        seconds, fraction=divmod(ms,1000)
        minutes, seconds=divmod(seconds,60)
        hours, minutes=divmod(minutes,60)
        return f"{hours:02}:{minutes:02}:{seconds:02}.{fraction:03}"
    blocks=[f'{stamp(r["startMs"])} --> {stamp(r["endMs"])}\n{html.escape(r["text"], quote=False)}' for r in rows]
    return "WEBVTT\n\n"+"\n\n".join(blocks)+"\n"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--language",help="MP4 subtitle stream language, e.g. spa")
    parser.add_argument("--compare-voice",type=Path,help="Compare the subtitles with the text and measured samples in this audio timeline.")
    parser.add_argument("--compare-srt",type=Path,help="Exit 2 if any selected cue differs from this authored SRT in text, line breaks or timing.")
    parser.add_argument("--require-default",action="store_true",help="Require one default text stream in the selected language or set.")
    parser.add_argument("--require-verbatim",action="store_true",help="Exit 2 unless the compared wording and phrase times match.")
    parser.add_argument("--report",type=Path,help="Save the review outcome as JSON.")
    args=parser.parse_args()
    inputs={p.resolve() for p in (args.video,args.compare_voice,args.compare_srt) if p}
    outputs=[p.resolve() for p in (args.output,args.report) if p]
    if args.output.suffix.lower()!=".vtt" or len(outputs)!=len(set(outputs)) or inputs.intersection(outputs):
        parser.error("Choose separate inputs, a .vtt output and an optional JSON report.")
    if args.require_verbatim and not args.compare_voice:
        parser.error("--require-verbatim needs --compare-voice.")
    track=extract(args.video,args.language)
    if not track or not track["cues"]:
        raise ValueError("The video has no timed text to export.")
    report={"language":track["language"],"streamIndex":track["index"],"default":track["default"],
            "candidateStreams":track["candidates"],**track["reading"],"output":str(args.output)}
    if args.compare_voice:
        timeline=json.loads(args.compare_voice.read_text(encoding="utf-8-sig"))
        report["speech"]=compare_speech(track["cues"],timeline["scenes"],timeline["sample_rate"])
    if args.compare_srt:
        report["authoredSrt"]=compare_authored_srt(track["cues"],args.compare_srt)
    unique_default=sum(s["default"] for s in track["candidates"])==1
    report["ok"]=(not args.require_verbatim or report["speech"]["ok"]) and (
        not args.compare_srt or report["authoredSrt"]["ok"]) and (not args.require_default or unique_default)
    write_atomic(args.output,webvtt(track["cues"]))
    if args.report:
        write_atomic(args.report,json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report["ok"] else 2


if __name__=="__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(exc,file=sys.stderr)
        sys.exit(2)
