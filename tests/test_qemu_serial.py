import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qemu_serial import has_serial_marker, normalized_serial_lines, serial_integer


class QemuSerialTests(unittest.TestCase):
    marker = b"LOCALZET_LIVE_READY"

    def test_normalizes_systemd_ansi_clear_and_crlf(self):
        self.assertTrue(has_serial_marker(b"\x1b[KLOCALZET_LIVE_READY\r\n", self.marker))

    def test_accepts_plain_exact_line(self):
        self.assertTrue(has_serial_marker(b"booting\nLOCALZET_LIVE_READY\n", self.marker))

    def test_rejects_substrings_and_extended_marker_lines(self):
        false_positives = (
            b"prefix LOCALZET_LIVE_READY suffix\r\n",
            b"XLOCALZET_LIVE_READY\n",
            b"LOCALZET_LIVE_READY_EXTRA\n",
        )
        for data in false_positives:
            with self.subTest(data=data):
                self.assertFalse(has_serial_marker(data, self.marker))

    def test_reads_exact_graphical_vt_line_after_ansi_normalization(self):
        data = b"VTNr=8\r\n\x1b[KLOCALZET_LIVE_GRAPHICAL_VT=7\r\n"
        self.assertEqual(serial_integer(data, b"LOCALZET_LIVE_GRAPHICAL_VT"), 7)

    def test_rejects_conflicting_or_embedded_vt_values(self):
        self.assertIsNone(serial_integer(
            b"xLOCALZET_LIVE_GRAPHICAL_VT=7\n", b"LOCALZET_LIVE_GRAPHICAL_VT"
        ))
        self.assertIsNone(serial_integer(
            b"LOCALZET_LIVE_GRAPHICAL_VT=7\nLOCALZET_LIVE_GRAPHICAL_VT=8\n",
            b"LOCALZET_LIVE_GRAPHICAL_VT",
        ))

    def test_splits_carriage_return_and_lf_line_endings(self):
        self.assertEqual(normalized_serial_lines(b"one\rtwo\r\nthree\n"), [
            b"one", b"two", b"three", b"",
        ])


if __name__ == "__main__":
    unittest.main()
