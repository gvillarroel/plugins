# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["piper-tts==1.4.2", "onnxruntime==1.32.0", "numpy==2.5.5"]
# ///
"""Render a scene-based narration, synchronized effects, captions, and a metered WAV master."""
import argparse
from contextlib import contextmanager
from hashlib import file_digest
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.request import Request, urlopen
import wave

import numpy as np


RATE = 48_000
PRESETS = {"neutral": (1.06, .34), "deliberate": (1.16, .46), "brisk": (.96, .25)}
MODEL_BASE = ("https://huggingface.co/rhasspy/piper-voices/resolve/"
              "e9c8a39444359388adaa94255becb37a5a2b8e51/")
VOICES = {
    "es_MX-claude-high": ("es/es_MX/claude/high/", "Apache-2.0",
        "3ef40a71ea63852cd8ab7e6fa7d2ecdcfa67a0b47c9c48e3f10e02ee02083ea0",
        "1afc81f703c0e4cb3b4d7c0dca096b8b54a98806807f0170cf5eb5557723c12d"),
    "es_AR-daniela-high": ("es/es_AR/daniela/high/", "CC BY-SA 4.0",
        "7ceb1fc0dab349418c5b54a639ae9ee595212d7c9ea422220d8419163d5cc985",
        "aedbf69647e1d754c62ecf8e0366ca5f16af3e768e3c6b5329af6eb6bde3852b"),
}


def checksum(path):
    with path.open("rb") as f:
        return file_digest(f, "sha256").hexdigest()


def numeric(value, name, low=0, high=float("inf")):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be a number in [{low}, {high}]")
    return float(value)


def samples(value, name):
    return round(numeric(value, name) * RATE)


def seconds(count):
    return round(count / RATE, 6)


def command(argv, **kwargs):
    env = os.environ.copy()
    if argv[0] == "earshot":
        # A uv-managed Windows interpreter exports its own Python home, but
        # the Earshot executable may use a different CPython version.
        for key in ("PYTHONHOME", "PYTHONPATH", "__PYVENV_LAUNCHER__", "UV_INTERNAL__PYTHONHOME"):
            env.pop(key, None)
    result = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise ValueError(f"{argv[0]} failed ({result.returncode}): {detail[-1800:]}")
    return result


def model_from_cache(cache, voice, offline=False):
    cache.mkdir(parents=True, exist_ok=True)
    folder, _, model_digest, config_digest = VOICES[voice]
    for extension, digest in ((".onnx", model_digest), (".onnx.json", config_digest)):
        name = voice + extension
        path = cache / name
        if path.is_file() and checksum(path) == digest:
            continue
        if offline:
            raise ValueError(f"Offline mode requires the verified cached file {path}")
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            request = Request(MODEL_BASE + folder + name, headers={"Accept-Encoding": "identity"})
            with urlopen(request, timeout=90) as response, temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            if checksum(temporary) != digest:
                raise ValueError(f"Voice checksum mismatch for {name}")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return cache / (voice + ".onnx")


def read_audio(path):
    if not path.is_file():
        raise ValueError(f"Missing audio file: {path}")
    sound = command(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", "0:a:0", "-ac", "1",
                     "-ar", str(RATE), "-f", "f32le", "-"]).stdout
    audio = np.frombuffer(sound, dtype="<f4").copy()
    if not len(audio) or not np.isfinite(audio).all() or np.max(abs(audio)) < 1e-6:
        raise ValueError(f"Missing audible signal: {path}")
    return audio


def save_audio(path, audio):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not len(audio) or not np.isfinite(audio).all() or max(abs(audio.min()), abs(audio.max())) > 1:
        raise ValueError(f"Invalid PCM level for {path.name}")
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, RATE, 0, "NONE", ""))
        wav.writeframes(np.rint(audio * 32767).astype("<i2").tobytes())


def meters(path):
    result = command(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af",
                      "loudnorm=I=-18:TP=-2:LRA=9:print_format=json", "-f", "null", "-"])
    log = result.stderr.decode("utf-8", "replace")
    values, _ = json.JSONDecoder().raw_decode(log[log.rindex("{"):])
    return {key: float(values[source]) for key, source in (
        ("integrated_lufs", "input_i"), ("true_peak_dbtp", "input_tp"), ("lra_lu", "input_lra"))}


