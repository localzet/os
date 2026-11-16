import json
import importlib.util
import tempfile
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
        self.assertEqual(data['colors']['accent'], '#4c9aff')
        self.assertEqual(data['colors']['primary'], '#2874c8')
        self.assertEqual(data['density']['panelHeight'], 30)
        self.assertEqual(data['colors']['surface'], '#101b2d')
        self.assertEqual(data['glass']['opaqueFallback'], data['colors']['surface'])
        css = (ROOT / 'extensions/localzet-shell@localzet.com/stylesheet.css').read_text()
        for name in ('accent', 'surface', 'background', 'textPrimary'):
            self.assertIn(data['colors'][name], css)
        self.assertLessEqual(data['radii']['lg'], 14)

    def test_native_midnight_palette(self):
        from localzet.appearance import MIDNIGHT_CSS
        data = json.loads((ROOT / 'assets/design-tokens.json').read_text())
        for key in ('background', 'surface', 'surfaceElevated', 'primary', 'textPrimary'):
            self.assertIn(data['colors'][key].encode(), MIDNIGHT_CSS)
        plymouth = (ROOT / 'packaging/live/aurora.plymouth').read_text()
        for key in ('background', 'surface', 'accent'):
            self.assertIn('0x' + data['colors'][key][1:], plymouth)

    def test_wallpaper_is_svg(self):
        root = ET.parse(ROOT / 'assets/wallpapers/aurora.svg').getroot()
        self.assertEqual(root.tag, '{http://www.w3.org/2000/svg}svg')
        self.assertEqual(root.attrib['viewBox'], '0 0 1920 1080')
        self.assertEqual(root.attrib['width'], '3840')
        self.assertEqual(root.attrib['height'], '2160')

    def test_original_dock_glyphs(self):
        folder = ROOT / "extensions/localzet-shell@localzet.com/icons"
        expected = {"launcher.svg", "browser.svg", "files.svg", "terminal.svg", "settings.svg"}
        self.assertEqual({path.name for path in folder.glob("*.svg")}, expected)
        for path in folder.glob("*.svg"):
            root = ET.parse(path).getroot()
            self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
            self.assertEqual(root.attrib["viewBox"], "0 0 64 64")
            self.assertTrue(all("href" not in key for node in root.iter() for key in node.attrib))

    def test_aurora_system_icon_theme(self):
        spec = importlib.util.spec_from_file_location("aurora_icons", ROOT / "scripts/build-aurora-icons.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            theme = module.build(directory)
            index = (theme / "index.theme").read_text()
            self.assertIn("Inherits=Adwaita,hicolor", index)
            self.assertNotIn("Papirus", index)
            files = list(theme.glob("scalable/*/*.svg"))
            self.assertGreaterEqual(len(files), 100)
            self.assertGreaterEqual(len(module.GLYPHS), 40)
            self.assertEqual(len({path.stem for path in files}), len(files))
            for path in files:
                root = ET.parse(path).getroot()
                self.assertEqual(root.attrib["viewBox"], "0 0 64 64")
                self.assertTrue(all("href" not in key for node in root.iter() for key in node.attrib))
            for name in ("Settings", "Hardware", "WindowsRuntime", "Containers", "Connect", "Installer", "Network"):
                icon = "com.localzet." + name
                self.assertTrue((theme / "scalable/apps" / (icon + ".svg")).is_file())
            self.assertIn("url(#blue)", (theme / "scalable/places/folder.svg").read_text())
            for name in module.SYMBOLIC:
                icon = ET.parse(theme / "scalable/categories" / (name + ".svg")).getroot()
                self.assertEqual(icon.attrib["width"], "16")
            for name in ("drive-harddisk", "media-flash-usb"):
                self.assertIn("url(#", (theme / "scalable/devices" / (name + ".svg")).read_text())
            self.assertIn("url(#graphite)", (theme / "scalable/apps/org.gnome.Ptyxis.svg").read_text())
            for upstream in ("firefox", "google-chrome", "microsoft-edge", "steam", "netbird", "nectarlink"):
                self.assertFalse((theme / "scalable/apps" / (upstream + ".svg")).exists())
            with self.assertRaises(FileExistsError):
                module.build(directory)

    def test_grub_branding(self):
        theme = (ROOT / "packaging/grub/theme.txt").read_text()
        self.assertIn('desktop-image: "background.png"', theme)
        self.assertIn('file = "logo.png"', theme)
        self.assertIn('selected_item_color = "#78b8ff"', theme)
        cfg = (ROOT / "packaging/live/grub.cfg").read_text()
        self.assertIn("if terminal_output gfxterm; then", cfg)
        self.assertEqual(cfg.count("menuentry "), 3)
        self.assertIn("diagnostics / recovery", cfg)
        self.assertIn("set default=0", cfg)
        self.assertIn("set timeout=5", cfg)
        svg = ET.parse(ROOT / "assets/brand/grub-background.svg").getroot()
        self.assertEqual(svg.attrib["viewBox"], "0 0 1024 768")
