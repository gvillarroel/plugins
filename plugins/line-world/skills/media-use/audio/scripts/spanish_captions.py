"""Write reading-sized Spanish captions from a measured scene timeline, without synthesizing audio."""
import argparse
from difflib import SequenceMatcher
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

LINE = 42
LONG_QUANTITY_LINE = 48
TARGET_CPS = 17
NUMBERS = set("""uno un una dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince
dieciseis diecisiete dieciocho diecinueve veinte treinta cuarenta cincuenta sesenta setenta ochenta noventa cien
ciento mil miles millon millones milmillones billon billones medio media cero""".split())
UNITS = [u.split() for u in ("por ciento", "dólares por onza troy", "dólares por onza", "dólares por participación",
                             "dólares por bitcóin", "dólares por unidad", "euros por unidad",
                             "puntos porcentuales", "puntos básicos", "porcentaje", "puntos", "dólares", "dólar",
                             "euros", "euro", "años", "centavos", "porcentual", "%", "USD", "EUR")]
WEAK = set("un una el la los las del al de a por en con sin para que y o ni entre mas casi unos unas".split())
PREDICATES = set("perdio perdieron cayo cayeron gano ganaron subio subieron bajo bajaron cerro cerraron paso pasaron".split())


def norm(word):
    return "".join(c for c in unicodedata.normalize("NFD", word.casefold().strip(".,;:()¡!¿?«»“”"))
                   if not unicodedata.combining(c))


def number(word):
    return bool(word in NUMBERS or re.fullmatch(r"veinti[a-z]+|quinient[oa]s|[a-z]+cient[oa]s|[+−-]?\d+(?:[.,]\d+)*%?", word))


def quantities(words):
    """Keep the full value and currency/rate together. 'Y' joins only numeric neighbors."""
    protected = []
    index = 0
    tokens = list(map(norm, words))
    while index < len(words):
        if not number(tokens[index]):
            index += 1
            continue
        start = index
        index += 1
        # In “un dos por ciento”, “un” is the article introducing the rate.
        if tokens[start] in ("un","una") and index < len(words) and number(tokens[index]) and tokens[index] not in ("mil","millon","millones","billon","billones"):
            continue
        while index < len(words):
            if words[index-1].endswith((",", ";", ":", ".", "!", "?")):
                break
            if number(tokens[index]):
                index += 1
            elif tokens[index] in ("y", "coma", "punto") and index+1 < len(words) and number(tokens[index+1]):
                index += 2
            else:
                break
        for unit in UNITS:
            if tokens[index:index+len(unit)] == list(map(norm, unit)):
                index += len(unit)
                break
        if index > start+1:
            protected.append((start, index))
    return protected


def syntax(words, idx):
    if idx in (0, len(words)):
        return 0
    left, right = norm(words[idx-1]), norm(words[idx])
    if words[idx-1].endswith((",", ";", ":", "!", "?")):
        return 0
    if left in WEAK:
        return 10
    if right in PREDICATES or (right=="y" and idx+1<len(words) and norm(words[idx+1]) in PREDICATES):
        return 0
    if right in {"cuando","pero","para","que","con"}: return 2
    return 4


def valid_marks(transcript, master_sha):
    if transcript is None:
        return []
    origin = transcript.get("origin", {})
    if not master_sha or origin.get("mediaSha256") != master_sha or origin.get("clock") != "seconds-from-first-decoded-sample":
        raise ValueError("The word clock must identify the exact audio master and its decoded-sample clock.")
    words = transcript.get("words")
    if not isinstance(words, list):
        raise ValueError("The word clock requires a words list.")
    previous = 0
    for item in words:
        if not isinstance(item,dict) or not isinstance(item.get("word"), str) or not item["word"].strip():
            raise ValueError("Invalid timed word.")
        a,b = item.get("start"),item.get("end")
        if not all(type(n) in (int,float) and math.isfinite(n) for n in (a,b)) or not previous <= a <= b:
            raise ValueError("Word intervals must be finite, positive or zero, and ordered.")
        previous = b
    origin_basis = "reviewed" if origin.get("method") == "human-listening" else "asr"
    return [{**item, "basis":origin_basis} for item in words]


