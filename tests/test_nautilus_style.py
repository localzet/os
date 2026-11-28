import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("patch_nautilus", ROOT / "scripts/patch-nautilus-style.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NautilusStyleTests(unittest.TestCase):
    def setUp(self):
        self.source = "\n".join(selector + " {}" for selector in module.REQUIRED)
        self.overlay = (ROOT / "assets/styles/nautilus-executive.css").read_text()

    def test_preserves_upstream_and_scopes_overlay(self):
        patched = module.patch(self.source, self.overlay)
        self.assertTrue(patched.startswith(self.source))
        self.assertIn("window.nautilus-window", patched)
        self.assertIn("(prefers-contrast: no-preference)", patched)
        self.assertIn("(prefers-color-scheme: dark)", patched)
        self.assertEqual(patched.count(module.MARKER), 1)

    def test_does_not_apply_twice(self):
        with self.assertRaisesRegex(ValueError, "already"):
            module.patch(module.patch(self.source, self.overlay), self.overlay)

    def test_rejects_unreviewed_source(self):
        with self.assertRaisesRegex(ValueError, "changed"):
            module.patch("", self.overlay)

    def test_rejects_unscoped_overlay(self):
        with self.assertRaisesRegex(ValueError, "reviewed"):
            module.patch(self.source, module.MARKER + " */ window {}")

    def test_uses_current_violet_ember_design_tokens(self):
        for color in ("#10091E", "#1A1028", "#28183F", "#34234F",
                      "#6436B5", "#9B72F2", "#FF7E00", "#F4EEFF", "#B9A5D5"):
            self.assertIn(color, self.overlay)
        for old_graphite in ("#202124", "#343539", "#303136"):
            self.assertNotIn(old_graphite, self.overlay)
        self.assertIn("background-color: #6436B5", self.overlay)
        self.assertIn("outline: 2px solid #FF7E00", self.overlay)

    def test_list_header_metadata_remains_accessible(self):
        self.assertIn("columnview > header", self.overlay)
        self.assertIn("columnview > header *", self.overlay)
        self.assertIn("columnview > listview > row .dim-label", self.overlay)
        self.assertIn("opacity: 1", self.overlay)
