"""Sector-exact synthetic GPT fixtures; never open a real block device."""
from copy import deepcopy
import unittest
from localzet.installer.free_space import inspect_free_space, EFI_TYPE

DATA_TYPE = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"


def fixture(sector=512):
    disk = "/dev/nvme0n1"
    total = 128 * 1024**3 // sector
    align = 1024**2 // sector
    rows = [
        {"node": disk + "p1", "start": align, "size": 512 * align,
         "type": EFI_TYPE, "uuid": "00000000-0000-4000-8000-000000000001"},
        {"node": disk + "p2", "start": 513 * align, "size": 64 * 1024 * align,
         "type": DATA_TYPE, "uuid": "00000000-0000-4000-8000-000000000002"},
    ]
    children = [
        {"type": "part", "path": row["node"], "name": row["node"].split("/")[-1],
         "size": row["size"] * sector, "partuuid": row["uuid"],
         "parttype": row["type"], "fstype": fs, "ro": False, "mountpoints": [None]}
        for row, fs in zip(rows, ("vfat", "ntfs"))
    ]
    payload = {"blockdevices": [{"type": "disk", "path": disk, "name": "nvme0n1",
                "serial": "MAIN", "tran": "nvme", "size": total * sector,
                "pttype": "gpt", "ro": False, "rm": False, "rota": False,
                "children": children}]}
    table = {"partitiontable": {"label": "gpt", "device": disk, "unit": "sectors",
                "id": "00000000-0000-4000-8000-000000000003", "sectorsize": sector,
                "firstlba": 34, "lastlba": total - 34, "partitions": rows}}
    return payload, table


class FreeSpaceTests(unittest.TestCase):
    def plan(self, payload, table, **kw):
        return inspect_free_space(payload, "serial:MAIN", kw.pop("live_disk", "/dev/sdb"),
                                  table, source_known=kw.pop("source_known", True), **kw)

    def test_gpt_512_and_4k(self):
        for sector in (512, 4096):
            with self.subTest(sector=sector):
                p, t = fixture(sector)
                saved = deepcopy((p, t))
                plan = self.plan(p, t)
                self.assertFalse(plan["install_ready"])
                self.assertFalse(plan["write_operations_available"])
                self.assertEqual(len(plan["efi_partitions_to_preserve"]), 1)
                extent = plan["aligned_free_extents"][-1]
                self.assertTrue(extent["meets_root_minimum"])
                self.assertGreaterEqual(extent["start_lba"], plan["partitions_to_preserve"][-1]["end_lba_exclusive"])
                self.assertEqual(extent["start_lba"] * sector % (1024**2), 0)
                self.assertEqual((p, t), saved)

    def test_reject_unknown_boot_or_boot_target(self):
        p, t = fixture()
        with self.assertRaises(ValueError):
            self.plan(p, t, source_known=False)
        with self.assertRaises(ValueError):
            self.plan(p, t, live_disk="/dev/nvme0n1")

    def test_overlap_rejected(self):
        p, t = fixture()
        t["partitiontable"]["partitions"][1]["start"] -= 1
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            self.plan(p, t)

    def test_mismatched_partition_uuid_size_or_type(self):
        for key, value in (("uuid", "00000000-0000-4000-8000-000000000009"),
                           ("size", 99), ("type", EFI_TYPE)):
            p, t = fixture()
            t["partitiontable"]["partitions"][1][key] = value
            with self.assertRaises(ValueError):
                self.plan(p, t)

    def test_mounted_encrypted_or_nested_rejected(self):
        for key, value in (("mountpoints", ["/mnt/windows"]), ("fstype", "BitLocker"),
                           ("children", [{"type": "crypt"}])):
            p, t = fixture()
            p["blockdevices"][0]["children"][1][key] = value
            with self.assertRaises(ValueError):
                self.plan(p, t)

    def test_no_large_extent_is_not_installable(self):
        p, t = fixture()
        row = t["partitiontable"]["partitions"][1]
        row["size"] += 48 * 1024**3 // 512
        p["blockdevices"][0]["children"][1]["size"] = row["size"] * 512
        plan = self.plan(p, t)
        self.assertFalse(any(x["meets_root_minimum"] for x in plan["aligned_free_extents"]))

    def test_gpt_changed_fingerprint(self):
        p, t = fixture()
        before = self.plan(p, t)
        t["partitiontable"]["partitions"][1]["start"] += 2048
        after = self.plan(p, t)
        self.assertNotEqual(before["gpt_fingerprint"], after["gpt_fingerprint"])
