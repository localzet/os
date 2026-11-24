import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qemu-live-visual.py"
sys.path.insert(0, str(SCRIPT.parent))

spec = importlib.util.spec_from_file_location("qemu_live_visual", SCRIPT)
assert spec and spec.loader
visual_script = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = visual_script
spec.loader.exec_module(visual_script)
choose_acceleration = visual_script.choose_acceleration


class QemuLiveVisualTests(unittest.TestCase):
    @patch("qemu_live_visual.os.access", return_value=True)
    def test_auto_uses_kvm_when_device_is_accessible(self, access):
        self.assertEqual(choose_acceleration("auto"), "kvm")
        access.assert_called_once()

    @patch("qemu_live_visual.os.access", return_value=False)
    def test_auto_falls_back_to_tcg_without_kvm_access(self, access):
        self.assertEqual(choose_acceleration("auto"), "tcg")
        access.assert_called_once()

    @patch("qemu_live_visual.os.access")
    def test_explicit_acceleration_does_not_depend_on_probe(self, access):
        self.assertEqual(choose_acceleration("kvm"), "kvm")
        self.assertEqual(choose_acceleration("tcg"), "tcg")
        access.assert_not_called()


if __name__ == "__main__":
    unittest.main()
