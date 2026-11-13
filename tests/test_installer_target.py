"""Dedicated SSD identity and non-target preservation planning."""
import unittest
from localzet.installer.target import TargetSelectionError, identity, read_only_target_plan, revalidate_target


def disk(path, serial, **kwargs):
    d = {
        "name": path.rsplit("/", 1)[-1], "path": path,
        "type": "disk", "size": 128 * 1024**3,
        "ro": False, "rm": False, "rota": False,
        "model": "Test SSD", "serial": serial, "wwn": "",
        "tran": "nvme", "children": [],
    }
    d.update(kwargs)
    return d


class SSDIdentityTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"blockdevices": [
            disk("/dev/nvme0n1", "MAIN-OS"),
            disk("/dev/nvme1n1", "NEW-SSD"),
        ]}

    def test_review_never_grants_write_permission(self):
        result = read_only_target_plan(self.payload, "serial:NEW-SSD")
        self.assertFalse(result["install_ready"])
        self.assertFalse(result["write_operations_available"])
        self.assertTrue(result["requires_revalidation_before_write"])
        self.assertEqual(result["target"]["serial"], "NEW-SSD")
        self.assertEqual(result["non_target_disks"][0]["serial"], "MAIN-OS")

    def test_dev_path_is_rejected(self):
        with self.assertRaises(TargetSelectionError):
            read_only_target_plan(self.payload, "/dev/nvme1n1")

    def test_empty_identity_is_rejected(self):
        with self.assertRaises(TargetSelectionError):
            read_only_target_plan(self.payload, "")

    def test_duplicate_serial_is_rejected(self):
        self.payload["blockdevices"].append(disk("/dev/nvme2n1", "NEW-SSD"))
        with self.assertRaises(TargetSelectionError):
            read_only_target_plan(self.payload, "serial:NEW-SSD")

    def test_unknown_identity_rejected(self):
        with self.assertRaises(TargetSelectionError):
            read_only_target_plan(self.payload, "wwn:absent")

    def test_mounted_target_rejected(self):
        self.payload["blockdevices"][1]["children"] = [
            {"name": "nvme1n1p1", "type": "part", "mountpoints": ["/"]},
        ]
        with self.assertRaises(TargetSelectionError):
            read_only_target_plan(self.payload, "serial:NEW-SSD")

    def test_usb_target_rejected(self):
        self.payload["blockdevices"][1]["rm"] = True
        with self.assertRaises(TargetSelectionError):
            read_only_target_plan(self.payload, "serial:NEW-SSD")

    def test_wwn_takes_precedence(self):
        self.payload["blockdevices"][1]["wwn"] = "0x12345"
        self.assertEqual(identity(self.payload["blockdevices"][1]), "wwn:0x12345")
        with self.assertRaises(TargetSelectionError):
            read_only_target_plan(self.payload, "serial:NEW-SSD")
        result = read_only_target_plan(self.payload, "wwn:0x12345")
        self.assertEqual(result["target"]["serial"], "NEW-SSD")

    def test_reordering_does_not_change_identity(self):
        first = read_only_target_plan(self.payload, "serial:NEW-SSD")
        self.payload["blockdevices"].reverse()
        self.payload["blockdevices"][0]["path"] = "/dev/nvme7n1"
        second = read_only_target_plan(self.payload, "serial:NEW-SSD")
        self.assertEqual(first["hardware_fingerprint"], second["hardware_fingerprint"])

    def test_no_serial_or_wwn(self):
        self.assertIsNone(identity(disk("/dev/nvme2n1", "")))

    def test_invalid_payload(self):
        with self.assertRaises(TargetSelectionError):
            read_only_target_plan({}, "serial:NEW-SSD")


    def test_revalidation_allows_renamed_target(self):
        original = read_only_target_plan(self.payload, "serial:NEW-SSD")
        self.payload["blockdevices"][1]["path"] = "/dev/nvme7n1"
        result = revalidate_target(self.payload, original)
        self.assertEqual(result["current_device_path_unstable"], "/dev/nvme7n1")
        self.assertFalse(result["write_operations_available"])

    def test_revalidation_rejects_partition_change(self):
        original = read_only_target_plan(self.payload, "serial:NEW-SSD")
        self.payload["blockdevices"][1]["children"] = [
            {"type": "part", "name": "nvme1n1p1", "size": 1024**3,
             "fstype": "ext4", "uuid": "new", "start": 2048, "ro": False},
        ]
        with self.assertRaisesRegex(TargetSelectionError, "layout_fingerprint"):
            revalidate_target(self.payload, original)

    def test_revalidation_rejects_hardware_change(self):
        original = read_only_target_plan(self.payload, "serial:NEW-SSD")
        self.payload["blockdevices"][1]["size"] += 1024**3
        with self.assertRaisesRegex(TargetSelectionError, "hardware_fingerprint"):
            revalidate_target(self.payload, original)

    def test_revalidation_rejects_old_plan_without_layout(self):
        original = read_only_target_plan(self.payload, "serial:NEW-SSD")
        del original["layout_fingerprint"]
        with self.assertRaises(TargetSelectionError):
            revalidate_target(self.payload, original)

    def test_nonremovable_usb_ssd_is_rejected(self):
        self.payload["blockdevices"][1]["tran"] = "usb"
        with self.assertRaises(TargetSelectionError):
            read_only_target_plan(self.payload, "serial:NEW-SSD")
