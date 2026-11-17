import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class WallpaperGlassTests(unittest.TestCase):
    def test_generator_creates_real_blurred_derivative(self):
        try:
            from PIL import Image, ImageChops, ImageStat
        except ImportError:
            self.skipTest("Pillow unavailable in source-only checks")
        spec = importlib.util.spec_from_file_location("executive_wallpaper", ROOT / "scripts/build-executive-wallpaper.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            pattern = Image.new("RGB", (1920, 1080))
            from PIL import ImageDraw
            draw = ImageDraw.Draw(pattern)
            for x in range(0, 1920, 32):
                draw.rectangle((x, 0, x+15, 1080), fill="white")
            pattern.save(source)
            output = root / "executive-dusk.jpg"
            module.render(source, output)
            with Image.open(output) as original, Image.open(root / "executive-dusk-glass.jpg") as blurred:
                self.assertEqual(original.size, (3840, 2160))
                self.assertEqual(blurred.size, original.size)
                def edge(im):
                    gray = im.convert("L")
                    return ImageStat.Stat(ImageChops.difference(gray.crop((0,0,3800,2160)), gray.crop((4,0,3804,2160)))).mean[0]
                self.assertLess(edge(blurred), edge(original) * .2)
