import runpy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class LiveDefaultsTests(unittest.TestCase):
    def test_first_login_uses_aurora_blue_and_localzet_icons(self):
        customizer = (ROOT / "packaging/live/customize-rootfs.sh").read_text(
            encoding="utf-8"
        )
        defaults = customizer.split("[org/gnome/desktop/background]", 1)[1].split(
            "[org/gnome/desktop/input-sources]", 1
        )[0]

        self.assertIn(
            "picture-uri='file:///usr/share/backgrounds/localzet/aurora-blue.webp'",
            defaults,
        )
        self.assertIn(
            "picture-uri-dark='file:///usr/share/backgrounds/localzet/aurora-blue.webp'",
            defaults,
        )
        self.assertIn("icon-theme='Localzet'", defaults)
        self.assertIn("accent-color='blue'", defaults)
        self.assertTrue((ROOT / "assets/wallpapers/aurora-blue.webp").is_file())
        self.assertNotIn("aurora.svg", defaults)
        self.assertIn(
            'gnome-icon-resolution-smoke.py" "$root/usr/lib/localzet/gnome-icon-resolution-smoke.py"',
            customizer,
        )
        self.assertIn(
            'gnome-shell-log-smoke.py" "$root/usr/lib/localzet/gnome-shell-log-smoke.py"',
            customizer,
        )

    def test_dock_tracks_and_disconnects_pinned_app_changes(self):
        dock = (
            ROOT / "extensions/localzet-shell@localzet.com/dock.js"
        ).read_text(encoding="utf-8")

        self.assertIn("'changed::pinned-apps'", dock)
        self.assertIn("this._settings.disconnect(this._pinnedAppsChanged)", dock)
        self.assertIn("this._pinnedAppsChanged = 0", dock)

    def test_live_image_has_gsettings_and_notification_commands(self):
        rootfs_builder = (ROOT / "scripts/build-live-rootfs.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("libglib2.0-bin", rootfs_builder)
        self.assertIn("libnotify-bin", rootfs_builder)

    def test_visual_control_agent_is_opt_in_for_disposable_visual_builds(self):
        rootfs_builder = (ROOT / "scripts/build-live-rootfs.sh").read_text(
            encoding="utf-8"
        )
        customizer = (ROOT / "packaging/live/customize-rootfs.sh").read_text(
            encoding="utf-8"
        )
        workflow = (ROOT / ".github/workflows/live-iso.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn('LOCALZET_LIVE_VISUAL_TEST:-0', rootfs_builder)
        self.assertIn('LOCALZET_LIVE_VISUAL_TEST:-0', customizer)
        self.assertIn('LOCALZET_LIVE_VISUAL_TEST=1', workflow)
        self.assertIn('scripts/gnome-visual-test-agent.py"', customizer)
        self.assertIn('python3-pyatspi', rootfs_builder)
        udev_rule = (
            ROOT / "packaging/live/90-localzet-visual-test-uaccess.rules"
        ).read_text(encoding="utf-8")
        autostart = (
            ROOT / "packaging/live/localzet-visual-test-agent.desktop"
        ).read_text(encoding="utf-8")

        self.assertIn('OWNER="1000"', udev_rule)
        self.assertIn('MODE="0600"', udev_rule)
        self.assertIn('X-GNOME-Autostart-Phase=Applications', autostart)

    def test_qemu_readiness_accepts_crlf_serial_marker(self):
        visual = runpy.run_path(
            str(ROOT / "scripts/qemu-live-visual.py"), run_name="visual_test"
        )
        with tempfile.TemporaryDirectory() as directory:
            serial = Path(directory) / "serial.log"
            stderr = Path(directory) / "qemu-stderr.log"
            serial.write_bytes(
                b"\x1b[KLOCALZET_LIVE_GRAPHICAL_VT=7\r\n"
                b"\x1b[KLOCALZET_LIVE_READY\r\n"
            )
            stderr.write_text("", encoding="utf-8")

            class RunningProcess:
                def poll(self):
                    return None

            self.assertEqual(
                visual["wait_for_ready"](serial, RunningProcess(), 1, stderr),
                7,
            )

    def test_qemu_readiness_requires_logind_graphical_vt(self):
        visual = runpy.run_path(
            str(ROOT / "scripts/qemu-live-visual.py"), run_name="visual_test"
        )
        with tempfile.TemporaryDirectory() as directory:
            serial = Path(directory) / "serial.log"
            stderr = Path(directory) / "qemu-stderr.log"
            serial.write_bytes(b"LOCALZET_LIVE_READY\r\n")
            stderr.write_text("", encoding="utf-8")

            class RunningProcess:
                def poll(self):
                    return None

            with self.assertRaisesRegex(RuntimeError, "graphical VT"):
                visual["wait_for_ready"](serial, RunningProcess(), 1, stderr)

    def test_qemu_keyboard_maps_enter_to_qcode_ret(self):
        visual = runpy.run_path(
            str(ROOT / "scripts/qemu-live-visual.py"), run_name="visual_test"
        )
        calls = []

        class RecordingQMP:
            def execute(self, command, arguments):
                calls.append((command, arguments))

        visual["press"](RecordingQMP(), "enter")

        self.assertEqual(calls[0][0], "send-key")
        self.assertEqual(calls[0][1]["keys"], [{"type": "qcode", "data": "ret"}])


if __name__ == "__main__":
    unittest.main()
