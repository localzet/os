#!/usr/bin/python3
"""Test-only, allowlisted control channel for an isolated GNOME guest."""
from __future__ import annotations

import json
import os
from pathlib import Path
import select
import subprocess
import time
from urllib.parse import unquote, urlparse


PORT = Path("/dev/virtio-ports/org.localzet.visual-test")
PROTOCOL = 1
MAX_LINE = 64 * 1024
THEMES = {"blue", "purple", "black"}
APP_IDS = {
    "settings": "com.localzet.Settings.desktop",
    "files": "org.gnome.Nautilus.desktop",
    "terminal": "org.gnome.Ptyxis.desktop",
}
WINDOW_NAMES = {
    "settings": ("Localzet Settings", "Параметры Localzet"),
    "files": ("Files", "Файлы", "Home", "Домашняя папка"),
    "terminal": ("Ptyxis", "Terminal", "Терминал"),
}
PAGES = {
    "home": ("Главная", "Localzet OS"),
    "appearance": ("Оформление", "Aurora"),
    "modules": ("Модули", "Модули Localzet OS"),
    "system": ("Система", "О системе"),
}
POPUPS = {
    "launcher": ("LOCALZET OS", "Найти приложение"),
    "quick_settings": ("Wi-Fi", "Bluetooth"),
    "notification": ("Localzet Aurora notification", "Aurora visual capture"),
}
NO_ARGUMENTS = {
    "state", "prime_restore_source", "restore", "desktop_ready",
    "notify", "icon_resolution", "shell_logs",
}
OPERATIONS = NO_ARGUMENTS | {
    "open_app", "open_page", "open_popup", "select_theme", "wait_window", "wait_popup",
}


class RequestError(ValueError):
    pass


def validate_request(request: object) -> tuple[int, str, dict[str, str]]:
    if not isinstance(request, dict) or set(request) != {"id", "op", "args"}:
        raise RequestError("request must contain only id, op, and args")
    request_id = request["id"]
    operation = request["op"]
    arguments = request["args"]
    if (not isinstance(request_id, int) or isinstance(request_id, bool)
            or request_id < 0 or request_id > 2**31 - 1):
        raise RequestError("id must be a non-negative 32-bit integer")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise RequestError("unsupported operation")
    if not isinstance(arguments, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in arguments.items()
    ):
        raise RequestError("args must contain string values")

    required = {
        "open_app": {"app"},
        "open_page": {"page"},
        "open_popup": {"popup"},
        "select_theme": {"theme"},
        "wait_window": {"app"},
        "wait_popup": {"popup"},
    }.get(operation, set())
    if set(arguments) != required:
        raise RequestError("unexpected or missing operation arguments")
    if operation in {"open_app", "wait_window"} and arguments.get("app") not in APP_IDS:
        raise RequestError("unsupported application")
    if operation == "open_page" and arguments.get("page") not in PAGES:
        raise RequestError("unsupported Settings page")
    if operation == "open_popup" and arguments.get("popup") != "launcher":
        raise RequestError("unsupported shell popup action")
    if operation == "select_theme" and arguments.get("theme") not in THEMES:
        raise RequestError("unsupported Aurora theme")
    if operation == "wait_popup" and arguments.get("popup") not in POPUPS:
        raise RequestError("unsupported shell popup")
    return request_id, operation, arguments


def _settings(schema: str, path: str | None = None):
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    source = Gio.SettingsSchemaSource.get_default()
    if source.lookup(schema, True) is None:
        raise RuntimeError(f"GSettings schema unavailable: {schema}")
    return Gio.Settings.new_with_path(schema, path) if path else Gio.Settings.new(schema)


def _profile_settings():
    root = _settings("org.gnome.Ptyxis")
    profile_uuid = root.get_string("default-profile-uuid")
    if not profile_uuid:
        return None
    import uuid
    try:
        profile_uuid = str(uuid.UUID(profile_uuid))
    except ValueError:
        return None
    path = f"/org/gnome/Ptyxis/Profiles/{profile_uuid}/"
    try:
        return _settings("org.gnome.Ptyxis.Profile", path)
    except RuntimeError:
        return None


def _state() -> dict:
    interface = _settings("org.gnome.desktop.interface")
    background = _settings("org.gnome.desktop.background")
    shell = _settings("com.localzet.shell")
    profile = _profile_settings()
    state = {
        "appearance": shell.get_string("appearance"),
        "accent_color": interface.get_string("accent-color"),
        "color_scheme": interface.get_string("color-scheme"),
        "icon_theme": interface.get_string("icon-theme"),
        "picture_uri": background.get_string("picture-uri"),
        "picture_uri_dark": background.get_string("picture-uri-dark"),
        "ptyxis_palette": profile.get_string("palette") if profile else None,
        "restore_point": _state_file().is_file(),
        "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
    }
    return state


