import tempfile
from pathlib import Path
import unittest
from localzet.hardware import inventory, plan


class HardwareTests(unittest.TestCase):
    def fixture(self, root, address, vendor, device_class, driver=None):
        path = root / address
        path.mkdir()
        for key, value in (("vendor", vendor), ("device", "0x1234"), ("class", device_class)):
            (path / key).write_text(value)
        if driver:
            (path / "driver").symlink_to("/sys/bus/pci/drivers/" + driver)

    def test_hybrid_and_cuda_conditional(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root, "0000:00:02.0", "0x8086", "0x030000", "i915")
            self.fixture(root, "0000:01:00.0", "0x10de", "0x030200", "nouveau")
            self.fixture(root, "0000:01:00.1", "0x10de", "0x040300", "snd_hda_intel")
            self.fixture(root, "0000:02:00.0", "0x10ec", "0x020000")
            result = plan(inventory(root))
            self.assertTrue(result["nvidia_gpu_detected"])
            self.assertTrue(result["hybrid_graphics_candidate"])
            self.assertEqual(len(result["graphics"]), 2)
            self.assertEqual(result["graphics"][1]["driver"], "nouveau")
            self.assertEqual(result["unbound_pci_devices"][0]["vendor"], "10ec")
            self.assertEqual(next(task for task in result["tasks"] if task["id"] == "cuda-toolkit")["status"], "conditional")
            self.assertFalse(result["install_ready"])

    def test_non_gpu_nvidia_does_not_trigger_cuda(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root, "0000:01:00.1", "0x10de", "0x040300")
            self.fixture(root, "0000:02:00.0", "0x1002", "0x030000", "amdgpu")
            self.fixture(root, "0000:03:00.0", "invalid", "0x030000")
            result = plan(inventory(root))
            self.assertFalse(result["nvidia_gpu_detected"])
            self.assertFalse(result["hybrid_graphics_candidate"])
            self.assertNotIn("cuda-toolkit", [task["id"] for task in result["tasks"]])
            self.assertIn("mesa-vulkan", [task["id"] for task in result["tasks"]])

    def test_empty_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = plan(inventory(Path(directory)))
            self.assertEqual(result["graphics"], [])
            self.assertFalse(result["install_ready"])
