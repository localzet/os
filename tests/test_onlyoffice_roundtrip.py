from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ci/onlyoffice-render-smoke.sh"
WORKFLOW = (ROOT / ".github/workflows/onlyoffice-render-smoke.yml").read_text(encoding="utf-8")


class OnlyOfficeRoundTripTests(unittest.TestCase):
    def test_roundtrip_is_real_and_offline(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("LOCALZET OFFICE ROUNDTRIP", source)
        self.assertIn("ctrl+s", source)
        self.assertIn('archive.read("word/document.xml")', source)
        self.assertIn("reopened-document.png", source)
        self.assertIn("tesseract", source)
        self.assertIn("sudo unshare --net", WORKFLOW)
        self.assertIn("tesseract-ocr", WORKFLOW)
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


if __name__ == "__main__":
    unittest.main()
