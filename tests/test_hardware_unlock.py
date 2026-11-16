import tempfile
import unittest
from pathlib import Path
from localzet.hardware import PCIDevice
from localzet.hardware_unlock import assess, review_status


class GPUUnlockTests(unittest.TestCase):
    def test_exact_ids_and_no_activation(self):
        devices = (
            PCIDevice("0000:01:00.0", "10de", "2204", "030000", "nvidia"),
            PCIDevice("0000:02:00.0", "10de", "2684", "030200", "nvidia"),
            PCIDevice("0000:03:00.0", "10de", "1e04", "030000", None),
            PCIDevice("0000:04:00.0", "10de", "ffff", "030000", None),
            PCIDevice("0000:01:00.1", "10de", "2204", "040300", None),
            PCIDevice("0000:05:00.0", "1002", "2204", "030000", "amdgpu"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = assess(devices, root)
            self.assertEqual([row["status"] for row in result["devices"]],
                ["upstream-candidate", "experimental", "experimental", "unsupported"])
            self.assertFalse(result["module_present"])
            self.assertFalse(result["activation_available"])
            self.assertFalse(result["speedup_verified"])
            (root / "gpu_unlock").mkdir()
            result = assess(devices, root)
            self.assertTrue(result["module_present"])
            self.assertFalse(result["speedup_verified"])
            self.assertFalse(result["activation_available"])

    def test_no_gpu(self):
        self.assertEqual(assess(())["devices"], [])

    def test_readiness_never_confuses_pci_match_with_activation(self):
        ampere = PCIDevice("0000:01:00.0", "10de", "2204", "030000", "nvidia")
        ada = PCIDevice("0000:02:00.0", "10de", "2684", "030000", "nvidia")
        unknown = PCIDevice("0000:03:00.0", "10de", "ffff", "030000", "nvidia")
        for devices, expected in (((), "no-gpu"), ((unknown,), "unsupported"),
                ((ampere, unknown), "mixed"), ((ampere, ada), "experimental"),
                ((ampere,), "candidate")):
            for boot in ("enabled", "disabled", "not-uefi", "unknown"):
                with self.subTest(devices=devices, boot=boot):
                    result = review_status(assess(devices), boot)
                    self.assertEqual(result["compatibility"], expected)
                    self.assertEqual(result["secure_boot"], boot)
                    self.assertFalse(result["activation_available"])
                    self.assertFalse(result["speedup_verified"])
                    self.assertEqual(result["blocker"], "release-review-required")
