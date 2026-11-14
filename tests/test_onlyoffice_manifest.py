import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
module_spec = importlib.util.spec_from_file_location("fetch_onlyoffice", ROOT / "scripts/fetch-onlyoffice.py")
module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(module)


class OnlyOfficeTests(unittest.TestCase):
    def test_official_pins(self):
        data = json.loads((ROOT / "config/upstream/onlyoffice.json").read_text())
        url, asset = module.spec(data, "deb")
        self.assertEqual(url, "https://github.com/ONLYOFFICE/DesktopEditors/releases/download/v10.0.0/onlyoffice-desktopeditors_amd64.deb")
        self.assertEqual(len(asset["sha256"]), 64)
        data["artifacts"]["deb"]["name"] = "../../bad.deb"
        with self.assertRaises(ValueError):
            module.spec(data, "deb")

    def test_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "fixture"
            file.write_bytes(b"test")
            asset = {"size": 4, "sha256": hashlib.sha256(b"test").hexdigest()}
            module.verify(file, asset)
            file.write_bytes(b"fail")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                module.verify(file, asset)
            file.write_bytes(b"longer")
            with self.assertRaisesRegex(ValueError, "size"):
                module.verify(file, asset)
