import json
from pathlib import Path
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from localzet.settings.appearance import (
    AppearanceError,
    BACKGROUND_SCHEMA,
    EXTENSION_SCHEMA,
    INTERFACE_SCHEMA,
    PTYXIS_PROFILE_SCHEMA,
    PTYXIS_SCHEMA,
    apply_appearance,
    current_appearance,
    restore_appearance,
    state_path,
)


class FakeSettings:
    def __init__(self, *, extension=True):
        self.values = {
            (INTERFACE_SCHEMA, "accent-color"): "blue",
            (INTERFACE_SCHEMA, "color-scheme"): "default",
            (INTERFACE_SCHEMA, "icon-theme"): "Adwaita",
            (INTERFACE_SCHEMA, "gtk-theme"): "Yaru-dark",
            (BACKGROUND_SCHEMA, "picture-uri"): "file:///usr/share/backgrounds/old.jpg",
            (BACKGROUND_SCHEMA, "picture-uri-dark"): "file:///usr/share/backgrounds/old-dark.jpg",
        }
        if extension:
            self.values[(EXTENSION_SCHEMA, "appearance")] = "blue"
        self.fail_once = None

    def supports(self, schema, key):
        return (schema, key) in self.values

    def get(self, schema, key):
        return self.values[(schema, key)]

    def set(self, schema, key, value):
        identity = (schema, key)
        if self.fail_once == identity:
            self.fail_once = None
            raise RuntimeError("simulated setting failure")
        self.values[identity] = value


