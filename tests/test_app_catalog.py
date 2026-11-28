import unittest
from unittest.mock import patch
from localzet import app_catalog as c


class AppCatalogTests(unittest.TestCase):
    def test_curated_installs_are_user_confirmed_and_fixed(self):
        for key, app in c.APPS.items():
            if not app.flatpak_id:
                continue
            cmd = c.install_command(key)
            self.assertEqual(cmd[:4], ("/usr/bin/flatpak", "install", "--user", "--from"))
            self.assertEqual(cmd[-1], "https://dl.flathub.org/repo/appstream/" + app.flatpak_id + ".flatpakref")
            self.assertNotIn("-y", cmd)
            self.assertNotIn("--noninteractive", cmd)
            self.assertEqual(c.terminal_command(key)[-len(cmd):], cmd)
        with self.assertRaises(KeyError):
            c.install_command("https://example.invalid/evil")
        with self.assertRaises(ValueError):
            c.install_command("vscode")

    def test_installed_and_missing_states_are_distinct(self):
        with patch.object(c, "executable", return_value=True):
            self.assertEqual(c.action("lutris", frozenset()), ("launch", ("/usr/games/lutris",)))
            self.assertEqual(c.action("steam", frozenset())[0], "install")
            self.assertEqual(c.action("steam", frozenset({"com.valvesoftware.Steam"})),
                             ("launch", ("/usr/bin/flatpak", "run", "com.valvesoftware.Steam")))
        with patch.object(c, "executable", return_value=False):
            self.assertEqual(c.action("lutris", frozenset())[0], "missing")
            self.assertEqual(c.action("steam", frozenset())[0], "website")
            self.assertEqual(c.action("music", frozenset()), ("website", "https://music.yandex.ru/download/"))

    def test_workspace_filter_uses_real_launch_states(self):
        states = {"lutris": "launch", "steam": "install", "vscode": "website"}
        self.assertEqual(c.visible_keys("installed", "", states), ("lutris",))
        self.assertEqual(c.visible_keys("Игры", "steam", states), ("steam",))
        self.assertEqual(c.visible_keys("Офис", "steam", states), ())
        self.assertEqual(c.visible_keys("all", "VISUAL studio", states), ("vscode",))
        self.assertEqual(c.visible_keys("unknown", "", states), ())

    def test_office_uses_managed_launcher_only_when_real_editor_exists(self):
        with patch.object(c, "executable", return_value=True):
            self.assertEqual(c.action("office", frozenset()), ("launch", ("/usr/bin/localzet-office",)))
        with patch.object(c, "executable", side_effect=lambda p: p == "/usr/bin/localzet-office"):
            self.assertEqual(c.action("office", frozenset())[0], "website")
        with patch.object(c, "executable", side_effect=lambda p: p == "/usr/bin/onlyoffice-desktopeditors"):
            self.assertEqual(c.action("office", frozenset()), ("launch", ("/usr/bin/onlyoffice-desktopeditors",)))

    def test_native_vendor_apps_are_detected_without_reinstall(self):
        for key, path in (("vscode", "/usr/bin/code"), ("chrome", "/usr/bin/google-chrome-stable"),
                          ("edge", "/usr/bin/microsoft-edge-stable")):
            with patch.object(c, "executable", side_effect=lambda p: p == path):
                self.assertEqual(c.action(key, frozenset()), ("launch", (path,)))
            with patch.object(c, "executable", return_value=False):
                self.assertEqual(c.action(key, frozenset())[0], "website")

    def test_aurora_icon_theme_covers_every_catalog_entry(self):
        import importlib.util
        from pathlib import Path
        from tempfile import TemporaryDirectory

        script = Path(__file__).resolve().parents[1] / "scripts/build-aurora-icons.py"
        spec = importlib.util.spec_from_file_location("build_aurora_icons", script)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)

        with TemporaryDirectory(prefix="localzet-aurora-icons-") as directory:
            theme = builder.build(directory)
            apps = theme / "scalable" / "apps"
            for app in c.APPS.values():
                with self.subTest(icon=app.icon):
                    self.assertTrue((apps / (app.icon + ".svg")).is_file(), app.icon)

    def test_catalog_covers_installed_system_and_media_apps(self):
        for key, path in (("files", "/usr/bin/nautilus"), ("containers", "/usr/bin/localzet-containers"),
                          ("vlc", "/usr/bin/vlc"), ("windows", "/usr/bin/localzet-windows"),
                          ("virtual-machines", "/usr/bin/virt-manager")):
            with patch.object(c, "executable", side_effect=lambda p: p == path):
                self.assertEqual(c.action(key, frozenset()), ("launch", (path,)))
            with patch.object(c, "executable", return_value=False):
                self.assertEqual(c.action(key, frozenset())[0], "missing")
        self.assertIn("hardware", c.visible_keys("Система", "CUDA", {}))
        self.assertEqual(c.action_source("telegram", "launch", (c.FLATPAK, "run", "org.telegram.desktop")), "Flatpak")
        self.assertEqual(c.action_source("vlc", "launch", ("/usr/bin/vlc",)), "Локально")
        self.assertEqual(c.action_source("steam", "install", c.terminal_command("steam")), "Flathub")
