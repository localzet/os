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

    def test_secure_boot_is_read_only_and_unknown_is_distinct(self):
        from localzet.hardware import secure_boot
        with tempfile.TemporaryDirectory() as directory:
            efi = Path(directory) / "efi"
            self.assertEqual(secure_boot(efi), "not-uefi")
            (efi / "efivars").mkdir(parents=True)
            self.assertEqual(secure_boot(efi), "unknown")
            value = efi / "efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
            for flag, expected in ((0, "disabled"), (1, "enabled"), (2, "unknown")):
                value.write_bytes(bytes((7, 0, 0, 0, flag)))
                self.assertEqual(secure_boot(efi), expected)
            value.write_bytes(b"")
            self.assertEqual(secure_boot(efi), "unknown")

    def test_parse_recommended_accepts_only_package_rows(self):
        from localzet.hardware import parse_recommended
        self.assertEqual(parse_recommended("nvidia-driver-580-open linux-modules-nvidia-580-open-generic\nbcmwl-kernel-source\n"),
            (("nvidia-driver-580-open", "linux-modules-nvidia-580-open-generic"), ("bcmwl-kernel-source",)))
        for output in ("--include-dkms", "nvidia-driver-580;id", "nvidia-driver-580 /tmp/foo",
                       "nvidia-driver-580 arbitrary-package", "nvidia-driver-580, (kernel modules provided by foo)"):
            with self.assertRaises(ValueError):
                parse_recommended(output)

    def test_archive_candidate_rejects_mixed_untrusted_and_wrong_release(self):
        from types import SimpleNamespace as NS
        from localzet.hardware import archive_candidate
        trusted = NS(trusted=True, origin="Ubuntu", archive="resolute-updates")
        for origins, expected in (([trusted], "ubuntu-candidate"), ([], "review-origin"),
                ([trusted, NS(trusted=True, origin="PPA", archive="resolute")], "review-origin"),
                ([NS(trusted=False, origin="Ubuntu", archive="resolute")], "review-origin"),
                ([NS(trusted=True, origin="Ubuntu", archive="noble")], "review-origin")):
            package = NS(candidate=NS(origins=origins, version="1", size=10, installed_size=20))
            result = archive_candidate({"cuda-toolkit": package}, "cuda-toolkit")
            self.assertEqual(result["status"], expected)
            self.assertEqual(result["version"], "1")
        self.assertEqual(archive_candidate({}, "cuda-toolkit")["status"], "unavailable")

    def test_resolve_never_enables_cuda_without_gpu(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        from localzet.hardware import resolve_local
        with patch.dict(sys.modules, {"apt": SimpleNamespace(Cache=lambda: {})}), patch(
                "localzet.hardware.recommendations", return_value={"status": "observed",
                "packages": [["nvidia-driver-580"]], "privileged_inventory": False}):
            result = resolve_local(())
            self.assertFalse(result["nvidia_gpu_detected"])
            self.assertEqual(result["nvidia_desktop_recommendations"], [])
            self.assertNotIn("cuda-toolkit", [row["name"] for row in result["archive_candidates"]])
            self.assertIsNone(result["cuda_compatible"])
            self.assertFalse(result["install_ready"])
