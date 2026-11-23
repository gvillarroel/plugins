# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Check the weekly archive's input selection without re-encoding either film."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import empaquetar


class PackageInputs(unittest.TestCase):
    def test_both_directory_layouts_use_distinct_locked_inputs(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch)
            landscape=root/"horizontal"
            landscape.mkdir()
            sibling=root/"móvil con espacios"
            sibling.mkdir()
            nested=landscape/"vertical"
            nested.mkdir()
            for portrait,expected in ((sibling,sibling),(None,nested)):
                with self.subTest(portrait=portrait),patch.object(empaquetar,"package_locked") as build:
                    empaquetar.package(landscape,root/"audio",root/"fuentes.zip",portrait=portrait)
                    self.assertEqual(build.call_args.args[-1],expected)
            with self.assertRaisesRegex(ValueError,"distinct"):
                empaquetar.package(landscape,root/"audio",root/"fuentes.zip",portrait=landscape)
            with self.assertRaisesRegex(ValueError,".zip"):
                empaquetar.package(landscape,root/"audio",landscape/"mercados.mp4",portrait=sibling)

    def test_candidate_orientation_matches_its_reviewed_viewport(self):
        with tempfile.TemporaryDirectory() as scratch:
            folder=Path(scratch)
            (folder/"mercados.mp4").write_bytes(b"orientation fixture")
            movie_sha=empaquetar.digest(folder/"mercados.mp4")
            (folder/"verificacion.json").write_text(json.dumps({"ok":True,"viewport":[390,844],"mp4Sha256":movie_sha}))
            (folder/"proyecto.json").write_text(json.dumps({"width":390,"height":844,"audioTimeline":"clock.json"}))
            (folder/"clock.json").write_text(json.dumps({"master":{"file":"master.wav"}}))
            (folder/"guion-visual.json").write_text("[]")
            with patch.object(empaquetar,"previous_hashes",return_value={}):
                self.assertEqual(empaquetar.reviewed_format(folder,True)[0],movie_sha)
                with self.assertRaisesRegex(ValueError,"orientation"):
                    empaquetar.reviewed_format(folder,False)
                (folder/"proyecto.json").write_text(json.dumps({"width":1280,"height":720,"audioTimeline":"clock.json"}))
                with self.assertRaisesRegex(ValueError,"orientation"):
                    empaquetar.reviewed_format(folder,False)


if __name__=="__main__":
    unittest.main()
