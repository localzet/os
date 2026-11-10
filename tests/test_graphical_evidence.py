"""ANSI-aware systemd/Localzet boot evidence checks."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "graphical_evidence", ROOT / "scripts/ci/assert-graphical.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GraphicalEvidenceTests(unittest.TestCase):
    def test_plain_target_reached(self):
        self.assertTrue(module.reached_graphical(
            b"[ OK ] Reached target graphical.target - Graphical Interface.\n"
        ))

    def test_ansi_colored_target_reached(self):
        self.assertTrue(module.reached_graphical(
            b"[\x1b[0;32m  OK  \x1b[0m] Reached target "
            b"\x1b[0;1;39mgraphical.target\x1b[0m - Graphical Interface.\r\n"
        ))

    def test_not_confused_by_queued_target(self):
        self.assertFalse(module.reached_graphical(
            b"Queued start job for default target graphical.target.\n"
        ))

    def test_not_confused_by_failed_target(self):
        self.assertFalse(module.reached_graphical(
            b"Dependency failed for graphical.target - Graphical Interface.\n"
        ))

    def test_complete_live_evidence(self):
        raw = (b"LOCALZET_BOOT_EVIDENCE_BEGIN\n"
               b"gdm_state=active\ngraphical_target=active\n"
               b"sessions:\n 1 localzet seat0\n"
               b"LOCALZET_BOOT_EVIDENCE_END\n")
        self.assertTrue(module.reached_graphical(raw))

    def test_incomplete_live_evidence(self):
        raw = (b"LOCALZET_BOOT_EVIDENCE_BEGIN\n"
               b"gdm_state=active\ngraphical_target=active\n")
        self.assertFalse(module.reached_graphical(raw))

    def test_live_evidence_inactive_gdm(self):
        raw = (b"LOCALZET_BOOT_EVIDENCE_BEGIN\n"
               b"gdm_state=inactive\ngraphical_target=active\n"
               b"LOCALZET_BOOT_EVIDENCE_END\n")
        self.assertFalse(module.reached_graphical(raw))

    def test_live_evidence_does_not_mix_blocks(self):
        raw = (b"LOCALZET_BOOT_EVIDENCE_BEGIN\n"
               b"gdm_state=active\ngraphical_target=inactive\n"
               b"LOCALZET_BOOT_EVIDENCE_END\n"
               b"LOCALZET_BOOT_EVIDENCE_BEGIN\n"
               b"gdm_state=inactive\ngraphical_target=active\n"
               b"LOCALZET_BOOT_EVIDENCE_END\n")
        self.assertFalse(module.reached_graphical(raw))

    def test_random_graphical_active_not_evidence(self):
        self.assertFalse(module.reached_graphical(
            b"some unrelated text gdm_state=active graphical_target=active"
        ))

    def test_real_autologin_with_inactive_graphical_target(self):
        raw = (b"LOCALZET_BOOT_EVIDENCE_BEGIN\n"
               b"gdm_state=active\ngraphical_target=inactive\n"
               b"sessions:\n1 1000 localzet seat0 628 user tty2 no -\n"
               b"GNOME processes:\n"
               b"localzet gnome-shell /usr/bin/gnome-shell --mode=user\n"
               b"LOCALZET_BOOT_EVIDENCE_END\n")
        self.assertTrue(module.reached_graphical(raw))

    def test_gdm_greeter_without_user_shell_is_not_enough(self):
        raw = (b"LOCALZET_BOOT_EVIDENCE_BEGIN\n"
               b"gdm_state=active\ngraphical_target=inactive\n"
               b"sessions:\n1 1000 localzet seat0 628 user tty2 no -\n"
               b"GNOME processes:\n"
               b"gdm gnome-shell /usr/bin/gnome-shell --mode=gdm\n"
               b"LOCALZET_BOOT_EVIDENCE_END\n")
        self.assertFalse(module.reached_graphical(raw))

    def test_user_shell_without_real_login_session_fails(self):
        raw = (b"LOCALZET_BOOT_EVIDENCE_BEGIN\n"
               b"gdm_state=active\ngraphical_target=inactive\n"
               b"sessions:\n"
               b"GNOME processes:\n"
               b"localzet gnome-shell /usr/bin/gnome-shell --mode=user\n"
               b"LOCALZET_BOOT_EVIDENCE_END\n")
        self.assertFalse(module.reached_graphical(raw))

    def test_empty_log(self):
        self.assertFalse(module.reached_graphical(b""))


if __name__ == "__main__":
    unittest.main()
