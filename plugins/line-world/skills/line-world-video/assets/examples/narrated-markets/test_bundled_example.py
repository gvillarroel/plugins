"""Run the included weekly film from a working directory outside the installation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


HERE=Path(__file__).resolve().parent


class InstalledExample(unittest.TestCase):
    def test_inputs_and_foreign_directory_preflight(self):
        sample=HERE/"ejemplo-2026-11-20"
        with TemporaryDirectory() as directory:
            cwd=Path(directory)
            def run(script,*args):
                return subprocess.run([sys.executable,"-B",str(HERE/script),*map(str,args)],cwd=cwd,capture_output=True)
            evidence=run("cierres.py","compare",sample/"datos.json",sample/"evidencia/recibo.json","sources")
            self.assertEqual(evidence.returncode,0,evidence.stderr)
            counts=json.loads((cwd/"sources/comparacion.json").read_bytes())["counts"]
            self.assertEqual(counts["match"],38)
            self.assertEqual(sum(counts.values()),38)
            for voice in json.loads((sample/"voces/duraciones.json").read_bytes())["scenes"]:
                self.assertEqual(hashlib.sha256((sample/"voces"/voice["file"]).read_bytes()).hexdigest(),voice["sha256"])
            render=run("generar.py","--ejemplo","--formato","vertical","--preflight-only","--out","mi episodio")
            self.assertEqual(render.returncode,0,render.stderr)
            out=cwd/"mi episodio"
            self.assertTrue(json.loads((out/"pre-render.json").read_bytes())["ok"])
            self.assertEqual(json.loads((out/"cotejo-fuentes.json").read_bytes())["counts"],counts)
            project=json.loads((out/"proyecto.json").read_bytes())
            self.assertEqual((project["width"],project["height"],project["fps"]),(390,844,30))

    def test_one_wrong_cent_does_not_replace_the_accepted_preflight(self):
        sample=HERE/"ejemplo-2026-11-20"
        with TemporaryDirectory() as directory:
            cwd=Path(directory)
            target=cwd/"aceptado"
            command=[sys.executable,"-B",str(HERE/"generar.py"),"--preflight-only","--out",str(target)]
            subprocess.run([*command,"--ejemplo"],cwd=cwd,capture_output=True,check=True)
            original=(target/"publicacion.json").read_bytes()
            data=json.loads((sample/"datos.json").read_bytes())
            data["series"]["oro"]["values"][-1]=3532.86
            changed=cwd/"cambio.json"
            changed.write_text(json.dumps(data),encoding="utf-8")
            rejected=subprocess.run([*command,"--datos",str(changed),"--audio",str(sample/"voces"),
                "--recibo",str(sample/"evidencia/recibo.json")],cwd=cwd,capture_output=True)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn(b"oro",rejected.stderr)
            self.assertIn(b"2026-11-20",rejected.stderr)
            self.assertEqual(original,(target/"publicacion.json").read_bytes())
            for name,expected in json.loads(original)["files"].items():
                self.assertEqual(hashlib.sha256((target/name).read_bytes()).hexdigest(),expected)

    def test_an_explicit_audio_folder_cannot_be_silently_ignored(self):
        with TemporaryDirectory() as directory:
            cwd=Path(directory)
            for args in (["--ejemplo","--audio","my voice"],["--datos","my data"]):
                attempt=subprocess.run([sys.executable,"-B",str(HERE/"generar.py"),*args,"--out","film"],
                                       cwd=cwd,capture_output=True)
                self.assertEqual(attempt.returncode,2,attempt.stderr)
                self.assertFalse((cwd/"film").exists())


if __name__=="__main__":
    unittest.main()
