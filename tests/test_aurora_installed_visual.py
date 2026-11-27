import importlib.util
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "aurora_installed_visual", ROOT / "scripts/ci/aurora-installed-visual.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AuroraInstalledVisualTests(unittest.TestCase):
    def setUp(self):
        self.tokens = __import__("json").loads((ROOT / "assets/design-tokens.json").read_text())

    def desktop_fixture(self):
        image = Image.new("RGB", (1280, 800), "#10091E")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1279, 39), fill="#28183F")
        draw.rectangle((440, 728, 840, 795), fill="#28183F")
        # A deterministic detailed wallpaper field, not a reference image.
        for y in range(48, 720, 16):
            for x in range(0, 1280, 16):
                value = (x * 7 + y * 11) % 80
                draw.rectangle((x, y, x + 15, y + 15),
                               fill=(35 + value, 20 + value // 2, 70 + value))
        return image

    def test_installed_desktop_palette_and_density_gate(self):
        result = module.analyze_desktop(self.desktop_fixture(), self.tokens)
        self.assertGreater(result["panel_purple_ratio"], 0.65)
        self.assertGreater(result["dock_purple_ratio"], 0.04)
        self.assertGreater(result["wallpaper_textured_tiles"], 100)

    def test_blank_lock_screen_is_rejected(self):
        with self.assertRaises(AssertionError):
            module.analyze_lock(Image.new("RGB", (1280, 800), "#10091E"))

    def test_realistic_lock_screen_texture_is_accepted(self):
        image = self.desktop_fixture()
        result = module.analyze_lock(image)
        self.assertGreater(result["textured_tiles"], 64)


if __name__ == "__main__":
    unittest.main()
