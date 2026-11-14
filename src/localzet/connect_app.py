"""Localzet Connect: user-initiated upstream Android integration."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tomllib

CLIENT = Path("/usr/bin/nectarlink-desktop")
BACKEND = Path("/usr/lib/localzet/install-nectarlink")
LOCK = Path("/opt/localzet-os/packaging/nectarlink/release.toml")


def main() -> int:
    import gi
    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gio, Gtk

    class Connect(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Connect")
            self.window = None
            self.running = False

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Connect")
            self.window.set_default_size(650, 460)
            self.window.connect("close-request", lambda *_: self.running)
            toolbar = Adw.ToolbarView()
            toolbar.add_top_bar(Adw.HeaderBar())
            self.window.set_content(toolbar)
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                           margin_top=24, margin_bottom=24, margin_start=28, margin_end=28)
            toolbar.set_content(page)
            icon = Gtk.Image.new_from_icon_name("phone-symbolic")
            icon.set_pixel_size(64)
            icon.set_halign(Gtk.Align.START)
            page.append(icon)
            title = Gtk.Label(label="Связь с телефоном", xalign=0)
            title.add_css_class("title-1")
            page.append(title)
            page.append(Gtk.Label(label="Android · NectarLink", xalign=0))
            page.append(Gtk.Label(
                label="Уведомления, файлы, буфер обмена и другие функции через локальную сеть. "
                      "Сопряжение и разрешения настраиваются в оригинальном клиенте.",
                wrap=True, xalign=0))
            self.version = Gtk.Label(wrap=True, xalign=0)
            self.version.add_css_class("dim-label")
            page.append(self.version)
            self.status = Gtk.Label(wrap=True, xalign=0, selectable=True)
            page.append(self.status)
            self.action = Gtk.Button()
            self.action.add_css_class("suggested-action")
            self.action.set_halign(Gtk.Align.START)
            self.action.connect("clicked", self.activate_client)
            page.append(self.action)
            link = Gtk.LinkButton(uri="https://github.com/thtbee/nectarlink", label="Исходный проект NectarLink")
            link.set_halign(Gtk.Align.START)
            page.append(link)
            self.refresh()
            self.window.present()

        def refresh(self):
            installed = CLIENT.is_file() and os.access(CLIENT, os.X_OK)
            if installed:
                self.version.set_label("Оригинальный клиент установлен.")
                self.status.set_label("Откройте NectarLink, чтобы добавить телефон.")
                self.action.set_label("Открыть NectarLink")
                self.action.set_sensitive(not self.running)
                return
            try:
                with LOCK.open("rb") as stream:
                    version = tomllib.load(stream)["version"]
                self.version.set_label(f"Официальный пакет {version}; SHA-256 проверяется перед установкой.")
            except (OSError, ValueError, KeyError):
                self.version.set_label("Закреплённый пакет недоступен.")
                self.action.set_sensitive(False)
                return
            live = "boot=casper" in Path("/proc/cmdline").read_text().split()
            self.action.set_label("Установить NectarLink")
            self.status.set_label(
                "Сначала установите Localzet OS на SSD." if live else
                "Пакет будет загружен с GitHub upstream. Потребуется подтверждение администратора."
            )
            self.action.set_sensitive(not live and BACKEND.is_file()
                                      and Path("/usr/bin/pkexec").is_file() and not self.running)

        def activate_client(self, *_):
            if self.running:
                return
            if CLIENT.is_file() and os.access(CLIENT, os.X_OK):
                try:
                    Gio.Subprocess.new([str(CLIENT)], Gio.SubprocessFlags.NONE)
                except Exception as error:
                    self.status.set_label(str(error))
                return
            try:
                self.running = True
                self.action.set_sensitive(False)
                self.status.set_label("Подтвердите установку. Не закрывайте приложение до завершения.")
                process = Gio.Subprocess.new(
                    ["/usr/bin/pkexec", str(BACKEND)],
                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
                )
                process.communicate_utf8_async(None, None, self.finished)
            except Exception as error:
                self.running = False
                self.refresh()
                self.status.set_label(str(error))

        def finished(self, process, result):
            self.running = False
            try:
                _, output, _ = process.communicate_utf8_finish(result)
                self.refresh()
                if not process.get_successful():
                    self.status.set_label("Установка не завершена.\n" + (output or "")[-1500:])
            except Exception as error:
                self.refresh()
                self.status.set_label(str(error))

    return Connect().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
