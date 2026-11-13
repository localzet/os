"""Post-install audit must detect Live-only secrets and services."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from localzet.installer.audit import audit_installed_root


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write("etc/os-release", "NAME=Localzet OS\n")
        self.write("etc/passwd", "root:x:0:0:root:/root:/bin/bash\nalice:x:1000:1000::/home/alice:/bin/bash\n")
        self.write("etc/shadow", "root:!:0:0:99999:7:::\nalice:$y$hashed:0:0:99999:7:::\n")
        self.write("etc/gdm3/custom.conf", "[daemon]\nAutomaticLoginEnable=False\n")

    def write(self, rel, contents):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contents)

    def check(self):
        return audit_installed_root(self.root)

    def test_clean_rootfs_passes(self):
        self.assertTrue(self.check()["safe_to_release"])
        self.assertIs(self.check()["writes_performed"], False)

    def test_live_account_blocked_even_if_locked_without_home(self):
        self.write("etc/passwd",
                   "root:x:0:0:root:/root:/bin/bash\n"
                   "localzet:x:1000:1000::/home/localzet:/bin/bash\n")
        self.write("etc/shadow",
                   "root:!:0:0:99999:7:::\n"
                   "localzet:!:0:0:99999:7:::\n")
        result = self.check()
        self.assertFalse(result["safe_to_release"])
        self.assertTrue(any("Live account" in p for p in result["problems"]))

    def test_live_account_name_only_matches_exact_username(self):
        self.write("etc/passwd",
                   "root:x:0:0:root:/root:/bin/bash\n"
                   "localzet-admin:x:1000:1000::/home/localzet-admin:/bin/bash\n")
        self.assertTrue(self.check()["safe_to_release"])

    def test_live_passwordless_sudo_blocked(self):
        self.write("etc/sudoers.d/90-localzet-live", "localzet ALL=(ALL) NOPASSWD:ALL\n")
        self.assertFalse(self.check()["safe_to_release"])

    def test_live_seat_guard_blocked(self):
        self.write("etc/systemd/system/localzet-live-seat-guard.service", "service\n")
        self.assertFalse(self.check()["safe_to_release"])

    def test_boot_diagnostics_blocked(self):
        self.write("usr/local/bin/localzet-boot-diagnostics", "script\n")
        self.assertFalse(self.check()["safe_to_release"])

    def test_empty_password_blocked(self):
        self.write("etc/shadow", "root:!:0:0:99999:7:::\nlocalzet::0:0:99999:7:::\n")
        self.assertTrue(any("empty password" in p for p in self.check()["problems"]))

    def test_live_autologin_blocked(self):
        self.write("etc/gdm3/custom.conf", "[daemon]\nAutomaticLoginEnable=True\nAutomaticLogin=localzet\n")
        self.assertFalse(self.check()["safe_to_release"])

    def test_timed_login_blocked(self):
        self.write("etc/gdm3/custom.conf", "[daemon]\nTimedLoginEnable=true\nTimedLogin=alice\n")
        self.assertFalse(self.check()["safe_to_release"])

    def test_alternate_gdm_config_blocked(self):
        self.write("etc/gdm/custom.conf", "[daemon]\nAutomaticLoginEnable=TRUE\n")
        self.assertFalse(self.check()["safe_to_release"])

    def test_gdm_symlink_rejected(self):
        path = self.root / "etc/gdm3/custom.conf"
        path.unlink()
        path.symlink_to("/nonexistent")
        self.assertFalse(self.check()["safe_to_release"])

    def test_orphan_live_shadow_blocked(self):
        self.write("etc/shadow", "root:!:0:0:99999:7:::\nlocalzet:!:0:0:99999:7:::\n")
        self.assertFalse(self.check()["safe_to_release"])

    def test_dangling_live_home_blocked(self):
        (self.root / "home").mkdir()
        (self.root / "home/localzet").symlink_to("/nonexistent")
        self.assertFalse(self.check()["safe_to_release"])

    def test_live_lock_settings_blocked(self):
        self.write("etc/dconf/db/localzet.d/00-defaults",
                   "[org/gnome/desktop/screensaver]\nlock-enabled=false\n")
        self.assertFalse(self.check()["safe_to_release"])

    def test_home_directory_blocked(self):
        (self.root / "home/localzet").mkdir(parents=True)
        self.assertFalse(self.check()["safe_to_release"])

    def test_live_readiness_artifacts_blocked(self):
        for relative in (
            "usr/lib/localzet/localzet-live-ready.py",
            "usr/lib/systemd/system/localzet-live-ready.service",
            "etc/systemd/system/graphical.target.wants/localzet-live-ready.service",
        ):
            with self.subTest(relative=relative):
                self.write(relative, "live-only\n")
                self.assertFalse(self.check()["safe_to_release"])
                (self.root / relative).unlink()

    def test_missing_shadow_rejected(self):
        (self.root / "etc/shadow").unlink()
        self.assertFalse(self.check()["safe_to_release"])

    def test_symlink_to_outside_rejected(self):
        (self.root / "etc/shadow").unlink()
        (self.root / "etc/shadow").symlink_to("/etc/shadow")
        result = self.check()
        self.assertFalse(result["safe_to_release"])
        self.assertTrue(any("unreadable" in p for p in result["problems"]))


if __name__ == "__main__":
    unittest.main()
