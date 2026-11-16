#!/usr/bin/env python3
"""Exercise actual GTK confirmation dialogs against the rootless fixture."""
import subprocess
import sys
import time
import traceback
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from localzet.containers import Engine
from localzet.containers_app import create_application

out = Path(sys.argv[1])
engine = Engine()
assert not engine.rootful
assert "name=rootless" in engine._run("info", "--format", "{{json .SecurityOptions}}")
app = create_application()
errors = []
deadline = time.monotonic() + 90
phase = 0
cid = next(row.id for row in engine.inventory() if row.name == "localzet-rootless-ci")


def state():
    return next(row.state for row in engine.inventory() if row.id == cid)


def select_fixture():
    app.search.set_text("localzet-rootless-ci")
    app.render()
    index = next(i for i in range(app.store.get_n_items())
                 if app.store.get_item(i).item.id == cid)
    app.selection.set_selected(index)
    assert app.selected().id == cid


def capture(label):
    windows = subprocess.check_output(
        ["xdotool", "search", "--onlyvisible", "--name", "Localzet Containers"],
        text=True).splitlines()
    subprocess.run(["import", "-window", windows[0], str(out / (label + ".png"))],
                   check=True, timeout=10)


def click_response(dialog, label):
    # Activate the actual dialog button, not a synthetic response signal.
    def walk(widget):
        yield widget
        child = widget.get_first_child()
        while child is not None:
            yield from walk(child)
            child = child.get_next_sibling()

    buttons = [widget for widget in walk(dialog)
               if isinstance(widget, Gtk.Button)
               and widget.get_label() == label
               and widget.get_mapped() and widget.get_sensitive()]
    if not buttons:
        # Adwaita may still be mapping the new dialog during its transition.
        return False
    assert len(buttons) == 1, f"Expected one visible response button: {label}"
    buttons[0].emit("clicked")
    return True


def advance():
    global phase
    try:
        assert time.monotonic() < deadline, f"Rootless GTK timed out in phase {phase}"
        if app.busy:
            return GLib.SOURCE_CONTINUE
        if phase == 0:
            app.engine_chosen(None, "rootless")
        elif phase == 1:
            assert not app.rootful and not app.last_error
            select_fixture()
            assert state() == "exited" and app.start_button.get_sensitive()
            app.start_button.emit("clicked")
        elif phase == 2:
            dialog = app.window.get_visible_dialog()
            if dialog is None or not click_response(dialog, "Отмена"):
                return GLib.SOURCE_CONTINUE
            assert state() == "exited"
        elif phase == 3:
            assert state() == "exited"
            app.start_button.emit("clicked")
        elif phase == 4:
            dialog = app.window.get_visible_dialog()
            if dialog is None or not click_response(dialog, "Запустить"):
                return GLib.SOURCE_CONTINUE
        elif phase == 5:
            assert not app.last_error and state() == "running"
            select_fixture()
            assert app.stop_button.get_sensitive()
            capture("rootless-running")
            app.stop_button.emit("clicked")
        elif phase == 6:
            dialog = app.window.get_visible_dialog()
            if dialog is None or not click_response(dialog, "Остановить"):
                return GLib.SOURCE_CONTINUE
        elif phase == 7:
            assert not app.last_error and state() == "exited"
            select_fixture()
            capture("rootless-stopped")
            print("PASS: rootless GTK cancel, confirmed start and stop", flush=True)
            phase += 1
            app.quit()
            return GLib.SOURCE_REMOVE
        phase += 1
        return GLib.SOURCE_CONTINUE
    except Exception:
        errors.append(traceback.format_exc())
        app.quit()
        return GLib.SOURCE_REMOVE


app.connect("activate", lambda *_: GLib.timeout_add(700, advance))
rc = app.run([sys.argv[0]])
if errors:
    raise SystemExit(errors[0])
if rc or phase != 8:
    raise SystemExit("Incomplete rootless GTK test")