def _state_file() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home) if state_home else Path.home() / ".local/state"
    return base / "localzet" / "appearance.json"


def _set_string(schema: str, key: str, value: str) -> None:
    settings = _settings(schema)
    if not settings.set_string(key, value):
        raise RuntimeError(f"GSettings rejected {schema} {key}")


def _accessible_nodes():
    import pyatspi

    desktop = pyatspi.Registry.getDesktop(0)
    pending = [(desktop, 0)]
    visited = 0
    while pending and visited < 5000:
        node, depth = pending.pop()
        visited += 1
        yield node
        if depth >= 24:
            continue
        try:
            count = min(node.getChildCount(), 500)
            pending.extend(
                (node.getChildAtIndex(index), depth + 1)
                for index in range(count)
            )
        except Exception:
            continue


def _node_name(node) -> str:
    try:
        return str(node.name or "").strip()
    except Exception:
        return ""


def _role_name(node) -> str:
    try:
        return str(node.getRoleName() or "").casefold()
    except Exception:
        return ""


def _is_showing(node) -> bool:
    try:
        import pyatspi
        return node.getState().contains(pyatspi.STATE_SHOWING)
    except Exception:
        return False


def _find_name(
    names: tuple[str, ...], *, actionable: bool = False, showing_only: bool = True
):
    targets = {name.casefold() for name in names}
    for node in _accessible_nodes():
        if _node_name(node).casefold() not in targets:
            continue
        if showing_only and not _is_showing(node):
            continue
        if actionable:
            try:
                if node.queryAction().nActions < 1:
                    continue
            except Exception:
                continue
        return node
    return None


def _showing_name_fragment(fragment: str) -> bool:
    target = fragment.casefold()
    for node in _accessible_nodes():
        if target in _node_name(node).casefold():
            if _is_showing(node):
                return True
    return False


def _activate_name(names: tuple[str, ...]) -> str:
    node = _find_name(names, actionable=True)
    if node is None:
        raise RuntimeError(f"accessible action not found: {names[0]}")
    if not node.queryAction().doAction(0):
        raise RuntimeError(f"accessible action failed: {_node_name(node)}")
    return _node_name(node)


def _action_count(node) -> int:
    try:
        return node.queryAction().nActions
    except Exception:
        return 0


def _activate_theme(theme: str) -> str:
    label = f"Применить Aurora {theme.title()}"
    action = _find_name((label,), actionable=True)
    if action is not None:
        if action.queryAction().doAction(0):
            return _node_name(action)
        raise RuntimeError(f"Appearance action failed for {theme}")

    target = f"Aurora {theme.title()}".casefold()
    for candidate in _accessible_nodes():
        if target not in _node_name(candidate).casefold():
            continue

        ancestor = candidate
        for _ in range(6):
            pending = [ancestor]
            actions = []
            visited = 0
            while pending and visited < 100:
                node = pending.pop()
                visited += 1
                if "button" in _role_name(node) and _action_count(node) > 0:
                    actions.append(node)
                try:
                    pending.extend(
                        node.getChildAtIndex(index)
                        for index in range(min(node.getChildCount(), 50))
                    )
                except Exception:
                    continue
            if len(actions) == 1:
                button = actions[0]
                if not button.queryAction().doAction(0):
                    raise RuntimeError(f"Appearance action failed for {theme}")
                return _node_name(button)
            try:
                ancestor = ancestor.parent
            except Exception:
                ancestor = None
            if ancestor is None:
                break

    available = [
        f"{_role_name(node)}:{_node_name(node)}"
        for node in _accessible_nodes()
        if _is_showing(node) and _action_count(node) > 0
    ][:20]
    raise RuntimeError(
        f"Appearance action not found for {theme}; accessible actions: {available}"
    )


