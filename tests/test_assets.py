import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class AssetsTests(unittest.TestCase):
    def test_gnome_metadata(self):
        folder = ROOT / 'extensions' / 'localzet-shell@localzet.com'
        metadata = json.loads((folder / 'metadata.json').read_text())
        self.assertEqual(metadata['uuid'], folder.name)
        self.assertIn('50', metadata['shell-version'])
        self.assertTrue((folder / 'extension.js').is_file())

    def test_design_tokens(self):
        data = json.loads((ROOT / 'assets/design-tokens.json').read_text())
        self.assertEqual(data['colors']['accent'], '#FF7E00')
        self.assertEqual(data['colors']['primary'], '#9B72F2')
        self.assertEqual(data['density']['panelHeight'], 32)
        self.assertLessEqual(data['radii']['lg'], 14)

    def test_wallpaper_is_svg(self):
        root = ET.parse(ROOT / 'assets/wallpapers/aurora.svg').getroot()
        self.assertEqual(root.tag, '{http://www.w3.org/2000/svg}svg')
        self.assertEqual(root.attrib['viewBox'], '0 0 1920 1080')
        self.assertEqual(root.attrib['width'], '3840')
        self.assertEqual(root.attrib['height'], '2160')

    def test_grub_branding(self):
        theme = (ROOT / "packaging/grub/theme.txt").read_text()
        self.assertIn('desktop-image: "background.png"', theme)
        self.assertIn('file = "logo.png"', theme)
        self.assertIn('selected_item_color = "#ffb46b"', theme)
        cfg = (ROOT / "packaging/live/grub.cfg").read_text()
        self.assertIn("if terminal_output gfxterm; then", cfg)
        self.assertEqual(cfg.count("menuentry "), 3)
        self.assertIn("diagnostics / recovery", cfg)
        self.assertIn("set default=0", cfg)
        self.assertIn("set timeout=5", cfg)
        svg = ET.parse(ROOT / "assets/brand/grub-background.svg").getroot()
        self.assertEqual(svg.attrib["viewBox"], "0 0 1024 768")
