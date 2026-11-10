"""P1 visual heuristic must reject a dark greeter and accept wallpaper colors."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "session_visual", ROOT / "scripts/ci/assert-session-visual.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class P1VisualHeuristicTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(module.saturated_share([]), 0.0)

    def test_neutral_gdm_background(self):
        pixels = [(35, 34, 38)] * 100
        self.assertEqual(module.saturated_share(pixels), 0.0)

    def test_localzet_colored_wallpaper(self):
        pixels = [(38, 56, 110)] * 60 + [(37, 36, 42)] * 40
        self.assertGreater(module.saturated_share(pixels), 0.12)

    def test_threshold_boundary(self):
        self.assertEqual(module.saturated_share([(20, 54, 35)]), 0.0)
        self.assertEqual(module.saturated_share([(20, 56, 35)]), 1.0)


if __name__ == "__main__":
    unittest.main()
