"""Native Windows Runtime front end. It never runs a selected file automatically."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from localzet import windows_runtime, windows_shortcuts


def main() -> int:
    import gi
    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gio, Gtk

    store = windows_shortcuts.ShortcutStore()
    initial = Path(sys.argv[1]) if len(sys.argv) == 2 else None
    initial_profile = "default"
    startup_error = None
    if len(sys.argv) == 3 and sys.argv[1] == "--shortcut":
        try:
            saved = store.load(sys.argv[2])
            initial, initial_profile = Path(saved["file"]), saved["profile"]
        except (OSError, ValueError, TypeError, KeyError) as error:
            startup_error = str(error)
    elif len(sys.argv) > 2:
        startup_error = "Неизвестный параметр запуска"

    class Runtime(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.WindowsRuntime",
                             flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.file = None
            self.window = None

        def do_activate(self):
            from localzet.appearance import apply_midnight
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Windows Runtime")
            self.appearance = apply_midnight(self.window)
            self.window.set_default_size(720, 680)
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
            office = Adw.PreferencesGroup(title="Microsoft 365",
                description="Настольный Office требует лицензии и совместимого Windows-окружения. "
                            "Работа современной версии через Wine не подтверждена.")
            web = Gtk.LinkButton(uri="https://www.microsoft365.com/",
                                 label="Открыть Microsoft 365 в браузере", halign=Gtk.Align.START)
            office.add(web)
            official = Gtk.LinkButton(
                uri="https://support.microsoft.com/ru-ru/office/lifecycle/officeinstall/use-the-office-offline-installer",
                label="Официальная установка и активация Office", halign=Gtk.Align.START)
            office.add(official)
            page.append(office)
            group = Adw.PreferencesGroup(title="Приложение")
            self.file_row = Adw.ActionRow(title="Выберите файл EXE или MSI")
            choose = Gtk.Button(label="Выбрать")
            choose.set_valign(Gtk.Align.CENTER)
            choose.connect("clicked", self.choose)
            self.file_row.add_suffix(choose)
            group.add(self.file_row)
            self.profile = Adw.EntryRow(title="Профиль Wine")
            self.profile.set_text(initial_profile)
            self.profile.connect("changed", lambda *_: self.update())
            group.add(self.profile)
            self.name = Adw.EntryRow(title="Название в меню")
            self.name.connect("changed", lambda *_: self.update())
            group.add(self.name)
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
            actions = Gtk.Box(spacing=8)
            actions.append(self.launch)
            self.save_button = Gtk.Button(label="Добавить в меню")
            self.save_button.connect("clicked", self.save_shortcut)
            actions.append(self.save_button)
            page.append(actions)
            self.saved_group = Adw.PreferencesGroup(title="Мои Windows-приложения",
                description="Выберите ярлык, чтобы открыть сохранённый профиль. Удаление ярлыка не удаляет программу.")
            self.saved_rows = []
            page.append(self.saved_group)
            self.status = Gtk.Label(wrap=True, xalign=0, selectable=True)
            page.append(self.status)
            self.refresh_shortcuts()
            if initial:
                self.set_file(initial)
            else:
                self.update()
            if startup_error:
                self.status.set_label(startup_error)
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
            self.name.set_text(path.stem[:100])
            self.trusted.set_active(False)
            self.update()

        def plan(self):
            if not self.file:
                raise ValueError("Выберите файл EXE или MSI.")
            data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
            return windows_runtime.launch_plan(self.file, self.profile.get_text(), data_home)

        def update(self):
            self.launch.set_sensitive(False)
            self.save_button.set_sensitive(False)
            try:
                if os.geteuid() == 0:
                    raise ValueError("Запуск Windows-приложений от root запрещён.")
                if not windows_runtime.WINE.is_file() or not os.access(windows_runtime.WINE, os.X_OK):
                    raise ValueError("Wine не установлен. Установите проверенный пакет Wine из репозитория Ubuntu.")
                plan = self.plan()
                architecture = {"x86": "32-бит (x86)", "x86-64": "64-бит (x86-64)",
                                "msi-unknown": "MSI, архитектура не определена"}[plan["architecture"]]
                self.status.set_label(f"Профиль: {plan['profile']} · {architecture} · совместимость не проверена")
                self.launch.set_sensitive(self.trusted.get_active())
                if plan["architecture"] != "msi-unknown" and self.trusted.get_active():
                    try:
                        windows_shortcuts.clean_title(self.name.get_text())
                        self.save_button.set_sensitive(True)
                    except ValueError:
                        pass
            except (OSError, ValueError, RuntimeError) as error:
                self.status.set_label(str(error))

        def refresh_shortcuts(self):
            for row in self.saved_rows:
                self.saved_group.remove(row)
            self.saved_rows.clear()
            try:
                for key, record in store.list():
                    row = Adw.ActionRow(title=record["title"], subtitle=record["profile"])
                    row.set_use_markup(False)
                    select = Gtk.Button(label="Выбрать", valign=Gtk.Align.CENTER)
                    select.connect("clicked", lambda _, selected=key: self.select_shortcut(selected))
                    remove = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                        tooltip_text="Удалить только ярлык")
                    remove.connect("clicked", lambda _, selected=key: self.remove_shortcut(selected))
                    row.add_suffix(select)
                    row.add_suffix(remove)
                    self.saved_group.add(row)
                    self.saved_rows.append(row)
            except (OSError, ValueError, TypeError) as error:
                self.status.set_label(str(error))

        def select_shortcut(self, key):
            try:
                record = store.load(key)
                self.profile.set_text(record["profile"])
                self.set_file(Path(record["file"]))
                self.name.set_text(record["title"])
            except (OSError, ValueError, TypeError, KeyError) as error:
                self.status.set_label(str(error))

        def save_shortcut(self, *_):
            if not self.trusted.get_active() or os.geteuid() == 0:
                return
            try:
                store.save(self.file, self.profile.get_text(), self.name.get_text())
                self.refresh_shortcuts()
                self.trusted.set_active(False)
                self.status.set_label("Ярлык добавлен в меню. Запуск требует подтверждения доверия.")
            except (OSError, ValueError, TypeError) as error:
                self.status.set_label(str(error))

        def remove_shortcut(self, key):
            if os.geteuid() == 0:
                return
            try:
                store.remove(key)
                self.refresh_shortcuts()
                self.status.set_label("Ярлык удалён; файлы и профиль Wine сохранены.")
            except (OSError, ValueError, TypeError, KeyError) as error:
                self.status.set_label(str(error))

        def run_file(self, *_):
            try:
                if not self.trusted.get_active():
                    return
                self.plan()
                process = Gio.Subprocess.new(
                    [sys.executable, str(Path(windows_runtime.__file__).resolve()),
                     str(self.file.resolve()), "--profile", self.profile.get_text(), "--run"],
                    Gio.SubprocessFlags.NONE,
                )
                self.trusted.set_active(False)
                self.status.set_label("Wine запущен. При первом запуске создаётся профиль.")
                process.wait_async(None, self.finished)
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
