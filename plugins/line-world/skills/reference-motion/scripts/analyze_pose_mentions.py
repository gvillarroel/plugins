"""Compare a measured visual event with a spoken word or a bounded caption interval."""
import argparse
from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path


CATALOG=Path(__file__).resolve().parents[1]/"references/voice-poses.json"
CLASSES=("before","near","after","unresolved")


def interval(value):
    pair=value if isinstance(value,list) else [value,value]
    if len(pair)!=2 or not all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in pair) or pair[0]>pair[1]:
        raise ValueError("Intervalo de tiempo inválido.")
    return pair


def compare(event, mention, band=.25):
    if not math.isfinite(band) or band<0:
        raise ValueError("La banda de comparación debe ser finita y positiva.")
    low,high=interval(event); first,last=interval(mention)
    delta=[round(low-last,6),round(high-first,6)]
    if delta[1]<-band: timing="before"
    elif delta[0]>band: timing="after"
    elif -band<=delta[0] and delta[1]<=band: timing="near"
    else: timing="unresolved"
    return {"delta_s":delta,"timing":timing}


def summarize(rows,band=.25):
    counts={}
    for scope in ("direct","concept-illustration"):
        group=[r for r in rows if r["semantic_match"]==scope]
        def tally(events):
            counter=Counter(compare(r["events"][key],r["mention_s"],band)["timing"] for r,key in events)
            return {k:counter[k] for k in CLASSES}
        phases={key:tally((r,key) for r in group if r["events"].get(key) is not None)
                for key in ("appearance","readable","action","emphasis","arrival")}
        counts[scope]={"passages":len(group),"primary":tally((r,r["primary_event"]) for r in group),"by_pose":phases}
    return {"band_s":band,"clock":"visual minus speech","counts":counts}


@lru_cache(maxsize=1)
def observations():
    return json.loads(CATALOG.read_text(encoding="utf-8"))["observations"]


def timing_reference(reference):
    if not reference: return None
    for r in observations():
        if reference.get("video_id")==r["video_id"] and reference.get("source_s")==r["source_s"]:
            event=r["primary_event"]
            return {"term":r["term"],"mention_s":r["mention_s"],"precision":r["mention_precision"],
                    "event":event,"visual_s":r["events"][event],"poses":r["poses"],"scope":r["semantic_match"],
                    **compare(r["events"][event],r["mention_s"]),"url":r["url"]}
    return None


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog",type=Path,default=CATALOG)
    parser.add_argument("--band",type=float,default=.25)
    args=parser.parse_args()
    print(json.dumps(summarize(json.loads(args.catalog.read_text(encoding="utf-8-sig"))["observations"],args.band),
                     ensure_ascii=False,indent=2))
