"""Exercise publication faults, interrupted writers and edits without a video encoder."""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from publicar import MANIFEST, publish, workspace


def candidate(label, *, audio=False):
    def build(stage,target):
        for name in ["datos.json","escena.html","mercados.mp4","verificacion.json"]:
            (stage/name).write_text(label,encoding="utf-8")
        if audio:
            (stage/"audio").mkdir()
            (stage/"audio/master.wav").write_bytes(label.encode())
        return set()
    return build


def contents(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob("*") if p.is_file()}


class Publication(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output=Path(temp.name)/"episodio"
        publish(self.output,False,candidate("primera"))
        (self.output/"notas.txt").write_text("texto del usuario",encoding="utf-8")

    def test_staging_failure_leaves_published_bytes_and_user_note_untouched(self):
        previous=contents(self.output)
        def failed(stage,target):
            candidate("segunda",audio=True)(stage,target)
            raise OSError(errno.ENOSPC,"full at final verifier")
        with self.assertRaises(OSError):publish(self.output,False,failed)
        self.assertEqual(contents(self.output),previous)
        self.assertFalse(workspace(self.output).exists())

    def test_rollback_after_atomic_replace_fails(self):
        previous=contents(self.output)
        real=os.replace
        def fail(source,target):
            if Path(source).parent.name=="candidate" and Path(target)==self.output/"mercados.mp4":
                raise OSError(errno.ENOSPC,"injected during replacement")
            real(source,target)
        with patch("publicar.os.replace",side_effect=fail),self.assertRaises(OSError):
            publish(self.output,False,candidate("segunda",audio=True))
        self.assertEqual(contents(self.output),previous)
        self.assertFalse((self.output/"audio").exists())

    def test_next_run_recovers_after_process_termination(self):
        previous=contents(self.output)
        code="""from pathlib import Path
import os,sys
from publicar import publish
from test_publicar import candidate
root=Path(sys.argv[1])
real=os.replace
def stop(source,target):
    real(source,target)
    if Path(source).parent.name=='candidate' and Path(target)==root/'datos.json':os._exit(87)
os.replace=stop
publish(root,False,candidate('interrumpida'))"""
        result=subprocess.run([sys.executable,"-B","-c",code,str(self.output)],cwd=Path(__file__).parent)
        self.assertEqual(result.returncode,87)
        self.assertTrue((workspace(self.output)/"active.json").is_file())
        def after_recovery(stage,target):
            self.assertEqual(contents(self.output),previous)
            raise RuntimeError("recover only")
        with self.assertRaisesRegex(RuntimeError,"recover only"):publish(self.output,False,after_recovery)
        self.assertEqual(contents(self.output),previous)

    def test_preflight_side_project_preserves_existing_final(self):
        previous=contents(self.output)
        def preview(stage,target):
            (stage/"datos.json").write_text("solo preflight",encoding="utf-8")
            return set()
        target=publish(self.output,True,preview)
        self.assertEqual(target,self.output/"preflight")
        self.assertEqual((target/"datos.json").read_text(encoding="utf-8"),"solo preflight")
        for name,data in previous.items():
            self.assertEqual((self.output/name).read_bytes(),data)

    def test_preserves_edited_files_and_an_input_with_an_output_name(self):
        edited=self.output/"escena.html"
        edited.write_text("edición manual",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"preserved"):publish(self.output,False,candidate("nueva"))
        self.assertEqual(edited.read_text(encoding="utf-8"),"edición manual")
        edited.write_text("primera",encoding="utf-8")
        data=self.output/"datos.json"
        def source_and_destination(stage,target):
            candidate("segunda")(stage,target)
            return {data}
        with self.assertRaisesRegex(ValueError,"preserved"):publish(self.output,False,source_and_destination)
        self.assertEqual(data.read_text(encoding="utf-8"),"primera")

    def test_detects_edits_while_preparing_candidate_and_releases_lock(self):
        def changed(stage,target):
            candidate("segunda")(stage,target)
            (target/"escena.html").write_text("trabajo concurrente",encoding="utf-8")
            return set()
        with self.assertRaisesRegex(ValueError,"changed during rendering"):publish(self.output,False,changed)
        self.assertEqual((self.output/"escena.html").read_text(encoding="utf-8"),"trabajo concurrente")
        self.assertFalse(workspace(self.output).exists())

    def test_existing_untracked_reserved_filename_is_preserved(self):
        mixed=self.output.parent/"project"
        mixed.mkdir()
        (mixed/"datos.json").write_text("original",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"preserved"):publish(mixed,False,candidate("segunda"))
        self.assertEqual(contents(mixed),{"datos.json":b"original"})

    def test_a_fresh_preflight_can_be_completed_in_place(self):
        root=self.output.parent/"nuevo"
        def preview(stage,target):
            (stage/"datos.json").write_text("previo",encoding="utf-8")
            return set()
        self.assertEqual(publish(root,True,preview),root)
        self.assertFalse((root/"mercados.mp4").exists())
        publish(root,False,candidate("final"))
        self.assertEqual((root/"mercados.mp4").read_text(encoding="utf-8"),"final")

    def test_stale_derived_previews_are_removed_only_when_unedited(self):
        def long_episode(stage,target):
            candidate("larga")(stage,target)
            (stage/"vista-4.png").write_bytes(b"view4")
            (stage/"vista-12.png").write_bytes(b"view12")
            return set()
        publish(self.output,False,long_episode)
        (self.output/"vista-4.png").write_bytes(b"retocada")
        publish(self.output,False,candidate("corta"))
        self.assertFalse((self.output/"vista-12.png").exists())
        self.assertEqual((self.output/"vista-4.png").read_bytes(),b"retocada")
        self.assertNotIn("vista-4.png",json.loads((self.output/MANIFEST).read_bytes())["files"])

    def test_two_writers_do_not_interleave(self):
        first=threading.Event();release=threading.Event();second=threading.Event()
        failures=[]
        def execute(label,signal,wait):
            def build(stage,target):
                signal.set()
                if wait: self.assertTrue(release.wait(5))
                return candidate(label)(stage,target)
            try:publish(self.output,False,build)
            except BaseException as exc:failures.append(exc)
        a=threading.Thread(target=execute,args=("A",first,True));b=threading.Thread(target=execute,args=("B",second,False))
        a.start();self.assertTrue(first.wait(5));b.start()
        try:self.assertFalse(second.wait(.2))
        finally:release.set();a.join(5);b.join(5)
        self.assertFalse(a.is_alive() or b.is_alive());self.assertEqual(failures,[])
        for name in ["datos.json","escena.html","mercados.mp4","verificacion.json"]:
            self.assertEqual((self.output/name).read_text(encoding="utf-8"),"B")
        self.assertIn("mercados.mp4",json.loads((self.output/MANIFEST).read_bytes())["files"])


if __name__=="__main__":unittest.main()

