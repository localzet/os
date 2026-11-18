import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("installer", Path(__file__).resolve().parents[1] / "packaging/network/install-network-client.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class NetworkCacheTests(unittest.TestCase):
    def test_missing_cache_uses_online_path(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(installer, "CACHE", Path(tmp)):
            self.assertFalse(installer.cached_packages("netbird", {}, [], Path(tmp)))

    def test_cached_exact_bytes_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "netbird"
            source.mkdir()
            target = root / "target"
            target.mkdir()
            original = b"original reviewed fixture"
            asset = {"name": "netbird.deb", "size": len(original), "sha256": hashlib.sha256(original).hexdigest()}
            manifest = {"assets": {"netbird": asset}}
            path = source / asset["name"]
            path.write_bytes(original)
            with patch.object(installer, "CACHE", root):
                self.assertTrue(installer.cached_packages("netbird", manifest, [asset["name"]], target))
                self.assertEqual((target / asset["name"]).read_bytes(), original)
                path.write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                    installer.cached_packages("netbird", manifest, [asset["name"]], target)
                path.unlink()
                with self.assertRaisesRegex(ValueError, "Incomplete"):
                    installer.cached_packages("netbird", manifest, [asset["name"]], target)

    def test_offline_plan_refuses_extra_packages_and_version_changes(self):
        versions = {"netbird": "0.83.1", "netbird-ui": "0.83.1"}
        plan = "Inst netbird (0.83.1 local-deb [amd64v1])\nInst netbird-ui (0.83.1 local-deb [amd64])\nConf netbird (0.83.1 local-deb [amd64])\n"
        self.assertEqual(installer.offline_plan(plan, versions), set(versions))
        for extra in ("Inst curl (9.0 Ubuntu [amd64])", "Remv curl [9.0]", "Conf netbird (9.0 local-deb [amd64])",
                      "Inst netbird [0.83.1] (9.0 local-deb [amd64])"):
            with self.assertRaises(ValueError):
                installer.offline_plan(plan + extra, versions)

    def test_offline_plan_accepts_existing_exact_package(self):
        self.assertEqual(installer.offline_plan("Inst netbird-ui:amd64 (0.83.1 local-deb [amd64])",
                         {"netbird": "0.83.1", "netbird-ui": "0.83.1"}), {"netbird-ui"})
