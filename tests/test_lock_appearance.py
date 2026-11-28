import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "extensions/localzet-lock@localzet.com"

class LockAppearanceTests(unittest.TestCase):
    def test_scope(self):
        metadata = json.loads((LOCK / "metadata.json").read_text())
        self.assertEqual(metadata["session-modes"], ["user", "unlock-dialog"])
        desktop = json.loads((ROOT / "extensions/localzet-shell@localzet.com/metadata.json").read_text())
        self.assertNotIn("unlock-dialog", desktop.get("session-modes", []))
        css = (LOCK / "lock-material.css").read_text()
        for selector in (".unlock-dialog-clock-time", ".unlock-dialog-clock-date", ".unlock-dialog-notifications-container"):
            self.assertIn(selector, css)
        for forbidden in ("prompt-entry", "login-dialog", "parental-controls"):
            self.assertNotIn(forbidden, css)
        source = (LOCK / "extension.js").read_text()
        self.assertIn("high-contrast", source)
        self.assertIn("unload_stylesheet", source)
        self.assertNotIn("screenShield", source)
    def test_desktop_lock_and_gdm_share_the_installed_wallpaper(self):
        rootfs = (ROOT / "packaging/live/customize-rootfs.sh").read_text()
        wallpaper = "file:///usr/share/backgrounds/localzet/executive-dusk.jpg"
        self.assertNotIn("[org/gnome/desktop/screensaver]", rootfs)
        self.assertIn("[org/gnome/desktop/background]", rootfs)
        self.assertEqual(rootfs.count(f"picture-uri='{wallpaper}'"), 2)
        self.assertEqual(rootfs.count(f"picture-uri-dark='{wallpaper}'"), 2)
        self.assertIn("DCONF_PROFILE=user GSETTINGS_BACKEND=dconf gsettings get org.gnome.desktop.background picture-uri-dark", rootfs)
        self.assertIn("DCONF_PROFILE=gdm GSETTINGS_BACKEND=dconf gsettings get org.gnome.desktop.background picture-uri-dark", rootfs)
        branding = (ROOT / "docs/design/NATIVE-BRANDING.md").read_text()
        self.assertIn("GNOME Shell 50's unlock dialog", branding)
        self.assertIn("org.gnome.desktop.background", branding)
        self.assertNotIn("lock screen reads `org.gnome.desktop.screensaver picture-uri`", branding)

    def test_packaged_and_enabled(self):
        for path in ("scripts/build-desktop-deb.sh", "packaging/live/customize-rootfs.sh"):
            self.assertIn("localzet-lock@localzet.com", (ROOT / path).read_text())
