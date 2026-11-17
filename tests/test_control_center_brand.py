import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/patch-control-center-brand.py"
spec = importlib.util.spec_from_file_location("brand_patch", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ControlCenterBrandTests(unittest.TestCase):
    def test_both_modes_only(self):
        text = ("distributor_logo = get_option('distributor_logo')\n"
                "  dark_mode_distributor_logo = get_option('dark_mode_distributor_logo')\n"
                "preserve_other_option = true\n")
        result = module.patch(text)
        self.assertEqual(result.count(module.LOGO), 1)
        self.assertEqual(result.count(module.DARK_LOGO), 1)
        self.assertIn("preserve_other_option = true", result)
        self.assertNotIn("get_option(", result)

    def test_changed_upstream_fails(self):
        with self.assertRaises(ValueError):
            module.patch("changed source")

    def test_duplicate_fails(self):
        line = "distributor_logo = get_option('distributor_logo')\n"
        with self.assertRaises(ValueError):
            module.patch(line * 2)

    def test_about_logo_is_shrinkable(self):
        original = """          maximum-size: 192;
          tightening-threshold: 192;

          child: Picture os_logo {
            can-shrink: false;"""
        result = module.patch_about(original)
        self.assertIn("maximum-size: 144", result)
        self.assertIn("can-shrink: true", result)
        self.assertIn("height-request: 144", result)
        with self.assertRaises(ValueError):
            module.patch_about("upstream changed")


class AboutLogoTests(unittest.TestCase):
    def test_only_background_removed(self):
        root = PATH.parents[1]
        spec = importlib.util.spec_from_file_location(
            "derive_about_logo", root / "scripts/derive-about-logo.py")
        derive = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(derive)
        original = (root / "assets/brand/localzet.svg").read_bytes()
        result = derive.transparent_logo(original)
        self.assertNotIn(derive.BACKGROUND, result)
        self.assertEqual(result, original.replace(derive.BACKGROUND, b"", 1))
        for invalid in (b"", original + derive.BACKGROUND):
            with self.assertRaises(ValueError):
                derive.transparent_logo(invalid)

    def test_dark_variant_changes_only_reviewed_fills(self):
        root = PATH.parents[1]
        spec = importlib.util.spec_from_file_location(
            "derive_about_logo", root / "scripts/derive-about-logo.py")
        derive = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(derive)
        original = (root / "assets/brand/localzet.svg").read_bytes()
        light = derive.transparent_logo(original)
        dark = derive.dark_logo(original)
        self.assertEqual(dark, light.replace(
            b".fil1 {fill:black}", b".fil1 {fill:#F2EFF8}").replace(
            b".fil2 {fill:black;fill-rule:nonzero}",
            b".fil2 {fill:#F2EFF8;fill-rule:nonzero}"))
        with self.assertRaises(ValueError):
            derive.dark_logo(original.replace(b".fil1 {fill:black}", b""))
