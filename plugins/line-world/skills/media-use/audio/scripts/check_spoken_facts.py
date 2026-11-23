# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check timed editorial expressions against independently transcribed audio."""
import argparse
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata


RATE = 16000
TRACK = "a:0"
CLOCK = "seconds-from-first-decoded-sample"
TOKEN = re.compile(r"\d+(?:[.,]\d+)+|[^\W_]+|[^\w\s]")
SIGNS = {"+": "más", "-": "menos", "−": "menos"}
TOKEN_ALIASES = {**SIGNS, "euro": "€", "euros": "€", "dólares": "dólar"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(obj, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def tokens(text):
    text = unicodedata.normalize("NFC", text).casefold()
    # Keep attached prefix currency with its own number (e.g. €1.99 or $12).
    text = re.sub(r"(?<!\w)([€$])(\d+(?:[.,]\d+)*)", r"\2\1", text)
    words = TOKEN.findall(text)
    return [TOKEN_ALIASES.get(word, word) for word in words
            if word[0].isalnum() or word in SIGNS or word == "%" or unicodedata.category(word[0]) == "Sc"]


def timed_tokens(words):
    entries = []
    for index, word in enumerate(words):
        text = word["word"].strip()
        # Some ASR tokenizers time "5" and ",15" separately. Keep the whole
        # decimal and both timestamps. An isolated decimal tail cannot mean 15.
        tail = re.match(r"^[.,]\d+", text)
        if tail:
            suffix = tail[0]
            if (entries and entries[-1][0].isdigit() and entries[-1][2] == index - 1
                    and words[index - 1]["word"].strip()[-1].isdigit() and word["start"] - words[index - 1]["end"] <= .25):
                integer, first, _ = entries.pop()
                entries.append((integer + suffix, first, index))
            else:
                entries.append((suffix, index, index))
            text = text[tail.end():]
        entries.extend((token, index, index) for token in tokens(text))
    return entries


def is_text(value):
    return isinstance(value, str) and bool(value.strip())


def time_value(value):
    return type(value) in (int, float) and math.isfinite(value)


def interval(item, duration, label, *, allow_point=False):
    require(isinstance(item, dict), f"{label} must be an object")
    start, end = item.get("start"), item.get("end")
    require(time_value(start) and time_value(end) and 0 <= start <= end <= duration
            and (allow_point or start < end), f"{label}: invalid start/end for {duration:.3f} s")
    return start, end


def decode(media):
    proc = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(media), "-map",
                           "0:" + TRACK, "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                          capture_output=True)
    require(proc.returncode == 0, "FFmpeg: " + proc.stderr.decode("utf-8", "replace").strip()[-800:])
    require(proc.stdout and len(proc.stdout) % 2 == 0, "No decoded audio samples")
    return proc.stdout


def capture(pcm, media_sha, model, language):
    try:
        import numpy as np
        from faster_whisper import WhisperModel
        from importlib.metadata import version
    except ImportError as error:
        raise ValueError("Capture requires faster-whisper and NumPy in this Python environment") from error
    engine = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=3, local_files_only=True)
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    # The recognizer receives audio and language only, never the editorial checks or captions.
    segments, _ = engine.transcribe(samples, language=language, beam_size=5, word_timestamps=True,
                                    condition_on_previous_text=False, initial_prompt=None, hotwords=None)
    words = [{"word": word.word.strip(), "start": float(word.start), "end": float(word.end)}
             for segment in segments for word in segment.words or []]
    origin = {"mediaSha256": media_sha, "audioStream": TRACK, "clock": CLOCK, "method": "unprompted-asr",
              "provider": "faster-whisper " + version("faster-whisper"), "model": str(model), "language": language}
    return {"version": 1, "origin": origin, "words": words}


def validate_transcript(data, media_sha, duration):
    require(isinstance(data, dict) and type(data.get("version")) is int and data["version"] == 1,
            "Transcript version must be 1")
    origin = data.get("origin")
    require(isinstance(origin, dict) and origin.get("mediaSha256") == media_sha, "Transcript media SHA-256 mismatch")
    require(origin.get("audioStream") == TRACK and origin.get("clock") == CLOCK,
            "Transcript must use the first audio stream and its decoded-sample clock")
    require(origin.get("method") in ("unprompted-asr", "human-listening") and is_text(origin.get("provider"))
            and is_text(origin.get("language")), "Declare independent listening or unprompted ASR, provider and language")
    words = data.get("words")
    require(isinstance(words, list), "Transcript words must be an array")
    previous_end = 0
    for index, word in enumerate(words):
        start, end = interval(word, duration, f"words[{index}]", allow_point=True)
        require(is_text(word.get("word")) and len(word["word"].split()) == 1, f"words[{index}] needs one word")
        require(start >= previous_end, f"words[{index}] overlaps a word or moves backwards")
        previous_end = end
    return words


def validate_checks(plan, duration):
    require(isinstance(plan, dict) and type(plan.get("version")) is int and plan["version"] == 1,
            "Editorial plan version must be 1")
    checks = plan.get("checks")
    require(isinstance(checks, list) and checks, "Provide at least one editorial check")
    ids = set()
    for check in checks:
        interval(check, duration, "check")
        name = check.get("id")
        require(is_text(name) and name not in ids, "Each check needs a unique id")
        ids.add(name)
        phrases = check.get("expressions")
        require(isinstance(phrases, list) and phrases and all(is_text(p) and tokens(p) for p in phrases),
                f"{name}: provide nonempty literal expressions")
    return checks


def check_window(check, words, entries):
    # Fully contained word intervals. A word on a cut belongs to the following window.
    local = [w for w in words if check["start"] <= w["start"] < check["end"] and w["end"] <= check["end"]]
    indices = [i for i, (_, first, last) in enumerate(entries)
               if check["start"] <= words[first]["start"] < check["end"] and words[last]["end"] <= check["end"]]
    actual = [entries[i][0] for i in indices]
    result = {"id": check["id"], "window": [check["start"], check["end"]], "expressions": check["expressions"]}
    strongest = (0, 0, 0)
    for phrase in check["expressions"]:
        expected = tokens(phrase)
        for i in range(len(actual) - len(expected) + 1):
            if actual[i:i + len(expected)] != expected:
                continue
            # A bare quantity never certifies the same quantity preceded by an explicit sign.
            pos = indices[i]
            if pos and entries[pos - 1][0] in ("menos", "más") and expected[0] not in ("menos", "más"):
                continue
            first, last = entries[pos][1], entries[indices[i + len(expected) - 1]][2]
            if any(b["start"] - a["end"] > 1 for a, b in zip(words[first:last], words[first + 1:last + 1])):
                continue
            return {**result, "status": "coincide", "matched": phrase, "heard": words[first:last + 1]}
        partial = difflib.SequenceMatcher(None, actual, expected, autojunk=False).find_longest_match()
        if partial.size > strongest[0]:
            strongest = (partial.size, entries[indices[partial.a]][1], entries[indices[partial.a + partial.size - 1]][2])
    _, first, last = strongest
    if strongest[0]:
        witness = [w for w in words[max(0, first - 3):last + 4]
                   if check["start"] <= w["start"] < check["end"] and w["end"] <= check["end"]]
    else:
        witness = local[:8]
    return {**result, "status": "revisar", "heard": witness,
            "reason": "Expresión completa sin reconocer." if local else "Sin palabras dentro de la ventana."}


def audit(media, plan_path, transcript_path, model, language, report_path, transcript_out):
    inputs = [media, plan_path] + ([transcript_path] if transcript_path else [])
    outputs = [report_path] + ([transcript_out] if transcript_out else [])
    paths = [p.resolve() for p in inputs + outputs]
    require(len(paths) == len(set(paths)), "Inputs and outputs must be distinct paths")
    media_sha = digest(media)
    pcm = decode(media)
    duration = len(pcm) / (2 * RATE)
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes.decode("utf-8-sig"))
    checks = validate_checks(plan, duration)
    source = load(transcript_path) if transcript_path else capture(pcm, media_sha, model, language)
    words = validate_transcript(source, media_sha, duration)
    entries = timed_tokens(words)
    results = [check_window(check, words, entries) for check in checks]
    require(digest(media) == media_sha, "Media changed during review")
    status = "revisar" if any(row["status"] == "revisar" for row in results) else "coincide"
    canonical = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report = {"version": 1, "status": status, "origin": source["origin"], "decodedDuration": duration,
              "editorialPlanSha256": hashlib.sha256(plan_bytes).hexdigest(),
              "transcriptJsonSha256": hashlib.sha256(canonical).hexdigest(),
              "transcriptWordCount": len(words), "checks": results}
    if transcript_out:
        save(transcript_out, source)
    save(report_path, report)
    return status


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path)
    parser.add_argument("plan", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--transcript", type=Path, help="Independent timed words and matching media SHA-256")
    mode.add_argument("--model", help="Local faster-whisper model directory or previously cached model name")
    parser.add_argument("--language", default="es")
    parser.add_argument("--save-transcript", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(args)
    try:
        status = audit(args.media, args.plan, args.transcript, args.model, args.language, args.report, args.save_transcript)
    except (OSError, ValueError, RuntimeError, TypeError) as error:
        print(f"spoken-facts: {error}", file=sys.stderr)
        return 2
    print(f"{status}: {args.report}")
    return int(status == "revisar")


if __name__ == "__main__":
    raise SystemExit(main())
