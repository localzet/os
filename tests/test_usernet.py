import importlib.util
import json
from pathlib import Path
import unittest

from localzet.usernet import classify

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fetch_usernet", ROOT / "scripts/fetch-usernet.py")
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)


class UserNetTests(unittest.TestCase):
    def test_pin(self):
        manifest = json.loads((ROOT / "config/upstream/usernet.json").read_text())
        url, asset = fetcher.spec(manifest)
        self.assertEqual(url, "https://github.com/localzet/UserNet/releases/download/v0.5.12/UserNet-linux.deb")
        self.assertEqual(len(asset["sha256"]), 64)
        self.assertEqual(manifest["deb_version"], "0.5.12.2026110805")
        manifest["version"] = "../bad"
        with self.assertRaises(ValueError):
            fetcher.spec(manifest)

    def test_classification_does_not_leak_addresses(self):
        self.assertEqual(classify("manual", [("127.0.0.1", 7890), ("::1", 7891),
            ("LOCALHOST", 8080), ("proxy.example", 3128), ("", 1234), ("other", 0)]),
            {"mode": "manual", "local": 3, "remote": 1})
        self.assertEqual(classify("auto", [("127.0.0.1", 7890)]),
            {"mode": "auto", "local": 0, "remote": 0})
        self.assertEqual(classify("none", ()), {"mode": "none", "local": 0, "remote": 0})
        self.assertEqual(classify("invalid", ())["mode"], "unavailable")
