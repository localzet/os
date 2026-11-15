import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS
from pathlib import Path

from localzet.hardware_cuda import GPU
from localzet.hardware_compute import parse_results, verify, SOURCE


class HardwareComputeTests(unittest.TestCase):
    def test_requires_all_gpu_results_exactly_once(self):
        addresses = ["0000:01:00.0", "0000:0a:00.0"]
        self.assertEqual(parse_results("PASS 0000:01:00.0 42\nPASS 0000:0A:00.0 42\n", addresses), addresses)
        for value in ("", "PASS 0000:01:00.0 42", "PASS 0000:01:00.0 43",
                      "PASS 0000:01:00.0 42\nPASS 0000:01:00.0 42",
                      "PASS 0000:01:00.0 42\nPASS 0000:0a:00.0 42\nPASS 0000:02:00.0 42"):
            with self.assertRaises(ValueError):
                parse_results(value, addresses)

    def test_probe_compiles_for_every_architecture_and_runs_as_user(self):
        gpus = (GPU("0000:01:00.0", "8.6", "590.44.01"),
                GPU("0000:02:00.0", "12.0", "590.44.01"))
        with patch("localzet.hardware_compute.os.geteuid", return_value=1000), patch(
                "localzet.hardware_compute.inventory", return_value=()), patch(
                "localzet.hardware_compute.running_gpus", return_value=gpus), patch(
                "localzet.hardware_compute.compiler", return_value=("/usr/bin/nvcc", "13.1")), patch(
                "localzet.hardware_compute.subprocess.run") as run:
            def execute(argv, **kwargs):
                if argv[0] == "/usr/bin/nvcc":
                    self.assertEqual(Path(argv[1]).read_text(), SOURCE)
                    self.assertIn("arch=compute_86,code=sm_86", argv)
                    self.assertIn("arch=compute_120,code=sm_120", argv)
                    self.assertIn("cudaDeviceSynchronize", SOURCE)
                    self.assertNotIn("CUDA_VISIBLE_DEVICES", kwargs["env"])
                    self.assertTrue(kwargs["check"])
                    return NS(stdout="")
                return NS(stdout="PASS 0000:01:00.0 42\nPASS 0000:02:00.0 42\n")
            run.side_effect = execute
            self.assertEqual(verify()["status"], "compute-verified")
            self.assertEqual(run.call_count, 2)

    def test_root_refused_before_runtime_query(self):
        with patch("localzet.hardware_compute.os.geteuid", return_value=0), patch(
                "localzet.hardware_compute.running_gpus") as runtime:
            with self.assertRaisesRegex(ValueError, "not root"):
                verify()
            runtime.assert_not_called()
