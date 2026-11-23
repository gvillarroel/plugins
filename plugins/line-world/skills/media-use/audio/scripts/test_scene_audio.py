from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

import scene_audio as audio


class SceneAudioTest(unittest.TestCase):
    def test_spanish_tts_reads_signed_values_without_altering_dates_or_other_voices(self):
        text = "Del +4 al -6, entre −0,5 y 2026-11-20. TLT-2 y 1e-3."
        expected = "Del más 4 al menos 6, entre menos 0,5 y 2026-11-20. TLT-2 y 1e-3."
        for voice in ("es", "es-419", "es_MX"):
            self.assertEqual(audio.spoken_text(text, {}, voice), expected)
        self.assertEqual(audio.spoken_text(text, {}, "en-US"), text)
        self.assertEqual(audio.spoken_text("El -6", {"-6": "sexto sótano"}, "es"), "El sexto sótano")

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.out = self.base / "generated"
        # Deliberately different input format: 24 kHz stereo, known duration.
        def tone(name, duration, hz):
            t = np.arange(round(duration * 24000)) / 24000
            pcm = np.int16(5000 * np.sin(2 * np.pi * hz * t))
            with wave.open(str(self.base / name), "wb") as writer:
                writer.setparams((2, 2, 24000, 0, "NONE", ""))
                writer.writeframes(np.repeat(pcm, 2).tobytes())
        tone("voice.wav", 1.2, 280)
        tone("cue.wav", .1, 750)
        self.scene = {"id": "one", "text": "Una. Dos.", "file": "voice.wav", "lead_s": .2, "tail_s": .1,
                      "marks": [{"text": "Una.", "start_s": 0, "end_s": .45},
                                {"text": "Dos.", "start_s": .55, "end_s": 1.2}],
                      "effects": [{"file": "cue.wav", "at_sentence": 2, "peak_dbfs": -24}]}

    def build(self, *scenes):
        return audio.build({"scenes": list(scenes)}, self.base,
                           self.out, self.base / "absent-model-cache", None)

    def test_recording_timeline_effect_and_repeatability(self):
        second = {"id": "two", "text": "Otra frase.", "file": "voice.wav", "duration_s": 2.4}
        first = self.build(self.scene, second)
        self.assertIsNone(first["voice"])
        self.assertFalse((self.base / "absent-model-cache").exists())
        self.assertEqual(first["master"]["samples"], round(3.9 * audio.RATE))
        scene, following = first["scenes"]
        self.assertEqual(scene["end_sample"], following["start_sample"])
        self.assertEqual(scene["effects"][0]["absolute_start_sample"], 36000)
        self.assertEqual(scene["sentences"][1]["absolute_start_sample"], 36000)
        self.assertAlmostEqual(first["master"]["integrated_lufs"], -18, delta=.3)
        self.assertLessEqual(first["master"]["true_peak_dbtp"], -1.5)
        self.assertIn("00:00:00,750", (self.out / "captions.srt").read_text(encoding="utf-8"))
        self.assertEqual(first, self.build(self.scene, second))
        self.build(second)
        self.assertFalse((self.out / scene["voice"]).exists())
        self.assertFalse((self.out / scene["effects"][0]["file"]).exists())

    def test_failed_render_preserves_accepted_master_and_authored_content(self):
        initial = self.build(self.scene)
        self.scene["effects"][0] = {"file": "cue.wav", "at_s": 1.49}
        with self.assertRaisesRegex(ValueError, "extends past"):
            self.build(self.scene)
        self.assertEqual(audio.checksum(self.out / "master.wav"), initial["master"]["sha256"])
        self.scene["effects"] = []
        (self.out / "voices/one.wav").write_bytes(b"my replacement")
        with self.assertRaisesRegex(ValueError, "user-authored or modified"):
            self.build(self.scene)
        self.assertEqual((self.out / "voices/one.wav").read_bytes(), b"my replacement")

    def test_high_crest_recording_keeps_clock_and_passes_master_limits(self):
        t=np.arange(2 * audio.RATE) / audio.RATE
        signal=(.025*np.sin(2*np.pi*420*t)).astype("float32")
        signal[audio.RATE//2]=.97
        audio.save_audio(self.base / "transient.wav", signal)
        result=self.build({"id":"accent","file":"transient.wav","text":"Transient."})
        self.assertEqual(result["scenes"][0]["voice_duration_s"], 2)
        self.assertEqual(result["master"]["samples"], round(2.67*audio.RATE))
        self.assertAlmostEqual(result["master"]["integrated_lufs"],-18,delta=1)
        self.assertLessEqual(result["master"]["true_peak_dbtp"],-1.5)

    def test_input_errors(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            self.build(self.scene, self.scene)
        with self.assertRaisesRegex(ValueError, "unique"):
            self.build(dict(self.scene, id="../bad"))
        with self.assertRaisesRegex(ValueError, "exceed"):
            self.build(dict(self.scene, duration_s=.5))
        with self.assertRaisesRegex(ValueError, "overlapping"):
            self.build(dict(self.scene, marks=[{"start_s": .4, "end_s": .2, "text": "Una."}]))
        with self.assertRaisesRegex(ValueError, "transcript"):
            self.build(dict(self.scene, marks=[{"start_s": 0, "end_s": .2, "text": "Otros."}]))

    def test_named_recording_optional_labels_preserve_plain_captions_and_audio(self):
        recipe = {"speakers": {"ana": {"name": "Ana", "voice": "es_AR-daniela-high"}},
                  "scenes": [dict(self.scene, speaker="ana")], "speaker_captions": True}
        cache = self.base / "unused-cache"
        result = audio.build(recipe, self.base, self.out, cache, None, offline=True)
        self.assertFalse(cache.exists())
        self.assertEqual(result["scenes"][0]["speaker_name"], "Ana")
        self.assertIsNone(result["voice"])
        labeled = (self.out / "captions-speakers.srt").read_text(encoding="utf-8")
        plain = (self.out / "captions.srt").read_text(encoding="utf-8")
        self.assertEqual(labeled.count("[Ana] "), 2)
        self.assertEqual(labeled.replace("[Ana] ", ""), plain)
        recipe["speaker_captions"] = False
        plain_build = audio.build(recipe, self.base, self.out, cache, None, offline=True)
        self.assertEqual(plain_build["master"]["sha256"], result["master"]["sha256"])
        self.assertFalse((self.out / "captions-speakers.srt").exists())

    def test_spanish_layout_uses_shared_clock_and_preserves_recorded_master(self):
        text = ("Esa semana, el rendimiento del Tesoro a diez años bajó del cinco coma quince "
                "al cuatro coma noventa y dos por ciento.")
        scene = {"id": "test", "file": "voice.wav", "text": text}
        original = self.build(scene)
        original_track = (self.out / "captions.srt").read_text(encoding="utf-8")
        self.assertIn(text, original_track)
        recipe = {"caption_layout": "es-lectura", "scenes": [scene]}
        reviewed = audio.build(recipe, self.base, self.out, self.base, None, offline=True)
        self.assertEqual(original["master"], reviewed["master"])
        self.assertEqual(original["scenes"], reviewed["scenes"])
        cues = reviewed["caption_layout"]["cues"]
        self.assertGreater(len(cues), 1)
        self.assertEqual(" ".join(w for c in cues for w in c["text"].split()), text)
        self.assertEqual({c["startBasis"] for c in cues}, {"phrase", "estimated"})
        self.assertTrue(all(len(line)<=42 for c in cues for line in c["text"].splitlines()))
        from spanish_captions import compose
        plain = self.out / "captions.srt"
        self.assertEqual(plain.read_text(encoding="utf-8"), compose(reviewed)[0])
        self.assertEqual(audio.checksum(plain), reviewed["captions"]["sha256"])
        plain.write_text("Un subtítulo del autor.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "user-authored"):
            self.build(scene)
        self.assertIn("del autor",plain.read_text(encoding="utf-8"))

    def test_legacy_caption_edit_survives_rebuilding_an_older_timeline(self):
        timeline = self.build(self.scene)
        timeline.pop("captions")
        (self.out/"timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
        self.assertEqual(self.build(self.scene)["master"], timeline["master"])
        (self.out/"timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
        (self.out/"captions.srt").write_text("Una edición bilingüe.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "user-authored"):
            self.build(self.scene)

    def test_roles_scene_overrides_and_model_reuse(self):
        models = []
        def load(choice, cache, seed, offline):
            models.append(choice)
            return len(models), {"model": str(choice), "seed": seed}

        def synth(scene, text, base, work, engine, preset, pronunciations):
            signal = audio.read_audio(self.base / "voice.wav") * (.75 if engine == 1 else .5)
            return signal, [(text, 0, len(signal))], "piper"
        spec = {"speakers": {"leo": {"name": "Leo", "voice": "es_MX-claude-high"},
                             "ines": {"name": "Inés", "model": "test.onnx", "preset": "deliberate"}},
                "scenes": [{"id": "a", "speaker": "leo", "text": "Uno."},
                           {"id": "b", "speaker": "ines", "text": "Dos."},
                           {"id": "c", "speaker": "ines", "text": "Tres.", "voice": "es_MX-claude-high", "preset": "brisk"}]}
        with patch.object(audio, "load_engine", side_effect=load), patch.object(audio, "prepare_voice", side_effect=synth):
            result = audio.build(spec, self.base, self.out, self.base, None, offline=True)
        self.assertEqual(models, [("es_MX-claude-high", None), (None, self.base / "test.onnx")])
        self.assertIsNone(result["voice"])
        self.assertEqual([r["preset"] for r in result["scenes"]], ["neutral", "deliberate", "brisk"])
        self.assertEqual(result["scenes"][0]["synthesis"], result["scenes"][2]["synthesis"])

    def test_missing_named_speaker_fails_and_offline_mode_never_fetches(self):
        with self.assertRaisesRegex(ValueError, "unknown speaker"):
            self.build(dict(self.scene, speaker="unknown"))
        with patch.object(audio, "urlopen", side_effect=AssertionError("network reached")):
            with self.assertRaisesRegex(ValueError, "Offline mode"):
                audio.model_from_cache(self.base, "es_AR-daniela-high", offline=True)


if __name__ == "__main__":
    unittest.main()
