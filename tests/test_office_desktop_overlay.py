import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("overlay", Path(__file__).resolve().parents[1] / "scripts/install-office-desktop-overlay.py")
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)


class OfficeOverlayTests(unittest.TestCase):
    def test_preserves_mime_actions_and_vendor_desktop_identity(self):
        source = "[Desktop Entry]\nName=ONLYOFFICE\nExec=desktopeditors %U\nTryExec=/usr/bin/desktopeditors\nMimeType=application/msword;\nDBusActivatable=true\n[Desktop Action New]\nName=New\nExec=/usr/bin/onlyoffice-desktopeditors --new:word\n"
        result = overlay.transform(source)
        self.assertIn("Exec=/usr/bin/localzet-office %U", result)
        self.assertIn("TryExec=/usr/bin/localzet-office", result)
        self.assertIn("MimeType=application/msword;", result)
        self.assertIn("Exec=/usr/bin/localzet-office --new:word", result)
        self.assertIn("DBusActivatable=false", result)

    def test_refuses_unreviewed_exec_and_missing_primary(self):
        for source in ("[Desktop Entry]\nExec=sh -c evil\n", "[Desktop Entry]\nName=Office\n"):
            with self.assertRaises(ValueError):
                overlay.transform(source)