def spoken_text(sentence, pronunciations, language):
    for spelling, pronunciation in pronunciations.items():
        sentence = re.sub(r"(?<!\w)" + re.escape(spelling) + r"(?!\w)",
                          lambda _: pronunciation, sentence, flags=re.IGNORECASE)
    if isinstance(language, str) and re.split("[-_]", language.casefold())[0] == "es":
        # Spanish eSpeak can silently drop unary signs. Preserve date ranges, codes and exponents.
        sentence = re.sub(r"(?<![\w.,:+%−-])([+−-])(?=\d)", lambda m: "más " if m[1] == "+" else "menos ", sentence)
    return sentence


def prepare_voice(scene, text, base, work, engine, preset, pronunciations):
    if scene.get("file"):
        voice = read_audio(base / scene["file"])
        supplied = scene.get("marks")
        if supplied is None:
            return voice, [(text, 0, len(voice))], "recording"
        if not isinstance(supplied, list) or not supplied:
            raise ValueError(f"{scene['id']}: marks must be a non-empty array")
        marks = []
        for mark in supplied:
            start, end = samples(mark["start_s"], "mark.start_s"), samples(mark["end_s"], "mark.end_s")
            phrase = mark["text"]
            if not isinstance(phrase, str) or not phrase.strip() or end <= start or end > len(voice) or (marks and start < marks[-1][2]):
                raise ValueError(f"{scene['id']}: invalid or overlapping recording marks")
            marks.append((phrase, start, end))
        if " ".join(" ".join(m[0] for m in marks).split()) != " ".join(text.split()):
            raise ValueError(f"{scene['id']}: marks must cover the transcript in order")
        return voice, marks, "recording"

    from piper.config import SynthesisConfig
    pace, pause = PRESETS[preset]
    settings = SynthesisConfig(length_scale=pace, noise_scale=.55, noise_w_scale=.5, volume=.78)
    chunks, marks, cursor = [], [], 0
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        spoken = spoken_text(sentence, pronunciations, engine.config.espeak_voice)
        intermediate = work / "sentence.wav"
        with wave.open(str(intermediate), "wb") as wav:
            engine.synthesize_wav(spoken, wav, syn_config=settings)
        clip = read_audio(intermediate)
        if marks:
            gap = np.zeros(round(pause * RATE), dtype=np.float32)
            cursor += len(gap)
            chunks.append(gap)
        marks.append((sentence, cursor, cursor + len(clip)))
        cursor += len(clip)
        chunks.append(clip)
    return np.concatenate(chunks), marks, "piper"


def prepare_effect(cue, base, work, seed):
    if bool(cue.get("file")) == bool(cue.get("sound")):
        raise ValueError("Each effect requires exactly one of file or Earshot sound")
    if cue.get("file"):
        source=base / cue["file"]
        return read_audio(source), {"source": "recording", "input": cue["file"], "input_sha256": checksum(source)}
    name = cue["sound"]
    wav = work / "earshot.wav"
    ear_seed = cue.get("seed", seed)
    if isinstance(ear_seed, bool) or not isinstance(ear_seed, int):
        raise ValueError("Effect seed must be an integer")
    response = json.loads(command(["earshot", "make", cue.get("want", name), "--sound", name,
                                   "--seed", str(ear_seed), "--mono", "--json", "-o", str(wav)]).stdout)
    measured = json.loads(command(["earshot", "measure", str(wav), "--light", "--json"]).stdout)
    if not response["takes"][0]["checks"]["ok"] or measured["clipped_samples"]:
        raise ValueError(f"Earshot reported a defective effect: {name}")
    return read_audio(wav), {"source": "earshot", "sound": name, "seed": ear_seed,
                             "raw_measurement": {k: measured[k] for k in ("duration", "true_peak_dbtp", "clipped_samples")}}


def normalize(audio, target, ceiling, work, limit_transients=False):
    raw = work / "measure.wav"
    # An intermediate headroom adjustment protects hot multichannel downmixes.
    safe = audio * min(1, .87 / float(np.max(abs(audio))))
    save_audio(raw, safe)
    stats = meters(raw)
    if not math.isfinite(stats["integrated_lufs"]):
        # EBU R128 requires a full 400 ms block. Short utterances use peak only.
        gain = ceiling - stats["true_peak_dbtp"]
    else:
        desired, peak_safe = target - stats["integrated_lufs"], ceiling - stats["true_peak_dbtp"]
        if limit_transients and desired > peak_safe + .1:
            # Oversample the limiter so intersample peaks stay below the ceiling.
            # Delay compensation preserves sample-exact marks and the source tail.
            filt = (f"aresample=192000,volume={desired}dB,alimiter=limit={10**(ceiling/20)}:"
                    f"attack=5:release=60:level=0:latency=1,aresample={RATE}")
            limited = command(["ffmpeg","-v","error","-nostdin","-i",str(raw),"-af",filt,"-f","f32le","-"]).stdout
            samples_out = np.frombuffer(limited,dtype="<f4")
            if len(samples_out) != len(audio):
                raise ValueError("Limiter changed the master duration")
            return samples_out
        gain = min(desired, peak_safe)
    return safe * 10 ** (gain / 20)


