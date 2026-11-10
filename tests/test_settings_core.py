"""GTK-free source tests for Localzet Settings."""
from pathlib import Path
import unittest

from localzet.settings.core import readable_bytes, memory_total, status_label, load_modules


class SettingsCoreTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(readable_bytes(0), "0 B")
        self.assertEqual(readable_bytes(1024**3), "1.0 GiB")
        self.assertEqual(readable_bytes(1536 * 1024**2), "1.5 GiB")

    def test_negative_bytes_rejected(self):
        with self.assertRaises(ValueError):
            readable_bytes(-1)

    def test_meminfo(self):
        self.assertEqual(memory_total("MemFree: 100 kB\nMemTotal: 1024 kB\n"), 1048576)
        self.assertIsNone(memory_total("MemTotal: invalid kB"))
        self.assertIsNone(memory_total("MemTotal: 64 GB"))

    def test_catalog_read_only(self):
        root = Path(__file__).resolve().parents[1]
        modules = load_modules(root / "config/modules")
        self.assertEqual(len(modules), 6)
        self.assertTrue(all(m.status in ("planned", "prototype", "supported") for m in modules))

    def test_status_labels(self):
        self.assertEqual(status_label("planned"), "В планах")
        self.assertEqual(status_label("other"), "Неизвестно")


if __name__ == "__main__":
    unittest.main()
