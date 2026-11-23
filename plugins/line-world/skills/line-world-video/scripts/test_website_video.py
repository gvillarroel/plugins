#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=11,<13", "playwright>=1.51,<2"]
# ///
"""Test preserved screenshot pixels, clear routes, exact audio clocks and cache reuse."""
import copy
import json
import math
import struct
import subprocess
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image, ImageDraw
from website_video import build, encode_clip, read, render, probe


class WebsiteVideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd()); self.root = Path(self.temp.name)
        image = Image.new('RGB', (900, 500), 'white'); draw = ImageDraw.Draw(image)
        draw.rectangle((120, 140, 380, 220), fill='#696969'); draw.rectangle((520, 140, 780, 220), fill='#cfcfcf')
        draw.text((145, 164), 'Synthetic control A', fill='white'); draw.text((545, 164), 'Synthetic control B', fill='#333e48'); image.save(self.root / 'capture.png')
        self.story = {'fps': 24, 'source': {'kind': 'synthetic-test', 'scope': 'Generated control fixture, not a real website screenshot.'}, 'scenes': [{'id': 'controls', 'capture': 'capture.png', 'duration': 3, 'scale': 1.7,
            'targets': {'a': {'box': [120, 140, 260, 80], 'port': [100, 180]}, 'b': {'box': [520, 140, 260, 80], 'port': [500, 180]}},
            'cues': [{'target': 'a', 'at': .5}, {'target': 'b', 'at': 2.3}]}]}

    def tearDown(self): self.temp.cleanup()

    def compile(self, story=None):
        path = self.root / 'request.json'; path.write_text(json.dumps(story or self.story), encoding='utf-8')
        return build(self.root, path)

    def test_build_keeps_original_bytes_and_self_contained_dependencies(self):
        original = (self.root / 'capture.png').read_bytes(); result = self.compile()
        self.assertTrue(result['ok']); self.assertEqual(original, (self.root / 'capture.png').read_bytes())
        for name in ['index.html', 'preview.html', 'tour.json', 'tour.js', 'website-tour.js', 'focus.js']: self.assertTrue((self.root / name).is_file())
        self.assertEqual(read(self.root / 'tour.json')['scenes'][0]['frames'], 72)

    def test_canvas_size_requires_a_pair_of_even_dimensions(self):
        for dimensions in ({'width': 390}, {'width': 391, 'height': 844}, {'width': 390, 'height': 0}):
            with self.subTest(dimensions=dimensions), self.assertRaisesRegex(ValueError, 'both width and height'):
                self.compile({**self.story, **dimensions})

    def test_portrait_render_preserves_actual_canvas_and_registered_targets(self):
        story = copy.deepcopy(self.story)
        story.update(width=390, height=844)
        story['scenes'][0]['scale'] = 1.05
        self.compile(story)
        movie, report = self.root / 'vertical.mp4', self.root / 'vertical.json'
        result = render(self.root, movie, report)
        self.assertTrue(result['ok'], result)
        video = next(s for s in probe(movie)['streams'] if s['codec_type'] == 'video')
        self.assertEqual((video['width'], video['height'], int(video['nb_frames'])), (390, 844, 72))
        receipt = read(report)
        self.assertEqual((receipt['width'], receipt['height']), (390, 844))
        self.assertEqual(receipt['issues'], [])

    def test_crop_and_spoken_control_must_fit_actual_source(self):
        s = copy.deepcopy(self.story); s['scenes'][0]['region'] = [0, 0, 400, 500]
        with self.assertRaisesRegex(ValueError, 'spoken control'): self.compile(s)
        s['scenes'][0]['region'] = [0, 0, 901, 500]
        with self.assertRaisesRegex(ValueError, 'actual screenshot'): self.compile(s)

    def test_blank_capture_and_escaping_paths_are_rejected(self):
        Image.new('RGB', (900, 500), 'white').save(self.root / 'capture.png')
        with self.assertRaisesRegex(ValueError, 'visible content'): self.compile()
        s = copy.deepcopy(self.story); s['scenes'][0]['capture'] = '../outside.png'
        with self.assertRaisesRegex(ValueError, 'inside the project'): self.compile(s)

    def test_negative_and_unordered_cues_are_rejected(self):
        for times in [[-.1, 2], [2, 1], [.5, .5]]:
            s = copy.deepcopy(self.story)
            for cue, at in zip(s['scenes'][0]['cues'], times): cue['at'] = at
            with self.assertRaisesRegex(ValueError, 'ordered'): self.compile(s)

    def test_dark_ui_and_declared_dark_theme_require_real_light_recapture(self):
        s = copy.deepcopy(self.story); s['source']['theme'] = 'dark'
        with self.assertRaisesRegex(ValueError, 'native light theme'): self.compile(s)
        image = Image.new('RGB', (900, 500), '#0d1117'); draw = ImageDraw.Draw(image)
        draw.rectangle((120, 140, 380, 220), fill='#555555'); draw.text((145, 164), 'Synthetic dark UI', fill='white'); image.save(self.root / 'capture.png')
        original = (self.root / 'capture.png').read_bytes()
        with self.assertRaisesRegex(ValueError, 'Select the native light theme'): self.compile()
        self.assertEqual(original, (self.root / 'capture.png').read_bytes())

    def tone(self):
        path = self.root / 'tone.wav'
        with wave.open(str(path), 'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(48000)
            out.writeframes(b''.join(struct.pack('<h', round(5000 * math.sin(2 * math.pi * 220 * n / 48000))) for n in range(36000)))
        return path

    def test_measured_audio_is_preserved_and_cannot_exceed_scene(self):
        self.tone(); s = copy.deepcopy(self.story); s['scenes'][0].update(audio='tone.wav', audioLead=2.5)
        with self.assertRaisesRegex(ValueError, 'Measured speech'): self.compile(s)
        s['scenes'][0]['audioLead'] = .2; self.compile(s)
        self.assertAlmostEqual(read(self.root / 'tour.json')['scenes'][0]['observedAudioSeconds'], .75)

    def test_real_render_audio_decode_and_unchanged_cache(self):
        self.tone(); s = copy.deepcopy(self.story)
        for name in ['second', 'third']:
            item = copy.deepcopy(s['scenes'][0]); item['id'] = name; s['scenes'].append(item)
        s['scenes'][0].update(audio='tone.wav', audioLead=.2); self.compile(s)
        movie, report, poster = self.root / 'final.mp4', self.root / 'review.json', self.root / 'poster.png'
        result = render(self.root, movie, report, poster=poster); self.assertTrue(result['ok'], result)
        p = probe(movie); video = next(v for v in p['streams'] if v['codec_type'] == 'video')
        self.assertEqual(int(video['nb_frames']), 216); self.assertTrue(any(v['codec_type'] == 'audio' for v in p['streams']))
        self.assertTrue(read(report)['fullDecode']); before = movie.stat().st_mtime_ns
        self.assertTrue(render(self.root, movie, report)['reused']); self.assertEqual(before, movie.stat().st_mtime_ns)
        s['scenes'][0]['cues'][1]['at'] = 2.6; self.compile(s)
        self.assertTrue(render(self.root, movie, report)['ok'])
        self.assertEqual([r['clipReused'] for r in read(report)['scenes']], [False, False, True])
        accepted = movie.read_bytes()
        run = subprocess.run

        def reject_decode(command, **kwargs):
            if command[0] == "ffmpeg" and command[-3:] == ["-f", "null", "-"]:
                raise subprocess.CalledProcessError(1, command)
            return run(command, **kwargs)

        with patch("website_video.subprocess.run", side_effect=reject_decode):
            self.assertFalse(render(self.root, movie, self.root / "rejected.json")["ok"])
        self.assertEqual(movie.read_bytes(), accepted)
        self.assertFalse(list(movie.parent.glob(".website-export-*")))
        (self.root / 'capture.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Screenshot bytes changed'): render(self.root, movie, report)

    def test_encoder_failure_keeps_prior_clip_and_cleans_staging(self):
        image = BytesIO()
        Image.new("RGB", (320, 180), "white").save(image, format="JPEG")
        page = Mock()
        page.evaluate.return_value = {"pose": 1}
        page.screenshot.return_value = image.getvalue()
        clip = self.root / "controls.mp4"
        self.assertEqual(encode_clip(page, 0, {"frames": 2}, 24, clip), 1)
        accepted = clip.read_bytes()
        self.assertEqual(int(probe(clip)["streams"][0]["nb_frames"]), 2)

        page.screenshot.return_value = b"invalid screenshot"
        with self.assertRaises(ValueError):
            encode_clip(page, 0, {"frames": 2}, 24, clip)
        self.assertEqual(clip.read_bytes(), accepted)
        self.assertFalse(list(self.root.glob(".website-clip-*")))

    def test_blocked_guide_route_fails_instead_of_covering_control(self):
        s = copy.deepcopy(self.story); s['scenes'][0]['targets']['a']['port'] = [200, 180]; self.compile(s)
        self.assertFalse(render(self.root, self.root / 'unused.mp4', self.root / 'blocked.json', audit_only=True)['ok'])
        self.assertFalse(read(self.root / 'blocked.json')['ok'])


if __name__ == '__main__': unittest.main()
