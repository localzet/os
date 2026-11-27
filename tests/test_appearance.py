import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localzet.appearance import MIDNIGHT_CSS


class AuroraAppearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens = json.loads((ROOT / "assets/design-tokens.json").read_text())
        cls.appearance = (ROOT / "src/localzet/appearance.py").read_text()
        cls.containers = (ROOT / "src/localzet/containers_app.py").read_text()

    def test_shared_provider_matches_canonical_application_tokens(self):
        colors = self.tokens["nativeApplications"]
        for key in ("background", "header", "sidebar", "card", "text",
                    "textSecondary", "selection", "focus", "primaryAction"):
            with self.subTest(token=key):
                self.assertIn(colors[key].lower().encode(), MIDNIGHT_CSS.lower())

    def test_light_and_high_contrast_are_explicit_system_preferences(self):
        self.assertIn('get_string("color-scheme")', self.appearance)
        self.assertIn('preference == "prefer-light"', self.appearance)
        self.assertIn("Adw.ColorScheme.PREFER_LIGHT", self.appearance)
        self.assertIn('get_boolean("high-contrast")', self.appearance)
        self.assertIn("window.remove_css_class", self.appearance)

    def test_containers_uses_only_violet_ember_dark_surfaces(self):
        colors = self.tokens["nativeApplications"]
        for key in ("background", "sidebar", "card", "text", "textSecondary",
                    "selection", "focus", "primaryAction"):
            with self.subTest(token=key):
                self.assertIn(colors[key].lower(), self.containers.lower())
        for obsolete in ("#202124", "#292a2e", "#343539", "#2f3034",
                         "#39495e", "#45464b", "#2874c8"):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, self.containers.lower())
        self.assertIn(".aurora-containers.localzet-midnight", self.containers)
        self.assertNotIn("aurora-dark", self.containers)


if __name__ == "__main__":
    unittest.main()
