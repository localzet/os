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
        self.assertEqual(data['colors']['accent'], '#FF7E00')
        self.assertEqual(data['colors']['primary'], '#9B72F2')
        self.assertEqual(data['density']['panelHeight'], 32)
        self.assertEqual(data['density']['dockIcon'], 28)
        self.assertEqual(data['density']['dockHeight'], 48)
        self.assertEqual(data['colors']['surface'], '#28183F')
        css = (ROOT / 'extensions/localzet-shell@localzet.com/stylesheet.css').read_text()
        self.assertIn(data['colors']['accent'], css)
        for name in ('panel', 'surface', 'card', 'text', 'textSecondary'):
            self.assertIn(data['shellSurfaces'][name], css)
        self.assertEqual(data['shellSurfaces']['surface'], data['glass']['opaqueFallback'])
        self.assertLessEqual(data['radii']['lg'], 14)

    def test_native_aurora_professional_palette(self):
        from localzet.appearance import MIDNIGHT_CSS
        data = json.loads((ROOT / 'assets/design-tokens.json').read_text())
        for key in ('background', 'header', 'card', 'text', 'textSecondary', 'focus', 'primaryAction'):
            self.assertIn(data['nativeApplications'][key].encode(), MIDNIGHT_CSS)
        self.assertIn(data['colors']['primary'].encode(), MIDNIGHT_CSS)
        self.assertIn(data['colors']['accent'].encode(), MIDNIGHT_CSS)
        plymouth = (ROOT / 'packaging/live/aurora.plymouth').read_text().lower()
        for key in ('background', 'surface', 'accent'):
            self.assertIn('0x' + data['colors'][key][1:].lower(), plymouth)

    def test_shell_glass_default_and_opaque_override(self):
        panel = (ROOT / "extensions/localzet-shell@localzet.com/panel.js").read_text()
        self.assertIn("LOCALZET_DISABLE_GLASS", panel)
        self.assertIn("Shell.BlurEffect", panel)
        self.assertIn("this._glassEnabled = GLib.getenv('LOCALZET_DISABLE_GLASS') !== '1';", panel)
        self.assertIn("high-contrast", panel)

    def test_landscape_default_and_alternate(self):
        registry = ET.parse(ROOT / "assets/wallpapers/localzet-wallpapers.xml").getroot()
        paths = {node.findtext("filename") for node in registry.findall("wallpaper")}
        self.assertEqual(paths, {"/usr/share/backgrounds/budgie/mt_shuksan_by_ezspain.jpg",
                                 "/usr/share/backgrounds/localzet/executive-dusk.jpg",
                                 "/usr/share/backgrounds/localzet/aurora.svg"})
        for path in ("scripts/build-desktop-deb.sh", "scripts/build-live-rootfs.sh",
                     ".github/workflows/gnome-visual-smoke.yml"):
            self.assertIn("budgie-wallpapers-resolute", (ROOT / path).read_text())
        for path in ("packaging/live/customize-rootfs.sh", "scripts/ci/gnome50-visual-smoke.sh"):
            self.assertIn("/usr/share/backgrounds/budgie/mt_shuksan_by_ezspain.jpg", (ROOT / path).read_text())
            self.assertIn("/usr/share/backgrounds/budgie/mont_blanc_from_arpy_lake_by_puffettacicciottella.jpg", (ROOT / path).read_text())
        self.assertIn("CC BY-SA 4.0", (ROOT / "assets/wallpapers/ATTRIBUTION.txt").read_text())
        package_script = (ROOT / "scripts/build-desktop-deb.sh").read_text()
        for value in ("python3-pil", "DEBIAN/postinst", "DEBIAN/postrm", "executive-dusk.jpg"):
            self.assertIn(value, package_script)

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
            self.assertIn("url(#violet)", (theme / "scalable/places/folder.svg").read_text())
            for name in module.SYMBOLIC:
                icon = ET.parse(theme / "scalable/categories" / (name + ".svg")).getroot()
                self.assertEqual(icon.attrib["width"], "16")
            for name in ("drive-harddisk", "media-flash-usb"):
                self.assertIn("url(#", (theme / "scalable/devices" / (name + ".svg")).read_text())
            self.assertIn("url(#graphite)", (theme / "scalable/apps/org.gnome.Ptyxis.svg").read_text())
            self.assertTrue(any(
                "url(#ember)" in path.read_text()
                for path in files
            ))
            for upstream in ("firefox", "google-chrome", "google-chrome-stable", "microsoft-edge", "microsoft-edge-stable",
                             "steam", "com.valvesoftware.Steam", "netbird", "org.wails.netbird", "nectarlink",
                             "org.telegram.desktop", "telegram-desktop", "com.discordapp.Discord", "discord",
                             "net.lutris.Lutris", "lutris", "com.heroicgameslauncher.hgl", "heroic",
                             "onlyoffice-desktopeditors", "onlyoffice", "code", "com.visualstudio.code",
                             "yandex-music", "YandexMusic", "gimp", "org.gimp.GIMP", "vlc",
                             "qbittorrent", "org.qbittorrent.qBittorrent", "com.localzet.usernet"):
                self.assertFalse((theme / "scalable/apps" / (upstream + ".svg")).exists())
            for kind in ("camera", "calendar", "clock", "mail", "vm", "scanner", "printer",
                         "installer", "help", "optical", "desktop", "office", "torrent", "paint", "chat", "games"):
                self.assertIn(kind, module.MATERIAL)
            self.assertNotEqual(module.render("chat", "apps", "com.localzet.AIWorkspace"),
                                module.render("code", "apps", "gvim"))
            with self.assertRaises(FileExistsError):
                module.build(directory)

    def test_grub_branding(self):
        theme = (ROOT / "packaging/grub/theme.txt").read_text()
        self.assertIn('desktop-image: "background.png"', theme)
        self.assertIn('file = "logo.png"', theme)
        self.assertIn('selected_item_color = "#FF7E00"', theme)
        cfg = (ROOT / "packaging/live/grub.cfg").read_text()
        self.assertIn("if terminal_output gfxterm; then", cfg)
        self.assertEqual(cfg.count("menuentry "), 3)
        self.assertIn("diagnostics / recovery", cfg)
        self.assertIn("set default=0", cfg)
        self.assertIn("set timeout=5", cfg)
        svg = ET.parse(ROOT / "assets/brand/grub-background.svg").getroot()
        self.assertEqual(svg.attrib["viewBox"], "0 0 1024 768")
