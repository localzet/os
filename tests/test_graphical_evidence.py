"""ANSI-aware systemd graphical.target evidence checks."""
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

    def test_empty_log(self):
        self.assertFalse(module.reached_graphical(b""))


if __name__ == "__main__":
    unittest.main()