def srt_stamp(frame):
    ms = round(frame * 1000 / RATE)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def voice_choice(settings, fallback, base):
    name = settings.get("voice")
    local = settings.get("model")
    if name is not None and local is not None:
        raise ValueError("Choose either voice or model for a speaker or scene")
    if local is not None:
        if not isinstance(local, str) or not local.strip():
            raise ValueError("model must be a local .onnx path")
        return (None, (base / local).resolve())
    if name is not None:
        if not isinstance(name, str) or name not in VOICES:
            raise ValueError(f"Unknown voice {name!r}; choose from {', '.join(VOICES)} or use model")
        return (name, None)
    return fallback


def load_engine(choice, cache, seed, offline):
    import onnxruntime
    from piper import PiperVoice
    name, local = choice
    model = local or model_from_cache(cache, name, offline)
    config = Path(str(model) + ".json")
    if not model.is_file() or not config.is_file():
        raise ValueError(f"Local Piper requires both {model} and its .onnx.json")
    onnxruntime.set_seed(seed)
    info = {"engine": "piper-tts 1.4.2", "model": model.name, "sha256": checksum(model),
            "config_sha256": checksum(config), "seed": seed}
    if not local:
        info.update(model_card=MODEL_BASE + VOICES[name][0] + "MODEL_CARD", dataset_license=VOICES[name][1])
    return PiperVoice.load(model), info


