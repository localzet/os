import tempfile
import unittest
from pathlib import Path

from localzet.windows_runtime import launch_plan, OLE_HEADER


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exe = self.root / "my app.exe"
        header = bytearray(64)
        header[:2] = b"MZ"
        header[60:64] = (64).to_bytes(4, "little")
        self.exe.write_bytes(header + b"PE\x00\x00")

    def test_plan_uses_distinct_prefixes_without_creating_them(self):
        a = launch_plan(self.exe, "office", self.root)
        b = launch_plan(self.exe, "game", self.root)
        self.assertNotEqual(a["prefix"], b["prefix"])
        self.assertFalse(Path(a["prefix"]).exists())
        self.assertEqual(a["argv"], ["/usr/bin/wine", str(self.exe)])
        self.assertFalse(a["sandboxed"])

    def test_msi_uses_msiexec(self):
        msi = self.root / "test.msi"
        msi.write_bytes(OLE_HEADER)
        self.assertEqual(launch_plan(msi, "test", self.root)["argv"][1:3], ["msiexec", "/i"])

    def test_invalid_profile(self):
        with self.assertRaises(ValueError):
            launch_plan(self.exe, "../escape", self.root)

    def test_rejects_fake_exe(self):
        self.exe.write_text("not an executable")
        with self.assertRaises(ValueError):
            launch_plan(self.exe, "test", self.root)

    def test_rejects_relative_data_home(self):
        with self.assertRaises(ValueError):
            launch_plan(self.exe, "test", Path("relative"))
