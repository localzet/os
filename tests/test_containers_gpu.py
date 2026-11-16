import unittest
from unittest.mock import Mock, patch
from localzet.containers import EngineError
from localzet.containers_gpu import gpu_status, probe_gpu, runtime_names
from localzet.hardware_cuda import GPU


class ContainersGPUTests(unittest.TestCase):
    def test_rootless_does_not_query_driver_or_docker(self):
        engine = Mock(rootful=False)
        self.assertEqual(gpu_status(engine)["state"], "rootless-not-reviewed")
        engine._run.assert_not_called()

    def test_runtime_status_and_probe(self):
        engine = Mock(rootful=True)
        image = "sha256:" + "a" * 64
        engine.resources.return_value = [{"ID": image}]
        engine._run.side_effect = ['{"nvidia":{},"runc":{}}', "00000000:01:00.0\n"]
        with patch("localzet.containers_gpu.inventory"), patch(
                "localzet.containers_gpu.running_gpus", return_value=(GPU("0000:01:00.0", "8.6", "590.44.01"),)):
            self.assertEqual(probe_gpu(engine, image), {"state": "gpu-visible", "devices": ["0000:01:00.0"]})
        args = engine._run.call_args.args
        for flag in ("--rm", "--read-only", "--cap-drop", "--network", "--gpus", "--pull"):
            self.assertIn(flag, args)
        self.assertNotIn("--privileged", args)
        self.assertIn(image, args)

    def test_invalid_image_and_mismatched_devices(self):
        engine = Mock(rootful=True)
        with self.assertRaises(EngineError):
            probe_gpu(engine, "--privileged")
        engine._run.assert_not_called()
        image = "sha256:" + "a" * 64
        engine.resources.return_value = [{"ID": image}]
        with patch("localzet.containers_gpu.gpu_status", return_value={"state": "runtime-configured-unverified", "devices": ["0000:01:00.0"]}):
            for output in ("", "00000000:02:00.0", "00000000:01:00.0\n00000000:01:00.0"):
                engine._run.return_value = output
                with self.assertRaises(EngineError):
                    probe_gpu(engine, image)

    def test_invalid_runtime_inventory(self):
        for output in ("[]", "null", "not json"):
            with self.assertRaises(EngineError):
                runtime_names(output)
