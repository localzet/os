#!/usr/bin/env python3
"""Exercise the process-local Aurora appearance against real GSettings changes."""
import time

import gi
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

from localzet.appearance import apply_midnight

interface = Gio.Settings.new("org.gnome.desktop.interface")
accessibility = Gio.Settings.new("org.gnome.desktop.a11y.interface")
original_scheme = interface.get_string("color-scheme")
original_contrast = accessibility.get_boolean("high-contrast")
app = Adw.Application(application_id="com.localzet.AppearanceRuntimeSmoke")


def drain():
    context = GLib.MainContext.default()
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)


def expect(window, wanted, label):
    drain()
    actual = window.has_css_class("localzet-midnight")
    if actual is not wanted:
        raise AssertionError(f"{label}: localzet-midnight={actual}, expected {wanted}")
    print(f"PASS: {label}", flush=True)


def activate(application):
    window = Adw.ApplicationWindow(application=application)
    window.set_default_size(360, 180)
    provider = apply_midnight(window)
    window.present()
    try:
        interface.set_string("color-scheme", "prefer-dark")
        accessibility.set_boolean("high-contrast", False)
        expect(window, True, "explicit dark preference uses Aurora tokens")

        interface.set_string("color-scheme", "prefer-light")
        expect(window, False, "explicit light preference removes Aurora dark provider")

        interface.set_string("color-scheme", "default")
        expect(window, True, "default preference returns to Aurora dark")

        accessibility.set_boolean("high-contrast", True)
        expect(window, False, "high contrast removes all Aurora glass/dark overrides")

        accessibility.set_boolean("high-contrast", False)
        expect(window, True, "disabling high contrast restores the selected dark scheme")
    finally:
        interface.set_string("color-scheme", original_scheme)
        accessibility.set_boolean("high-contrast", original_contrast)
        drain()
        window.destroy()
        application.quit()


app.connect("activate", activate)
raise SystemExit(app.run([]))
