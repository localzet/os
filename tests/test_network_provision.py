import unittest
from unittest.mock import patch
from localzet import network_provision as n


class NetworkProvisionTests(unittest.TestCase):
    def test_fixed_commands(self):
        self.assertEqual(n.command("netbird"), ["/usr/bin/pkexec", "/usr/lib/localzet/install-netbird"])
        self.assertEqual(n.command("usernet"), ["/usr/bin/pkexec", "/usr/lib/localzet/install-usernet"])
        with self.assertRaises(ValueError):
            n.command("https://example.invalid/evil")

    def test_live_or_root_or_foreign_os_never_available(self):
        with patch.object(n.os, "geteuid", return_value=0):
            self.assertFalse(n.available("netbird"))
        with patch.object(n.os, "geteuid", return_value=1000), patch.object(n.Path, "read_text", return_value="boot=casper"):
            self.assertFalse(n.available("usernet"))
        with patch.object(n.os, "geteuid", return_value=1000), patch.object(n.Path, "read_text", side_effect=["quiet", "ID=ubuntu"]):
            self.assertFalse(n.available("netbird"))
