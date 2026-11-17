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
        self.header = bytes(header)
        self.write_pe()

    def write_pe(self, machine=0x8664, magic=0x020B, optional_size=2):
        coff = bytearray(20)
        coff[:2] = machine.to_bytes(2, "little")
        coff[16:18] = optional_size.to_bytes(2, "little")
        self.exe.write_bytes(self.header + b"PE\x00\x00" + coff + magic.to_bytes(2, "little"))

    def test_plan_uses_distinct_prefixes_without_creating_them(self):
        a = launch_plan(self.exe, "office", self.root)
        b = launch_plan(self.exe, "game", self.root)
        self.assertNotEqual(a["prefix"], b["prefix"])
        self.assertFalse(Path(a["prefix"]).exists())
        self.assertEqual(a["argv"], ["/usr/bin/wine", str(self.exe)])
        self.assertFalse(a["sandboxed"])
        self.assertEqual(a["architecture"], "x86-64")

    def test_msi_uses_msiexec(self):
        msi = self.root / "test.msi"
        msi.write_bytes(OLE_HEADER)
        self.assertEqual(launch_plan(msi, "test", self.root)["argv"][1:3], ["msiexec", "/i"])

    def test_architecture_and_invalid_headers(self):
        self.write_pe(0x014C, 0x010B)
        self.assertEqual(launch_plan(self.exe, "test", self.root)["architecture"], "x86")
        for machine, magic in ((0x8664, 0x010B), (0x014C, 0x020B), (0xAA64, 0x020B)):
            self.write_pe(machine, magic)
            with self.assertRaisesRegex(ValueError, "Unsupported PE architecture"):
                launch_plan(self.exe, "test", self.root)
        self.write_pe(optional_size=224)
        with self.assertRaisesRegex(ValueError, "Invalid PE optional header"):
            launch_plan(self.exe, "test", self.root)

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
