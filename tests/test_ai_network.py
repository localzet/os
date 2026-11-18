import unittest
from pathlib import Path
from localzet.ai_network import validate_endpoint, sandbox_command, PROXY


class AINetworkTests(unittest.TestCase):
    def test_local_manual_only(self):
        self.assertEqual(validate_endpoint("manual", "127.0.0.1", 7890, True), 7890)
        for row in (("none", "127.0.0.1", 7890, True),
                    ("auto", "127.0.0.1", 7890, True),
                    ("manual", "example.org", 7890, True),
                    ("manual", "127.0.0.1", 0, True),
                    ("manual", "127.0.0.1", 7890, False)):
            with self.assertRaises(ValueError):
                validate_endpoint(*row)

    def test_fixed_clients_isolation_and_no_proxy_exceptions(self):
        for tool in ("codex", "claude"):
            command = sandbox_command(tool, ["--version"], Path("/tmp/relay"),
                                      Path("/home/test"), Path("/home/test/project"))
            self.assertIn("--unshare-net", command)
            self.assertIn("--unshare-pid", command)
            self.assertIn("/usr/bin/localzet-ai", command)
            self.assertEqual(command[-3:], ["--inside", tool, "--version"])
            for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
                self.assertIn(["--setenv", key, PROXY], [command[i:i+3] for i in range(len(command))])
            for key in ("NO_PROXY", "no_proxy"):
                self.assertIn(["--setenv", key, ""], [command[i:i+3] for i in range(len(command))])
        with self.assertRaises(ValueError):
            sandbox_command("bash", [], Path("/tmp/relay"), Path("/home/test"), Path("/home/test"))

    def test_missing_gsettings_schema_is_detected_before_constructor(self):
        from unittest.mock import MagicMock, patch
        import sys
        from localzet.ai_network import usernet_port
        gio = MagicMock()
        gio.SettingsSchemaSource.get_default.return_value.lookup.return_value = None
        with patch.dict(sys.modules, {"gi.repository": MagicMock(Gio=gio)}):
            with self.assertRaisesRegex(ValueError, "GNOME"):
                usernet_port()
            gio.Settings.new.assert_not_called()
