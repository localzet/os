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
    def test_packaged_and_enabled(self):
        for path in ("scripts/build-desktop-deb.sh", "packaging/live/customize-rootfs.sh"):
            self.assertIn("localzet-lock@localzet.com", (ROOT / path).read_text())
