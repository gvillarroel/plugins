"""Find rapidly alternating visual states in a sequence of decoded frames."""
from __future__ import annotations

from collections import deque
import math
from typing import NamedTuple

import numpy as np

RAPID_STEP_SECONDS = .45


class Sample(NamedTuple):
    planes: tuple
    colors: bytes
    shape: tuple


def signature(rgb):
    """Compact masks with a dead band so small codec errors do not become cuts."""
    # Keep the horizontal and vertical sampling density similar in portrait and landscape.
    stride = max(1, math.ceil(max(rgb.shape[:2]) / 160))
    thumb = rgb[stride // 2::stride, stride // 2::stride]
    r, g, b = thumb.astype(np.int16).transpose(2, 0, 1)
    light = (2 * r + 5 * g + b) // 8
    planes = [(light, 76), (light, 145), (light, 210),
              (r-g, 46), (b-g, 46), (g-r, 46)]
    def pack(mask):
        return int.from_bytes(np.packbits(mask).tobytes(), "big")
    masks = tuple((pack(value < level-12), pack(value > level+12)) for value, level in planes)
    return Sample(masks, thumb.tobytes(), light.shape), light.size


def changed(left, right):
    if left is right:
        return 0
    mask = 0
    for (low_a, high_a), (low_b, high_b) in zip(left.planes, right.planes):
        mask |= (low_a & high_b) | (high_a & low_b)
    return mask


def visible_edge(mask, count, poses):
    height,width = poses[0].shape
    if count > max(32, math.ceil(.01*height*width)):
        return True
    # A single compressed color boundary can shimmer without the object
    # changing state. Keep thin real rules and cursors if their RGB jump
    # is distinct; compact shapes with a 2x2 interior need no extra contrast.
    raw = mask.to_bytes((height*width+7)//8, "big")
    field = np.unpackbits(np.frombuffer(raw,np.uint8))[:height*width].reshape(height,width).astype(bool)
    if np.any(field[1:,1:] & field[:-1,1:] & field[1:,:-1] & field[:-1,:-1]):
        return True
    patches = [np.frombuffer(p.colors,np.uint8).reshape(height,width,3)[field].astype(np.int16) for p in poses]
    jumps = [np.abs(right-left).max(axis=1) for left,right in zip(patches,patches[1:])]
    return np.count_nonzero(np.minimum.reduce(jumps) >= 64) >= math.ceil(count/2)


def repeated_area(a, b, c, d, minimum):
    cd = changed(c, d)
    if cd.bit_count() < minimum:
        return 0
    ab, bc = changed(a,b), changed(b,c)
    overlap = ab & bc & cd
    common = overlap.bit_count()
    if common < minimum or common < .8 * (ab | bc | cd).bit_count():
        return 0
    drift = (changed(a,c) | changed(b,d)).bit_count()
    return common if drift <= common*.2 and visible_edge(overlap,common,(a,b,c,d)) else 0


class RepeatedStates:
    """Look for A–B–A–B at one location, including a change every source frame."""

    def __init__(self, fps, *, presentation_times=None):
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Frame rate must be finite and positive.")
        self.fps = fps
        self.times = None if presentation_times is None else tuple(presentation_times)
        self.largest_step = max(1, math.floor(RAPID_STEP_SECONDS * fps))
        if self.times is not None:
            if len(self.times)<2 or any(not math.isfinite(t) for t in self.times) or any(
                    b<=a for a,b in zip(self.times,self.times[1:])):
                raise ValueError("Supply every increasing picture time followed by its final end.")
            left=0
            self.largest_step=1
            for right in range(len(self.times)-1):
                while self.times[right]-self.times[left]>RAPID_STEP_SECONDS+.000001:
                    left+=1
                self.largest_step=max(self.largest_step,right-left)
        self.history = deque(maxlen=3*self.largest_step+1)
        self.pose_runs = [(scale,deque(maxlen=4)) for scale in (1,4,16)]
        self.frames = 0
        self.intervals = []
        self.hold = 0

    def observe(self, rgb):
        current, pixels = signature(rgb)
        if self.history and current == self.history[-1]:
            current = self.history[-1]
            self.hold += 1
        else:
            self.hold = 1
        self.history.append(current)
        frame = self.frames
        self.frames += 1
        min_pixels = max(12, math.ceil(.003 * pixels))
        # A few changed edge pixels in a held H.264 picture can split one
        # large pose into two at the most sensitive scale. Keep the same
        # four-state test at larger change areas alongside small highlights.
        for scale, poses in self.pose_runs:
            threshold = min_pixels*scale
            if threshold > pixels or (poses and changed(poses[-1][1],current).bit_count() < threshold):
                continue
            previous = self.history[-2] if len(self.history)>1 else current
            poses.append((frame,current,previous))
            if len(poses) == 4:
                _,(fb,b,a),(fc,c,_),(fd,d,_) = poses
                if max(fc-fb,fd-fc) <= self.largest_step:
                    common = repeated_area(a,b,c,d,threshold)
                    if common:
                        self._record([fb-1,fb,fc,fd],common/pixels)
        if self.hold >= len(self.history):
            return
        # Sample near-repeated poses too, including returns during continuous motion.
        for step in range(1, min(self.largest_step, frame // 3) + 1):
            a, b, c = (self.history[-1-i*step] for i in (3, 2, 1))
            common = repeated_area(a,b,c,current,min_pixels)
            if common:
                self._record([frame-3*step,frame-2*step,frame-step,frame],common/pixels)

    def _record(self, witnesses, area):
        first, second, third, last = witnesses
        holds = [self.time(third)-self.time(second), self.time(last)-self.time(third)] if self.times is not None else [
            (third-second)/self.fps, (last-third)/self.fps]
        if max(holds) > RAPID_STEP_SECONDS+.000001:
            return
        item = {"firstFrame": first, "lastFrame": last, "start": self.time(first), "firstSwitch":self.time(second),
                "end": self.time(last+1), "strongestFrames": witnesses,
                "halfCycleSeconds": max(holds), "middleStepSeconds":holds, "changedFraction": round(area, 6)}
        if not self.intervals or first > self.intervals[-1]["lastFrame"]+1:
            self.intervals.append(item)
            return
        # A later observation at a longer lag can bridge two earlier intervals.
        existing = self.intervals.pop()
        first_switch = min(item["firstSwitch"], existing["firstSwitch"])
        while self.intervals and first <= self.intervals[-1]["lastFrame"]+1:
            earlier = self.intervals.pop()
            first = min(first, earlier["firstFrame"])
            first_switch = min(first_switch, earlier["firstSwitch"])
            if earlier["changedFraction"] > existing["changedFraction"]:
                existing = earlier
        first = min(first, existing["firstFrame"])
        peak = max((existing, item), key=lambda entry: entry["changedFraction"])
        self.intervals.append({**peak, "firstFrame": first, "start": self.time(first), "firstSwitch":first_switch,
                               "lastFrame": last, "end": self.time(last+1)})

    def time(self, frame):
        return self.times[frame] if self.times is not None else frame/self.fps

    def report(self):
        return {"ok": not self.intervals, "frames": self.frames, "intervals": self.intervals,
                "maxHalfCycleSeconds": RAPID_STEP_SECONDS, "minimumChangedFraction": .003,
                "scope": "Four near-repeated states at the source cadence, with the same area changing on three successive switches. Heuristic for editorial review."}


class SubjectCadence:
    """Look for a flipping label or highlight while another part of the picture moves."""
    def __init__(self, fps):
        self.fps = fps
        self.active = {}
        self.intervals = []

    def configure(self, regions, frame, *, cut=False):
        for name, (_, previous, _, _, _) in list(self.active.items()):
            if cut or name not in regions or not np.array_equal(previous, regions[name]):
                self._close(name)
        for name, mask in regions.items():
            if name in self.active:
                continue
            ys, xs = np.where(mask)
            if xs.size < 12:
                continue
            bounds = (slice(int(ys.min()), int(ys.max())+1), slice(int(xs.min()), int(xs.max())+1))
            area = mask[bounds]
            self.active[name] = (RepeatedStates(self.fps), mask, bounds, None if area.all() else area, frame)

    def observe(self, frame):
        for checker, _, bounds, clip, _ in self.active.values():
            pixels = frame[bounds]
            if clip is not None:
                pixels = np.where(clip[:, :, None], pixels, 0)
            checker.observe(pixels)

    def _close(self, name):
        checker, _, _, _, offset = self.active.pop(name)
        for original in checker.report()["intervals"]:
            span = dict(original)
            span.update(subject=name, firstFrame=offset+span["firstFrame"], lastFrame=offset+span["lastFrame"],
                        strongestFrames=[offset+i for i in span["strongestFrames"]],
                        start=offset/self.fps+span["start"], firstSwitch=offset/self.fps+span["firstSwitch"],
                        end=offset/self.fps+span["end"])
            self.intervals.append(span)

    def finish(self):
        for name in list(self.active):
            self._close(name)
        return sorted(self.intervals, key=lambda item: (item["firstFrame"], item["subject"]))
