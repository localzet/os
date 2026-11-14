import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "packaging/live/localzet-live-ready.py"
spec = importlib.util.spec_from_file_location("live_readiness", SOURCE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class LiveReadinessTests(unittest.TestCase):
    def check_session(self, properties, shell=True):
        def command(*args):
            if args[0] == "findmnt":
                return "overlay"
            if args[0] == "systemctl":
                return "active"
            if args[0] == "pgrep":
                return "123" if shell else ""
            if args[1] == "list-sessions":
                return "1 1000 localzet seat0"
            if args[1] == "show-session":
                return "\n".join(f"{k}={v}" for k, v in properties.items())
            raise AssertionError(args)
        with patch.object(probe.Path, "read_text", side_effect=[
            "boot=casper", 'ID=localzet'
        ]), patch.object(probe, "run", side_effect=command):
            return probe.readiness()

    def properties(self, **overrides):
        result = dict(Name="localzet", Active="yes", Type="wayland",
                      Class="user", Remote="no", Seat="seat0", Desktop="")
        result.update(overrides)
        return result

    def test_real_local_session_without_desktop_metadata(self):
        self.assertIsNone(self.check_session(self.properties()))

    def test_missing_compositor(self):
        self.assertIn('"gnome_shell":false', self.check_session(self.properties(), shell=False))

    def test_wrong_session_type(self):
        self.assertIsNotNone(self.check_session(self.properties(Type="tty")))

    def test_remote_and_greeter_sessions(self):
        for changes in ({"Remote": "yes"}, {"Class": "greeter"}, {"Name": "gdm"},
                        {"Seat": ""}, {"Active": "no"}):
            with self.subTest(changes=changes):
                self.assertIsNotNone(self.check_session(self.properties(**changes)))
