"""Protect evidence against misleading crops, scale changes, and overwritten sources."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from build_review_evidence import REPO, build


class EvidenceContractTests(unittest.TestCase):
    def setUp(self):
        # Temporary work stays under the explicitly writable repository.
        self.temp = tempfile.TemporaryDirectory(prefix="critic-test-", dir=REPO)
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(REPO))
        self.addCleanup(self.temp.cleanup)
        self.source = self.root / "source.png"
        art = Image.new("RGBA", (400, 200))
        ImageDraw.Draw(art).rectangle((100, 80, 300, 100), fill="#ffffff")
        art.save(self.source)
        self.payload = {"widths": [300], "items": [{
            "id": "sample", "group": "sample", "kind": "artwork", "image": "source.png",
            "provenance": "Synthetic test fixture", "regions": [{"label": "Small line", "box": [100, 80, 300, 100]}]
        }]}

    def run_build(self, payload=None, report=None):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(payload or self.payload), encoding="utf-8")
        return build(manifest, self.root / "boards", report or self.root / "report.json")

    def test_sparse_art_preserves_full_frame_and_source(self):
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        report = self.run_build()
        item = report["items"][0]
        self.assertEqual(item["view_box"], [0, 0, 400, 200])
        self.assertEqual(item["views"][0]["height_px"], 150)
        self.assertEqual(item["views"][0]["regions"][0]["projected_box_height_px"], 15)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), digest)
        with Image.open(self.root / "boards/sample.png") as im:
            self.assertGreaterEqual(im.width, 300)

    def test_product_frame_changes_scale_without_changing_art(self):
        # Same physical pixel height of text, twice as wide an image: half the projected height.
        product = Image.new("RGBA", (800, 400), "#121415")
        with Image.open(self.source) as art:
            product.alpha_composite(art, (200, 100))
        product.save(self.root / "product.png")
        payload = copy.deepcopy(self.payload)
        payload["items"].append({"id": "product", "group": "sample", "kind": "schematic_product",
            "image": "product.png", "provenance": "Synthetic garment frame", "regions": [
                {"label": "Small line", "box": [300, 180, 500, 200]}]})
        rows = self.run_build(payload)["items"]
        self.assertEqual(rows[0]["views"][0]["regions"][0]["projected_box_height_px"], 15)
        self.assertEqual(rows[1]["views"][0]["regions"][0]["projected_box_height_px"], 7.5)

    def test_critical_region_cannot_be_silently_cropped(self):
        payload = copy.deepcopy(self.payload)
        payload["items"][0].update(crop=[0, 0, 200, 200], crop_note="Declared crop")
        with self.assertRaisesRegex(ValueError, "outside view"):
            self.run_build(payload)
        self.assertFalse((self.root / "boards").exists())

    def test_unexplained_crop_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["items"][0]["crop"] = [0, 0, 400, 200]
        with self.assertRaisesRegex(ValueError, "crop_note"):
            self.run_build(payload)

    def test_blank_source_is_rejected(self):
        Image.new("RGBA", (400, 200)).save(self.source)
        with self.assertRaisesRegex(ValueError, "completely transparent"):
            self.run_build()

    def test_report_cannot_overwrite_source(self):
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "overwrite source"):
            self.run_build(report=self.source)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), digest)

    def test_output_cannot_escape_repository(self):
        with self.assertRaisesRegex(ValueError, "inside repository"):
            self.run_build(report=REPO.parent / "critic-forbidden-output.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