def _wait_for_name(names: tuple[str, ...], timeout: float = 30.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        node = _find_name(names, showing_only=True)
        if node is not None:
            return _node_name(node)
        time.sleep(0.25)
    raise TimeoutError(f"accessible UI did not become ready: {names[0]}")


def _find_window(app: str) -> dict | None:
    names = WINDOW_NAMES[app]
    for node in _accessible_nodes():
        role = _role_name(node)
        if role not in {"frame", "window"}:
            continue
        if not _is_showing(node):
            continue
        name = _node_name(node)
        if any(candidate.casefold() in name.casefold() for candidate in names):
            return {"app": app, "title": name, "role": role, "ready": True}
    return None


def _wait_window(app: str) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        window = _find_window(app)
        if window is not None:
            return window
        time.sleep(0.25)
    raise TimeoutError(f"{app} window was not exposed by GNOME accessibility")


def _open_app(app: str) -> dict:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    info = Gio.DesktopAppInfo.new(APP_IDS[app])
    if info is None or not info.launch([], None):
        raise RuntimeError(f"could not launch allowlisted app: {app}")
    return _wait_window(app)


def _page_ready(page: str) -> dict:
    tab, marker = PAGES[page]
    _activate_name((tab,))
    _wait_for_name((marker,))
    return {"page": page, "window": _wait_window("settings"), "ready": True}


def _apply_theme(theme: str) -> dict:
    _activate_theme(theme)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        state = _state()
        if state["appearance"] == theme:
            return {
                "theme": theme,
                "state": state,
                "window": _wait_window("settings"),
                "ready": True,
            }
        time.sleep(0.25)
    raise TimeoutError(f"Aurora {theme.title()} did not apply in Appearance")


def _restore() -> dict:
    _activate_name(("Восстановить исходные настройки оформления",))
    expected_wallpaper = "file:///usr/share/backgrounds/localzet/aurora-black.webp"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        state = _state()
        if (state["appearance"] == "purple"
                and state["icon_theme"] == "Adwaita"
                and state["picture_uri"] == expected_wallpaper
                and state["picture_uri_dark"] == expected_wallpaper
                and state["color_scheme"] == "default"
                and not state["restore_point"]):
            return {"state": state, "window": _wait_window("settings"), "ready": True}
        time.sleep(0.25)
    raise TimeoutError("Appearance restore did not return the saved GNOME values")


def _wait_popup(popup: str) -> dict:
    names = POPUPS[popup]
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        visible = []
        for name in names:
            if _showing_name_fragment(name):
                visible.append(name)
        if len(visible) == len(names):
            return {"popup": popup, "visible_controls": visible, "ready": True}
        time.sleep(0.25)
    raise TimeoutError(f"GNOME {popup} popup is not accessible")


def _open_popup(popup: str) -> dict:
    if popup != "launcher":
        raise RequestError("unsupported shell popup action")
    if _showing_name_fragment("Найти приложение"):
        return _wait_popup(popup)
    activated = _activate_name(("Localzet OS",))
    return {**_wait_popup(popup), "activated": activated}


def _desktop_ready() -> dict:
    state = _state()
    wallpaper = urlparse(state["picture_uri"])
    dock_launcher = _find_name(("Приложения",))
    if wallpaper.scheme != "file" or not Path(unquote(wallpaper.path)).is_file():
        raise RuntimeError("desktop wallpaper is missing or is not a local file")
    if dock_launcher is None or not _is_showing(dock_launcher):
        raise RuntimeError("Localzet Dock launcher is not visible")
    return {
        "scene": "desktop",
        "ready": True,
        "wallpaper_uri": state["picture_uri"],
        "icon_theme": state["icon_theme"],
        "dock_launcher": _node_name(dock_launcher),
    }


def _icon_resolution() -> dict:
    import configparser
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, Gio, Gtk

    Gtk.init()
    display = Gdk.Display.get_default()
    if display is None:
        raise RuntimeError("GTK has no graphical display")
    theme_name = Gio.Settings.new("org.gnome.desktop.interface").get_string("icon-theme")
    theme = Gtk.IconTheme.get_for_display(display)
    icon_root = Path("/usr/share/icons/Localzet")
    icon_files = sorted(icon_root.rglob("*.svg"))
    local = []
    missing = []
    for path in icon_files:
        paintable = theme.lookup_icon(
            path.stem, None, 32, 1, Gtk.TextDirection.LTR,
            Gtk.IconLookupFlags.NONE,
        )
        resolved_file = paintable.get_file() if paintable else None
        resolved = Path(resolved_file.get_path()) if resolved_file else None
        if resolved is None or not resolved.is_relative_to(icon_root):
            missing.append(path.stem)
        else:
            local.append({"name": path.stem, "resolved": str(resolved)})

    upstream = []
    for desktop_path in (
        Path("/usr/share/applications/org.gnome.Nautilus.desktop"),
        Path("/usr/share/applications/org.gnome.Ptyxis.desktop"),
    ):
        if not desktop_path.is_file():
            upstream.append({"desktop": desktop_path.name, "resolved": None})
            continue
        entry = configparser.ConfigParser(interpolation=None)
        entry.read(desktop_path, encoding="utf-8")
        icon_name = entry["Desktop Entry"].get("Icon", "")
        paintable = theme.lookup_icon(
            icon_name, None, 32, 1, Gtk.TextDirection.LTR,
            Gtk.IconLookupFlags.NONE,
        ) if icon_name else None
        icon_file = paintable.get_file() if paintable else None
        resolved = Path(icon_file.get_path()) if icon_file else None
        upstream.append({
            "desktop": desktop_path.name,
            "icon": icon_name,
            "resolved": str(resolved) if resolved else None,
            "uses_upstream": bool(resolved and not resolved.is_relative_to(icon_root)),
        })
    if theme_name != "Localzet" or missing or any(not item.get("uses_upstream") for item in upstream):
        raise RuntimeError("installed GTK icon resolution failed")
    return {
        "theme": theme_name,
        "local_icons": len(local),
        "missing_local": missing,
        "upstream": upstream,
        "resolved": local,
    }


def dispatch(operation: str, arguments: dict[str, str]) -> dict:
    if operation == "state":
        return _state()
    if operation == "prime_restore_source":
        wallpaper = "file:///usr/share/backgrounds/localzet/aurora-black.webp"
        for key, value in (
            ("picture-uri", wallpaper),
            ("picture-uri-dark", wallpaper),
        ):
            _set_string("org.gnome.desktop.background", key, value)
        for key, value in (
            ("icon-theme", "Adwaita"),
            ("accent-color", "blue"),
            ("color-scheme", "default"),
        ):
            _set_string("org.gnome.desktop.interface", key, value)
        _set_string("com.localzet.shell", "appearance", "purple")
        return {"state": _state(), "ready": True}
    if operation == "open_app":
        return _open_app(arguments["app"])
    if operation == "wait_window":
        return _wait_window(arguments["app"])
    if operation == "open_page":
        return _page_ready(arguments["page"])
    if operation == "select_theme":
        return _apply_theme(arguments["theme"])
    if operation == "restore":
        return _restore()
    if operation == "desktop_ready":
        ready_windows = [
            window for app in WINDOW_NAMES
            if (window := _find_window(app)) is not None
        ]
        if ready_windows:
            raise RuntimeError(f"desktop still has app windows: {ready_windows}")
        return _desktop_ready()
    if operation == "wait_popup":
        return _wait_popup(arguments["popup"])
    if operation == "open_popup":
        return _open_popup(arguments["popup"])
    if operation == "notify":
        subprocess.run(
            ["notify-send", "--app-name=Localzet", "--expire-time=10000",
             "Localzet Aurora notification", "Aurora visual capture"],
            check=True, timeout=5,
        )
        return {"sent": True, "popup": "notification"}
    if operation == "icon_resolution":
        return _icon_resolution()
    if operation == "shell_logs":
        result = subprocess.run(
            ["journalctl", "--user", "-b", "--no-pager", "--output=cat"],
            check=True, capture_output=True, text=True, timeout=15,
        )
        errors = [line for line in result.stdout.splitlines() if "JS ERROR:" in line]
        return {"js_errors": errors, "count": len(errors), "passed": not errors}
    raise RequestError("unsupported operation")


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        offset += os.write(descriptor, payload[offset:])


def serve(descriptor: int) -> None:
    greeting = {
        "event": "ready",
        "protocol": PROTOCOL,
        "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
        "wayland": bool(os.environ.get("WAYLAND_DISPLAY")),
    }
    _write_all(descriptor, json.dumps(greeting, separators=(",", ":")).encode() + b"\n")
    buffer = bytearray()
    while True:
        readable, _, _ = select.select([descriptor], [], [], 1)
        if not readable:
            continue
        chunk = os.read(descriptor, 4096)
        if not chunk:
            return
        buffer.extend(chunk)
        if len(buffer) > MAX_LINE:
            raise RequestError("request exceeds protocol limit")
        while b"\n" in buffer:
            line, _, remainder = buffer.partition(b"\n")
            buffer = bytearray(remainder)
            request_id = None
            try:
                request_id, operation, arguments = validate_request(json.loads(line))
                response = {
                    "id": request_id,
                    "ok": True,
                    "result": dispatch(operation, arguments),
                }
            except Exception as error:
                response = {
                    "id": request_id,
                    "ok": False,
                    "error": str(error)[:1000],
                }
            payload = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
            _write_all(descriptor, payload.encode("utf-8") + b"\n")


def main() -> int:
    while True:
        try:
            if PORT.exists():
                descriptor = os.open(PORT, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
                try:
                    serve(descriptor)
                finally:
                    os.close(descriptor)
        except (OSError, RequestError) as error:
            print(f"Localzet visual test agent: {error}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
