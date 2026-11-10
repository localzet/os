"""Disk inventory should fail closed and never alter storage."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from localzet.installer.preflight import inspect_disk, inventory  # noqa: E402


def disk(**kwargs):
    return {
        "name": "nvme1n1", "path": "/dev/nvme1n1", "type": "disk",
        "ro": False, "rm": False, "rota": False, "size": 128 * 1024**3,
        "children": [], **kwargs,
    }


class DiskSafetyTests(unittest.TestCase):
    def test_pristine_ssd_requires_manual_confirmation(self):
        out = inspect_disk(disk())
        self.assertEqual(out["status"], "manual_review_only")
        self.assertFalse(out["blockers"])
        self.assertIn("does NOT authorize", out["warnings"][-1])

    def test_mounted_root_blocks_disk(self):
        root = {"name": "nvme1n1p1", "type": "part", "mountpoints": ["/", "/boot/efi"]}
        out = inspect_disk(disk(children=[root]))
        self.assertEqual(out["status"], "blocked")
        self.assertIn("Mounted or active", out["blockers"][0])

    def test_removable_usb_blocked(self):
        self.assertEqual(inspect_disk(disk(rm=True))["status"], "blocked")

    def test_rotational_disk_blocked(self):
        self.assertEqual(inspect_disk(disk(rota=True))["status"], "blocked")

    def test_unknown_disk_properties_fail_closed(self):
        self.assertEqual(inspect_disk(disk(rota=None))["status"], "blocked")

    def test_read_only_device_blocked(self):
        self.assertEqual(inspect_disk(disk(ro=True))["status"], "blocked")

    def test_small_disk_blocked(self):
        self.assertEqual(inspect_disk(disk(size=1024))["status"], "blocked")

    def test_existing_unmounted_partition_not_assumed_blank(self):
        out = inspect_disk(disk(children=[
            {"name": "nvme1n1p1", "type": "part", "fstype": "ext4",
             "mountpoints": [None]},
        ]))
        self.assertEqual(out["status"], "manual_review_only")
        self.assertTrue(any("Existing partitions" in w for w in out["warnings"]))

    def test_raid_member_blocked(self):
        out = inspect_disk(disk(children=[
            {"name": "nvme1n1p1", "type": "part",
             "fstype": "linux_raid_member", "mountpoints": [None]}
        ]))
        self.assertEqual(out["status"], "blocked")

    def test_luks_member_blocked(self):
        out = inspect_disk(disk(fstype="crypto_LUKS"))
        self.assertEqual(out["status"], "blocked")

    def test_nested_mapper_blocked(self):
        out = inspect_disk(disk(children=[
            {"name": "cryptdata", "type": "crypt", "mountpoints": [None]}
        ]))
        self.assertEqual(out["status"], "blocked")

    def test_no_destructive_result(self):
        result = inventory({"blockdevices": [disk()]})
        self.assertFalse(result["writable_operations_available"])
        self.assertFalse(result["install_ready"])
        self.assertNotIn("erase", result["disks"][0])

    def test_non_disks_are_not_candidates(self):
        result = inventory({"blockdevices": [
            {"type": "rom", "path": "/dev/sr0"}, disk(),
        ]})
        self.assertEqual(len(result["disks"]), 1)

    def test_malformed_input_rejected(self):
        with self.assertRaises(ValueError):
            inventory({"devices": []})


if __name__ == "__main__":
    unittest.main()
