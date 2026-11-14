from pathlib import Path
import sys
import unittest
from copy import deepcopy
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from localzet.profiles import load_manifest, plan


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.data = load_manifest(ROOT / "config/profiles.json")

    def test_complete_contains_all_approved_directions(self):
        result = plan(self.data, "complete", browser="edge")
        selected = {app["id"] for app in result["applications"]}
        self.assertTrue({"office", "telegram", "windows", "gaming", "containers",
                         "netbird", "usernet", "phone", "music", "edge"} <= selected)
        self.assertNotIn("chrome", selected)
        self.assertNotIn("libreoffice", " ".join(result["ubuntu_package_candidates"]))
        self.assertNotIn("onlyoffice-desktopeditors", result["ubuntu_package_candidates"])
        self.assertIn("office", result["external_or_localzet_pending"])
        self.assertFalse(result["install_ready"])
        self.assertFalse(result["write_operations_available"])

    def test_minimal_and_standard(self):
        minimal = plan(self.data, "minimal")
        standard = plan(self.data, "standard")
        self.assertFalse(minimal["browser_choice_pending"])
        self.assertTrue(standard["browser_choice_pending"])
        self.assertIn("telegram-desktop", standard["ubuntu_package_candidates"])
        self.assertNotIn("telegram-desktop", minimal["ubuntu_package_candidates"])

    def test_optional_and_exclusive_browser(self):
        result = plan(self.data, "complete", browser="chrome", extras=["discord"])
        self.assertIn("discord", result["external_or_localzet_pending"])
        for extras in (["edge"], ["discord", "discord"], ["office"], ["unknown"]):
            with self.assertRaises(ValueError):
                plan(self.data, "complete", browser="chrome", extras=extras)

    def test_untrusted_package_rejected(self):
        changed = deepcopy(self.data)
        changed["applications"]["desktop"]["packages"] = ["git;rm"]
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "manifest.json"
            p.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                load_manifest(p)
