"""Native application center for actual local launch and user-confirmed installation."""
from __future__ import annotations

import os
import subprocess
import sys
from localzet import app_catalog


def main() -> int:
    import gi
    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gio, GLib, Gtk
    from localzet.appearance import apply_midnight

    class AppCenter(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Apps", flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.rows = {}
            self.window = None

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet — Приложения")
            self.appearance = apply_midnight(self.window)
            self.window.set_default_size(740, 670)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Обновить состояние")
            refresh.connect("clicked", lambda *_: self.refresh())
            header.pack_end(refresh)
            toolbar.add_top_bar(header)
            self.window.set_content(toolbar)
            scroll = Gtk.ScrolledWindow()
            toolbar.set_content(scroll)
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                           margin_top=22, margin_bottom=22, margin_start=24, margin_end=24)
            scroll.set_child(page)
            title = Gtk.Label(label="Приложения", xalign=0)
            title.add_css_class("title-1")
            page.append(title)
            self.status = Gtk.Label(label="", xalign=0, wrap=True)
            self.status.add_css_class("dim-label")
            page.append(self.status)
            groups = {}
            for key, item in app_catalog.APPS.items():
                if item.group not in groups:
                    groups[item.group] = Adw.PreferencesGroup(title=item.group)
                    page.append(groups[item.group])
                row = Adw.ActionRow(title=item.name, subtitle=item.note, subtitle_lines=3)
                image = Gtk.Image.new_from_icon_name(item.icon)
                image.set_pixel_size(28)
                row.add_prefix(image)
                button = Gtk.Button(valign=Gtk.Align.CENTER)
                button.connect("clicked", lambda _button, selected=key: self.activate_app(selected))
                row.add_suffix(button)
                groups[item.group].add(row)
                self.rows[key] = button
            self.refresh()
            self.window.present()

        def refresh(self):
            try:
                self.installed = app_catalog.flatpak_installed()
                self.status.set_label("Установка Flatpak — для текущего пользователя. Подтвердите источник и разрешения в открывшемся окне. После установки нажмите «Обновить».")
            except (OSError, subprocess.SubprocessError):
                self.installed = frozenset()
                self.status.set_label("Не удалось прочитать список Flatpak. Повторите обновление.")
            labels = {"launch": "Открыть", "install": "Установить", "website": "Сайт", "missing": "Недоступно"}
            for key, button in self.rows.items():
                kind, _ = app_catalog.action(key, self.installed)
                button.set_label(labels[kind])
                button.set_sensitive(kind != "missing" and os.geteuid() != 0)

        def activate_app(self, key):
            if os.geteuid() == 0:
                return
            try:
                kind, value = app_catalog.action(key, self.installed)
                if kind == "website":
                    Gio.AppInfo.launch_default_for_uri(value, None)
                elif kind in ("launch", "install"):
                    subprocess.Popen(value, start_new_session=True)
                    if kind == "install":
                        self.status.set_label("Подтвердите установку в Ptyxis. Затем обновите список; открытие терминала не означает, что установка завершилась.")
            except (OSError, ValueError, subprocess.SubprocessError, GLib.Error) as error:
                self.status.set_label(str(error))

    return AppCenter().run([sys.argv[0]])
