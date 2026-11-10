"""Prevent accidental activation of incomplete installer configuration."""
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "packaging/calamares/staging"


class InstallerStagingTests(unittest.TestCase):
    def test_installer_stays_disabled(self):
        policy = tomllib.loads((ROOT / "config/installer/staging.toml").read_text())
        self.assertFalse(policy["release"]["enabled"])
        self.assertFalse(policy["release"]["ready_for_physical_disks"])
        self.assertFalse(policy["safety"]["allow_unattended_erase"])
        self.assertTrue(policy["safety"]["require_explicit_disk_selection"])
        self.assertTrue(policy["safety"]["require_destructive_confirmation"])

    def test_only_example_configs_exist(self):
        for name in ("settings", "partition", "users", "unpackfs"):
            self.assertTrue((BASE / f"{name}.conf.example").is_file())
            self.assertFalse((BASE / f"{name}.conf").exists())

    def test_partition_defaults_to_no_choice(self):
        self.assertIn("initialPartitioningChoice: none",
                      (BASE / "partition.conf.example").read_text())

    def test_installed_user_must_authenticate(self):
        text = (BASE / "users.conf.example").read_text()
        self.assertIn("displayAutologin: false", text)
        self.assertIn("doAutologin: false", text)
        self.assertIn("allowWeakPasswords: false", text)

    def test_installer_is_not_shipped_in_live_iso(self):
        builder = ROOT / "scripts/build-live-iso.sh"
        if builder.exists():
            text = builder.read_text()
            self.assertNotIn("packaging/calamares/staging", text)
            self.assertNotIn("apt-get install calamares", text)


if __name__ == "__main__":
    unittest.main()
