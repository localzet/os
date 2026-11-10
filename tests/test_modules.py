import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from localzet.modules import ManifestError, load_catalog, resolve
from localzet.cli import main

MODULES = Path(__file__).resolve().parents[1] / "config" / "modules"


class ModuleTests(unittest.TestCase):
    def test_all_manifests_load(self):
        catalog = load_catalog(MODULES)
        self.assertEqual(len(catalog), 6)
        self.assertEqual(catalog["usernet"].status, "planned")

    def test_dependency_order(self):
        catalog = load_catalog(MODULES)
        self.assertEqual([m.id for m in resolve(catalog, ("netbird", "containers", "netbird"))],
                         ["usernet", "netbird", "containers"])

    def test_unknown_dependency(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "example.toml"
            path.write_text('id="example"\ntitle="E"\ndescription="D"\nstatus="planned"\npackages=[]\ndepends_on=["missing"]\n')
            with self.assertRaisesRegex(ManifestError, "unknown"):
                load_catalog(Path(root))

    def test_cycle_detected(self):
        with tempfile.TemporaryDirectory() as root:
            for src, dst in (("one", "two"), ("two", "one")):
                (Path(root) / f"{src}.toml").write_text(
                    f'id="{src}"\ntitle="{src}"\ndescription="test"\nstatus="planned"\npackages=[]\ndepends_on=["{dst}"]\n'
                )
            with self.assertRaisesRegex(ManifestError, "cycle"):
                load_catalog(Path(root))

    def test_rejects_package_command_injection(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "example.toml").write_text(
                'id="example"\ntitle="E"\ndescription="D"\nstatus="planned"\npackages=["git;rm -rf /"]\ndepends_on=[]\n'
            )
            with self.assertRaisesRegex(ManifestError, "packages"):
                load_catalog(Path(root))

    def test_rejects_non_string_status(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "example.toml").write_text(
                'id="example"\ntitle="E"\ndescription="D"\nstatus=["planned"]\npackages=[]\ndepends_on=[]\n'
            )
            with self.assertRaisesRegex(ManifestError, "status"):
                load_catalog(Path(root))

    def test_cli_validate(self):
        self.assertEqual(main(["--manifest-dir", str(MODULES), "validate"]), 0)


if __name__ == "__main__":
    unittest.main()