def boundaries(words, start, end, marks):
    observed = [w for w in marks if start-0.000001 <= w["start"] < w["end"] <= end+0.000001]
    before = [norm(w) for w in words]
    after = [norm(w["word"]) for w in observed]
    timed = {0: (start,"phrase"), len(words): (end,"phrase")}
    for i,j,length in SequenceMatcher(None, before, after, autojunk=False).get_matching_blocks():
        for off in range(length):
            at = i+off
            # Repeated, isolated function words make ambiguous timing anchors.
            if at and (length >= 2 or (before.count(before[at]) == 1 and after.count(before[at]) == 1)):
                sec = observed[j+off]["start"]
                if start < sec < end:
                    timed[at] = (sec,observed[j+off].get("basis","asr"))
    known = sorted(timed)
    for lo,hi in zip(known, known[1:]):
        sizes = [len(w)+1 for w in words[lo:hi]]
        left, right = timed[lo][0], timed[hi][0]
        amount = 0
        for offset, weight in enumerate(sizes[:-1], 1):
            amount += weight
            timed[lo+offset] = (left + (right-left)*amount/sum(sizes), "estimated")
    return timed


def divide(phrase, rate, marks, authored=None):
    words = phrase["text"].split()
    protected = quantities(words)
    interiors = {i for a,b in protected for i in range(a+1,b)}
    # A measure wraps only when it cannot fit a single line. Prefer whole
    # number groups and units, even when other wraps balance the lines better.
    keep_line = {i for a,b in protected if len(" ".join(words[a:b])) <= LINE for i in range(a+1,b)}
    wrap_cost = {}
    overflow = set()
    extended = []
    for a,b in protected:
        if len(" ".join(words[a:b])) > LINE:
            cuts = []
            for i in range(a+1,b):
                left,right = norm(words[i-1]),norm(words[i])
                if left in ("coma","punto","por") or (left,right) in (("onza","troy"),("puntos","basicos"),("puntos","porcentuales")):
                    keep_line.add(i)
                    continue
                if right in ("coma","punto","dolares","euros","por","puntos"):
                    penalty=0
                elif left in ("mil","millon","millones","billon","billones"):
                    penalty=20
                elif left=="y" or right=="y":
                    penalty=80
                else:
                    penalty=36
                wrap_cost[i]=penalty
                cuts.append(i)
            fits = any(max(len(" ".join(words[a:i])),len(" ".join(words[i:b]))) <= LINE for i in cuts)
            if not fits:
                if any(max(len(" ".join(words[a:i])),len(" ".join(words[i:b]))) <= LONG_QUANTITY_LINE for i in cuts):
                    extended.append((a,b))
                    continue
                # Keep a long decimal or currency together as far as the
                # display allows. Never drop, abbreviate or rewrite a word.
                for i in cuts:
                    interiors.discard(i)
                    overflow.add(i)
    start = phrase["absolute_start_sample"]/rate
    end = phrase["absolute_end_sample"]/rate
    times = boundaries(words, start, end, marks)

    def layout(a,b):
        text = " ".join(words[a:b])
        if len(text) <= LINE:
            return (0, text)
        choices=[]
        for cut in range(a+1,b):
            if cut in keep_line: continue
            left,right = " ".join(words[a:cut])," ".join(words[cut:b])
            def width_ok(line, first, last):
                return len(line) <= LINE or (len(line) <= LONG_QUANTITY_LINE and
                        any(lo <= first < last <= hi for lo,hi in extended))
            if width_ok(left,a,cut) and width_ok(right,cut,b):
                excess=max(0,len(left)-LINE)+max(0,len(right)-LINE)
                # On a narrow player another 3–4 characters can reflow a
                # declared two-line cue into three painted rows.
                cost = syntax(words,cut)*2 + abs(len(left)-len(right))*.32 + wrap_cost.get(cut,0) + excess*48
                if len(left) > len(right):
                    cost += .3
                choices.append((cost, left+"\n"+right))
        return min(choices) if choices else None

    @lru_cache(maxsize=None)
    def visit(a):
        if a == len(words): return (0, [])
        best = None
        for b in range(a+1,len(words)+1):
            width = len(" ".join(words[a:b]))
            if width > (LONG_QUANTITY_LINE if extended else LINE)*2+1: break
            if b in interiors: continue
            lines=layout(a,b)
            duration=times[b][0]-times[a][0]
            if not lines or duration <= 0: continue
            tail=visit(b)
            if tail is None: continue
            cost=(12 + lines[0] + syntax(words,b)*3 + (160+wrap_cost[b] if b in overflow else 0) + 2*(times[b][1]=="estimated") +
                  4*max(0,width/duration-TARGET_CPS)**2 + 50*max(0,.84-duration)**2 +
                  20*max(0,duration-7)**2 + tail[0])
            if best is None or cost<best[0]:
                best=(cost, [(a,b,lines[1])]+tail[1])
        return best

    if authored is not None:
        if not isinstance(authored,list) or not authored or not all(isinstance(c,str) and c.strip() for c in authored):
            raise ValueError("Each authored layout needs nonempty cue text.")
        if " ".join(authored).split() != words:
            raise ValueError("An authored layout must preserve all recorded words and punctuation in order.")
        groups=[]
        cursor=0
        for cue in authored:
            lines=cue.splitlines()
            if not 1 <= len(lines) <= 2 or any(not l.strip() for l in lines):
                raise ValueError("An authored layout exceeds two lines or the line length.")
            finish=cursor+len(cue.split())
            at=cursor
            for line in lines:
                last=at+len(line.split())
                if len(line)>LINE and not (len(line)<=LONG_QUANTITY_LINE and any(lo<=at<last<=hi for lo,hi in extended)):
                    raise ValueError("An authored layout exceeds the line length.")
                at=last
            if finish in interiors or (len(lines)==2 and cursor+len(lines[0].split()) in keep_line):
                raise ValueError("An authored break separates a numeral or unit.")
            groups.append((cursor,finish,cue))
            cursor=finish
    else:
        result=visit(0)
        if result is None:
            raise ValueError(f"No two-line layout fits a complete expression in {phrase['text']!r}; provide authored captions.")
        groups=result[1]
    return [{"startMs":round(times[a][0]*1000),"endMs":round(times[b][0]*1000),"text":value,
             "startBasis":times[a][1],"endBasis":times[b][1],
             **({"longQuantityLine": max(map(len,value.splitlines()))} if any(len(line)>LINE for line in value.splitlines()) else {}),
             **({"quantityContinues": True} if b in overflow else {})} for a,b,value in groups]


