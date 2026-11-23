#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "opencv-python-headless>=4.9"]
# ///
"""Measure a single object entrance and its reading holds in a downloaded MP4."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np


def region_mask(frame, bounds, cutoff):
    height, width = frame.shape
    x1, y1, x2, y2 = bounds
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("Each region needs normalized x1,y1,x2,y2 within the picture.")
    area = frame[round(y1 * height):round(y2 * height), round(x1 * width):round(x2 * width)]
    if not area.size:
        raise ValueError("The region is smaller than one analysis pixel.")
    return np.packbits(area < cutoff)


BITS = np.array([n.bit_count() for n in range(256)], dtype=np.uint8)


def count(mask):
    return int(BITS[mask].sum())


def runs(times, active, dt):
    ranges = []
    for i in np.flatnonzero(active):
        if i > 0 and active[i - 1]:
            ranges[-1][1] = round(times[i] + dt, 6)
        else:
            ranges.append([times[i], round(times[i] + dt, 6)])
    return ranges


def assess(times, reveal, anchor, expected_start, duration, tolerance, min_hold, initially_blank):
    if len(times) < 4 or len(reveal) != len(times) or len(anchor) != len(times):
        raise ValueError("The observed interval needs at least four decoded frames and both regions.")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("Video presentation timestamps must increase.")
    before = np.array([count(row ^ reveal[0]) for row in reveal])
    after = np.array([count(row ^ reveal[-1]) for row in reveal])
    anchor_change = max(count(row ^ anchor[0]) for row in anchor)
    change = int(before[-1])
    # Relative threshold applies to the actual changed ink, not to blank canvas area.
    # Twelve pixels at 480-wide suppress normal codec ringing around text edges.
    noise = max(12, round(change * .01))
    disturbed = np.flatnonzero(before > noise)
    unsettled = np.flatnonzero(after > noise)
    start = int(disturbed[0]) if disturbed.size else None
    settled = int(unsettled[-1]) + 1 if unsettled.size and unsettled[-1] < len(times) - 1 else None
    back_to_opening = bool(start is not None and np.any(before[start + 1:] <= noise))
    decodable_motion = (start is not None and settled is not None and
                        np.count_nonzero((before > noise) & (after > noise)) >= 2)
    observed_start = times[start] if start is not None else None
    observed_end = times[settled] if settled is not None else None
    dt = float(np.median(np.diff(times)))
    active = [False] + [count(a ^ b) > noise for a, b in zip(reveal, reveal[1:])]
    hold = times[-1] + dt - observed_end if observed_end is not None else 0
    checks = {
        "differentStartAndEnd": change > 2 * noise,
        "initialRegionClear": not initially_blank or count(reveal[0]) <= noise,
        "anchorPresentAndStable": count(anchor[0]) > 2 * noise and anchor_change <= max(12, count(anchor[0]) * .02),
        "startNearNativeSetting": observed_start is not None and abs(observed_start - expected_start) <= tolerance,
        "measurableMotion": bool(decodable_motion),
        "settlesNearNativeSetting": observed_end is not None and abs(observed_end - expected_start - duration) <= tolerance,
        "neverReturnsToOpening": not back_to_opening,
        "stableReadTime": hold >= min_hold,
    }
    return {
        "ok": all(checks.values()), "checks": checks, "framesMeasured": len(times),
        "firstSampleSeconds": times[0], "lastSampleSeconds": times[-1],
        "observedStartSeconds": observed_start, "settledSeconds": observed_end,
        "measuredFinalHoldSeconds": round(hold, 4), "firstInkPixels": count(reveal[0]),
        "lastInkPixels": count(reveal[-1]), "changedPixels": change, "noiseBudgetPixels": noise,
        "anchorInkPixels": count(anchor[0]), "maxAnchorDifferencePixels": anchor_change,
        "motionIntervalsSeconds": runs(times, active, dt),
    }


def measure(file, spec):
    start, end = spec["sampleWindowSeconds"]
    expected = spec["expectedStartSeconds"]
    duration = spec["durationSeconds"]
    tolerance = spec["toleranceSeconds"]
    min_hold = spec["minFinalHoldSeconds"]
    values = (start, end, expected, duration, tolerance, min_hold)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
        raise ValueError("Times must be finite numbers.")
    if not (0 <= start < expected < expected + duration < end and tolerance > 0 and min_hold > 0):
        raise ValueError("Use a window within one scene, containing both the complete entrance and its two holds.")
    cutoff = spec.get("darkThreshold", 175)
    if not isinstance(cutoff, int) or not 1 <= cutoff <= 254:
        raise ValueError("darkThreshold must be an integer from 1 to 254.")
    analysis_width = spec.get("analysisWidth", 480)
    if type(analysis_width) is not int or not 160 <= analysis_width <= 1920:
        raise ValueError("analysisWidth must be an integer from 160 to 1920.")
    cap = cv2.VideoCapture(str(file))
    if not cap.isOpened():
        raise ValueError("Could not open the video.")
    times, reveal, anchor = [], [], []
    try:
        while cap.grab():
            time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if time >= end:
                break
            if time < start:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                raise ValueError(f"Could not decode the frame at {time:.3f} seconds.")
            height, width = frame.shape[:2]
            small = cv2.resize(frame, (analysis_width, round(analysis_width * height / width)), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            times.append(round(time, 6))
            reveal.append(region_mask(gray, spec["revealRegion"], cutoff))
            anchor.append(region_mask(gray, spec["anchorRegion"], cutoff))
    finally:
        cap.release()
    if len(times) < 4 or times[-1] + 1.5 * np.median(np.diff(times)) < end:
        raise ValueError("The video ended before the requested sample window.")
    report = assess(times, reveal, anchor, expected, duration, tolerance, min_hold, spec.get("initiallyBlank", True))
    with file.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {**report, "video": file.name, "sha256": digest, "plan": spec,
            "analysisWidth": analysis_width, "scope": "Thresholded pixel masks. Native object identity, effects, wording and voice require separate observations."}


def intersection(first, second):
    return sum(max(0, min(b, d) - max(a, c)) for a, b in first for c, d in second)


def measure_pair(file, spec):
    targets = spec["targets"]
    if not isinstance(targets, list) or len(targets) != 2 or len({r["id"] for r in targets}) != 2:
        raise ValueError("A paired test requires two independently named targets.")
    a, b = (r["revealRegion"] for r in targets)
    if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
        raise ValueError("The two target regions must be disjoint.")
    minimum = spec.get("minConcurrentMotionSeconds")
    if isinstance(minimum, bool) or not isinstance(minimum, (float, int)) or not math.isfinite(minimum) or minimum <= 0:
        raise ValueError("minConcurrentMotionSeconds must be a positive number.")
    shared = {k: v for k, v in spec.items() if k not in {"targets", "minConcurrentMotionSeconds"}}
    reports = {row["id"]: measure(file, {**shared, **row}) for row in targets}
    a_report, b_report = reports.values()
    if a_report["sha256"] != b_report["sha256"]:
        raise ValueError("The video changed between the two measurements.")
    concurrent = intersection(a_report["motionIntervalsSeconds"], b_report["motionIntervalsSeconds"])
    checks = {
        "twoOverlappingMotions": concurrent >= minimum,
        "stableAnchor": all(r["checks"]["anchorPresentAndStable"] for r in reports.values()),
        "twoReadingHolds": all(r["checks"]["stableReadTime"] and r["checks"]["neverReturnsToOpening"] for r in reports.values()),
        "bothStartOnCue": all(r["checks"]["startNearNativeSetting"] for r in reports.values()),
        "bothMatchNativeEnd": all(r["checks"]["settlesNearNativeSetting"] for r in reports.values()),
    }
    return {"ok": all(r["ok"] for r in reports.values()) and concurrent >= minimum, "checks": checks,
            "video": file.name, "sha256": a_report["sha256"],
            "concurrentMotionSeconds": round(concurrent, 6), "minConcurrentMotionSeconds": minimum, "targets": reports}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.output and args.output.resolve() in {args.video.resolve(), args.plan.resolve()}:
            raise ValueError("The report must use a path separate from its inputs.")
        spec = json.loads(args.plan.read_text(encoding="utf-8"))
        report = measure_pair(args.video, spec) if "targets" in spec else measure(args.video, spec)
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        print(output)
        raise SystemExit(0 if report["ok"] else 2)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"{error}\n")
