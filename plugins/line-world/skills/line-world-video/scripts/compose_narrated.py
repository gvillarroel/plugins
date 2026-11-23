# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2", "numpy>=2,<3", "av>=18,<20"]
# ///
"""Compose seekable visual scenes on a measured voice clock and run attention hooks."""
import argparse
import asyncio
import base64
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import url2pathname
import wave

from playwright.async_api import Error as BrowserError, async_playwright
from check_audio_channels import master_clock
from check_narrated_export import verify as verify_sound_and_captions
from caption_tracks import compare_speech, languages, parse_srt, reading_summary

from review_attention import SourceStillness, focus_handoffs, inspect, read, required, schedule, score_hash, validate
from review_solid_regions import inspect as inspect_solids, regions as solid_regions

PAINT_HOOK=Path(__file__).resolve().parents[1]/"assets/runtime/review-solid-paints.js"


def sha(path):
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()


def collect_sources(project, sources):
    """Collect protected paths before validating the timing or opening an output."""
    project = project.resolve()
    spec = read(project)
    required(isinstance(spec, dict), "The project must be a JSON object.")
    root = project.parent
    references = [spec.get(k) for k in ("audioTimeline", "attention", "subtitles", "solidRegions")]
    scenes = spec.get("scenes", [])
    for scene in scenes if isinstance(scenes, list) else []:
        if isinstance(scene, dict):
            references.append(scene.get("html"))
    sources.update((root / item).resolve() for item in references if isinstance(item, str) and item)
    assets = spec.get("assets", [])
    required(isinstance(assets, list) and all(isinstance(item, str) and item for item in assets),
             "assets must be a list of local project paths.")
    sources.update((root / item).resolve() for item in assets)
    if isinstance(spec.get("audioTimeline"), str):
        timeline = (root / spec["audioTimeline"]).resolve()
        if "subtitles" not in spec:
            sources.add((timeline.parent / "captions.srt").resolve())
        if timeline.is_file():
            audio = read(timeline)
            if isinstance(audio, dict) and isinstance(audio.get("master"), dict) and isinstance(audio["master"].get("file"), str):
                sources.add((timeline.parent / audio["master"]["file"]).resolve())