def srt_stamp(ms):
    return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"


def compose(clock, transcript=None):
    marks=valid_marks(transcript,clock["master"]["sha256"])
    layouts=(transcript or {}).get("subtitleLayouts",{})
    if not isinstance(layouts,dict):
        raise ValueError("subtitleLayouts must map scene/zero-based-sentence to verbatim cue strings.")
    if any(value is None for value in layouts.values()):
        raise ValueError("Each authored layout must include its verbatim cues.")
    used=set()
    cues=[]
    for scene in clock["scenes"]:
        for index,phrase in enumerate(scene["sentences"]):
            key=f"{scene['id']}/{index}"
            used.add(key)
            for cue in divide(phrase,clock["sample_rate"],marks,layouts.get(key)):
                cues.append({"scene":scene["id"],"sentence":index,"layout":"authored" if key in layouts else "automatic",**cue})
    if set(layouts)-used:
        raise ValueError("The authored subtitle layout refers to an unknown recorded sentence.")
    text="\n\n".join(f"{i}\n{srt_stamp(c['startMs'])} --> {srt_stamp(c['endMs'])}\n{c['text']}"
                     for i,c in enumerate(cues,1))+"\n"
    return text,cues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="new folder for captions.srt and its timing report")
    parser.add_argument("--words", type=Path, help="optional word marks tied to this master's SHA-256")
    args = parser.parse_args()
    try:
        clock = json.loads(args.timeline.read_text(encoding="utf-8-sig"))
        with (args.timeline.parent / clock["master"]["file"]).open("rb") as audio:
            if hashlib.file_digest(audio, "sha256").hexdigest() != clock["master"]["sha256"]:
                raise ValueError("The WAV differs from the timeline's master SHA-256.")
        marks = json.loads(args.words.read_text(encoding="utf-8-sig")) if args.words else None
        text, cues = compose(clock, marks)
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "captions.srt").write_text(text, encoding="utf-8")
        (args.out / "cortes-subtitulos.json").write_text(json.dumps(
            {"masterSha256": clock["master"]["sha256"], "cues": cues}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(cues)} cues in {args.out}")
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(1, f"spanish_captions: {exc}\n")


if __name__ == "__main__":
    main()
