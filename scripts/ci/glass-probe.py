#!/usr/bin/env python3
"""High-frequency live backdrop used to verify GNOME compositor blur.

This is CI-only test content, not a wallpaper or product asset. The alternating
Violet/Ember tiles make a wallpaper-only or opaque overlay distinguishable from
a real Shell.BlurEffect BACKGROUND sample.
"""
import sys

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk


CELL = 12
EMBER = (1.0, 0.494, 0.0)
VIOLET = (0.608, 0.447, 0.949)


def draw_probe(_area, cr, width, height):
    for y in range(0, height, CELL):
        for x in range(0, width, CELL):
            color = EMBER if ((x // CELL) + (y // CELL)) % 2 == 0 else VIOLET
            cr.set_source_rgb(*color)
            cr.rectangle(x, y, CELL, CELL)
            cr.fill()


def activate(app):
    window = Gtk.ApplicationWindow(application=app)
    window.set_title("Localzet Glass Probe")
    window.set_default_size(1440, 900)
    window.set_decorated(False)
    area = Gtk.DrawingArea()
    area.set_draw_func(draw_probe)
    window.set_child(area)
    window.maximize()
    window.present()
    print("LOCALZET_GLASS_PROBE_READY", flush=True)


def main():
    app = Gtk.Application(
        application_id="org.localzet.GlassProbe",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    app.connect("activate", activate)
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
