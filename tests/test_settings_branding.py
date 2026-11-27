from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ComponentsBrandingTests(unittest.TestCase):
    def test_visible_identity_matches_product_and_launcher(self):
        source = (ROOT / "src/localzet/settings/app.py").read_text(encoding="utf-8")
        desktop = (ROOT / "packaging/com.localzet.Settings.desktop").read_text(encoding="utf-8")
        self.assertIn('title="Компоненты Localzet"', source)
        self.assertIn('Adw.WindowTitle(title="Компоненты Localzet"', source)
        self.assertIn('Gtk.Label(label="Aurora Professional"', source)
        self.assertIn("Name[ru]=Компоненты Localzet", desktop)
        self.assertNotIn("Aurora · Executive", source)

    def test_styles_are_scoped_to_localzet_components(self):
        source = (ROOT / "src/localzet/settings/app.py").read_text(encoding="utf-8")
        css = (ROOT / "apps/localzet-settings/settings.css").read_text(encoding="utf-8")
        for name in ("localzet-settings-sidebar", "localzet-settings-nav", "localzet-settings-page-heading"):
            self.assertIn(name, source)
            self.assertIn(name, css)
        self.assertNotIn("executive-sidebar", source + css)
        self.assertNotIn("executive-nav", source + css)
        self.assertNotIn("executive-page-heading", source + css)

    def test_smoke_checks_the_visible_components_window(self):
        smoke = (ROOT / "scripts/ci/settings-gtk-smoke.sh").read_text(encoding="utf-8")
        self.assertIn('--name "Компоненты Localzet"', smoke)
        self.assertIn("Localzet Components: page=", smoke)


if __name__ == "__main__":
    unittest.main()