class AppearanceTests(unittest.TestCase):
    def setUp(self):
        state_home = tempfile.TemporaryDirectory()
        self.addCleanup(state_home.cleanup)
        environment = patch.dict("os.environ", {"XDG_STATE_HOME": state_home.name})
        environment.start()
        self.addCleanup(environment.stop)

    def test_ptyxis_palette_tracks_theme_and_is_restored(self):
        profile_uuid = "a3d6b7e2-186b-4b5b-9225-6abcde123456"
        profile_schema = (
            f"{PTYXIS_PROFILE_SCHEMA}:/org/gnome/Ptyxis/Profiles/"
            f"{profile_uuid}/"
        )
        settings = FakeSettings()
        settings.values[(PTYXIS_SCHEMA, "default-profile-uuid")] = profile_uuid
        settings.values[(profile_schema, "palette")] = "Ubuntu"
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"XDG_DATA_HOME": directory}):
                snapshot = Path(directory) / "appearance.json"
                apply_appearance("purple", store=settings, snapshot=snapshot)
                self.assertEqual(settings.get(profile_schema, "palette"), "Aurora Purple")
                palette_dir = Path(directory) / "org.gnome.Ptyxis" / "palettes"
                self.assertTrue((palette_dir / "Aurora Blue.palette").is_file())
                self.assertTrue((palette_dir / "Aurora Purple.palette").is_file())
                self.assertTrue((palette_dir / "Aurora Black.palette").is_file())

                result = restore_appearance(store=settings, snapshot=snapshot)

        self.assertEqual(result.pending, 0)
        self.assertEqual(settings.get(profile_schema, "palette"), "Ubuntu")

    def test_gtk_theme_tracks_aurora_variant_and_restores_previous_theme(self):
        settings = FakeSettings()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            apply_appearance("purple", store=settings, snapshot=snapshot)
            self.assertEqual(
                settings.get(INTERFACE_SCHEMA, "gtk-theme"),
                "Localzet-Aurora-Purple",
            )

            restore_appearance(store=settings, snapshot=snapshot)

        self.assertEqual(settings.get(INTERFACE_SCHEMA, "gtk-theme"), "Yaru-dark")

    def test_snapshot_rejects_untrusted_ptyxis_profile_path(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            snapshot.write_text(json.dumps([{
                "schema": f"{PTYXIS_PROFILE_SCHEMA}:/org/gnome/Ptyxis/Profiles/../../",
                "key": "palette",
                "value": "Ubuntu",
            }]), encoding="utf-8")
            with self.assertRaisesRegex(AppearanceError, "неизвестные настройки"):
                restore_appearance(store=FakeSettings(), snapshot=snapshot)

    def test_invalid_theme_does_not_modify_settings(self):
        settings = FakeSettings()
        before = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(AppearanceError):
                apply_appearance("orange", store=settings, snapshot=Path(directory) / "appearance.json")
        self.assertEqual(settings.values, before)

    def test_switch_keeps_original_snapshot_and_restore_returns_every_value(self):
        settings = FakeSettings()
        before = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            apply_appearance("purple", store=settings, snapshot=snapshot)
            first_snapshot = json.loads(snapshot.read_text())
            self.assertEqual(settings.get(INTERFACE_SCHEMA, "accent-color"), "purple")
            apply_appearance("black", store=settings, snapshot=snapshot)
            self.assertEqual(json.loads(snapshot.read_text()), first_snapshot)
            self.assertEqual(settings.get(EXTENSION_SCHEMA, "appearance"), "black")
            self.assertEqual(settings.get(INTERFACE_SCHEMA, "accent-color"), "purple")
            result = restore_appearance(store=settings, snapshot=snapshot)
            self.assertEqual(result.restored, len(before))
            self.assertEqual(result.pending, 0)
            self.assertEqual(settings.values, before)
            self.assertFalse(snapshot.exists())

    def test_restore_waits_for_in_progress_apply(self):
        apply_started = Event()
        allow_apply_to_finish = Event()
        restore_started = Event()

        class BlockingSettings(FakeSettings):
            def set(self, schema, key, value):
                super().set(schema, key, value)
                if (schema, key, value) == (EXTENSION_SCHEMA, "appearance", "purple"):
                    apply_started.set()
                    if not allow_apply_to_finish.wait(timeout=5):
                        raise RuntimeError("timed out waiting for test release")

        settings = BlockingSettings()
        before = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            with ThreadPoolExecutor(max_workers=2) as executor:
                applying = executor.submit(
                    apply_appearance, "purple", store=settings, snapshot=snapshot
                )
                self.assertTrue(apply_started.wait(timeout=2))

                def restore():
                    restore_started.set()
                    return restore_appearance(store=settings, snapshot=snapshot)

                restoring = executor.submit(restore)
                try:
                    self.assertTrue(restore_started.wait(timeout=2))
                    time.sleep(0.05)
                    self.assertFalse(restoring.done())
                finally:
                    allow_apply_to_finish.set()

                applying.result(timeout=2)
                result = restoring.result(timeout=2)

            self.assertEqual(result.pending, 0)
            self.assertEqual(settings.values, before)
            self.assertFalse(snapshot.exists())

    def test_parallel_apply_calls_preserve_the_original_restore_point(self):
        apply_started = Event()
        allow_apply_to_finish = Event()

        class BlockingSettings(FakeSettings):
            def set(self, schema, key, value):
                super().set(schema, key, value)
                if (schema, key, value) == (EXTENSION_SCHEMA, "appearance", "purple"):
                    apply_started.set()
                    if not allow_apply_to_finish.wait(timeout=5):
                        raise RuntimeError("timed out waiting for test release")

        settings = BlockingSettings()
        before = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            with ThreadPoolExecutor(max_workers=2) as executor:
                applying_purple = executor.submit(
                    apply_appearance, "purple", store=settings, snapshot=snapshot
                )
                self.assertTrue(apply_started.wait(timeout=2))
                applying_black = executor.submit(
                    apply_appearance, "black", store=settings, snapshot=snapshot
                )
                try:
                    time.sleep(0.05)
                    self.assertFalse(applying_black.done())
                finally:
                    allow_apply_to_finish.set()

                applying_purple.result(timeout=2)
                applying_black.result(timeout=2)

            self.assertEqual(settings.get(EXTENSION_SCHEMA, "appearance"), "black")
            result = restore_appearance(store=settings, snapshot=snapshot)
            self.assertEqual(result.pending, 0)
            self.assertEqual(settings.values, before)
            self.assertFalse(snapshot.exists())

    def test_missing_shell_extension_applies_general_theme_and_restores(self):
        settings = FakeSettings(extension=False)
        before = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            changed = apply_appearance("purple", store=settings, snapshot=snapshot)
            self.assertEqual(len(changed), len(before))
            self.assertNotIn((EXTENSION_SCHEMA, "appearance"), settings.values)
            self.assertEqual(current_appearance(settings), "purple")
            result = restore_appearance(store=settings, snapshot=snapshot)
            self.assertEqual(result.restored, len(before))
            self.assertEqual(result.pending, 0)
            self.assertEqual(current_appearance(settings), "blue")
        self.assertEqual(settings.values, before)

    def test_restore_keeps_shell_setting_pending_when_extension_is_removed(self):
        settings = FakeSettings()
        before = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            apply_appearance("purple", store=settings, snapshot=snapshot)
            del settings.values[(EXTENSION_SCHEMA, "appearance")]

            result = restore_appearance(store=settings, snapshot=snapshot)

            self.assertEqual(result.restored, len(before) - 1)
            self.assertEqual(result.pending, 1)
            self.assertEqual(
                {(item["schema"], item["key"], item["value"])
                 for item in json.loads(snapshot.read_text())},
                {(EXTENSION_SCHEMA, "appearance", "blue")},
            )
            settings.values[(EXTENSION_SCHEMA, "appearance")] = "purple"
            result = restore_appearance(store=settings, snapshot=snapshot)

            self.assertEqual(result.restored, 1)
            self.assertEqual(result.pending, 0)
            self.assertEqual(settings.values, before)
            self.assertFalse(snapshot.exists())

    def test_legacy_snapshot_restores_local_fallback_from_shell_value(self):
        settings = FakeSettings()
        original = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            apply_appearance("purple", store=settings, snapshot=snapshot)
            values = [
                item for item in json.loads(snapshot.read_text())
                if not (item["schema"] == "com.localzet.settings" and item["key"] == "appearance")
            ]
            snapshot.write_text(json.dumps(values), encoding="utf-8")
            del settings.values[(EXTENSION_SCHEMA, "appearance")]

            result = restore_appearance(store=settings, snapshot=snapshot)

            self.assertEqual(result.pending, 1)
            self.assertEqual(current_appearance(settings), original[(EXTENSION_SCHEMA, "appearance")])
            self.assertEqual(
                {(item["schema"], item["key"]) for item in json.loads(snapshot.read_text())},
                {(EXTENSION_SCHEMA, "appearance")},
            )

    def test_newly_available_shell_schema_is_added_to_restore_snapshot(self):
        settings = FakeSettings(extension=False)
        before = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            apply_appearance("purple", store=settings, snapshot=snapshot)
            settings.values[(EXTENSION_SCHEMA, "appearance")] = "blue"
            before[(EXTENSION_SCHEMA, "appearance")] = "blue"
            apply_appearance("black", store=settings, snapshot=snapshot)
            restore_appearance(store=settings, snapshot=snapshot)
        self.assertEqual(settings.values, before)

    def test_apply_rolls_back_partial_changes_and_keeps_recovery_file(self):
        settings = FakeSettings()
        before = settings.values.copy()
        settings.fail_once = (INTERFACE_SCHEMA, "icon-theme")
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            with self.assertRaises(AppearanceError):
                apply_appearance("black", store=settings, snapshot=snapshot)
            self.assertEqual(settings.values, before)
            self.assertTrue(snapshot.is_file())

    def test_unwritable_snapshot_is_reported_before_settings_change(self):
        settings = FakeSettings()
        before = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            blocked_parent = Path(directory) / "file-not-directory"
            blocked_parent.write_text("block", encoding="utf-8")
            with self.assertRaises(AppearanceError):
                apply_appearance(
                    "black",
                    store=settings,
                    snapshot=blocked_parent / "appearance.json",
                )
        self.assertEqual(settings.values, before)

    def test_relative_xdg_state_home_is_rejected_before_settings_change(self):
        settings = FakeSettings()
        before = settings.values.copy()
        with patch.dict("os.environ", {"XDG_STATE_HOME": "relative-state"}):
            with self.assertRaises(AppearanceError):
                apply_appearance("purple", store=settings)
        self.assertEqual(settings.values, before)

    def test_snapshot_removal_failure_is_reported_after_restore(self):
        settings = FakeSettings()
        before = settings.values.copy()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            apply_appearance("black", store=settings, snapshot=snapshot)
            real_unlink = Path.unlink

            def reject_snapshot_unlink(path, *args, **kwargs):
                if path == snapshot:
                    raise PermissionError("simulated permission error")
                return real_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", reject_snapshot_unlink):
                with self.assertRaises(AppearanceError):
                    restore_appearance(store=settings, snapshot=snapshot)

            self.assertEqual(settings.values, before)
            self.assertTrue(snapshot.is_file())

    def test_corrupt_snapshot_is_not_applied_or_deleted(self):
        settings = FakeSettings()
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "appearance.json"
            invalid_snapshots = (
                '[{"schema": [], "key": "appearance", "value": "blue"}]',
                '[{"schema": "com.localzet.settings", "key": {}, "value": "blue"}]',
                '[{"schema": "com.localzet.settings", "key": "appearance", "value": []}]',
                '[{"schema": "org.gnome.shell", "key": "enabled-extensions", "value": "bad"}]',
            )
            for raw in invalid_snapshots:
                with self.subTest(snapshot=raw):
                    snapshot.write_text(raw, encoding="utf-8")
                    with self.assertRaises(AppearanceError):
                        restore_appearance(store=settings, snapshot=snapshot)
            self.assertTrue(snapshot.is_file())

            snapshot.write_bytes(b"\xff")
            with self.assertRaises(AppearanceError):
                restore_appearance(store=settings, snapshot=snapshot)
            self.assertTrue(snapshot.is_file())

    def test_current_appearance_uses_blue_when_shell_schema_is_unavailable(self):
        self.assertEqual(current_appearance(FakeSettings(extension=False)), "blue")

    def test_corrupt_local_theme_falls_back_to_blue(self):
        settings = FakeSettings(extension=False)
        path = state_path().with_name("appearance-current.json")
        path.parent.mkdir(parents=True)
        path.write_text('{"appearance": []}', encoding="utf-8")
        self.assertEqual(current_appearance(settings), "blue")

        path.write_bytes(b"\xff")
        self.assertEqual(current_appearance(settings), "blue")


if __name__ == "__main__":
    unittest.main()
