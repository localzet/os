"""Fail-closed selection tests for temporary Live seat recovery."""
import unittest
from localzet.live.seatguard import candidate_session, may_recover


def session(name, klass, service, state="online", seat="seat0", kind="wayland"):
    return {"Name": name, "Class": klass, "Service": service, "State": state,
            "Seat": seat, "Type": kind}


class SeatGuardTests(unittest.TestCase):
    def setUp(self):
        self.sessions = {
            "1": session("localzet", "user", "gdm-autologin"),
            "c1": session("gdm-greeter", "greeter", "gdm-launch-environment"),
        }

    def test_recovery_rate_limit(self):
        self.assertTrue(may_recover(0, 100.0, 0.0))
        self.assertFalse(may_recover(1, 120.0, 100.0))
        self.assertTrue(may_recover(1, 126.0, 100.0))

    def test_max_four_recoveries(self):
        self.assertFalse(may_recover(4, 300.0, 0.0))
        self.assertFalse(may_recover(9, 300.0, 0.0))

    def test_displaced_session(self):
        self.assertEqual(candidate_session(self.sessions, "c1"), "1")

    def test_active_user_no_action(self):
        self.assertIsNone(candidate_session(self.sessions, "1"))

    def test_not_a_greeter(self):
        self.sessions["c1"]["Class"] = "user"
        self.assertIsNone(candidate_session(self.sessions, "c1"))

    def test_no_live_user(self):
        del self.sessions["1"]
        self.assertIsNone(candidate_session(self.sessions, "c1"))

    def test_other_user(self):
        self.sessions["1"]["Name"] = "admin"
        self.assertIsNone(candidate_session(self.sessions, "c1"))

    def test_manual_authentication_not_targeted(self):
        self.sessions["1"]["Service"] = "gdm-password"
        self.assertIsNone(candidate_session(self.sessions, "c1"))

    def test_not_wayland(self):
        self.sessions["1"]["Type"] = "tty"
        self.assertIsNone(candidate_session(self.sessions, "c1"))

    def test_other_seat(self):
        self.sessions["1"]["Seat"] = "seat1"
        self.assertIsNone(candidate_session(self.sessions, "c1"))

    def test_duplicate_candidates(self):
        self.sessions["2"] = self.sessions["1"].copy()
        self.assertIsNone(candidate_session(self.sessions, "c1"))

    def test_missing_active_session(self):
        self.assertIsNone(candidate_session(self.sessions, "unknown"))

    def test_session_closing(self):
        self.sessions["1"]["State"] = "closing"
        self.assertIsNone(candidate_session(self.sessions, "c1"))


if __name__ == "__main__":
    unittest.main()
