#!/usr/bin/env python3
"""Render actual GTK icon lookups and audit installed desktop entries."""
import argparse
import json
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

parser = argparse.ArgumentParser()
parser.add_argument("theme_root", type=Path)
parser.add_argument("report", type=Path)
args = parser.parse_args()
Gtk.init()
theme = Gtk.IconTheme.new()
theme.set_search_path([str(args.theme_root), "/usr/share/icons"])
theme.set_theme_name("Aurora")
root = (args.theme_root / "Aurora").resolve()
names = sorted(p.stem for p in root.glob("scalable/*/*.svg"))
for name in names:
    icon = theme.lookup_icon(name, None, 48, 1, Gtk.TextDirection.LTR, Gtk.IconLookupFlags(0))
    file = icon.get_file()
    assert file is not None and Path(file.get_path()).resolve().is_relative_to(root), name
    # Force GTK to resolve the actual paintable rather than checking filenames only.
    assert icon.get_intrinsic_width() > 0, name

coverage = []
for app in Gio.AppInfo.get_all():
    if not app.should_show():
        continue
    icon = app.get_icon()
    if isinstance(icon, Gio.ThemedIcon):
        resolved = theme.lookup_icon(icon.get_names()[0], icon.get_names()[1:], 48, 1,
                                     Gtk.TextDirection.LTR, Gtk.IconLookupFlags(0)).get_file()
        own = resolved is not None and Path(resolved.get_path()).resolve().is_relative_to(root)
        coverage.append({"id": app.get_id(), "names": icon.get_names(), "aurora": own})
    else:
        coverage.append({"id": app.get_id(), "aurora": False, "reason": "non-themed-icon"})
args.report.write_text(json.dumps({"names": len(names), "desktop_entries": coverage}, indent=2))
print("PASS:", len(names), "GTK icon lookups resolved in Aurora", flush=True)

# A real GTK window with representative icons from the installed theme.
samples = [
    ("org.gnome.Epiphany", "Browser"), ("org.gnome.Nautilus", "Files"),
    ("org.gnome.Ptyxis", "Terminal"), ("org.gnome.Settings", "Settings"),
    ("com.localzet.Containers", "Containers"), ("com.localzet.Hardware", "Hardware"),
    ("com.localzet.WindowsRuntime", "Windows"), ("com.localzet.Connect", "Connect"),
    ("com.localzet.Settings", "Components"), ("org.gnome.TextEditor", "Editor"),
    ("org.gnome.Loupe", "Photos"), ("org.gnome.Totem", "Video"),
    ("org.gnome.Software", "Store"), ("org.gnome.Calculator", "Calculator"),
    ("org.gnome.FileRoller", "Archive"), ("com.localzet.Network", "Network"), ("folder", "Folder"),
    ("folder-download", "Downloads"), ("folder-pictures", "Pictures"),
    ("folder-music", "Music"), ("drive-harddisk", "SSD"), ("media-flash-usb", "USB"),
    ("application-pdf", "PDF"), ("user-trash", "Trash"),
    ("org.gnome.Snapshot", "Camera"), ("org.gnome.Calendar", "Calendar"),
    ("org.gnome.clocks", "Clock"), ("org.gnome.Evolution", "Mail"),
    ("virt-manager", "Virtual machines"), ("org.gnome.SimpleScan", "Scanner"),
    ("system-config-printer", "Printer"), ("com.localzet.Installer", "Installer"),
    ("com.localzet.AIWorkspace", "AI Workspace"), ("localzet-catalog-qbittorrent", "Torrent"),
    ("localzet-catalog-gimp", "Graphics"), ("drive-optical", "Optical"),
]
app = Gtk.Application(application_id="com.localzet.AuroraIconReview")

def activate(app):
    win = Gtk.ApplicationWindow(application=app, title="Aurora icon theme")
    win.set_default_size(980, 690)
    grid = Gtk.Grid(column_spacing=12, row_spacing=10)
    grid.set_margin_top(24)
    grid.set_margin_bottom(24)
    grid.set_margin_start(24)
    grid.set_margin_end(24)
    grid.set_column_homogeneous(True)
    for i, (name, label) in enumerate(samples):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        paintable = theme.lookup_icon(name, None, 48, 1, Gtk.TextDirection.LTR, Gtk.IconLookupFlags(0))
        image = Gtk.Image.new_from_paintable(paintable)
        image.set_pixel_size(48)
        box.append(image)
        box.append(Gtk.Label(label=label))
        grid.attach(box, i % 6, i // 6, 1, 1)
    win.set_child(grid)
    win.present()

app.connect("activate", activate)
app.run([])
