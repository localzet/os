import importlib.util
import json
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
        self.tokens = json.loads((ROOT / "assets/design-tokens.json").read_text())["nativeFiles"]

    def test_preserves_upstream_and_scopes_overlay(self):
        patched = module.patch(self.source, self.overlay)
        self.assertTrue(patched.startswith(self.source))
        self.assertIn("window.nautilus-window", patched)
        self.assertIn("(prefers-contrast: no-preference)", patched)
        self.assertIn("(prefers-color-scheme: dark)", patched)
        self.assertEqual(patched.count(module.MARKER), 1)

    def test_overlay_uses_canonical_native_files_tokens(self):
        for key in ("background", "sidebar", "pathbar", "text", "textSecondary",
                    "selectionBase", "selectionAccent", "focus"):
            with self.subTest(token=key):
                self.assertIn(self.tokens[key].lower(), self.overlay.lower())
        self.assertIn("border-radius: 6px", self.overlay)
        self.assertIn("border-radius: 8px", self.overlay)

    def test_old_graphite_palette_is_not_present(self):
        for obsolete in ("#202124", "#292a2e", "#343539", "#2f3034",
                         "#39495e", "#45464b", "#2874c8"):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, self.overlay.lower())

    def test_does_not_apply_twice(self):
        with self.assertRaisesRegex(ValueError, "already"):
            module.patch(module.patch(self.source, self.overlay), self.overlay)

    def test_rejects_unreviewed_source(self):
        with self.assertRaisesRegex(ValueError, "changed"):
            module.patch("", self.overlay)

    def test_rejects_unscoped_overlay(self):
        with self.assertRaisesRegex(ValueError, "reviewed"):
            module.patch(self.source, module.MARKER + " */ window {}")


if __name__ == "__main__":
    unittest.main()
