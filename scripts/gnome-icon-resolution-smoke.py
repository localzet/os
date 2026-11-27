#!/usr/bin/env python3
"""Check GTK's actual resolution of installed Localzet and upstream icons."""
from configparser import ConfigParser
import argparse
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gdk, Gtk


THEME_ROOT = Path("/usr/share/icons/Localzet")
APPLICATIONS = (
    Path("/usr/share/applications/org.gnome.Nautilus.desktop"),
    Path("/usr/share/applications/org.gnome.Ptyxis.desktop"),
)


def emit(line: str) -> None:
    print(line, flush=True)


def lookup(theme, name: str) -> Path | None:
    paintable = theme.lookup_icon(
        name,
        None,
        32,
        1,
        Gtk.TextDirection.LTR,
        Gtk.IconLookupFlags.NONE,
    )
    if paintable is None:
        return None
    icon_file = paintable.get_file()
    return Path(icon_file.get_path()) if icon_file and icon_file.get_path() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", type=int, default=1)
    args = parser.parse_args()
    Gtk.init()
    display = Gdk.Display.get_default()
    if display is None:
        emit("LOCALZET_ICON_RESULT FAIL no-gtk-display")
        return 1

    configured_theme = Gio.Settings.new("org.gnome.desktop.interface").get_string(
        "icon-theme"
    )
    theme = Gtk.IconTheme.get_for_display(display)
    icon_paths = sorted(THEME_ROOT.rglob("*.svg"))
    missing_local: list[str] = []
    resolutions: list[tuple[str, Path | None]] = []

    for path in icon_paths:
        icon_name = path.stem
        resolved = lookup(theme, icon_name)
        local = resolved is not None and resolved.is_relative_to(THEME_ROOT)
        resolutions.append((icon_name, resolved))
        if not local:
            missing_local.append(icon_name)

    upstream_errors: list[str] = []
    upstream_count = 0
    for desktop_path in APPLICATIONS:
        if not desktop_path.is_file():
            upstream_errors.append(f"missing desktop entry {desktop_path.name}")
            continue
        entry = ConfigParser(interpolation=None)
        entry.read(desktop_path, encoding="utf-8")
        icon_name = entry["Desktop Entry"].get("Icon", "")
        resolved = lookup(theme, icon_name) if icon_name else None
        is_local = resolved is not None and resolved.is_relative_to(THEME_ROOT)
        emit(f"Upstream {desktop_path.name} ({icon_name}): {resolved or 'UNRESOLVED'}")
        if resolved is None or is_local:
            upstream_errors.append(f"upstream icon did not resolve: {desktop_path.name}")
        else:
            upstream_count += 1

    page_size = 30
    page_count = max(1, (len(resolutions) + page_size - 1) // page_size)
    if not 1 <= args.page <= page_count:
        parser.error(f"--page must be between 1 and {page_count}")
    start = (args.page - 1) * page_size
    visible = resolutions[start:start + page_size]
    emit(f"GTK icon theme: {configured_theme}")
    emit(f"Localzet icon resolution page {args.page}/{page_count}")
    for icon_name, resolved in visible:
        emit(f"{icon_name}: {resolved or 'UNRESOLVED'}")
    for desktop_path in APPLICATIONS:
        if not desktop_path.is_file():
            continue
        entry = ConfigParser(interpolation=None)
        entry.read(desktop_path, encoding="utf-8")
        icon_name = entry["Desktop Entry"].get("Icon", "")
        resolved = lookup(theme, icon_name) if icon_name else None
        emit(f"Upstream {desktop_path.stem}: {icon_name} -> {resolved or 'UNRESOLVED'}")

    status = "PASS" if not missing_local and not upstream_errors and configured_theme == "Localzet" else "FAIL"
    emit(
        f"LOCALZET_ICON_RESULT {status} local={len(icon_paths) - len(missing_local)}/{len(icon_paths)} "
        f"upstream={upstream_count}/{len(APPLICATIONS)} theme={configured_theme}"
    )
    for error in missing_local + upstream_errors:
        emit(f"LOCALZET_ICON_ERROR {error}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
