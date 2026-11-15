import copy
import unittest
from unittest.mock import Mock
from localzet.hardware_install import apply_reviewed, fingerprint


def reviewed():
    return {"kernel": "7.0.0-15-generic", "secure_boot": "enabled",
            "graphics": [{"address": "0000:01:00.0", "vendor": "10de", "device": "1234",
                          "device_class": "030000", "driver": "nouveau"}],
            "targets": ["nvidia-driver-580"], "target_versions": {"nvidia-driver-580": "580.1"},
            "changes": [{"name": "nvidia-driver-580", "version": "580.1", "action": "install"}],
            "download_bytes": 100, "additional_installed_bytes": 200}


class HardwareInstallTests(unittest.TestCase):
    def test_changed_review_refuses_commit(self):
        approved = reviewed()
        for change in ("kernel", "secure_boot", "graphics", "target_versions", "changes"):
            current = copy.deepcopy(approved)
            current[change] = None
            cache = Mock()
            receipt = Mock()
            with self.assertRaisesRegex(ValueError, "changed"):
                apply_reviewed(cache, approved, review_fn=lambda _: current, receipt_fn=receipt)
            cache.commit.assert_not_called()
            cache.clear.assert_called_once()
            receipt.assert_not_called()

    def test_same_review_commits_exact_cache_and_records_success(self):
        cache = Mock()
        cache.commit.return_value = True
        approved = reviewed()
        current = copy.deepcopy(approved)
        current["download_bytes"] = 0
        self.assertEqual(fingerprint(approved), fingerprint(current))
        records = []
        state = apply_reviewed(cache, approved, review_fn=lambda _: current,
                               receipt_fn=lambda record: records.append(copy.deepcopy(record)))
        cache.commit.assert_called_once_with(allow_unauthenticated=False)
        self.assertEqual(state, "installed-reboot-verification-required")
        self.assertEqual([record["state"] for record in records],
                         ["installing", "installed-reboot-verification-required"])

    def test_failed_commit_leaves_recovery_receipt(self):
        cache = Mock()
        cache.commit.side_effect = RuntimeError("fixture failure")
        approved = reviewed()
        records = []
        with self.assertRaises(RuntimeError):
            apply_reviewed(cache, approved, review_fn=lambda _: approved,
                           receipt_fn=lambda record: records.append(copy.deepcopy(record)))
        self.assertEqual(records[-1]["state"], "failed-recovery-required")
        cache.commit.assert_called_once()

    def test_receipt_required_before_commit_and_noop(self):
        cache = Mock()
        approved = reviewed()
        with self.assertRaisesRegex(ValueError, "receipt"):
            apply_reviewed(cache, approved, review_fn=lambda _: approved)
        cache.commit.assert_not_called()
        approved["changes"] = []
        self.assertEqual(apply_reviewed(cache, approved, review_fn=lambda _: approved),
                         "already-installed")
        cache.commit.assert_not_called()

    def test_receipt_write_failure_blocks_install(self):
        cache = Mock()
        approved = reviewed()
        with self.assertRaises(OSError):
            apply_reviewed(cache, approved, review_fn=lambda _: approved,
                           receipt_fn=Mock(side_effect=OSError("disk full")))
        cache.commit.assert_not_called()
