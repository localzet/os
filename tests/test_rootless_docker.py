import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from localzet import rootless_docker as r
from localzet.containers import EngineError


class RootlessTests(unittest.TestCase):
    def test_subordinate_range(self):
        self.assertTrue(r.has_range("alice:100000:65536", "alice", 1000))
        self.assertTrue(r.has_range("1000:100000:65536", "alice", 1000))
        for value in ("other:100000:65536", "alice:0:65536", "alice:100000:65535", "alice:x:65536", "alice:4294967000:65536"):
            self.assertFalse(r.has_range(value, "alice", 1000))

    def test_invalid_action_and_root(self):
        with self.assertRaises(ValueError):
            r.change("restart")
        with patch.object(r.os, "geteuid", return_value=0):
            with self.assertRaises(EngineError):
                r.change("start")

    def test_stop_only_fixed_unit(self):
        with patch.object(r, "_preflight"), patch.object(r, "_ctl") as ctl:
            self.assertEqual(r.change("stop"), "остановлен")
            ctl.assert_called_once_with("stop", r.UNIT)

    def test_start_verifies_real_security_option(self):
        socket = MagicMock(spec=Path)
        socket.exists.return_value = False
        socket.is_symlink.return_value = False
        with patch.object(r, "_preflight", return_value=socket), patch.object(r.Path, "is_file", return_value=True), patch.object(r.os, "access", return_value=True), patch.object(r.Path, "read_text", return_value="alice:100000:65536"), patch.object(r.pwd, "getpwuid", return_value=MagicMock(pw_name="alice")), patch.object(r, "_ctl", side_effect=["not-found", "inactive", ""]) as ctl, patch.object(r, "Engine") as engine:
            engine.return_value._run.return_value = '["name=rootless","name=seccomp"]'
            self.assertEqual(r.change("start"), "rootless подтверждён")
            ctl.assert_called_with("start", r.UNIT)