def build(spec, base, out, cache, model, offline=False):
    scenes = spec["scenes"]
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a non-empty array")
    ids = [scene["id"] for scene in scenes]
    if any(not isinstance(i, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Scene IDs must be unique lowercase ASCII slugs")
    preset = spec.get("preset", "neutral")
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset {preset!r}; choose from {', '.join(PRESETS)}")
    target = numeric(spec.get("target_lufs", -18), "target_lufs", -30, -12)
    seed = spec.get("seed", 31)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2147483647:
        raise ValueError("seed must be an integer between 0 and 2147483647")
    pronunciations = spec.get("pronunciations", {})
    if not isinstance(pronunciations, dict) or not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in pronunciations.items()):
        raise ValueError("pronunciations must map non-empty spellings to non-empty pronunciations")
    speakers = spec.get("speakers", {})
    if not isinstance(speakers, dict):
        raise ValueError("speakers must map IDs to named speakers")
    for speaker, settings in speakers.items():
        if (not isinstance(speaker, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", speaker)
            or not isinstance(settings, dict) or not isinstance(settings.get("name"), str)
            or not settings["name"].strip() or len(settings["name"].splitlines()) != 1):
            raise ValueError("Each speaker needs a lowercase slug and a one-line display name")
    labeled = spec.get("speaker_captions", False)
    if type(labeled) is not bool:
        raise ValueError("speaker_captions must be true or false")
    layout = spec.get("caption_layout", "sentences")
    if layout not in ("sentences", "es-lectura"):
        raise ValueError("caption_layout must be sentences or es-lectura")
    default_voice = (None, model) if model else ("es_MX-claude-high", None)
    if any(not s.get("file") for s in scenes):
        if model and ("voice" in spec or "model" in spec):
            raise ValueError("Choose a global voice or model in the recipe, or --model")
        default_voice = voice_choice(spec, default_voice, base)
    engines = {}
    scene_voices = bool(speakers) or any("voice" in s or "model" in s or "preset" in s for s in scenes)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as staging:
        work = Path(staging)
        payload = work / "deliverables"
        payload.mkdir()
        tracks, rows, captions, speaker_captions, cursor = [], [], [], [], 0
        for scene in scenes:
            key, text = scene["id"], scene["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"{key}: a transcript is required")
            speaker = scene.get("speaker")
            if speaker is not None and (not isinstance(speaker, str) or speaker not in speakers):
                raise ValueError(f"{key}: unknown speaker {speaker!r}")
            settings = speakers.get(speaker, {})
            local_preset = scene.get("preset", settings.get("preset", preset))
            if local_preset not in PRESETS:
                raise ValueError(f"{key}: unknown preset {local_preset!r}")
            engine, info = None, None
            if not scene.get("file"):
                choice = voice_choice(scene, voice_choice(settings, default_voice, base), base)
                if choice not in engines:
                    engines[choice] = load_engine(choice, cache, seed, offline)
                engine, info = engines[choice]
            voice, marks, source = prepare_voice(scene, text.strip(), base, work, engine, local_preset, pronunciations)
            voice = normalize(voice, target, -3, work)
            stem = f"voices/{key}.wav"
            save_audio(payload / stem, voice)
            lead = samples(scene.get("lead_s", .22), "lead_s")
            tail = samples(scene.get("tail_s", .45), "tail_s")
            n = lead + len(voice) + tail
            if "duration_s" in scene:
                n = samples(scene["duration_s"], "duration_s")
                if n < lead + len(voice) + tail:
                    raise ValueError(f"{key}: narration and padding exceed the requested scene duration")
            track = np.zeros(n, dtype=np.float32)
            track[lead:lead + len(voice)] = voice
            phrases = []
            for phrase, begin, end in marks:
                a, b = cursor + lead + begin, cursor + lead + end
                timecode = f"{len(captions)+1}\n{srt_stamp(a)} --> {srt_stamp(b)}\n"
                captions.append(f"{timecode}{phrase}\n")
                if labeled:
                    label = f"[{settings['name']}] " if speaker else ""
                    speaker_captions.append(f"{timecode}{label}{phrase}\n")
                phrases.append({"text": phrase, "start_s": seconds(lead + begin), "end_s": seconds(lead + end),
                                "absolute_start_sample": a, "absolute_end_sample": b})
            effects = []
            for index, cue in enumerate(scene.get("effects", []), 1):
                if ("at_s" in cue) == ("at_sentence" in cue):
                    raise ValueError("Effects require exactly one of at_s or at_sentence (one-based)")
                if "at_sentence" in cue:
                    sentence = cue["at_sentence"]
                    if type(sentence) is not int or not 1 <= sentence <= len(marks):
                        raise ValueError(f"{key}: at_sentence is outside the available marks")
                    onset = lead + marks[sentence - 1][1]
                else:
                    onset = samples(cue["at_s"], "at_s")
                effect, details = prepare_effect(cue, base, work, seed + index)
                if onset + len(effect) > n:
                    raise ValueError(f"{key}: effect {index} extends past the scene")
                peak = numeric(cue.get("peak_dbfs", -24), "peak_dbfs", -60, -10)
                effect = effect * (10 ** (peak / 20) / float(np.max(abs(effect))))
                asset = f"effects/{key}-{index:02}.wav"
                save_audio(payload / asset, effect)
                track[onset:onset + len(effect)] += effect
                effects.append({**details, "file": asset, "sha256": checksum(payload / asset),
                                "at_s": seconds(onset), "duration_s": seconds(len(effect)),
                                "absolute_start_sample": cursor + onset, "stem_peak_dbfs": peak})
            recording = {"input":scene["file"],"input_sha256":checksum(base/scene["file"])} if scene.get("file") else {}
            if speaker:
                recording.update(speaker=speaker, speaker_name=settings["name"])
            if info and scene_voices:
                recording.update(synthesis=info, preset=local_preset)
            rows.append({**recording,"id": key, "start_s": seconds(cursor), "end_s": seconds(cursor+n), "duration_s": seconds(n),
                         "start_sample": cursor, "end_sample": cursor+n, "source": source, "voice": stem,
                         "voice_sha256": checksum(payload / stem),
                         "voice_start_s": seconds(lead), "voice_duration_s": seconds(len(voice)),
                         "sentences": phrases, "effects": effects})
            tracks.append(track)
            cursor += n
        master = normalize(np.concatenate(tracks), target, -2, work, limit_transients=True)
        recorded = payload / "master.wav"
        save_audio(recorded, master)
        stats = meters(recorded)
        if not math.isfinite(stats["integrated_lufs"]) or abs(stats["integrated_lufs"] - target) > 1 or stats["true_peak_dbtp"] > -1.5:
            raise ValueError(f"Master failed loudness checks: {stats}. Rebalance the source levels or extend very short material.")
        voice_info = next(iter(engines.values()))[1] if len(engines) == 1 else None
        timeline = {"version": 1, "sample_rate": RATE, "channels": 1, "preset": preset, "voice": voice_info,
                    "master": {"file": "master.wav", "frames": cursor, "samples": cursor, "duration_s": seconds(cursor), "target_lufs": target,
                               **stats, "sha256": checksum(recorded)}, "scenes": rows}
        if layout == "es-lectura":
            from spanish_captions import compose
            caption_text, cues = compose(timeline)
            timeline["caption_layout"] = {"name": layout, "cues": cues}
        else:
            caption_text = "\n".join(captions)
        plain_file = payload / "captions.srt"
        plain_file.write_text(caption_text, encoding="utf-8")
        timeline["captions"] = {"file": plain_file.name, "sha256": checksum(plain_file)}
        if labeled:
            names_file = payload / "captions-speakers.srt"
            names_file.write_text("\n".join(speaker_captions), encoding="utf-8")
            timeline["speaker_captions"] = {"file": names_file.name, "sha256": checksum(names_file)}
        (payload / "timeline.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        publish(payload, out, work / "backup")
        return timeline


@contextmanager
def writer_lock(directory):
    # OS file locks release even if a process is killed.
    with (directory / ".scene-audio.lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def publish(payload, out, backup):
    out.mkdir(parents=True, exist_ok=True)
    installed, originals = [], []
    with writer_lock(out):
        # Only assets from an earlier successful build may be replaced or
        # retired. Human recordings elsewhere in the output folder stay put.
        owned = {}
        previous = out / "timeline.json"
        if previous.is_file():
            prior = json.loads(previous.read_text(encoding="utf-8"))
            if prior.get("version") != 1 or not isinstance(prior.get("scenes"), list) or "master" not in prior:
                raise ValueError(f"Output directory contains another timeline: {previous}")
            owned = {"master.wav": prior["master"]["sha256"], "timeline.json": None}
            plain = out / "captions.srt"
            if prior.get("captions", {}).get("file") == plain.name:
                owned[plain.name] = prior["captions"]["sha256"]
            elif plain.is_file():
                # Older scene_audio timelines predate caption hashes. Verify
                # that the SRT still matches the original sentence output.
                phrases = (p for row in prior["scenes"] for p in row["sentences"])
                legacy = "\n".join(f"{i}\n{srt_stamp(p['absolute_start_sample'])} --> "
                                   f"{srt_stamp(p['absolute_end_sample'])}\n{p['text']}\n"
                                   for i,p in enumerate(phrases,1))
                if plain.read_text(encoding="utf-8") == legacy:
                    owned[plain.name] = checksum(plain)
            labeled = prior.get("speaker_captions", {})
            if labeled.get("file") == "captions-speakers.srt":
                owned["captions-speakers.srt"] = labeled.get("sha256")
            for row in prior["scenes"]:
                if re.fullmatch(r"voices/[a-z0-9_-]+\.wav", row["voice"]):
                    owned[row["voice"]] = row.get("voice_sha256")
                for effect in row["effects"]:
                    if re.fullmatch(r"effects/[a-z0-9_-]+\.wav", effect["file"]):
                        owned[effect["file"]] = effect.get("sha256")
        files = sorted(f for f in payload.rglob("*") if f.is_file())
        needed = {f.relative_to(payload).as_posix() for f in files}
        for rel in needed | set(owned):
            path = out / rel
            if path.is_symlink() or path.parent.resolve() != path.parent or (path.exists() and not path.is_file()):
                raise ValueError(f"Not a regular output path: {path}")
            if path.exists() and rel in needed:
                if rel not in owned or (owned[rel] and checksum(path) != owned[rel]):
                    raise ValueError(f"Output file is user-authored or modified: {path}")
        try:
            for rel in set(owned) - needed:
                dest = out / rel
                if dest.is_file() and owned[rel] and checksum(dest) == owned[rel]:
                    saved = backup / rel
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    dest.replace(saved)
                    originals.append((saved, dest))
            for f in sorted(files, key=lambda item: item.name == "timeline.json"):
                relative = f.relative_to(payload)
                dest = out / relative
                dest.parent.mkdir(exist_ok=True)
                if dest.exists():
                    saved = backup / relative
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    dest.replace(saved)
                    originals.append((saved, dest))
                f.replace(dest)
                installed.append(dest)
        except BaseException:
            for dest in reversed(installed):
                dest.unlink(missing_ok=True)
            for saved, dest in reversed(originals):
                saved.replace(dest)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="UTF-8 JSON scene specification")
    parser.add_argument("--out", type=Path, required=True, help="dedicated output directory")
    parser.add_argument("--model", type=Path, help="custom local Piper .onnx with adjacent .onnx.json")
    parser.add_argument("--cache", type=Path, default=Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache")) / "piper-voices")
    parser.add_argument("--offline", action="store_true", help="Use only local files and verified cached voices")
    args = parser.parse_args()
    try:
        result = build(json.loads(args.spec.read_text(encoding="utf-8-sig")), args.spec.resolve().parent,
                       args.out.resolve(), args.cache, args.model, args.offline)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as err:
        parser.exit(1, f"scene_audio: {err}\n")
    print(f"{args.out / 'master.wav'} • {result['master']['duration_s']} s • {result['master']['integrated_lufs']} LUFS")


if __name__ == "__main__":
    main()
