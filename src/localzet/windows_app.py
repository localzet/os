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
            from localzet.appearance import apply_midnight, palette_css
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Windows Runtime")
            self.appearance = apply_midnight(self.window)
            self.window.set_default_size(940, 620)
            self.window.set_size_request(700, 460)
            self.window.add_css_class("windows-workspace")
            self.css = Gtk.CssProvider()
            self.css.load_from_data(palette_css(b"""
                .windows-workspace .runtime-sidebar { padding: 12px 8px; border-right: 1px solid alpha(currentColor,.12); }
                .localzet-midnight .runtime-sidebar { background-color: __SURFACE__; }
                .windows-workspace .runtime-sidebar button { padding: 8px 10px; border-radius: 6px; }
                .windows-workspace .runtime-sidebar button.selected { background-color: __SELECTION__; color: __TEXT__; font-weight: 600; }
                .windows-workspace .runtime-content { padding: 16px 20px; }
                .windows-workspace .runtime-heading { font-size: 21px; font-weight: 600; }
                .windows-workspace .runtime-actions button { border-radius: 6px; min-height: 28px; }
                .windows-workspace .boxed-list > row { min-height: 44px; border-radius: 6px; }
            """))
            Gtk.StyleContext.add_provider_for_display(self.window.get_display(), self.css,
                                                       Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            header.set_title_widget(Adw.WindowTitle(title="Windows Runtime", subtitle="Localzet OS"))
            toolbar.add_top_bar(header)
            self.window.set_content(toolbar)
            workspace = Gtk.Box()
            toolbar.set_content(workspace)
            sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, width_request=176)
            sidebar.set_hexpand(False)
            sidebar.add_css_class("runtime-sidebar")
            caption = Gtk.Label(label="СОВМЕСТИМОСТЬ", xalign=0, margin_start=9, margin_bottom=8)
            caption.add_css_class("dim-label")
            sidebar.append(caption)
            workspace.append(sidebar)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
            content.add_css_class("runtime-content")
            workspace.append(content)
            self.heading = Gtk.Label(xalign=0)
            self.heading.add_css_class("runtime-heading")
            content.append(self.heading)
            self.description = Gtk.Label(xalign=0, wrap=True)
            self.description.add_css_class("dim-label")
            content.append(self.description)
            self.stack = Gtk.Stack(vexpand=True, hexpand=True)
            content.append(self.stack)
            self.nav = {}
            pages = {}
            for index, (key, title, description, icon) in enumerate((
                ("run", "Запуск", "EXE и MSI · отдельные профили Wine", "system-run-symbolic"),
                ("library", "Библиотека", "Сохранённые ярлыки и профили приложений", "view-app-grid-symbolic"),
                ("office", "Office", "Microsoft 365 · официальные способы установки", "applications-office-symbolic"),
            ), 1):
                button = Gtk.Button()
                button.add_css_class("flat")
                box = Gtk.Box(spacing=9)
                box.append(Gtk.Image.new_from_icon_name(icon))
                box.append(Gtk.Label(label=title, xalign=0, hexpand=True))
                button.set_child(box)
                button.connect("clicked", lambda _button, selected=key: self.navigate(selected))
                sidebar.append(button)
                self.nav[key] = (button, title, description)
                action = Gio.SimpleAction.new("section-" + str(index), None)
                action.connect("activate", lambda *_args, selected=key: self.navigate(selected))
                self.add_action(action)
                self.set_accels_for_action("app.section-" + str(index), ["<Control>" + str(index)])
                scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
                page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_end=6)
                scroll.set_child(page)
                self.stack.add_named(scroll, key)
                pages[key] = page
            sidebar.append(Gtk.Box(vexpand=True))
            note = Gtk.Label(label="Wine · Localzet OS", xalign=0, margin_start=9)
            note.add_css_class("dim-label")
            sidebar.append(note)
            page = pages["office"]
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
            page = pages["run"]
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
            actions = Gtk.Box(spacing=8, halign=Gtk.Align.START)
            actions.add_css_class("runtime-actions")
            actions.append(self.launch)
            self.save_button = Gtk.Button(label="Добавить в меню")
            self.save_button.connect("clicked", self.save_shortcut)
            actions.append(self.save_button)
            page.append(actions)
            page = pages["library"]
            self.saved_group = Adw.PreferencesGroup(title="Мои Windows-приложения",
                description="Выберите ярлык, чтобы открыть сохранённый профиль. Удаление ярлыка не удаляет программу.")
            self.saved_rows = []
            page.append(self.saved_group)
            self.empty_library = Gtk.Label(label="Нет сохранённых ярлыков. Добавьте доверенный EXE на странице запуска.",
                                           wrap=True, xalign=0)
            self.empty_library.add_css_class("dim-label")
            page.append(self.empty_library)
            self.status = Gtk.Label(wrap=True, xalign=0, selectable=True, max_width_chars=75)
            self.status.add_css_class("dim-label")
            content.append(self.status)
            self.navigate("run")
            self.refresh_shortcuts()
            if initial:
                self.set_file(initial)
            else:
                self.update()
            if startup_error:
                self.status.set_label(startup_error)
            self.window.present()

        def navigate(self, key):
            self.stack.set_visible_child_name(key)
            for name, (button, title, description) in self.nav.items():
                if name == key:
                    button.add_css_class("selected")
                    self.heading.set_label(title)
                    self.description.set_label(description)
                    self.window.set_title("Localzet Windows Runtime — " + title)
                else:
                    button.remove_css_class("selected")

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
                self.empty_library.set_visible(not self.saved_rows)
            except (OSError, ValueError, TypeError) as error:
                self.status.set_label(str(error))

        def select_shortcut(self, key):
            try:
                record = store.load(key)
                self.profile.set_text(record["profile"])
                self.set_file(Path(record["file"]))
                self.name.set_text(record["title"])
                self.navigate("run")
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
