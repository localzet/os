import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch, Mock
from localzet.hardware import PCIDevice
from localzet.hardware_cuda import GPU, parse_gpu_query, running_gpus, select_toolkit, cuda_transaction


def cache():
    origin = NS(trusted=True, origin="Ubuntu", archive="resolute")
    return {name: NS(candidate=NS(version=version, origins=[origin], size=1, installed_size=2))
            for name, version in (("cuda-toolkit-13-1", "13.1.1-0ubuntu1"),
                                  ("nvidia-cuda-toolkit", "12.4.131~12.4.1-8"))}


class HardwareCudaTests(unittest.TestCase):
    def test_gpu_query_normalizes_bus_and_rejects_invalid_rows(self):
        self.assertEqual(parse_gpu_query("00000000:01:00.0, 8.6, 590.44.01\n"),
                         (GPU("0000:01:00.0", "8.6", "590.44.01"),))
        for text in ("", "00000000:01:00.0, N/A, 590.44.01",
                     "00000000:01:00.0, 8.6, invalid",
                     "00000000:01:00.0, 8.6, 590.44.01\n00000000:01:00.0, 8.6, 590.44.01"):
            with self.assertRaises(ValueError):
                parse_gpu_query(text)

    def test_toolkit_selection_requires_exact_supported_arch_and_driver(self):
        for capability, driver, expected in (("12.0", "590.44.01", "cuda-toolkit-13-1"),
                ("8.6", "590.44.01", "cuda-toolkit-13-1"),
                ("8.6", "580.95.05", "nvidia-cuda-toolkit"),
                ("6.1", "590.44.01", "nvidia-cuda-toolkit")):
            self.assertEqual(select_toolkit((GPU("0000:01:00.0", capability, driver),), cache()), expected)
        for capability, driver in (("12.0", "580.95.05"), ("3.5", "590.44.01"),
                                   ("13.0", "600.00.01"), ("8.6", "525.60.13")):
            with self.assertRaises(ValueError):
                select_toolkit((GPU("0000:01:00.0", capability, driver),), cache())

    def test_mixed_gpu_selection_and_candidate_origin(self):
        modern = GPU("0000:01:00.0", "8.6", "590.44.01")
        older = GPU("0000:02:00.0", "6.1", "590.44.01")
        self.assertEqual(select_toolkit((modern, older), cache()), "nvidia-cuda-toolkit")
        with self.assertRaises(ValueError):
            select_toolkit((GPU("0000:01:00.0", "12.0", "590.44.01"), older), cache())
        packages = cache()
        packages["cuda-toolkit-13-1"].candidate.version = "13.2.0"
        self.assertEqual(select_toolkit((modern,), packages), "nvidia-cuda-toolkit")

    def test_runtime_must_match_all_bound_gpu_addresses(self):
        gpu = PCIDevice("0000:01:00.0", "10de", "1234", "030000", "nvidia")
        audio = PCIDevice("0000:01:00.1", "10de", "1234", "040300", "snd_hda_intel")
        with patch("localzet.hardware_cuda.subprocess.run") as run:
            with self.assertRaises(ValueError):
                running_gpus((audio,))
            run.assert_not_called()
            run.return_value.stdout = "00000000:01:00.0, 8.6, 590.44.01"
            self.assertEqual(running_gpus((gpu, audio))[0].capability, "8.6")
            with self.assertRaises(ValueError):
                running_gpus((gpu, PCIDevice("0000:02:00.0", "10de", "1234", "030200", "nvidia")))
            with self.assertRaises(ValueError):
                running_gpus((PCIDevice(gpu.address, gpu.vendor, gpu.device, gpu.device_class, "nouveau"),))

    def test_cuda_does_not_change_active_driver(self):
        apt = Mock()
        gpu = GPU("0000:01:00.0", "8.6", "590.44.01")
        with patch("localzet.hardware_cuda.running_gpus", return_value=(gpu,)), patch(
                "localzet.hardware_cuda.select_toolkit", return_value="cuda-toolkit-13-1"), patch(
                "localzet.hardware_cuda.simulate_packages", return_value={
                    "status": "simulated", "changes": [{"name": "libnvidia-compute-590:amd64"}]}):
            with self.assertRaisesRegex(ValueError, "active driver"):
                cuda_transaction(apt, (), retain_marks=True)
            apt.clear.assert_called_once()
