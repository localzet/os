import json
import unittest
from unittest.mock import patch
from localzet.hardware import PCIDevice
from localzet.hardware_firstboot import decode_state, identity, next_step


GPU = PCIDevice("0000:01:00.0", "10de", "1234", "030000", "nouveau")
AUDIO = PCIDevice("0000:01:00.1", "10de", "1234", "040300", "snd_hda_intel")


class FirstBootTests(unittest.TestCase):
    def previous(self, state, **kwargs):
        return {"schema": 1, "state": state, "hardware": identity((GPU,)),
                "boot_id": "first-boot", **kwargs}

    def test_no_nvidia_and_working_driver(self):
        self.assertEqual(next_step(None, (AUDIO,), "first-boot", False), "not-applicable")
        self.assertEqual(next_step(None, (GPU,), "first-boot", False), "driver")
        self.assertEqual(next_step(None, (GPU,), "first-boot", True), "cuda")

    def test_requires_new_boot_and_working_runtime(self):
        state = self.previous("awaiting-reboot")
        self.assertEqual(next_step(state, (GPU,), "first-boot", True), "awaiting-reboot")
        self.assertEqual(next_step(state, (GPU,), "second-boot", True), "cuda")
        self.assertEqual(next_step(state, (GPU,), "second-boot", False), "blocked")

    def test_offline_resume_and_changed_hardware(self):
        for phase in ("driver", "cuda"):
            state = self.previous("offline", phase=phase)
            self.assertEqual(next_step(state, (GPU,), "second-boot", True), "cuda")
            self.assertEqual(next_step(state, (), "second-boot", False), "blocked")
            self.assertEqual(next_step(state, (GPU,), "second-boot", False),
                             "driver" if phase == "driver" else "blocked")

    def test_interruption_and_terminal_states_never_retry(self):
        for state in ("driver-installing", "cuda-installing"):
            self.assertEqual(next_step(self.previous(state), (GPU,), "second-boot", True), "recovery-required")
        self.assertEqual(next_step(self.previous("compute-verification-required"), (), "second-boot", False), "blocked")
        for state in ("not-applicable", "blocked", "recovery-required", "compute-verification-required"):
            self.assertEqual(next_step(self.previous(state), (GPU,), "second-boot", True), state)

    def test_explicit_authorization_required(self):
        from localzet.hardware_firstboot import run
        with patch("localzet.hardware_firstboot.installed_system"), patch(
                "localzet.hardware_firstboot.authorized", return_value=False), patch(
                "localzet.hardware_firstboot.update_cache") as update, patch(
                "localzet.hardware_firstboot.transaction") as transaction:
            with self.assertRaisesRegex(ValueError, "authorization"):
                run()
            update.assert_not_called()
            transaction.assert_not_called()

    def test_general_policy_baseline_and_reboot(self):
        hardware = (GPU, AUDIO)
        state = {"schema": 1, "state": "base-awaiting-reboot",
                 "hardware": identity(hardware, True), "boot_id": "first"}
        self.assertEqual(next_step(None, hardware, "first", False, True), "base")
        self.assertEqual(next_step(state, hardware, "first", True, True), "base-awaiting-reboot")
        self.assertEqual(next_step(state, hardware, "second", False, True), "driver")
        self.assertEqual(next_step(state, hardware, "second", True, True), "cuda")
        self.assertEqual(next_step(state, (GPU,), "second", True, True), "blocked")

    def test_receipt_validation(self):
        valid = self.previous("offline", phase="driver")
        self.assertEqual(decode_state(json.dumps(valid).encode()), valid)
        self.assertIsNone(decode_state(None))
        for value in (None, [], {}, {**valid, "schema": True},
                      {**valid, "state": []}, {**valid, "state": "unknown"},
                      {**valid, "boot_id": ""}, {**valid, "hardware": ["bad"]},
                      {**valid, "phase": []}, {**valid, "phase": "unknown"}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "receipt"):
                decode_state(json.dumps(value).encode())
        with self.assertRaisesRegex(ValueError, "receipt"):
            decode_state(b"not-json")

    def test_invalid_receipt_never_touches_apt(self):
        from localzet.hardware_firstboot import run
        with patch("localzet.hardware_firstboot.installed_system"), patch(
                "localzet.hardware_firstboot.authorized", return_value="general"), patch(
                "localzet.hardware_firstboot.read_private", return_value=b"{}"), patch(
                "localzet.hardware_firstboot.inventory") as inventory, patch(
                "localzet.hardware_firstboot.update_cache") as update, patch(
                "localzet.hardware_firstboot.transaction") as transaction, patch.dict(
                "os.environ", {}, clear=False):
            with self.assertRaisesRegex(ValueError, "receipt"):
                run()
            inventory.assert_not_called()
            update.assert_not_called()
            transaction.assert_not_called()
