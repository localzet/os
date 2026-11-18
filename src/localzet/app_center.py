"""Native application workspace: browse, search, launch and confirm installation."""
from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
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
            self.nav = {}
            self.groups = {}
            self.installed = frozenset()
            self.kinds = {}
            self.window = None
            self.section = "all"
            self.pool = ThreadPoolExecutor(max_workers=1)

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet — Приложения")
            self.window.add_css_class("localzet-app-workspace")
            self.appearance = apply_midnight(self.window)
            self.window.set_default_size(930, 620)
            self.window.set_size_request(720, 450)
            self.css = Gtk.CssProvider()
            self.css.load_from_data(b"""
                .localzet-app-workspace .app-sidebar { padding: 10px 8px; border-right: 1px solid alpha(currentColor,.12); }
                .localzet-midnight .app-sidebar { background-color: #292a2e; }
                .localzet-app-workspace .app-sidebar button { min-height: 24px; }
                .localzet-app-workspace .app-list .boxed-list { border-radius: 6px; }
                .localzet-app-workspace .app-list .boxed-list > row { border-radius: 4px; min-height: 46px; }
                .localzet-app-workspace .app-list .boxed-list > row > box { padding-top: 3px; padding-bottom: 3px; }
                .localzet-app-workspace .app-action { min-height: 26px; border-radius: 5px; }
                .localzet-app-workspace .app-sidebar button { padding: 5px 8px; border-radius: 5px; }
                .localzet-app-workspace .app-sidebar button.selected { background-color: alpha(currentColor,.12); font-weight: 600; }
                .localzet-app-workspace .app-heading { font-size: 18px; font-weight: 600; }
                .localzet-app-workspace .app-footer { padding: 6px 12px; border-top: 1px solid alpha(currentColor,.12); }
            """)
            Gtk.StyleContext.add_provider_for_display(self.window.get_display(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            header.set_title_widget(Adw.WindowTitle(title="Приложения", subtitle="Localzet OS"))
            self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Обновить состояние")
            self.refresh_button.connect("clicked", lambda *_: self.refresh())
            header.pack_end(self.refresh_button)
            toolbar.add_top_bar(header)
            self.window.set_content(toolbar)
            shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            workspace = Gtk.Box(vexpand=True)
            shell.append(workspace)
            toolbar.set_content(shell)
            sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, width_request=166)
            sidebar.add_css_class("app-sidebar")
            workspace.append(sidebar)
            label = Gtk.Label(label="КАТАЛОГ", xalign=0, margin_start=9, margin_bottom=7)
            label.add_css_class("dim-label")
            sidebar.append(label)
            sections = (("all", "Все приложения", "view-app-grid-symbolic"),
                        ("installed", "Установленные", "emblem-ok-symbolic"),
                        ("Игры", "Игры", "applications-games-symbolic"),
                        ("Связь и медиа", "Связь и медиа", "applications-multimedia-symbolic"),
                        ("Разработка и браузеры", "Разработка", "applications-development-symbolic"),
                        ("Офис", "Офис", "applications-office-symbolic"),
                        ("Система", "Система", "preferences-system-symbolic"))
            for index, (key, caption, icon) in enumerate(sections, 1):
                button = Gtk.Button()
                button.add_css_class("flat")
                content = Gtk.Box(spacing=9)
                content.append(Gtk.Image.new_from_icon_name(icon))
                content.append(Gtk.Label(label=caption, xalign=0, hexpand=True))
                button.set_child(content)
                button.connect("clicked", lambda _, selected=key: self.navigate(selected))
                sidebar.append(button)
                self.nav[key] = (button, caption)
                action = Gio.SimpleAction.new("section-" + str(index), None)
                action.connect("activate", lambda *_args, selected=key: self.navigate(selected))
                self.add_action(action)
                self.set_accels_for_action("app.section-" + str(index), ["<Control>" + str(index)])
            sidebar.append(Gtk.Box(vexpand=True))
            footnote = Gtk.Label(label="Ubuntu · Flathub\nОфициальные сайты", wrap=True, xalign=0, margin_start=9)
            footnote.add_css_class("dim-label")
            sidebar.append(footnote)

            main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True,
                           margin_top=12, margin_bottom=8, margin_start=14, margin_end=14)
            workspace.append(main)
            top = Gtk.Box(spacing=12)
            self.heading = Gtk.Label(xalign=0, hexpand=True)
            self.heading.add_css_class("app-heading")
            top.append(self.heading)
            self.search = Gtk.SearchEntry(placeholder_text="Поиск приложений", width_request=185)
            self.search.connect("search-changed", lambda *_: self.render())
            top.append(self.search)
            main.append(top)
            search_action = Gio.SimpleAction.new("search", None)
            search_action.connect("activate", lambda *_: self.search.grab_focus())
            self.add_action(search_action)
            self.set_accels_for_action("app.search", ["<Control>f"])
            self.summary = Gtk.Label(xalign=0)
            self.summary.add_css_class("dim-label")
            main.append(self.summary)
            scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
            main.append(scroll)
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            page.add_css_class("app-list")
            scroll.set_child(page)
            self.empty = Gtk.Label(label="Нет подходящих приложений", xalign=0, margin_top=20)
            self.empty.add_css_class("dim-label")
            page.append(self.empty)
            for key, item in app_catalog.APPS.items():
                if item.group not in self.groups:
                    self.groups[item.group] = Adw.PreferencesGroup(title=item.group)
                    page.append(self.groups[item.group])
                row = Adw.ActionRow(title=item.name, subtitle=item.note, title_lines=1, subtitle_lines=1)
                row.set_use_markup(False)
                image = Gtk.Image.new_from_icon_name(item.icon)
                image.set_pixel_size(28)
                row.add_prefix(image)
                state = Gtk.Label(xalign=1)
                state.add_css_class("dim-label")
                state.set_width_chars(9)
                state.set_valign(Gtk.Align.CENTER)
                row.add_suffix(state)
                button = Gtk.Button(valign=Gtk.Align.CENTER, width_request=94)
                button.add_css_class("app-action")
                button.connect("clicked", lambda _button, selected=key: self.activate_app(selected))
                row.add_suffix(button)
                self.groups[item.group].add(row)
                self.rows[key] = (row, button, state)
            self.status = Gtk.Label(label="", xalign=0, wrap=True, selectable=True)
            self.status.add_css_class("dim-label")
            self.status.add_css_class("app-footer")
            shell.append(self.status)
            self.navigate("all")
            self.refresh()
            self.window.present()

        def navigate(self, section):
            if section not in self.nav:
                return
            self.section = section
            caption = self.nav[section][1]
            self.heading.set_label(caption)
            self.window.set_title("Localzet — " + caption)
            for key, (button, _) in self.nav.items():
                (button.add_css_class if key == section else button.remove_css_class)("selected")
            self.render()

        def render(self):
            visible = set(app_catalog.visible_keys(self.section, self.search.get_text(), self.kinds))
            groups = set()
            for key, (row, _, _) in self.rows.items():
                row.set_visible(key in visible)
                if key in visible:
                    groups.add(app_catalog.APPS[key].group)
            for group, widget in self.groups.items():
                widget.set_visible(group in groups)
            self.empty.set_visible(not visible)
            count = sum(self.kinds.get(key) == "launch" for key in visible)
            self.summary.set_label(f"Приложений: {len(visible)}   ·   Установлено: {count}")

        def refresh(self):
            self.refresh_button.set_sensitive(False)
            self.status.set_label("Проверка установленных приложений…")
            for _, button, _ in self.rows.values():
                button.set_sensitive(False)
            future = self.pool.submit(app_catalog.flatpak_installed)
            future.add_done_callback(lambda result: GLib.idle_add(self.refresh_finished, result))

        def refresh_finished(self, future):
            if not self.window:
                return GLib.SOURCE_REMOVE
            self.refresh_button.set_sensitive(True)
            try:
                self.installed = future.result()
                self.status.set_label("Flatpak: установка для текущего пользователя с подтверждением источника и разрешений.")
            except (OSError, subprocess.SubprocessError):
                self.installed = frozenset()
                self.status.set_label("Не удалось прочитать список Flatpak. Повторите обновление.")
            labels = {"launch": "Открыть", "install": "Установить", "website": "Сайт", "missing": "Недоступно"}
            states = {"launch": "Установлено", "install": "Доступно", "website": "Внешний сайт", "missing": "Не установлено"}
            for key, (row, button, state) in self.rows.items():
                kind, command = app_catalog.action(key, self.installed)
                self.kinds[key] = kind
                button.set_label(labels[kind])
                button.set_sensitive(kind != "missing" and os.geteuid() != 0)
                state.set_label(app_catalog.action_source(key, kind, command))
                state.set_tooltip_text(states[kind])
                row.set_tooltip_text(app_catalog.APPS[key].note)
                if kind == "install":
                    button.add_css_class("suggested-action")
                else:
                    button.remove_css_class("suggested-action")
            self.render()
            return GLib.SOURCE_REMOVE

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
                        self.status.set_label("Подтвердите установку в Ptyxis, затем обновите список приложений.")
            except (OSError, ValueError, subprocess.SubprocessError, GLib.Error) as error:
                self.status.set_label(str(error))

        def do_shutdown(self):
            self.window = None
            self.pool.shutdown(wait=False, cancel_futures=True)
            Adw.Application.do_shutdown(self)

    return AppCenter().run([sys.argv[0]])
