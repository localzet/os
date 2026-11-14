import tempfile
import unittest
from pathlib import Path
from localzet.installer.storage_diagnostics import (
    describe, report, storage_controllers, parse_boot_entries, EFI_TYPE
)


def disk(path="/dev/nvme0n1", **changes):
    return dict({"name": path.rsplit("/", 1)[-1], "type": "disk", "path": path,
                 "size": 64 * 1024**3, "ro": False, "rm": False, "rota": False,
                 "serial": "PRIVATE-SERIAL", "tran": "nvme", "children": []}, **changes)


class DiagnosticsTests(unittest.TestCase):
    def test_existing_disk_is_visible_but_blocked(self):
        data = report({"blockdevices": [disk(children=[
            {"type": "part", "path": "/dev/nvme0n1p1", "parttype": EFI_TYPE, "fstype": "vfat"}
        ])]}, None, [])
        self.assertEqual(data["internal_disks_visible"], 1)
        self.assertFalse(data["disks"][0]["eligible"])
        self.assertEqual(data["disks"][0]["efi_partitions"], ["/dev/nvme0n1p1"])
        self.assertNotIn("PRIVATE-SERIAL", str(data))

    def test_unknown_source_never_eligible(self):
        data = report({"blockdevices": [disk()]}, None, [], source_known=False)
        self.assertFalse(data["disks"][0]["eligible"])

    def test_missing_disks_and_intel_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp) / "0000:00:0e.0"
            device.mkdir()
            for key, value in (("class", "0x010400"), ("vendor", "0x8086"),
                               ("device", "0x9a0b")):
                (device / key).write_text(value)
            controllers = storage_controllers(Path(tmp))
            data = report({"blockdevices": []}, None, controllers)
            self.assertTrue(data["intel_rst_possible"])
            self.assertIn("Intel RAID/VMD", describe(data))
            self.assertIsNone(controllers[0]["driver"])

    def test_boot_entries_are_hints(self):
        rows = parse_boot_entries(r"Boot0001* ubuntu HD(1,GPT,abcd)/File(\EFI\ubuntu\shimx64.efi)" + "\n" +
                                  r"Boot0002* Windows Boot Manager HD(1,GPT,abcd)/File(\EFI\Microsoft\Boot\bootmgfw.efi)")
        self.assertEqual([r["kind"] for r in rows], ["possible-grub", "windows"])
        self.assertEqual(rows[0]["label"], "ubuntu")
