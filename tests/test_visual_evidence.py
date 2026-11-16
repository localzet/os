import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("visual_evidence", ROOT / "scripts/visual-evidence.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class VisualEvidenceTests(unittest.TestCase):
    def test_blank_and_content(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow unavailable on source-only runner")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.ppm"
            for color in ("white", "black"):
                image = Image.new("RGB", (640, 400), color)
                ImageDraw.Draw(image).text((260, 200), "Display output is not active.", fill="gray")
                image.save(path)
                self.assertFalse(module.meaningful(module.visual_metrics(path)))
            # Simulated detailed UI across multiple areas; no actual UI claim.
            image = Image.new("RGB", (640, 400), "white")
            draw = ImageDraw.Draw(image)
            for y in range(20, 400, 40):
                for x in range(20, 640, 80):
                    draw.rectangle((x, y, x+35, y+18), fill=(x%255, y%255, (x+y)%255))
            image.save(path)
            self.assertTrue(module.meaningful(module.visual_metrics(path)))
            with self.assertRaises(ValueError):
                module.visual_metrics(path, (800, 800, 400, 300))
