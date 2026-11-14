"""Security and metadata checks for generated GNOME extension bundles."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("shell_bundle", ROOT / "scripts/verify-shell-bundle.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ShellBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "extension.zip"

    def bundle(self, *, uuid=module.UUID, version="50", extra=None, omit=None):
        files = {
            "metadata.json": json.dumps({"uuid": uuid, "shell-version": [version]}),
            "extension.js": "export default class Shell {}",
            "stylesheet.css": ".localzet-indicator {}",
            "dock.js": "export class LocalzetDock {}",
            "panel.js": "export class AuroraPanel {}",
        }
        if extra:
            files.update(extra)
        if omit:
            files.pop(omit)
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, content in files.items():
                archive.writestr(name, content)

    def test_valid(self):
        self.bundle()
        self.assertEqual(len(module.validate(self.path)), 64)

    def test_uuid_mismatch(self):
        self.bundle(uuid="other@example.com")
        with self.assertRaisesRegex(ValueError, "UUID"):
            module.validate(self.path)

    def test_shell_version_mismatch(self):
        self.bundle(version="49")
        with self.assertRaisesRegex(ValueError, "GNOME"):
            module.validate(self.path)

    def test_missing_source(self):
        self.bundle(omit="extension.js")
        with self.assertRaisesRegex(ValueError, "missing"):
            module.validate(self.path)

    def test_missing_imported_module(self):
        self.bundle(omit='panel.js')
        with self.assertRaisesRegex(ValueError, 'missing'):
            module.validate(self.path)

    def test_reject_path_traversal(self):
        self.bundle(extra={"../bad": "exploit"})
        with self.assertRaisesRegex(ValueError, "unsafe"):
            module.validate(self.path)

    def test_reject_nested_path(self):
        self.bundle(extra={"nested/bad": "exploit"})
        with self.assertRaisesRegex(ValueError, "unsafe"):
            module.validate(self.path)

    def test_reject_duplicate_entries(self):
        self.bundle()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.path, "a") as archive:
                archive.writestr("extension.js", "duplicate")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            module.validate(self.path)

if __name__ == "__main__":
    unittest.main()
