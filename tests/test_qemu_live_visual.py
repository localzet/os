import importlib.util
import json
import runpy
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Event, Thread
import time
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

agent_spec = importlib.util.spec_from_file_location(
    "gnome_visual_test_agent", ROOT / "scripts" / "gnome-visual-test-agent.py"
)
assert agent_spec and agent_spec.loader
visual_agent = importlib.util.module_from_spec(agent_spec)
agent_spec.loader.exec_module(visual_agent)


class QemuLiveVisualTests(unittest.TestCase):
    def test_guest_agent_startup_timeout_is_bounded(self):
        self.assertEqual(visual_script.GUEST_AGENT_READY_TIMEOUT, 30)

    def test_appearance_theme_action_uses_its_row_when_button_label_is_generic(self):
        class Action:
            nActions = 1

            def __init__(self):
                self.invoked = False

            def doAction(self, _index):
                self.invoked = True
                return True

        class Node:
            def __init__(self, name, role, children=(), action=None):
                self.name = name
                self.role = role
                self.children = list(children)
                self.action = action
                self.parent = None
                for child in self.children:
                    child.parent = self

            def getRoleName(self):
                return self.role

            def getChildCount(self):
                return len(self.children)

            def getChildAtIndex(self, index):
                return self.children[index]

            def queryAction(self):
                return self.action

        click = Action()
        apply_button = Node("Применить", "push button", action=click)
        blue_row = Node("Aurora Blue", "list item", [apply_button])
        settings = Node("Localzet Settings", "frame", [blue_row])

        with patch.object(
            visual_agent, "_accessible_nodes",
            lambda: [settings, blue_row, apply_button],
        ), \
                patch.object(visual_agent, "_is_showing", lambda _node: True):
            activated = visual_agent._activate_theme("blue")

        self.assertEqual(activated, "Применить")
        self.assertTrue(click.invoked)

    def test_appearance_apply_reports_ready_after_state_and_window_confirmation(self):
        wallpaper = "file:///usr/share/backgrounds/localzet/aurora-purple.webp"
        state = {
            "appearance": "purple",
            "accent_color": "purple",
            "color_scheme": "prefer-dark",
            "icon_theme": "Localzet",
            "gtk_theme": "Localzet-Aurora-Purple",
            "picture_uri": wallpaper,
            "picture_uri_dark": wallpaper,
            "ptyxis_profile_uuid": "a3d6b7e2186b4b5b92256abcde123456",
            "ptyxis_palette": "Aurora Purple",
        }
        window = {"app": "settings", "title": "Localzet Settings", "ready": True}
        with patch.object(visual_agent, "_activate_theme"), \
                patch.object(visual_agent, "_state", return_value=state), \
                patch.object(visual_agent, "_wait_window", return_value=window):
            result = visual_agent._apply_theme("purple")

        self.assertTrue(result["ready"])
        self.assertEqual(result["state"], state)
        self.assertEqual(result["window"], window)

    def test_appearance_apply_waits_for_terminal_palette_and_all_desktop_settings(self):
        wallpaper = "file:///usr/share/backgrounds/localzet/aurora-purple.webp"
        expected = {
            "appearance": "purple",
            "accent_color": "purple",
            "color_scheme": "prefer-dark",
            "icon_theme": "Localzet",
            "gtk_theme": "Localzet-Aurora-Purple",
            "picture_uri": wallpaper,
            "picture_uri_dark": wallpaper,
            "ptyxis_profile_uuid": "a3d6b7e2186b4b5b92256abcde123456",
            "ptyxis_palette": "Aurora Purple",
        }
        pending = {**expected, "ptyxis_palette": "Aurora Blue"}
        window = {"app": "settings", "title": "Localzet Settings", "ready": True}
        with patch.object(visual_agent, "_activate_theme"), \
                patch.object(visual_agent, "_state", side_effect=[pending, expected]) as read_state, \
                patch.object(visual_agent, "_wait_window", return_value=window):
            result = visual_agent._apply_theme("purple")

        self.assertEqual(read_state.call_count, 2)
        self.assertEqual(result["state"], expected)

    def test_appearance_apply_allows_palette_before_first_ptyxis_profile(self):
        wallpaper = "file:///usr/share/backgrounds/localzet/aurora-blue.webp"
        state = {
            "appearance": "blue",
            "accent_color": "blue",
            "color_scheme": "prefer-dark",
            "icon_theme": "Localzet",
            "gtk_theme": "Localzet-Aurora-Blue",
            "picture_uri": wallpaper,
            "picture_uri_dark": wallpaper,
            "ptyxis_profile_uuid": None,
            "ptyxis_palette": None,
        }
        window = {"app": "settings", "title": "Localzet Settings", "ready": True}
        with patch.object(visual_agent, "_activate_theme"), \
                patch.object(visual_agent, "_state", return_value=state), \
                patch.object(visual_agent, "_wait_window", return_value=window):
            result = visual_agent._apply_theme("blue")

        self.assertTrue(result["ready"])
        self.assertIsNone(result["state"]["ptyxis_profile_uuid"])

    def test_appearance_restore_accepts_visible_button_label_and_confirms_state(self):
        wallpaper = "file:///usr/share/backgrounds/localzet/aurora-black.webp"
        state = {
            "appearance": "purple",
            "icon_theme": "Adwaita",
            "gtk_theme": "Yaru-dark",
            "picture_uri": wallpaper,
            "picture_uri_dark": wallpaper,
            "color_scheme": "default",
            "restore_point": False,
        }
        window = {"app": "settings", "title": "Localzet Settings", "ready": True}
        with patch.object(visual_agent, "_activate_name") as activate, \
                patch.object(visual_agent, "_state", return_value=state), \
                patch.object(visual_agent, "_wait_window", return_value=window):
            result = visual_agent._restore()

        activate.assert_called_once_with((
            "Восстановить исходные настройки оформления",
            "Восстановить исходный вид",
        ))
        self.assertTrue(result["ready"])
        self.assertEqual(result["state"], state)
        self.assertEqual(result["window"], window)

    def test_terminal_capture_uses_the_selected_ptyxis_profile(self):
        window = {"app": "terminal", "title": "Ptyxis", "ready": True}
        profile_uuid = "a3d6b7e2186b4b5b92256abcde123456"
        profile = type("Profile", (), {
            "get_string": lambda _self, _key: "Aurora Purple",
        })()
        with tempfile.TemporaryDirectory() as directory:
            palette_dir = Path(directory) / "org.gnome.Ptyxis" / "palettes"
            palette_dir.mkdir(parents=True)
            (palette_dir / "Aurora Purple.palette").write_text(
                "[Palette]\nName=Aurora Purple\nBackground=#20112e\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"XDG_DATA_HOME": directory}), \
                patch.object(visual_agent, "_default_profile_uuid", return_value=profile_uuid), \
                patch.object(visual_agent, "_profile_settings", return_value=profile), \
                patch.object(visual_agent.subprocess, "Popen") as launch, \
                patch.object(visual_agent, "_wait_window", return_value=window):
                result = visual_agent._open_app("terminal")

        launch.assert_called_once_with(
            ["ptyxis", "--standalone", "--new-window"],
            close_fds=True,
            start_new_session=True,
        )
        self.assertEqual(result["profile_uuid"], profile_uuid)
        self.assertEqual(result["profile_palette"], "Aurora Purple")
        self.assertEqual(result["palette"]["background"], "#20112e")
        self.assertTrue(result["ready"])

    def test_default_profile_uuid_preserves_compact_value(self):
        profile_uuid = "a3d6b7e2186b4b5b92256abcde123456"
        root = type("RootSettings", (), {
            "get_string": lambda _self, _key: profile_uuid,
        })()
        with patch.object(visual_agent, "_settings", return_value=root):
            self.assertEqual(visual_agent._default_profile_uuid(), profile_uuid)

    def test_profile_settings_preserves_uuid_path_representation(self):
        for profile_uuid in (
            "a3d6b7e2186b4b5b92256abcde123456",
            "a3d6b7e2-186b-4b5b-9225-6abcde123456",
        ):
            with self.subTest(profile_uuid=profile_uuid):
                profile = object()
                with patch.object(
                    visual_agent, "_default_profile_uuid", return_value=profile_uuid,
                ), patch.object(
                    visual_agent, "_settings", return_value=profile,
                ) as settings:
                    self.assertIs(visual_agent._profile_settings(), profile)
                settings.assert_called_once_with(
                    "org.gnome.Ptyxis.Profile",
                    f"/org/gnome/Ptyxis/Profiles/{profile_uuid}/",
                )

    def test_terminal_first_launch_uses_the_default_profile(self):
        window = {"app": "terminal", "title": "Ptyxis", "ready": True}
        with patch.object(visual_agent, "_default_profile_uuid", return_value=None), \
                patch.object(visual_agent, "_profile_settings", return_value=None), \
                patch.object(visual_agent.subprocess, "Popen") as launch, \
                patch.object(visual_agent, "_wait_window", return_value=window):
            result = visual_agent._open_app("terminal")

        launch.assert_called_once_with(
            ["ptyxis", "--standalone", "--new-window"],
            close_fds=True,
            start_new_session=True,
        )
        self.assertIsNone(result["profile_uuid"])
        self.assertIsNone(result["profile_palette"])

    def test_terminal_framebuffer_must_render_the_selected_palette(self):
        result = visual_script.verify_terminal_palette_sample(
            "purple", (32, 17, 46), 4096, 4096,
        )
        self.assertEqual(result["sampled_background"], "#20112e")
        self.assertGreaterEqual(result["dominant_ratio"], 0.90)

        with self.assertRaisesRegex(RuntimeError, "expected #20112e, got #0a1120"):
            visual_script.verify_terminal_palette_sample(
                "purple", (10, 17, 32), 4096, 4096,
            )

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

    def test_visual_guest_control_uses_a_strict_allowlist(self):
        agent = runpy.run_path(str(ROOT / "scripts/gnome-visual-test-agent.py"))
        validate = agent["validate_request"]

        self.assertEqual(
            validate({"id": 3, "op": "select_theme", "args": {"theme": "blue"}}),
            (3, "select_theme", {"theme": "blue"}),
        )
        self.assertEqual(
            validate({"id": 5, "op": "open_popup", "args": {"popup": "launcher"}}),
            (5, "open_popup", {"popup": "launcher"}),
        )
        self.assertEqual(
            validate({"id": 6, "op": "close_app", "args": {"app": "terminal"}}),
            (6, "close_app", {"app": "terminal"}),
        )
        for request in (
            {"id": 4, "op": "run", "args": {"command": "gsettings get"}},
            {"id": 4, "op": "open_app", "args": {"app": "shell"}},
            {"id": 4, "op": "select_theme", "args": {"theme": "ubuntu"}},
            {"id": 4, "op": "state", "args": {"path": "/etc/passwd"}},
            {"id": 6, "op": "open_popup", "args": {"popup": "notification"}},
        ):
            with self.subTest(request=request), self.assertRaises(agent["RequestError"]):
                validate(request)

    def test_shell_popup_action_is_allowlisted_and_confirmed(self):
        completed = type("Completed", (), {"stdout": "(true,)\n"})()
        with patch.object(
            visual_agent.subprocess, "run", return_value=completed
        ) as run:
            result = visual_agent._open_popup("launcher")

        run.assert_called_once_with(
            [
                "gdbus", "call", "--session", "--dest", "org.localzet.VisualTest",
                "--object-path", "/org/localzet/VisualTest", "--method",
                "org.localzet.VisualTest.OpenLauncher",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertTrue(result["ready"])
        self.assertEqual(result["popup"], "launcher")
        self.assertEqual(result["action"], "OpenLauncher")

    def test_shell_popup_action_rejects_unconfirmed_open_state(self):
        completed = type("Completed", (), {"stdout": "(false,)\n"})()
        with patch.object(visual_agent.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "did not report an open state"):
                visual_agent._open_popup("launcher")

    def test_visual_runner_does_not_type_commands_and_uses_virtio_control(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("type_text", source)
        self.assertNotIn('press(qmp, "alt", "f4")', source)
        self.assertNotIn("live-appearance-verify.py", source)
        self.assertIn('"virtserialport,chardev=visual-control,name=org.localzet.visual-test"', source)
        self.assertIn('agent.call("open_popup", {"popup": "launcher"})', source)
        self.assertIn('agent.call("open_popup", {"popup": "quick_settings"})', source)
        self.assertIn('agent.call("close_app", {"app": "terminal"})', source)
        self.assertIn('qmp.execute("screendump"', source)

    def test_guest_control_uses_structured_request_and_response_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "visual-control.sock"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen(1)
            errors = []

            def serve():
                try:
                    connection, _ = listener.accept()
                    with connection:
                        greeting = json.dumps({
                            "event": "ready", "protocol": 1, "wayland": True,
                        }).encode() + b"\n"
                        connection.sendall(greeting[:12])
                        time.sleep(0.01)
                        connection.sendall(greeting[12:])
                        buffer = bytearray()
                        while b"\n" not in buffer:
                            buffer.extend(connection.recv(4096))
                        request = json.loads(bytes(buffer).split(b"\n", 1)[0])
                        response = json.dumps({
                            "id": request["id"],
                            "ok": True,
                            "result": {"scene": "desktop", "ready": True},
                        }).encode() + b"\n"
                        connection.sendall(response)
                except Exception as error:
                    errors.append(error)
                finally:
                    listener.close()

            server = Thread(target=serve, daemon=True)
            server.start()
            control = visual_script.GuestControl(path, timeout=2)
            try:
                greeting = control.wait_ready(timeout=2)
                result = control.call("desktop_ready", timeout=2)
            finally:
                control.close()
            server.join(timeout=2)

        self.assertFalse(errors)
        self.assertEqual(greeting["protocol"], 1)
        self.assertEqual(result, {"scene": "desktop", "ready": True})

    def test_guest_window_readiness_requires_a_showing_window(self):
        class Window:
            name = "Localzet Settings"

            @staticmethod
            def getRoleName():
                return "frame"

        with patch.object(visual_agent, "_accessible_nodes", lambda: [Window()]), \
                patch.object(visual_agent, "_is_showing", lambda _node: False):
            self.assertIsNone(visual_agent._find_window("settings"))

        with patch.object(visual_agent, "_accessible_nodes", lambda: [Window()]), \
                patch.object(visual_agent, "_is_showing", lambda _node: True):
            self.assertTrue(visual_agent._find_window("settings")["ready"])

    def test_guest_window_readiness_can_use_gnome_window_state(self):
        with patch.object(visual_agent, "_find_window", return_value=None), \
                patch.object(visual_agent, "_shell_window_title", return_value="Ptyxis"):
            window = visual_agent._wait_window("terminal")

        self.assertEqual(window["title"], "Ptyxis")
        self.assertEqual(window["source"], "gnome-shell")
        self.assertTrue(window["ready"])

    def test_gnome_window_query_uses_only_allowlisted_app_names(self):
        with self.assertRaisesRegex(visual_agent.RequestError, "unsupported application"):
            visual_agent._shell_window_title("arbitrary")

        completed = type("Completed", (), {"stdout": "('Ptyxis',)\n"})()
        with patch.object(visual_agent.subprocess, "run", return_value=completed) as run:
            self.assertEqual(visual_agent._shell_window_title("terminal"), "Ptyxis")

        args = run.call_args.args[0]
        self.assertEqual(args[-2:], ["org.localzet.VisualTest.FindWindow", "terminal"])

    def test_guest_close_app_confirms_the_window_is_gone(self):
        completed = type("Completed", (), {"stdout": "(true,)\n"})()
        with patch.object(visual_agent.subprocess, "run", return_value=completed) as run, \
                patch.object(
                    visual_agent,
                    "_find_window",
                    side_effect=[{"app": "terminal"}, None],
                ) as find_window, \
                patch.object(visual_agent, "_shell_window_title", return_value=None):
            with patch.object(visual_agent.time, "sleep"):
                result = visual_agent._close_app("terminal")

        self.assertEqual(result, {"app": "terminal", "closed": True, "ready": True})
        self.assertEqual(find_window.call_count, 2)
        self.assertEqual(
            run.call_args.args[0][-2:],
            ["org.localzet.VisualTest.CloseWindow", "terminal"],
        )

    def test_guest_close_app_rejects_an_unconfirmed_close_request(self):
        completed = type("Completed", (), {"stdout": "(false,)\n"})()
        with patch.object(visual_agent.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "did not request closing"):
                visual_agent._close_app("settings")

    def test_desktop_readiness_requires_local_wallpaper_and_visible_dock(self):
        with tempfile.TemporaryDirectory() as directory:
            wallpaper = Path(directory) / "aurora-blue.webp"
            wallpaper.touch()
            state = {
                "picture_uri": wallpaper.as_uri(),
                "icon_theme": "Localzet",
            }
            dock_launcher = object()
            with patch.object(visual_agent, "_state", lambda: state), \
                    patch.object(visual_agent, "_find_name", lambda _names: dock_launcher), \
                    patch.object(visual_agent, "_is_showing", lambda _node: True), \
                    patch.object(visual_agent, "_node_name", lambda _node: "Приложения"):
                ready = visual_agent._desktop_ready()

            self.assertTrue(ready["ready"])
            self.assertEqual(ready["wallpaper_uri"], wallpaper.as_uri())
            self.assertEqual(ready["dock_launcher"], "Приложения")

            with patch.object(visual_agent, "_state", lambda: state), \
                    patch.object(visual_agent, "_find_name", lambda _names: None):
                with self.assertRaisesRegex(RuntimeError, "Dock launcher"):
                    visual_agent._desktop_ready()


if __name__ == "__main__":
    unittest.main()
