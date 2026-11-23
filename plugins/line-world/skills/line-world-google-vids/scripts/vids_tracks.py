"""Restore reviewed timed text and chapters to a local copy of a native Vids download."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from batch_clips import sha


def probe(path, *args):
    command = ["ffprobe", "-v", "error", "-threads", "1", *args, "-of", "json", str(path)]
    return json.loads(subprocess.check_output(command))


def inventory(path):
    return probe(path, "-show_streams", "-show_chapters", "-show_data_hash", "sha256")


def packet_receipt(path, stream):
    """Include exact rational clocks, compressed payloads and gapless audio trim metadata."""
    packets = probe(path, "-select_streams", str(stream["index"]), "-show_packets", "-show_data_hash", "sha256",
                    "-show_entries", "packet=pts,dts,duration,size,flags,data_hash:packet_side_data")["packets"]
    if not packets:
        raise ValueError(f"Stream {stream['index']} in {path.name} has no packets.")
    base = Fraction(stream["time_base"])
    digest = hashlib.sha256()
    for packet in packets:
        for field in ("pts", "dts", "duration"):
            if field in packet:
                packet[field] = str(packet[field] * base)
        digest.update(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    return {"codec": stream["codec_name"], "codecParametersSha256": stream.get("extradata_hash"),
            "packetCount": len(packets), "timedPacketsSha256": digest.hexdigest()}


def srt(path, index):
    command = ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-copyts", "-threads", "1", "-i", str(path),
               "-map", f"0:{index}", "-f", "srt", "-"]
    return subprocess.check_output(command).decode("utf-8-sig").replace("\r\n", "\n")


def av(info):
    return [stream for stream in info["streams"] if stream["codec_type"] in ("audio", "video")]


def subtitles(info):
    return [stream for stream in info["streams"] if stream["codec_type"] == "subtitle"]


def language_of(stream):
    return stream.get("tags", {}).get("language", "und")


def chapter_list(info):
    result = []
    for ch in info.get("chapters", []):
        base = Fraction(ch["time_base"])
        result.append({"start": str(ch["start"] * base), "end": str(ch["end"] * base),
                       "title": ch.get("tags", {}).get("title", "")})
    return result


def timed_srt(reviewed, offset_ms, media_end):
    """Shift both ends of each rendered SRT cue and reject truncation at either boundary."""
    if type(offset_ms) is not int:
        raise ValueError("The caption offset must be a whole number of milliseconds.")
    stamp = r"(\d+):(\d\d):(\d\d),(\d{3})"
    def milliseconds(parts):
        h, m, s, ms = map(int, parts)
        return ((h * 60 + m) * 60 + s) * 1000 + ms
    def timestamp(ms):
        sec, ms = divmod(ms, 1000)
        minutes, sec = divmod(sec, 60)
        h, minutes = divmod(minutes, 60)
        return f"{h:02}:{minutes:02}:{sec:02},{ms:03}"
    blocks = reviewed.split("\n\n")
    count = 0
    for i, block in enumerate(blocks):
        if not block:
            continue
        number, timing, body = block.split("\n", 2)
        match = re.fullmatch(stamp + " --> " + stamp + r"([^\n]*)", timing)
        if not match or not number.isdigit() or not body.strip():
            raise ValueError("The reviewed subtitle stream contains an invalid cue.")
        first = milliseconds(match.groups()[:4]) + offset_ms
        end = milliseconds(match.groups()[4:8]) + offset_ms
        if first < 0 or end <= first or Fraction(end, 1000) > media_end:
            raise ValueError(f"Cue {number} starts before zero, is empty or extends beyond the native audio/video clock.")
        if offset_ms:
            blocks[i] = f"{number}\n{timestamp(first)} --> {timestamp(end)}{match[9]}\n{body}"
        count += 1
    if not count:
        raise ValueError("The reviewed subtitle stream has no timed text.")
    return "\n\n".join(blocks), count


def restore(video, reference, language, output, caption_offset_ms=0):
    video, reference, output = map(Path, (video, reference, output))
    if not re.fullmatch("[a-z]{3}", language):
        raise ValueError("Use a three-letter MP4 language code, e.g. spa.")
    if output.suffix.lower() != ".mp4" or output.resolve() in (video.resolve(), reference.resolve()):
        raise ValueError("Choose a separate .mp4 for the local derivative.")
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    native, authored = inventory(video), inventory(reference)
    media = av(native)
    if not any(item["codec_type"] == "video" for item in media):
        raise ValueError("The native download needs a video stream.")
    tracks = subtitles(authored)
    if reference.suffix.lower() not in (".srt", ".vtt"):
        tracks = [stream for stream in tracks if language_of(stream) == language]
    if len(tracks) != 1:
        raise ValueError(f"The reference must contain one identifiable {language} subtitle track.")
    selected = tracks[0]
    reviewed = srt(reference, selected["index"])
    duration = max(((item.get("start_pts", 0) + item["duration_ts"]) * Fraction(item["time_base"])
                    for item in media if "duration_ts" in item), default=0)
    expected_srt, cue_count = timed_srt(reviewed, caption_offset_ms, duration)
    chapter_input = 1 if authored.get("chapters") else 0
    expected_chapters = chapter_list(authored if chapter_input else native)
    last_chapter = max((Fraction(ch["end"]) for ch in expected_chapters), default=0)
    if last_chapter > duration + Fraction(1, 1000):
        raise ValueError("Reviewed chapters extend beyond the native audio/video clock.")
    keep = [s for s in subtitles(native) if language_of(s) != language]
    inputs = [video, reference]
    input_hashes = [sha(path) for path in inputs]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        staged = Path(temporary) / "verified.mp4"
        command = ["ffmpeg", "-v", "error", "-nostdin", "-xerror", "-copyts", "-i", str(video), "-i", str(reference)]
        selection = f"1:{selected['index']}"
        if caption_offset_ms:
            # Shifting an MP4 as an input can shorten cues when its initial empty mov_text packet goes negative.
            corrected = Path(temporary) / "timed.srt"
            corrected.write_text(expected_srt, encoding="utf-8", newline="\n")
            command += ["-i", str(corrected)]
            selection = "2:s:0"
        for stream in [*media, *keep]:
            command += ["-map", f"0:{stream['index']}"]
        target = f"s:{len(keep)}"
        command += ["-map", selection, "-map_chapters", str(chapter_input), "-c", "copy"]
        if caption_offset_ms or selected["codec_name"] != "mov_text":
            command += [f"-c:{target}", "mov_text"]
        # mov_text includes its original bitrate box in the codec parameters. Suppress an extra muxer copy.
        command += [f"-metadata:s:{target}", "language=" + language, f"-disposition:{target}", "default",
                    "-avoid_negative_ts", "disabled", "-write_btrt", "0", "-movflags", "+faststart", str(staged)]
        subprocess.run(command, check=True)
        result = inventory(staged)
        if chapter_list(result) != expected_chapters:
            raise ValueError("The derivative changed chapter times or titles.")
        output_tracks = subtitles(result)
        if ([language_of(s) for s in output_tracks] != [language_of(s) for s in keep] + [language]
                or not output_tracks[-1]["disposition"]["default"]):
            raise ValueError("The derivative has unexpected subtitle tracks or dispositions.")
        if srt(staged, output_tracks[-1]["index"]) != expected_srt:
            raise ValueError("The derivative changed the reviewed subtitle text, line breaks or times.")
        receipts = []
        retained = [*media, *keep]
        copied = [*av(result), *output_tracks[:-1]]
        if len(retained) != len(copied):
            raise ValueError("The derivative lost a requested stream.")
        for source, target_stream in zip(retained, copied):
            before = packet_receipt(video, source)
            if language_of(target_stream) != language_of(source) or before != packet_receipt(staged, target_stream):
                raise ValueError(f"Packets, clocks or codec parameters changed in native stream {source['index']}.")
            receipts.append({"nativeIndex": source["index"], "outputIndex": target_stream["index"], **before})
        if [sha(path) for path in inputs] != input_hashes:
            raise ValueError("An input changed during verification.")
        digest = sha(staged)
        # Publish only a fully checked copy. Both operations fail if a concurrent writer won the same name.
        if os.name == "nt":
            os.rename(staged, output)
        else:
            os.link(staged, output)
    return {"ok": True, "status": "local-reviewed-derivative", "output": str(output.resolve()), "sha256": digest,
            "nativeSha256": input_hashes[0], "referenceSha256": input_hashes[1], "language": language,
            "cueCount": cue_count, "captionOffsetMs": caption_offset_ms,
            "referenceTimedTextSha256": hashlib.sha256(reviewed.encode()).hexdigest(),
            "timedTextSha256": hashlib.sha256(expected_srt.encode()).hexdigest(),
            "chapters": expected_chapters, "copiedStreams": receipts}
