"""Catch channel swaps and a removed high-frequency effect that a mono speech check accepts."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

import numpy as np
from check_audio_channels import compare, master_clock
from check_narrated_export import audio_agreement


class AudioChannels(unittest.TestCase):
    def test_lossless_master_preserves_an_odd_sample_count_and_stereo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wav, flac, streamed = (root / name for name in ("mix.wav", "mix.flac", "pipe.flac"))
            rate, length = 44100, 16217
            samples = np.random.default_rng(18).integers(-20000, 20000, (length, 2), dtype="<i2").tobytes()
            with wave.open(str(wav), "wb") as out:
                out.setparams((2, 2, rate, 0, "NONE", ""))
                out.writeframes(samples)
            encoder = ["ffmpeg", "-v", "error", "-i", str(wav), "-c:a", "flac", "-f", "flac"]
            subprocess.run([*encoder, str(flac)], check=True)
            streamed.write_bytes(subprocess.check_output([*encoder, "pipe:1"]))
            self.assertEqual(int.from_bytes(streamed.read_bytes()[18:26], "big") & ((1 << 36) - 1), 0)
            for master in (wav, flac, streamed):
                with self.subTest(master=master.name):
                    self.assertEqual(master_clock(master), (2, rate, length))
                    pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(master), "-f", "s16le", "-"])
                    self.assertEqual(pcm, samples)
                    scenes = [{"id":"prueba", "voice":{"end_sample":length}}]
                    self.assertTrue(compare(master, wav, scenes, rate, 2)["ok"])
                    with self.assertRaisesRegex(ValueError, "clock"):
                        compare(master, wav, scenes, 48000, 2)
            broken = root / "broken.flac"
            broken.write_bytes(b"fLaC" + b"\0" * 20)
            with self.assertRaisesRegex(ValueError, "STREAMINFO"):
                master_clock(broken)
            broken.write_bytes(flac.read_bytes()[:100])
            with self.assertRaises(ValueError):
                compare(broken, wav, scenes, rate, 2)

    def test_stereo_order_missing_effect_and_mono_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rate=48000
            frames=rate*2
            t=np.arange(frames)/rate
            env=np.minimum(1,t*20)*np.minimum(1,(2-t)*20)
            left=.22*np.sin(2*np.pi*(330*t+24*t*t))*env
            right=.20*np.sin(2*np.pi*(690*t+31*t*t))*env
            lo,hi=rate,int(1.12*rate)
            left[lo:hi]=.18*np.sin(2*np.pi*10500*t[lo:hi])*np.hanning(hi-lo)
            stereo=np.column_stack((left,right))
            def wav(name,samples):
                path=root/(name+".wav")
                with wave.open(str(path),"wb") as out:
                    out.setparams((2,2,rate,0,"NONE",""))
                    out.writeframes(np.rint(samples*32767).astype("<i2").tobytes())
                return path
            master=wav("master",stereo)
            def aac(source,name):
                path=root/(name+".m4a")
                subprocess.run(["ffmpeg","-v","error","-i",str(source),"-c:a","aac","-b:a","224k",str(path)],check=True)
                return path
            scenes=[{"id":"escena","voice":{"end_sample":frames,"effects":[
                {"sound":"tono agudo","absolute_start_sample":lo,"duration_s":.12}]}}]
            approved=compare(master,aac(master,"correcta"),scenes,rate,2)
            self.assertTrue(approved["ok"],approved)
            swapped=aac(wav("intercambio",stereo[:,::-1]),"intercambiada")
            self.assertTrue(audio_agreement(master,swapped,scenes,rate)[0]["ok"])
            self.assertFalse(compare(master,swapped,scenes,rate,2)["ok"])
            silent=stereo.copy()
            silent[lo:hi,0]=0
            removed=aac(wav("sin-efecto",silent),"resultado")
            self.assertTrue(audio_agreement(master,removed,scenes,rate)[0]["ok"])
            damaged=compare(master,removed,scenes,rate,2)
            self.assertFalse(damaged["ok"])
            self.assertFalse(damaged["scenes"][0]["effects"][0]["channels"][0]["ok"])
            self.assertIn("channel count",compare(master,removed,scenes,rate,1)["error"])


if __name__=="__main__":
    unittest.main()
