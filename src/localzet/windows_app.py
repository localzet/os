"""Native Windows Runtime front end. It never runs a selected file automatically."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from localzet import windows_runtime


def main() -> int:
    import gi
    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gio, Gtk

    initial = Path(sys.argv[1]) if len(sys.argv) == 2 else None

    class Runtime(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.WindowsRuntime",
                             flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.file = None
            self.window = None

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Windows Runtime")
            self.window.set_default_size(650, 480)
            toolbar = Adw.ToolbarView()
            toolbar.add_top_bar(Adw.HeaderBar())
            self.window.set_content(toolbar)
            scroll = Gtk.ScrolledWindow()
            toolbar.set_content(scroll)
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                           margin_top=24, margin_bottom=24, margin_start=28, margin_end=28)
            scroll.set_child(page)
            title = Gtk.Label(label="Windows-приложения", xalign=0)
            title.add_css_class("title-1")
            page.append(title)
            description = Gtk.Label(
                label="Запускайте доверенные EXE и MSI через Wine. "
                      "Отдельный профиль хранит настройки и библиотеки приложения.",
                wrap=True, xalign=0)
            description.add_css_class("dim-label")
            page.append(description)
            group = Adw.PreferencesGroup(title="Приложение")
            self.file_row = Adw.ActionRow(title="Выберите файл EXE или MSI")
            choose = Gtk.Button(label="Выбрать")
            choose.set_valign(Gtk.Align.CENTER)
            choose.connect("clicked", self.choose)
            self.file_row.add_suffix(choose)
            group.add(self.file_row)
            self.profile = Adw.EntryRow(title="Профиль Wine")
            self.profile.set_text("default")
            self.profile.connect("changed", lambda *_: self.update())
            group.add(self.profile)
            page.append(group)
            self.trusted = Gtk.CheckButton(label="Я доверяю этому файлу и разрешаю его запуск")
            self.trusted.connect("toggled", lambda *_: self.update())
            page.append(self.trusted)
            warning = Gtk.Label(
                label="Wine не является песочницей. Windows-приложение может читать "
                      "ваши файлы и использовать сеть. Совместимость не гарантируется.",
                wrap=True, xalign=0)
            warning.add_css_class("warning")
            page.append(warning)
            self.launch = Gtk.Button(label="Запустить")
            self.launch.add_css_class("suggested-action")
            self.launch.set_halign(Gtk.Align.START)
            self.launch.connect("clicked", self.run_file)
            page.append(self.launch)
            self.status = Gtk.Label(wrap=True, xalign=0, selectable=True)
            page.append(self.status)
            if initial:
                self.set_file(initial)
            else:
                self.update()
            self.window.present()

        def choose(self, *_):
            dialog = Gtk.FileDialog(title="Выберите Windows-приложение")
            model = Gio.ListStore.new(Gtk.FileFilter)
            file_filter = Gtk.FileFilter()
            file_filter.set_name("Windows EXE / MSI")
            for pattern in ("*.exe", "*.EXE", "*.msi", "*.MSI"):
                file_filter.add_pattern(pattern)
            model.append(file_filter)
            dialog.set_filters(model)
            dialog.open(self.window, None, self.chosen)

        def chosen(self, dialog, result):
            try:
                file = dialog.open_finish(result)
                path = file.get_path()
                if not path:
                    raise ValueError("Поддерживаются только локальные файлы.")
                self.set_file(Path(path))
            except Exception:
                # Closing the native chooser must not start anything.
                return

        def set_file(self, path):
            self.file = path
            self.file_row.set_subtitle(str(path))
            self.trusted.set_active(False)
            self.update()

        def plan(self):
            if not self.file:
                raise ValueError("Выберите файл EXE или MSI.")
            data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
            return windows_runtime.launch_plan(self.file, self.profile.get_text(), data_home)

        def update(self):
            self.launch.set_sensitive(False)
            try:
                if os.geteuid() == 0:
                    raise ValueError("Запуск Windows-приложений от root запрещён.")
                if not windows_runtime.WINE.is_file() or not os.access(windows_runtime.WINE, os.X_OK):
                    raise ValueError("Wine не установлен. Установите проверенный пакет Wine из репозитория Ubuntu.")
                plan = self.plan()
                self.status.set_label(f"Профиль: {plan['profile']} · совместимость не проверена")
                self.launch.set_sensitive(self.trusted.get_active())
            except (OSError, ValueError, RuntimeError) as error:
                self.status.set_label(str(error))

        def run_file(self, *_):
            try:
                if not self.trusted.get_active():
                    return
                self.plan()
                process = Gio.Subprocess.new(
                    [sys.executable, str(Path(windows_runtime.__file__).resolve()),
                     str(self.file), "--profile", self.profile.get_text(), "--run"],
                    Gio.SubprocessFlags.NONE,
                )
                self.status.set_label("Wine запущен. При первом запуске создаётся профиль.")
                process.wait_async(None, self.finished)
                self.trusted.set_active(False)
            except Exception as error:
                self.status.set_label(f"Не удалось запустить приложение: {error}")

        def finished(self, process, result):
            try:
                process.wait_finish(result)
                if not process.get_successful():
                    self.status.set_label("Windows-приложение завершилось с ошибкой. Проверьте совместимость.")
                else:
                    self.status.set_label("Windows-приложение завершено.")
            except Exception as error:
                self.status.set_label(str(error))

    return Runtime().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
