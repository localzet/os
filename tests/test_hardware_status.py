import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from localzet.hardware_status import read_status, publish


class HardwareStatusTests(unittest.TestCase):
    def test_only_sanitized_root_owned_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            self.assertEqual(read_status(path), {"state": "no-record"})
            path.write_text(json.dumps({"schema": 1, "state": "awaiting-reboot", "updated": 42}))
            path.chmod(0o644)
            with patch("localzet.hardware_status.os.fstat") as stat:
                from types import SimpleNamespace
                import stat as modes
                stat.return_value = SimpleNamespace(st_mode=modes.S_IFREG | 0o644, st_uid=0)
                self.assertEqual(read_status(path)["state"], "awaiting-reboot")
                for record in ({"schema": 1, "state": "unknown", "updated": 42},
                               {"schema": 1, "state": "offline", "updated": 42, "private": "not public"},
                               {"schema": 1, "state": "offline", "updated": True}):
                    path.write_text(json.dumps(record))
                    self.assertEqual(read_status(path)["state"], "unavailable")
                path.write_text("x" * 4097)
                self.assertEqual(read_status(path)["state"], "unavailable")
            link = Path(directory) / "link"
            link.symlink_to(path)
            self.assertEqual(read_status(link)["state"], "unavailable")

    def test_publish_requires_root_and_known_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            with patch("localzet.hardware_status.os.geteuid", return_value=1000):
                with self.assertRaises(ValueError):
                    publish("offline", path)
            with self.assertRaises(ValueError):
                publish("arbitrary", path)
            self.assertFalse(path.exists())
