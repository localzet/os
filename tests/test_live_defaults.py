import runpy
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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

    def test_qemu_readiness_accepts_crlf_serial_marker(self):
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

            visual["wait_for_ready"](serial, RunningProcess(), 1, stderr)


if __name__ == "__main__":
    unittest.main()
