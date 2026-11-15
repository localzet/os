#!/usr/bin/env python3
"""Exercise the production GTK workspace against real isolated Docker fixtures."""
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from localzet.containers_app import create_application

name, image, out = sys.argv[1:]
out = Path(out)
out.mkdir(parents=True, exist_ok=True)
app = create_application()
errors = []
deadline = time.monotonic() + 90
steps = iter(("containers", "compose", "images", "volumes", "networks", "containers"))
pending = None
previous = None

def capture(page):
    windows = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--name",
                                      "Localzet Containers"], text=True).splitlines()
    subprocess.run(["import", "-window", windows[0], str(out / ("populated-" + page + ".png"))],
                   check=True, timeout=10)

def advance():
    global pending, previous
    try:
        if time.monotonic() > deadline:
            raise AssertionError("GTK populated workspace timed out")
        if app.busy:
            return GLib.SOURCE_CONTINUE
        if pending is None:
            # Explicitly select the existing system engine using its real
            # response handler. No socket override or fake inventory.
            app.engine_chosen(None, "rootful")
            pending = next(steps)
            return GLib.SOURCE_CONTINUE
        if previous != pending:
            if pending != app.active_page:
                app.nav_buttons[pending].emit("clicked")
                return GLib.SOURCE_CONTINUE
            if pending == "containers":
                assert app.rootful and not app.last_error
                rows = app.rows
                assert any(row.name == name for row in rows), rows
                app.search.set_text(name)
                app.render()
                index = next(i for i in range(app.store.get_n_items())
                             if app.store.get_item(i).item.name == name)
                app.selection.set_selected(index)
                assert app.selected().name == name
                assert app.detail.get_label().startswith(name)
                assert app.start_button.get_sensitive() and not app.stop_button.get_sensitive()
            else:
                selection = app.resource_selection
                assert selection is not None, pending
                model = selection.get_model()
                rows = [model.get_item(i).item for i in range(model.get_n_items())]
                key = {"compose": "name", "images": "Repository", "volumes": "Name", "networks": "Name"}[pending]
                expected = image.split(":")[0] if pending == "images" else name
                index = next(i for i, row in enumerate(rows) if row[key] == expected)
                selection.set_selected(index)
                assert selection.get_selected_item().item[key] == expected
            previous = pending
            # Wait one tick for GTK to paint the updated selection.
            return GLib.SOURCE_CONTINUE
        capture(pending)
        print("PASS: populated GTK " + pending, flush=True)
        try:
            pending = next(steps)
            if pending == previous:
                previous = None
        except StopIteration:
            app.quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE
    except Exception:
        errors.append(traceback.format_exc())
        app.quit()
        return GLib.SOURCE_REMOVE

app.connect("activate", lambda *_: GLib.timeout_add(700, advance))
rc = app.run([sys.argv[0]])
if errors:
    raise SystemExit(errors[0])
if rc:
    raise SystemExit(rc)
if previous != "containers":
    raise SystemExit("Incomplete populated GTK run")
