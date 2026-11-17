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
            self.assertEqual(c.action("lutris", frozenset()), ("launch", ("/usr/bin/lutris",)))
            self.assertEqual(c.action("steam", frozenset())[0], "install")
            self.assertEqual(c.action("steam", frozenset({"com.valvesoftware.Steam"})),
                             ("launch", ("/usr/bin/flatpak", "run", "com.valvesoftware.Steam")))
        with patch.object(c, "executable", return_value=False):
            self.assertEqual(c.action("lutris", frozenset())[0], "missing")
            self.assertEqual(c.action("steam", frozenset())[0], "website")
            self.assertEqual(c.action("music", frozenset()), ("website", "https://music.yandex.ru/download/"))
