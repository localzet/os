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

    def test_document_ink_ignores_chrome(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow unavailable on source-only runner")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.png"
            image = Image.new("RGB", (640, 400), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((10, 0, 630, 80), fill="#205ea8")
            image.save(path)
            self.assertEqual(module.document_ink(path), 0)
            draw.rectangle((160, 160, 340, 180), fill="#205ea8")
            image.save(path)
            self.assertGreater(module.document_ink(path), 250)


    def test_wallpaper_similarity_survives_lock_blur_and_dim(self):
        try:
            from PIL import Image, ImageDraw, ImageFilter
        except ImportError:
            self.skipTest("Pillow unavailable on source-only runner")
        with tempfile.TemporaryDirectory() as directory:
            desktop = Path(directory) / "desktop.png"
            lock = Path(directory) / "lock.png"
            wrong = Path(directory) / "wrong.png"
            image = Image.new("RGB", (1280, 800), "#25334f")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 390, 1280, 800), fill="#263e36")
            draw.polygon([(0, 500), (240, 260), (420, 470), (700, 180), (950, 470), (1280, 240), (1280, 800), (0, 800)], fill="#647184")
            draw.polygon([(240, 260), (320, 340), (420, 470), (310, 390)], fill="#d2d7dc")
            draw.polygon([(700, 180), (790, 290), (950, 470), (820, 390)], fill="#d8dce2")
            draw.rectangle((60, 80, 180, 170), fill="#8d7ba8")
            image.save(desktop)
            blurred = image.filter(ImageFilter.GaussianBlur(radius=18)).point(lambda value: int(value * 0.48))
            ImageDraw.Draw(blurred).text((520, 340), "23:27", fill="#e8e4f0", stroke_width=2)
            blurred.save(lock)
            gradient = Image.new("RGB", (1280, 800))
            pixels = gradient.load()
            for y in range(800):
                value = int(20 + 40 * y / 800)
                for x in range(1280):
                    pixels[x, y] = (value, value + 4, value + 18)
            gradient.save(wrong)
            self.assertGreater(module.wallpaper_similarity(desktop, lock), 0.55)
            self.assertLess(module.wallpaper_similarity(desktop, wrong), 0.55)
