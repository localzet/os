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

    def test_qmp_pointer_coordinates_use_the_full_absolute_axis_range(self):
        class Recorder:
            events = None

            def execute(self, command, arguments):
                self.assert_command = command
                self.events = arguments["events"]

        qmp = Recorder()
        visual_script.click(qmp, 80, 16)

        self.assertEqual(qmp.assert_command, "input-send-event")
        self.assertEqual(qmp.events[0]["data"]["value"], round(
            80 * visual_script.ABSOLUTE_POINTER_MAX / (visual_script.WIDTH - 1)
        ))
        self.assertEqual(qmp.events[1]["data"]["value"], round(
            16 * visual_script.ABSOLUTE_POINTER_MAX / (visual_script.HEIGHT - 1)
        ))
        self.assertEqual(qmp.events[2]["data"], {"button": "left", "down": True})
        self.assertEqual(qmp.events[3]["data"], {"button": "left", "down": False})

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
        state = {"appearance": "purple"}
        window = {"app": "settings", "title": "Localzet Settings", "ready": True}
        with patch.object(visual_agent, "_activate_theme"), \
                patch.object(visual_agent, "_state", return_value=state), \
                patch.object(visual_agent, "_wait_window", return_value=window):
            result = visual_agent._apply_theme("purple")

        self.assertTrue(result["ready"])
        self.assertEqual(result["state"], state)
        self.assertEqual(result["window"], window)

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
        for request in (
            {"id": 4, "op": "run", "args": {"command": "gsettings get"}},
            {"id": 4, "op": "open_app", "args": {"app": "shell"}},
            {"id": 4, "op": "select_theme", "args": {"theme": "ubuntu"}},
            {"id": 4, "op": "state", "args": {"path": "/etc/passwd"}},
        ):
            with self.subTest(request=request), self.assertRaises(agent["RequestError"]):
                validate(request)

    def test_visual_runner_does_not_type_commands_and_uses_virtio_control(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("type_text", source)
        self.assertNotIn("live-appearance-verify.py", source)
        self.assertIn('"virtserialport,chardev=visual-control,name=org.localzet.visual-test"', source)
        self.assertIn("click(qmp, 80, 16)", source)
        self.assertIn('agent.call("wait_popup", {"popup": "launcher"})', source)
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
