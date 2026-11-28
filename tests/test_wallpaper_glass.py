import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WallpaperGlassTests(unittest.TestCase):
    def test_generator_creates_only_the_4k_wallpaper(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow unavailable in source-only checks")
        spec = importlib.util.spec_from_file_location(
            "executive_wallpaper", ROOT / "scripts/build-executive-wallpaper.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            pattern = Image.new("RGB", (1920, 1080))
            draw = ImageDraw.Draw(pattern)
            for x in range(0, 1920, 32):
                draw.rectangle((x, 0, x + 15, 1080), fill="white")
            pattern.save(source)
            output = root / "executive-dusk.jpg"
            module.render(source, output)
            with Image.open(output) as original:
                self.assertEqual(original.size, (3840, 2160))
            self.assertFalse(root.joinpath("executive-dusk-glass.jpg").exists())

    def test_runtime_uses_real_mutter_background_blur(self):
        wallpaper = (ROOT / "extensions/localzet-shell@localzet.com/wallpaper-glass.js").read_text()
        dock = (ROOT / "extensions/localzet-shell@localzet.com/dock.js").read_text()
        for source in (wallpaper, dock):
            self.assertIn("new Shell.BlurEffect", source)
            self.assertIn("Shell.BlurMode.BACKGROUND", source)
            self.assertIn("add_effect_with_name", source)
        self.assertIn("EFFECT_RADIUS = 18", wallpaper)
        self.assertIn("EFFECT_BRIGHTNESS = 0.85", wallpaper)
        self.assertIn("name: EFFECT_NAME", wallpaper)
        self.assertIn("radius: 18", dock)
        self.assertIn("brightness: 0.85", dock)
        self.assertIn("name: 'localzet-dock-background-blur'", dock)
        self.assertNotIn("background-image", wallpaper)
        self.assertNotIn("executive-dusk-glass.jpg", wallpaper)
        self.assertIn("add_effect_with_name", wallpaper)
        self.assertIn("this._menu.box ?? this._menu.actor", wallpaper)
        self.assertIn("effect.queue_repaint()", wallpaper)
        self.assertIn("effect.get_mode()", wallpaper)
        self.assertIn("add_effect_with_name", dock)
        self.assertIn("effect.queue_repaint()", dock)
        self.assertIn("effect.get_mode()", dock)

    def test_accessibility_and_performance_fallbacks_remain(self):
        source = (ROOT / "extensions/localzet-shell@localzet.com/wallpaper-glass.js").read_text()
        for required in (
            "LOCALZET_DISABLE_GLASS",
            "high-contrast",
            "Main.sessionMode.isLocked",
            "Main.sessionMode.isGreeter",
            "watch(Main.sessionMode, 'updated')",
            "Main.overview.visible",
            "monitors.length !== 1",
            "scale_factor !== 1",
            "list_windows()",
        ):
            self.assertIn(required, source)


    def test_dock_fails_closed_before_rechecking_window_state(self):
        dock = (ROOT / "extensions/localzet-shell@localzet.com/dock.js").read_text()
        self.assertIn("Main.sessionMode.connect('updated'", dock)
        self.assertIn("this._scheduleMaterialRefresh()", dock)
        self.assertIn("this._materialRefreshPending", dock)
        self.assertIn("this._clearMaterial()", dock)
        self.assertIn("global.display.connect('window-created'", dock)
        self.assertIn("Localzet Dock: overview hidden", dock)
        self.assertIn("Localzet Launcher: button=", dock)

    def test_visual_smoke_uses_measured_launcher_button(self):
        smoke = (ROOT / "scripts/ci/gnome50-visual-smoke.sh").read_text()
        self.assertIn("Escape Escape", smoke)
        self.assertIn("Localzet Launcher: button=", smoke)
        self.assertIn("button_w / 2", smoke)
        self.assertIn("button_h / 2", smoke)


if __name__ == "__main__":
    unittest.main()
