from configparser import ConfigParser
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "theme/icons/Localzet"
NAMESPACE = "{http://www.w3.org/2000/svg}"
EXPECTED_CONTEXTS = {
    "scalable/actions": "Actions",
    "scalable/apps": "Applications",
    "scalable/categories": "Categories",
    "scalable/devices": "Devices",
    "scalable/emblems": "Emblems",
    "scalable/mimetypes": "MimeTypes",
    "scalable/places": "Places",
    "scalable/status": "Status",
}


class IconThemeTests(unittest.TestCase):
    def test_index_declares_scalable_fallback_contexts(self):
        config = ConfigParser()
        config.read(THEME / "index.theme", encoding="utf-8")
        declared = set(config["Icon Theme"]["Directories"].split(","))
        self.assertEqual(declared, set(EXPECTED_CONTEXTS))
        self.assertEqual(config["Icon Theme"]["Inherits"], "Adwaita,hicolor")
        for directory, context in EXPECTED_CONTEXTS.items():
            with self.subTest(directory=directory):
                section = config[directory]
                self.assertEqual(section["Type"], "Scalable")
                self.assertEqual(section["Context"], context)
                self.assertEqual(section["MinSize"], "16")
                self.assertEqual(section["MaxSize"], "256")
                self.assertTrue((THEME / directory).is_dir())

    def test_svg_artwork_is_nonempty_and_local(self):
        files = sorted(THEME.rglob("*.svg"))
        self.assertGreaterEqual(len(files), 100)
        for path in files:
            with self.subTest(icon=path.relative_to(THEME)):
                root = ET.parse(path).getroot()
                self.assertEqual(root.tag, f"{NAMESPACE}svg")
                self.assertTrue(root.attrib.get("viewBox"))
                drawable = {"path", "rect", "circle", "ellipse", "polygon", "polyline", "line"}
                self.assertTrue(any(element.tag.removeprefix(NAMESPACE) in drawable for element in root.iter()))
                self.assertFalse(any(element.tag.removeprefix(NAMESPACE) in {"script", "foreignObject", "image"}
                                     for element in root.iter()))

    def test_generated_icons_are_valid_svg(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "Localzet"
            subprocess.run(
                ["python3", str(ROOT / "scripts/generate-icon-theme.py"), "--theme-root", str(destination)],
                check=True,
                capture_output=True,
                text=True,
            )
            generated = sorted(destination.rglob("*.svg"))
            self.assertEqual(len(generated), 109)
            for path in generated:
                with self.subTest(icon=path.name):
                    ET.parse(path)

    def test_shell_brand_mark_matches_approved_asset_source(self):
        asset = ROOT / "assets/icons/aurora/localzet-symbol.svg"
        installed = THEME / "scalable/apps/localzet-symbol.svg"
        self.assertEqual(asset.read_bytes(), installed.read_bytes())

    def test_shell_wordmark_matches_approved_atom_geometry(self):
        asset = ROOT / "assets/icons/aurora/localzet-brand.svg"
        installed = THEME / "scalable/apps/localzet-brand.svg"
        self.assertEqual(asset.read_bytes(), installed.read_bytes())
        shell_asset = ROOT / "extensions/localzet-shell@localzet.com/localzet-brand.svg"
        self.assertEqual(asset.read_bytes(), shell_asset.read_bytes())
        extension = (ROOT / "extensions/localzet-shell@localzet.com/extension.js").read_text()
        self.assertIn("new Gio.FileIcon", extension)
        self.assertIn("this.dir.get_child('localzet-brand.svg')", extension)
        svg = ET.parse(asset).getroot()
        self.assertEqual(len(svg.findall(f"{NAMESPACE}ellipse")), 0)
        self.assertEqual(len(svg.findall(f"{NAMESPACE}g/{NAMESPACE}ellipse")), 3)

    def test_own_desktop_entries_have_packaged_icon_and_metainfo(self):
        applications = ROOT / "packaging"
        icon_names = {
            path.stem
            for path in (THEME / "scalable/apps").glob("*.svg")
        }
        for app in ("Settings", "Connect", "WindowsRuntime"):
            desktop = ConfigParser(interpolation=None)
            desktop.read(applications / f"com.localzet.{app}.desktop", encoding="utf-8")
            icon = desktop["Desktop Entry"]["Icon"]
            with self.subTest(app=app):
                self.assertIn(icon, icon_names)
                metainfo = applications / f"com.localzet.{app}.metainfo.xml"
                self.assertEqual(ET.parse(metainfo).getroot().findtext("id"), f"com.localzet.{app}")

    def test_package_builder_installs_and_refreshes_theme(self):
        builder = (ROOT / "scripts/build-desktop-deb.sh").read_text(encoding="utf-8")
        self.assertIn('"$pkg/usr/share/icons/"', builder)
        self.assertIn('"$pkg/usr/share/icons/hicolor/scalable/apps"', builder)
        self.assertIn("for icon in localzet-settings localzet-connect localzet-windows; do", builder)
        self.assertIn("/scalable/apps/$icon.svg", builder)
        self.assertIn("gtk-update-icon-cache, libglib2.0-bin", builder)
        self.assertIn('gtk-update-icon-cache --force --quiet /usr/share/icons/Localzet', builder)
        self.assertIn('gtk-update-icon-cache --force --quiet /usr/share/icons/hicolor', builder)
        self.assertIn("rm -f /usr/share/icons/Localzet/icon-theme.cache", builder)

    def test_svg_renders_at_required_sizes_when_gdk_pixbuf_is_available(self):
        try:
            import gi
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf
        except (ImportError, ValueError):
            self.skipTest("python3-gi with GdkPixbuf is not installed")

        icons = sorted((THEME / "scalable").rglob("*.svg"))
        self.assertEqual(len(icons), 122)
        with tempfile.TemporaryDirectory() as directory:
            for icon in icons:
                for size in (16, 20, 24, 32, 48, 64, 128, 256):
                    with self.subTest(icon=icon.name, size=size):
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                            str(icon), size, size, False,
                        )
                        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (size, size))
                        pixels = pixbuf.get_pixels()
                        if pixbuf.get_has_alpha():
                            self.assertTrue(any(pixels[3::pixbuf.get_n_channels()]))
                        else:
                            self.assertTrue(any(pixels))
                        if icon.name == "localzet-settings.svg" and size == 32:
                            output = Path(directory) / f"{icon.stem}-{size}.png"
                            self.assertTrue(pixbuf.savev(str(output), "png", []))
                            self.assertGreater(output.stat().st_size, 64)


if __name__ == "__main__":
    unittest.main()
