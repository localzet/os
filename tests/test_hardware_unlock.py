import tempfile
import unittest
from pathlib import Path
from localzet.hardware import PCIDevice
from localzet.hardware_unlock import assess


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
