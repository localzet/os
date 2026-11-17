import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from localzet.recovery import (
    grub_inventory, kernel_inventory, package_audit, hardware_receipts, RECEIPTS,
)


class RecoveryTests(unittest.TestCase):
    def test_kernel_pairs_require_nonempty_regular_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            boot = Path(tmp)
            for name in ("vmlinuz-6.17.0-1-generic", "initrd.img-6.17.0-1-generic",
                         "vmlinuz-6.17.0-2-generic", "initrd.img-6.17.0-2-generic",
                         "vmlinuz-6.17.0-3-generic"):
                (boot / name).write_bytes(b"fixture")
            (boot / "initrd.img-6.17.0-3-generic").symlink_to("initrd.img-6.17.0-1-generic")
            (boot / "vmlinuz-6.17.0-4-generic").write_bytes(b"fixture")
            (boot / "initrd.img-6.17.0-4-generic").touch()
            info = kernel_inventory(boot, "6.17.0-2-generic")
            self.assertTrue(info["running_pair_present"])
            self.assertEqual(info["fallback_pairs"], ["6.17.0-1-generic"])
            self.assertFalse(kernel_inventory(boot, "other")["running_pair_present"])

    def test_grub_distinguishes_actual_recovery_kernel_command(self):
        config = """
menuentry 'Recovery (label alone is not enough)' {
    linux /boot/vmlinuz-6.17.0-1-generic root=UUID=fixture ro quiet
}
menuentry 'Advanced options' {
    linux /boot/vmlinuz-6.17.0-2-generic root=UUID=fixture ro recovery nomodeset
    linuxefi /boot/vmlinuz-6.17.0-2-generic root=UUID=fixture ro
}
# linux /boot/vmlinuz-fake recovery
"""
        info = grub_inventory(config, "6.17.0-2-generic")
        self.assertTrue(info["running_normal_entry"])
        self.assertTrue(info["running_recovery_entry"])
        self.assertEqual(info["recovery_entries"], ["6.17.0-2-generic"])
        self.assertFalse(grub_inventory(config, "6.17.0-1-generic")["running_recovery_entry"])

    def test_package_audit_does_not_assume_zero_exit_is_clean(self):
        for code, stdout, stderr, expected in (
                (0, "", "", "clean"),
                (0, "half-configured fixture", "", "needs-review"),
                (1, "", "", "unknown"),
                (0, "", "warning", "unknown")):
            with self.subTest(expected=expected):
                def command(argv, **kwargs):
                    self.assertEqual(argv, ["/usr/bin/dpkg", "--audit"])
                    return subprocess.CompletedProcess(argv, code, stdout, stderr)
                self.assertEqual(package_audit(command), expected)
        def timeout(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 30)
        self.assertEqual(package_audit(timeout), "unknown")

    def test_missing_and_malformed_receipts_never_claim_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.assertEqual(set(hardware_receipts(directory).values()), {"absent"})
            path = directory / RECEIPTS[0]
            path.write_text(json.dumps({"state": "installed-reboot-verification-required"}))
            path.chmod(0o600)
            # Unprivileged CI must not trust a user-owned root transaction file.
            with patch("localzet.recovery.os.fstat") as fake:
                fake.return_value.st_mode = 0o100600
                fake.return_value.st_uid = 0
                self.assertEqual(hardware_receipts(directory)[RECEIPTS[0]], "verification-required")
                path.write_text(json.dumps({"state": "installing"}))
                self.assertEqual(hardware_receipts(directory)[RECEIPTS[0]], "recovery-review-required")
                path.write_text("not JSON")
                self.assertEqual(hardware_receipts(directory)[RECEIPTS[0]], "unknown")
            path.unlink()
            path.symlink_to("/etc/passwd")
            self.assertEqual(hardware_receipts(directory)[RECEIPTS[0]], "unknown")


if __name__ == "__main__":
    unittest.main()
