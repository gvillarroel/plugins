import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

import codex_image_asset as helper


class CodexImageTest(unittest.TestCase):
    def test_checkerboard_or_opaque_alpha_is_not_a_cutout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"asset.png"
            image=Image.new("RGBA",(2,2),(100,100,100,255))
            image.putpixel((1,1),(180,180,180,255))
            image.save(path)
            with self.assertRaisesRegex(ValueError,"transparent and visible"):
                helper.examine(path,"cutout")
            image.putpixel((0,0),(0,0,0,0))
            image.putpixel((1,0),(180,180,180,130))
            image.save(path)
            checks=helper.examine(path,"cutout")
            self.assertEqual((checks["transparent_pixels"],checks["partially_visible_pixels"]),(1,1))

    def test_record_edit_verify_then_detect_changed_reference_and_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            image,prompt,manifest,reference=(root/name for name in ("edited.png","prompt.txt","record.json","before.png"))
            for p,color in ((image,"red"),(reference,"blue")): Image.new("RGB",(16,16),color).save(p)
            prompt.write_text("Conservar el encuadre y cambiar el color.",encoding="utf-8")
            argv=[sys.executable,helper.__file__,"record",str(image),str(prompt),str(manifest),"--operation","edit",
                  "--generation-id","fixture","--purpose","Comprobar los archivos originales","--alpha","opaque","--reference",str(reference)]
            subprocess.run(argv,capture_output=True,check=True)
            self.assertEqual(helper.verify(manifest)["size"],[16,16])
            self.assertNotEqual(subprocess.run(argv,capture_output=True).returncode,0)
            old_prompt=prompt.read_bytes()
            prompt.write_text("Otro texto",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Prompt changed"):helper.verify(manifest)
            prompt.write_bytes(old_prompt)
            reference.write_bytes(b"replacement")
            with self.assertRaisesRegex(ValueError,"reference checksum"):helper.verify(manifest)

    def test_near_opaque_core_is_opt_in_for_a_transparent_cutout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"asset.png"
            image=Image.new("RGBA",(4,4),(0,0,0,0))
            for x,y,a in ((1,1,254),(1,2,250),(2,1,130)):
                image.putpixel((x,y),(80,80,80,a))
            image.save(path)
            details=helper.examine(path,"cutout",.66)["alpha_detail"]
            self.assertEqual(details["maximum"],254)
            self.assertEqual(details["visible_bounds"],(1,1,3,3))
            self.assertEqual(details["transparent_perimeter_fraction"],1)
            self.assertEqual(details["near_opaque_pixels"],2)
            with self.assertRaisesRegex(ValueError,"66.67% near-opaque"):
                helper.examine(path,"cutout",.8)
            self.assertTrue(helper.examine(path,"cutout")["transparent_pixels"])
            with self.assertRaisesRegex(ValueError,"between zero and one"):
                helper.examine(path,"cutout",float("nan"))

    def test_published_composition_binds_the_original_image_and_movie(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            image,prompt,movie,composed=(root/name for name in ("asset.png","prompt.txt","movie.mp4","render.json"))
            Image.new("RGB",(2,2),"white").save(image)
            prompt.write_text("Example",encoding="utf-8")
            movie.write_bytes(b"fixture bytes; movie samples are checked separately")
            spec={"version":1,"operation":"generate","tool":"Codex ImageGen","generation_id":"fixture","purpose":"Verify",
                  "image":image.name,"sha256":helper.digest(image),"prompt":prompt.name,"prompt_sha256":helper.digest(prompt),
                  "alpha":"opaque","composition_report":composed.name}
            record=root/"origin.json"
            helper.write(record,spec)
            receipt={"ok":True,"published":True,"candidateSha256":helper.digest(movie),
                     "inputs":{str(image.resolve()):helper.digest(image)}}
            helper.write(composed,receipt)
            self.assertEqual(helper.verify(record,movie)["movie"]["composition_report_sha256"],helper.digest(composed))
            receipt["inputs"]={str(root/"other.png"):helper.digest(image)}
            helper.write(composed,receipt)
            with self.assertRaisesRegex(ValueError,"original bitmap path and digest"):
                helper.verify(record,movie)
            movie.write_bytes(b"other bytes")
            with self.assertRaisesRegex(ValueError,"certify this published movie"):
                helper.verify(record,movie)

    def test_recipe_must_really_draw_the_right_bitmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            img,txt=root/"asset.png",root/"prompt.txt"
            Image.new("RGB",(10,10),"white").save(img)
            txt.write_text("Ejemplo",encoding="utf-8")
            spec={"version":1,"operation":"generate","tool":"Codex ImageGen","generation_id":"fixture",
                  "purpose":"Inspección","image":img.name,"sha256":helper.digest(img),"prompt":txt.name,
                  "prompt_sha256":helper.digest(txt),"alpha":"opaque","asset_id":"object","recipe":"scene.json"}
            recipe={"assets":{"object":img.name},"scenes":[{"id":"s","props":{"title":"object"}}]}
            manifest=root/"origin.json";manifest.write_text(json.dumps(spec),encoding="utf-8")
            scene=root/"scene.json";scene.write_text(json.dumps(recipe),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"never drawn"):helper.verify(manifest)
            recipe["scenes"][0]["props"]["media"]="object";scene.write_text(json.dumps(recipe),encoding="utf-8")
            self.assertEqual(helper.verify(manifest)["integration"]["scenes"],["s"])


if __name__=="__main__":
    unittest.main()
