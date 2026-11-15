import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from localzet.hardware import PCIDevice
from localzet.hardware_common import cpu_vendor, common_targets, review_common
from localzet.hardware_firstboot import identity, next_step, authorized

AMD = PCIDevice("0000:01:00.0", "1002", "1234", "030000", "amdgpu")
INTEL = PCIDevice("0000:00:02.0", "8086", "1234", "030000", "i915")
NVIDIA = PCIDevice("0000:02:00.0", "10de", "1234", "030200", "nouveau")


class CommonHardwareTests(unittest.TestCase):
    def test_microcode_and_graphics_targets(self):
        self.assertEqual(common_targets((AMD,), "AuthenticAMD", True),
            ("linux-firmware", "amd64-microcode", "libgl1-mesa-dri", "mesa-vulkan-drivers"))
        self.assertEqual(common_targets((INTEL, NVIDIA), "GenuineIntel", True),
            ("linux-firmware", "intel-microcode", "libgl1-mesa-dri", "mesa-vulkan-drivers"))
        self.assertEqual(common_targets((NVIDIA,), "GenuineIntel", False), ("linux-firmware",))
        self.assertEqual(common_targets((), "unknown", True), ("linux-firmware",))

    def test_cpu_vendor_rejects_conflicting_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cpuinfo"
            path.write_text("vendor_id : GenuineIntel\nvendor_id : GenuineIntel\n")
            self.assertEqual(cpu_vendor(path), "GenuineIntel")
            path.write_text("vendor_id : AuthenticAMD\nvendor_id : GenuineIntel\n")
            self.assertEqual(cpu_vendor(path), "unknown")

    def test_general_policy_is_separate_from_original_consent(self):
        for raw, expected in ((b"nvidia-driver-and-cuda-v1\n", "nvidia"),
                              (b"general-hardware-and-cuda-v2\n", "general"),
                              (b"yes", None), (None, None)):
            with patch("localzet.hardware_firstboot.read_private", return_value=raw):
                self.assertEqual(authorized(), expected)

    def test_common_phase_then_nvidia_or_completion(self):
        for devices, expected in (((AMD,), "base-complete"), ((INTEL, NVIDIA), "driver")):
            state = {"state": "base-awaiting-reboot", "hardware": identity(devices, True),
                     "boot_id": "first"}
            self.assertEqual(next_step(None, devices, "first", False, True), "base")
            self.assertEqual(next_step(state, devices, "first", False, True), "base-awaiting-reboot")
            self.assertEqual(next_step(state, devices, "second", False, True), expected)
            self.assertEqual(next_step({**state, "state": "base-ready"}, devices, "first", False, True), expected)
            self.assertEqual(next_step({**state, "state": "offline", "phase": "base"}, devices, "second", False, True), "base")
            self.assertEqual(next_step({**state, "state": "base-installing"}, devices, "second", False, True), "recovery-required")

    def test_common_plan_rejects_kernel_change(self):
        from unittest.mock import Mock
        cache = Mock()
        with patch("localzet.hardware_common.inventory", return_value=(AMD,)), patch(
            "localzet.hardware_common.cpu_vendor", return_value="AuthenticAMD"), patch(
            "localzet.hardware_common.physical_cpu", return_value=True), patch(
            "localzet.hardware_common.simulate_packages", return_value={
                "status": "simulated", "changes": [{"name": "linux-image-generic"}]}):
            with self.assertRaisesRegex(ValueError, "kernel"):
                review_common(cache)
            cache.clear.assert_called_once()