def atomic_report(path, receipt):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(receipt, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        except BaseException:
            handle.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def master_plan(path):
    spec=read(path)
    root=path.resolve().parent
    fps=spec["fps"]
    width,height=spec["width"],spec["height"]
    required(type(fps) is int and 1<=fps<=120,"Use a positive integer export frame rate up to 120.")
    required(all(type(v) is int and v>0 and v%2==0 for v in (width,height)),"Use positive even delivery dimensions.")
    timeline=(root/spec["audioTimeline"]).resolve()
    audio=read(timeline)
    master=(timeline.parent/audio["master"]["file"]).resolve()
    required(sha(master)==audio["master"]["sha256"],"The audio timeline describes another master.")
    _,rate,samples=master_clock(master)
    required(rate==audio["sample_rate"] and samples==audio["master"].get("samples",audio["master"].get("frames")),
             "The measured clock differs from the audio file.")
    frames=math.ceil(samples*fps/rate)
    scenes=spec["scenes"]
    required(scenes and [s["id"] for s in scenes]==[s["id"] for s in audio["scenes"]],
             "Visual scene IDs must match the audio timeline in order.")
    required(len({s["id"] for s in scenes})==len(scenes),"Duplicate visual scene IDs.")
    cuts=[]
    sample_cursor=0
    for source,record in zip(scenes,audio["scenes"]):
        required(record["start_sample"]==sample_cursor and record["end_sample"]>sample_cursor,
                 "Audio scene boundaries must be contiguous sample indices.")
        sample_cursor=record["end_sample"]
        start=round(record["start_sample"]*fps/rate)
        end=round(sample_cursor*fps/rate) if sample_cursor<samples else frames
        required(start<end,"Audio scene is shorter than a presentation frame.")
        doc=(root/source["html"]).resolve()
        required(doc.is_file(),"Missing authored scene: "+str(doc))
        cuts.append({"id":source["id"],"title":source.get("title",source["id"]),"html":doc,
                     "start":start,"end":end,"voice":record})
    required(sample_cursor==samples,"The final audio scene does not reach the end of the master.")
    captions=(timeline.parent/"captions.srt") if "subtitles" not in spec else (root/spec["subtitles"])
    required(captions.is_file(),"Missing the synchronized subtitle file.")
    audio_language,subtitle_language=languages(spec)
    caption_mode=spec.get("captionMode","authored")
    required(caption_mode in ("authored","verbatim"),"captionMode must be authored or verbatim.")
    rows=parse_srt(captions.read_text(encoding="utf-8-sig"))
    required(rows and max(row["endMs"] for row in rows)<=math.ceil(1000*frames/fps)+1,
             "The subtitle cues must fit the measured film.")
    captions_review={"mode":caption_mode,"audioLanguage":audio_language,"subtitleLanguage":subtitle_language,
                     "reading":reading_summary(rows)}
    if audio_language==subtitle_language or caption_mode=="verbatim":
        captions_review["speech"]=compare_speech(rows,audio["scenes"],rate)
    score=validate(read(root/spec["attention"]),audio)
    required((score["fps"],score["frames"])==(fps,frames),"The attention score uses another export clock.")
    return spec,master,captions,cuts,score,captions_review


async def launch(runtime,channel):
    if channel: return await runtime.chromium.launch(channel=channel)
    try: return await runtime.chromium.launch()
    except BrowserError as exc:
        if os.name!="nt" or "Executable doesn't exist" not in str(exc): raise
        return await runtime.chromium.launch(channel="msedge")


def ffmetadata(text):
    return str(text).replace("\\","\\\\").replace("\n"," ").replace("\r"," ").replace("=","\\=").replace(";","\\;").replace("#","\\#")


async def load_scene(page, scene, info):
    await page.goto(scene["html"].as_uri(), wait_until="load", timeout=0)
    await page.evaluate("async()=>{await document.fonts.ready; if(window.ready?.then) await window.ready;}")
    await page.wait_for_function("typeof window.renderAt==='function'", timeout=10000)
    await page.evaluate("info=>{window.lineWorldScene=info}", info)
    return await page.evaluate("""()=>{const c=document.querySelector('canvas[data-export-surface]');
        return !!c && c.width===innerWidth && c.height===innerHeight}""")


async def capture_frame(page, t, frame, canvas):
    capture = await page.evaluate("""async ([t,frame,canvas])=>{
        window.lineWorldPaintReview.begin(frame);
        await renderAt(t,frame,window.lineWorldScene);
        if(document.fonts.status==="loading") await document.fonts.ready;
        const paint=window.lineWorldPaintReview.inspect();
        const png=canvas && !paint.findings.length ?
            document.querySelector('canvas[data-export-surface]').toDataURL('image/png').split(',')[1] : null;
        return {paint,png};
    }""", [t,frame,canvas])
    if capture["paint"]["findings"]:
        return capture["paint"], None
    png = base64.b64decode(capture["png"]) if canvas else await page.screenshot(type="png",animations="allow",timeout=0)
    return capture["paint"], png


async def timed_capture(page, t, frame, canvas, timeout):
    if timeout is None:
        return await capture_frame(page,t,frame,canvas)
    # Playwright has a pending protocol reply while JS is unresolved. Close
    # the old target before cancelling Python's waiter so its exception is
    # consumed and cannot surface later during an otherwise successful retry.
    capture=asyncio.create_task(capture_frame(page,t,frame,canvas))
    done,_=await asyncio.wait({capture},timeout=timeout)
    if done:
        return await capture
    try:
        await asyncio.wait_for(page.close(),min(5,timeout))
    finally:
        if not capture.done():
            done,_=await asyncio.wait({capture},timeout=min(2,timeout))
            if not done:
                capture.cancel()
        await asyncio.gather(capture,return_exceptions=True)
    raise TimeoutError


def prepare_caption_track(captions, destination):
    """Encode styled SubRip on its packet clock, with the decoder's style header alive."""
    try:
        import av
    except ModuleNotFoundError as exc:
        if exc.name != "av":
            raise
        raise RuntimeError('Rendering captions needs PyAV. Run the composer with uv run --script '
                           'or install it in this Python environment with python -m pip install "av>=18,<20".') from exc

    with av.open(str(captions), format="srt") as source, av.open(str(destination), "w", format="mp4") as target:
        source_track = source.streams.subtitles[0]
        decoder = source_track.codec_context
        decoder.open()
        header = decoder.subtitle_header
        required(header, "The SubRip decoder did not supply its subtitle style header.")
        output_track = target.add_stream("mov_text")
        output_track.time_base = output_track.codec_context.time_base = Fraction(1, 1_000_000)
        # mov_text reads the ASS header as a C string. Open the encoder while
        # the decoder is alive, before demuxing or flushing the short stream.
        output_track.codec_context.subtitle_header = header.rstrip(b"\0") + b"\0"
        target.start_encoding()
        for packet in source.demux(source_track):
            if packet.pts is None:  # PyAV's final, empty flush packet.
                continue
            cue = decoder.decode2(packet)
            required(cue is not None, "The SubRip decoder could not read a timed subtitle.")
            encoded = output_track.codec_context.encode_subtitle(cue)
            encoded.stream = output_track
            encoded.time_base = packet.time_base
            encoded.pts, encoded.dts, encoded.duration = packet.pts, packet.dts, packet.duration
            target.mux(encoded)


async def encode(target,work,spec,master,captions,scenes,score,channel,local_inputs,remote_origins,paint_report,timeout,stillness):
    fps=spec["fps"]
    audio_language,subtitle_language=languages(spec)
    subtitle_track=work/"captions.mp4"
    prepare_caption_track(captions,subtitle_track)
    chapter_file=work/"chapters.txt"
    chapter_file.write_text(";FFMETADATA1\n"+"".join(
        f"[CHAPTER]\nTIMEBASE=1/{fps}\nSTART={s['start']}\nEND={s['end']}\ntitle={ffmetadata(s['title'])}\n"
        for s in scenes),encoding="utf-8")
    cmd=["ffmpeg","-v","error","-y","-f","image2pipe","-framerate",str(fps),"-c:v","png","-i","pipe:0",
        "-i",str(master),"-i",str(subtitle_track),"-f","ffmetadata","-i",str(chapter_file),"-map","0:v:0","-map","1:a:0",
        "-map","2:s:0","-map_chapters","3","-c:v","libx264","-preset","veryfast","-crf","17","-threads","3",
        "-vf","scale=out_color_matrix=bt709:out_range=tv","-colorspace","bt709","-color_range","tv",
        "-color_trc","bt709","-color_primaries","bt709","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k",
        "-c:s","copy","-metadata:s:s:0","language="+subtitle_language,"-metadata:s:a:0","language="+audio_language,
        "-disposition:s:0","0","-movflags","+faststart",str(target)]
    async with async_playwright() as runtime:
        browser=await launch(runtime,channel)
        try:
            session=await browser.new_context(viewport={"width":spec["width"],"height":spec["height"]},device_scale_factor=1)
            await session.add_init_script(path=str(PAINT_HOOK))
            page_errors=[]
            session.on("page",lambda tab: tab.on("pageerror",lambda exc: page_errors.append(str(exc))))
            page=await session.new_page()
            def observe_request(request):
                url = urlsplit(request.url)
                if url.scheme == "file":
                    raw = ("//" + url.netloc if url.netloc and url.netloc != "localhost" else "") + url.path
                    path = Path(url2pathname(raw)).resolve()
                    if path.is_file() and path not in local_inputs:
                        local_inputs[path] = sha(path)
                elif url.scheme in {"https", "http"}:
                    remote_origins.add(f"{url.scheme}://{url.hostname}")
            def observe_failure(request):
                reason = request.failure or "unavailable"
                if reason != "net::ERR_ABORTED":
                    page_errors.append(f"{request.resource_type} request failed ({reason})")
            session.on("request", observe_request)
            session.on("requestfailed", observe_failure)
            with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
                try:
                    for scene in scenes:
                        reviewed={"id":scene["id"],"framesChecked":0,"surfaces":{},"covered":[],"findings":[]}
                        paint_report["scenes"].append(reviewed)
                        context={k:scene[k] for k in ("id","start","end","voice")}
                        context.update(fps=fps,beats=[b for b in score["beats"] if b["start"]<scene["end"] and b["end"]>scene["start"]])
                        try:
                            canvas=await asyncio.wait_for(load_scene(page,scene,context),timeout)
                        except TimeoutError as exc:
                            raise ValueError(f"Scene {scene['id']}: browser stalled while loading the scene and its fonts.") from exc
                        retried=False
                        for i in range(scene["start"],scene["end"]):
                            t=(i-scene["start"])/fps
                            try:
                                paint,png=await timed_capture(page,t,i,canvas,timeout)
                            except TimeoutError as exc:
                                reviewed["stalledFrame"]=i
                                if retried:
                                    raise ValueError(f"Scene {scene['id']}, frame {i}: browser stalled again.") from exc
                                retried=True
                                print(f"Scene {scene['id']}, frame {i}: retrying stalled capture in a fresh tab.",file=sys.stderr,flush=True)
                                try:
                                    page=await asyncio.wait_for(session.new_page(), timeout)
                                    canvas=await asyncio.wait_for(load_scene(page,scene,context),timeout)
                                    paint,png=await timed_capture(page,t,i,canvas,timeout)
                                except TimeoutError as second:
                                    raise ValueError(f"Scene {scene['id']}, frame {i}: browser stalled during retry.") from second
                                reviewed["recoveredFrame"]=i
                            if page_errors: raise ValueError(page_errors[0])
                            reviewed["framesChecked"]+=1
                            surface=paint["surface"]
                            reviewed["surfaces"][surface]=reviewed["surfaces"].get(surface,0)+1
                            for covered in paint["covered"]:
                                if covered not in reviewed["covered"]: reviewed["covered"].append(covered)
                            if paint["findings"]:
                                reviewed["findings"]=paint["findings"]
                                reviewed["firstFailureFrame"]=i
                                raise ValueError(f"Scene {scene['id']}, frame {i}: {paint['findings'][0]['kind']} on an authored surface.")
                            stillness.observe(png)
                            proc.stdin.write(png)
                    proc.stdin.close()
                    required(proc.wait()==0,"FFmpeg failed to encode the narrated film.")
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait()
                    # Windows can report EINVAL when a buffered pipe flushes
                    # after its reader has exited. Keep the scene/frame error.
                    if not proc.stdin.closed:
                        try:
                            proc.stdin.close()
                        except OSError:
                            pass
        finally:
            await browser.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--browser",choices=["msedge","chrome","chromium"])
    parser.add_argument("--preflight",action="store_true")
    parser.add_argument("--frame-timeout",type=float,default=90,
                        help="Seconds without a completed browser frame before retrying once per scene. Zero disables the watchdog.")
    args=parser.parse_args()
    if not math.isfinite(args.frame_timeout) or args.frame_timeout<0: parser.error("--frame-timeout must be finite and nonnegative.")
    if not args.preflight and not args.output: parser.error("Rendering requires --output.")
    if args.output and args.output.suffix.lower()!=".mp4": parser.error("Use an MP4 output path.")
    targets = [p.resolve() for p in (args.output, args.report) if p]
    sources = {args.project.resolve()}
    hashes = {}
    origins = set()
    receipt = {"ok": False, "published": False, "stage": "preflight"}
    if len(set(targets)) != len(targets) or set(targets) & sources:
        parser.error("Outputs must be distinct from each other and from the project.")
    try:
        collect_sources(args.project, sources)
        required(not set(targets) & sources, "An output is also a project input.")
        hashes.update({p: sha(p) for p in sorted(sources)})
        spec, master, captions, scenes, score, caption_review = master_plan(args.project)
        receipt["preRender"] = {"seconds": schedule(score), "frames": score["frames"], "captions":caption_review,
                                "focusHandoffs":focus_handoffs(score)}
        paint_plan=None
        if "solidRegions" in spec:
            reference=spec["solidRegions"]
            paint_plan=read(args.project.parent/reference) if isinstance(reference,str) else reference
            receipt["preRender"]["solidRegions"]=solid_regions(paint_plan,spec["width"],spec["height"],score["frames"])
        required(caption_review["mode"]!="verbatim" or caption_review["speech"]["ok"],
                 "The verbatim captions differ from the recorded words or phrase clock. See preRender.captions.speech.")
        if args.preflight:
            receipt["ok"] = True
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=args.output.parent) as directory:
                work = Path(directory)
                candidate = work / "candidate.mp4"
                receipt["stage"] = "render"
                receipt["sourcePaint"]={"scenes":[],"hookSha256":sha(PAINT_HOOK)}
                stillness=SourceStillness(score,spec["width"],spec["height"])
                asyncio.run(encode(candidate, work, spec, master, captions, scenes, score, args.browser,
                                   hashes, origins,receipt["sourcePaint"],args.frame_timeout or None,stillness))
                required(not set(targets) & set(hashes), "An output is also a runtime input.")
                changed = [str(p) for p, value in hashes.items() if not p.is_file() or sha(p) != value]
                required(not changed, "Inputs changed during capture: " + ", ".join(changed))
                receipt["stage"] = "post-export"
                receipt["candidateSha256"] = sha(candidate)
                receipt["sourceStillness"]=stillness.receipt(receipt["candidateSha256"])
                receipt["sourceStillnessSha256"]=score_hash(receipt["sourceStillness"])
                receipt["postExport"] = inspect(candidate, score,receipt["sourceStillness"])
                if paint_plan is not None:
                    receipt["solidRegions"]=inspect_solids(candidate,paint_plan,(spec["width"],spec["height"],score["frames"]))
                audio_language,subtitle_language=languages(spec)
                receipt["audioAndCaptions"] = verify_sound_and_captions(
                    candidate, master, captions, scenes, score["fps"], audio_language, master_clock(master)[1], subtitle_language)
                receipt["ok"] = (receipt["postExport"]["ok"] and receipt["audioAndCaptions"]["ok"]
                                 and receipt.get("solidRegions",{}).get("ok",True))
                if receipt["ok"]:
                    os.replace(candidate, args.output)
                    receipt["published"] = True
    except (OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError, EOFError, wave.Error, subprocess.SubprocessError, BrowserError) as exc:
        receipt.update(ok=False, error=str(exc))
    receipt["inputs"] = {str(p): value for p, value in sorted(hashes.items())}
    receipt["remoteOrigins"] = sorted(origins)
    if args.report.resolve() in sources | set(hashes):
        parser.error("The report path refers to a project input.")
    atomic_report(args.report, receipt)
    if receipt.get("error"):
        print(receipt["error"], file=sys.stderr)
    print(json.dumps({"ok":receipt["ok"], "report":str(args.report), "published":receipt["published"]}))
    return 0 if receipt["ok"] else 2


if __name__=="__main__":
    raise SystemExit(main())
