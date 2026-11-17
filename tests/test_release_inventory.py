import hashlib
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "release_inventory", ROOT / "scripts/collect-release-inventory.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryParsingTests(unittest.TestCase):
    def test_bad_records_fail_closed(self):
        for record in ("", "a\tb", "foo\tfoo\t1\tall\tfoo\t1\trc ",
                       "../foo\tfoo\t1\tall\tfoo\t1\tii ",
                       "foo\tfoo\t1\tall\tfoo\t1\tii \n" * 2):
            with self.subTest(record=record), self.assertRaises(ValueError):
                module.parse_packages(record)


@unittest.skipUnless(shutil.which("dpkg-query"), "requires dpkg-query")
class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.root = self.directory / "rootfs"
        admin = self.root / "var/lib/dpkg"
        admin.mkdir(parents=True)
        (admin / "status").write_text(
            "Package: fixture-one\nStatus: install ok installed\n"
            "Architecture: all\nVersion: 1.2-3+localzet1\n"
            "Source: upstream-fixture (1.2-3)\n"
            "Maintainer: Fixture <fixture@example.invalid>\n"
            "Description: First fixture\n\n"
            "Package: fixture-two\nStatus: install ok installed\n"
            "Architecture: amd64\nVersion: 2.0-1\n"
            "Maintainer: Fixture <fixture@example.invalid>\n"
            "Description: Second fixture\n\n")
        self.manifest = self.directory / "filesystem.manifest"
        self.manifest.write_text("fixture-one 1.2-3+localzet1\nfixture-two 2.0-1\n")
        self.docs = self.root / "usr/share/doc"
        self.docs.mkdir(parents=True)
        (self.docs / "fixture-one").mkdir()
        self.copyright = self.docs / "fixture-one/copyright"
        self.copyright.write_bytes(b"synthetic notice")

    def test_real_dpkg_inventory_and_source_metadata(self):
        result = module.collect(self.root, self.manifest)
        self.assertEqual(result["package_count"], 2)
        self.assertFalse(result["redistribution_approved"])
        self.assertEqual(result["copyright_review_required"], ["fixture-two"])
        first, second = result["packages"]
        self.assertEqual(first["source_package"], "upstream-fixture")
        self.assertEqual(first["source_version"], "1.2-3")
        self.assertEqual(first["copyright"]["sha256"],
                         hashlib.sha256(b"synthetic notice").hexdigest())
        self.assertEqual(second["source_package"], "fixture-two")
        self.assertEqual(second["source_version"], "2.0-1")

    def test_relative_notice_link_and_escaping_link(self):
        (self.docs / "fixture-two").symlink_to("fixture-one")
        result = module.collect(self.root, self.manifest)
        self.assertEqual(result["copyright_review_required"], [])
        self.assertFalse(result["redistribution_approved"])
        (self.docs / "fixture-two").unlink()
        outside = self.directory / "outside"
        outside.mkdir()
        (outside / "copyright").write_text("not part of the rootfs")
        (self.docs / "fixture-two").symlink_to(outside)
        result = module.collect(self.root, self.manifest)
        self.assertEqual(result["packages"][1]["copyright"]["status"], "escaping-link")
        self.assertNotIn("sha256", result["packages"][1]["copyright"])

    def test_missing_or_wrong_iso_manifest(self):
        self.manifest.write_text("fixture-one 1.2-3+localzet1\n")
        with self.assertRaisesRegex(ValueError, "differs"):
            module.collect(self.root, self.manifest)
        self.manifest.write_text("fixture-one 1.2-3+localzet1\nfixture-two 2.0-2\n")
        with self.assertRaisesRegex(ValueError, "differs"):
            module.collect(self.root, self.manifest)

    def test_host_root_rejected(self):
        with self.assertRaisesRegex(ValueError, "not the host"):
            module.collect(Path("/"), self.manifest)


if __name__ == "__main__":
    unittest.main()
