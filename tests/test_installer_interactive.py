import unittest
import tempfile
from pathlib import Path

from localzet.installer.interactive import eligible_plan, confirmation_for, validate_request, secure_boot_disabled, EFI_GUID


def disk(path="/dev/nvme0n1", serial="TARGET", **kwargs):
    result = {
        "name": path.rsplit("/", 1)[-1], "path": path,
        "type": "disk", "size": 64 * 1024**3,
        "ro": False, "rm": False, "rota": False,
        "model": "Test SSD", "serial": serial, "wwn": "",
        "tran": "nvme", "children": [],
    }
    result.update(kwargs)
    return result


class InteractiveInstallerTests(unittest.TestCase):
    def setUp(self):
        self.target = disk()
        self.usb = disk("/dev/sdb", "LIVE", tran="usb", rm=True)
        self.payload = {"blockdevices": [self.target, self.usb]}

    def plan(self):
        return eligible_plan(self.payload, "serial:TARGET", "/dev/sdb")

    def request(self):
        plan = self.plan()
        return {"plan": plan, "confirmation": confirmation_for(plan),
                "backup_acknowledged": True, "username": "tester",
                "password": "test-password-123"}

    def test_blank_internal_ssd_with_usb_source(self):
        plan = self.plan()
        self.assertFalse(plan["write_operations_available"])
        validate_request(self.request())

    def test_second_internal_disk_blocks(self):
        self.payload["blockdevices"].append(disk("/dev/nvme1n1", "OTHER"))
        with self.assertRaises(ValueError):
            self.plan()

    def test_partition_table_or_signature_blocks(self):
        for key, value in (("pttype", "gpt"), ("fstype", "ext4"),
                           ("children", [{"type": "part", "name": "p1"}])):
            with self.subTest(key=key):
                self.target[key] = value
                with self.assertRaises(ValueError):
                    self.plan()
                self.target.pop(key)

    def test_boot_disk_cannot_be_target(self):
        with self.assertRaises(ValueError):
            eligible_plan({"blockdevices": [self.target]}, "serial:TARGET", "/dev/nvme0n1")

    def test_confirmation_and_backup_are_required(self):
        request = self.request()
        request["confirmation"] = "INSTALL serial:OTHER"
        with self.assertRaises(ValueError):
            validate_request(request)
        request = self.request()
        request["backup_acknowledged"] = False
        with self.assertRaises(ValueError):
            validate_request(request)

    def test_reserved_user_and_invalid_password(self):
        for field, value in (("username", "root"), ("username", "localzet"),
                             ("username", "../test"), ("password", "short"),
                             ("password", "long:password"), ("password", "long\npassword")):
            with self.subTest(field=field, value=value):
                request = self.request()
                request[field] = value
                with self.assertRaises(ValueError):
                    validate_request(request)


class SecureBootTests(unittest.TestCase):
    def test_firmware_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sb = root / f"SecureBoot-{EFI_GUID}"
            setup = root / f"SetupMode-{EFI_GUID}"
            self.assertFalse(secure_boot_disabled(root))
            setup.write_bytes(b"\x06\0\0\0\x01")
            self.assertTrue(secure_boot_disabled(root))
            sb.write_bytes(b"\x06\0\0\0\x01")
            self.assertFalse(secure_boot_disabled(root))
            sb.write_bytes(b"\x06\0\0\0\x00")
            self.assertTrue(secure_boot_disabled(root))
            sb.write_bytes(b"\x06\0\0\0" + (0).to_bytes(4, "little"))
            self.assertTrue(secure_boot_disabled(root))
            sb.write_bytes(b"\x06\0\0\0\x02")
            with self.assertRaises(ValueError):
                secure_boot_disabled(root)
