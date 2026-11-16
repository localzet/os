"""Localzet Settings: native GTK4/libadwaita app, not an installer.

The only actions here launch predefined unprivileged system applications.
Not-yet-implemented modules have informational rows, never fake switches.
"""
from __future__ import annotations

from pathlib import Path
import sys
import os
from localzet.settings.core import load_modules, status_label, system_info


def main() -> int:
    try:
        import gi
        gi.require_version("Adw", "1")
        gi.require_version("Gtk", "4.0")
        from gi.repository import Adw, Gdk, Gio, Gtk
    except (ImportError, ValueError) as exc:
        print(f"Localzet Settings requires GTK4, libadwaita and python3-gi: {exc}", file=sys.stderr)
        return 2


    class SettingsApp(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Settings", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
            self.window = None

        def _start(self, command: list[str]) -> None:
            try:
                Gio.Subprocess.new(command, Gio.SubprocessFlags.NONE)
            except Exception as error:
                self.toasts.add_toast(Adw.Toast.new(f"Не удалось открыть приложение: {error}"))

        def _row(self, title: str, detail: str, command: list[str] | None = None, icon: str | None = None):
            row = Adw.ActionRow(title=title, subtitle=detail)
            row.set_use_markup(False)
            if icon:
                row.add_prefix(Gtk.Image.new_from_icon_name(icon))
            if command:
                button = Gtk.Button(icon_name="go-next-symbolic")
                button.add_css_class("flat")
                button.set_valign(Gtk.Align.CENTER)
                button.set_tooltip_text("Открыть")
                button.connect("clicked", lambda _button, args=command: self._start(args))
                row.add_suffix(button)
                row.set_activatable_widget(button)
            return row

        def _overview_page(self):
            page = Adw.PreferencesPage()
            system = Adw.PreferencesGroup(
                title="Рабочая среда",
                description="Основные настройки устройства и рабочего стола.",
            )
            system.add_css_class("localzet-summary")
            for name, subtitle, command, icon in (
                ("Внешний вид", "Обои, цветовая схема и акцент", ["gnome-control-center", "appearance"], "preferences-desktop-wallpaper-symbolic"),
                ("Сеть", "Wi-Fi, Ethernet и сетевые подключения", ["gnome-control-center", "network"], "network-wired-symbolic"),
                ("Мониторы", "Разрешение, расположение и масштабирование", ["gnome-control-center", "display"], "video-display-symbolic"),
                ("Звук", "Устройства ввода и вывода", ["gnome-control-center", "sound"], "audio-speakers-symbolic"),
                ("Питание", "Параметры энергопотребления", ["gnome-control-center", "power"], "battery-symbolic"),
            ):
                system.add(self._row(name, subtitle, command, icon))
            page.add(system)
            apps = Adw.PreferencesGroup(title="Приложения и инструменты")
            apps.add(self._row("Файлы", "Папки и накопители", ["nautilus"], "folder-symbolic"))
            apps.add(self._row("Терминал", "Командная строка", ["ptyxis"]))
            apps.add(self._row("Частные сети", "NetBird · состояние VPN и подключение", ["localzet-network"]))
            apps.add(self._row("Оборудование", "Драйверы, GPU и состояние CUDA", ["localzet-hardware-manager"]))
            apps.add(self._row("Windows-приложения", "Localzet Windows Runtime · Wine", ["localzet-windows"]))
            phone = Adw.PreferencesGroup(title="NectarLink")
            client = Path("/usr/bin/nectarlink-desktop")
            status = "Android · NectarLink" if client.is_file() and os.access(client, os.X_OK) else "Настроить связь с Android"
            phone.add(self._row("Связь с телефоном", status, ["localzet-connect"]))
            page.add(apps)
            page.add(phone)
            return page

        def _modules_page(self):
            page = Adw.PreferencesPage()
            group = Adw.PreferencesGroup(
                title="Модули Localzet OS",
                description="Каталог возможностей. Установка появится после проверки системного backend.",
            )
            root = Path(__file__).resolve().parents[3]
            options = (Path("/opt/localzet-os/config/modules"), root / "config/modules")
            catalog = next((path for path in options if path.is_dir()), None)
            if catalog:
                try:
                    for module in load_modules(catalog):
                        group.add(self._row(
                            f"{module.title} · {status_label(module.status)}",
                            module.description,
                        ))
                except (OSError, ValueError) as error:
                    group.add(self._row("Каталог недоступен", str(error)))
            else:
                group.add(self._row("Каталог недоступен", "Не найдены описания модулей"))
            page.add(group)
            return page

        def _system_page(self):
            page = Adw.PreferencesPage()
            data = system_info()
            group = Adw.PreferencesGroup(
                title="О системе", description="Только чтение, без телеметрии",
            )
            for name, value in (
                ("Система", data.system),
                ("Ядро Linux", data.kernel),
                ("Архитектура", data.architecture),
                ("Логических процессоров", data.processors),
                ("Оперативная память", data.memory),
                ("Системный диск", data.root_storage),
            ):
                group.add(self._row(name, value))
            page.add(group)
            return page

        def _navigate(self, _list, row):
            if row is None:
                return
            name = row.get_name()
            self.stack.set_visible_child_name(name)
            print("Localzet Settings: page=" + name, flush=True)

        def do_activate(self):
            from localzet.appearance import apply_midnight
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(
                application=self, title="Localzet Settings",
            )
            self.appearance = apply_midnight(self.window)
            self.window.set_default_size(1000, 700)
            self.window.set_size_request(660, 440)
            self.window.add_css_class("localzet-settings")
            self.stack = Adw.ViewStack()
            pages = (
                (self._overview_page(), "home", "Рабочая среда", "go-home-symbolic", "Настройки рабочего стола и устройства"),
                (self._modules_page(), "modules", "Компоненты", "application-x-addon-symbolic", "Каталог возможностей Localzet OS"),
                (self._system_page(), "system", "О системе", "computer-symbolic", "Сведения о текущей системе"),
            )
            self.nav = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
            self.nav.add_css_class("executive-nav")
            self.nav_rows = {}
            for page, name, title, icon, detail in pages:
                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                                  margin_top=20, margin_bottom=4, margin_start=28, margin_end=28)
                heading.add_css_class("executive-page-heading")
                title_label = Gtk.Label(label=title, xalign=0)
                title_label.add_css_class("title-1")
                heading.append(title_label)
                subtitle = Gtk.Label(label=detail, xalign=0, wrap=True)
                subtitle.add_css_class("dim-label")
                heading.append(subtitle)
                content.append(heading)
                page.set_vexpand(True)
                content.append(page)
                self.stack.add_titled_with_icon(content, name, title, icon)
                row = Gtk.ListBoxRow()
                row.set_name(name)
                row_content = Gtk.Box(spacing=10, margin_top=10, margin_bottom=10,
                                      margin_start=12, margin_end=12)
                row_content.append(Gtk.Image.new_from_icon_name(icon))
                row_content.append(Gtk.Label(label=title, xalign=0, hexpand=True))
                row.set_child(row_content)
                self.nav.append(row)
                self.nav_rows[name] = row
            self.nav.connect("row-selected", self._navigate)
            sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            sidebar.add_css_class("executive-sidebar")
            sidebar.set_size_request(212, -1)
            brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                            margin_top=18, margin_start=16, margin_end=16)
            label = Gtk.Label(label="Localzet OS", xalign=0)
            label.add_css_class("title-2")
            brand.append(label)
            caption = Gtk.Label(label="Aurora · Executive", xalign=0)
            caption.add_css_class("dim-label")
            brand.append(caption)
            sidebar.append(brand)
            sidebar.append(self.nav)
            sidebar.append(Gtk.Box(vexpand=True))
            footer = Gtk.Label(label="Системные компоненты", xalign=0,
                               margin_start=16, margin_bottom=16)
            footer.add_css_class("dim-label")
            sidebar.append(footer)
            layout = Gtk.Box()
            layout.append(sidebar)
            layout.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
            self.stack.set_hexpand(True)
            layout.append(self.stack)
            header = Adw.HeaderBar()
            header.set_title_widget(Adw.WindowTitle(title="Настройки Localzet", subtitle=""))
            toolbar = Adw.ToolbarView()
            toolbar.add_top_bar(header)
            toolbar.set_content(layout)
            self.toasts = Adw.ToastOverlay()
            self.toasts.set_child(toolbar)
            self.window.set_content(self.toasts)
            for index, name in enumerate(("home", "modules", "system"), 1):
                action = Gio.SimpleAction.new("page-" + name, None)
                action.connect("activate", lambda _a, _p, n=name: self.nav.select_row(self.nav_rows[n]))
                self.add_action(action)
                self.set_accels_for_action("app.page-" + name, [f"<Control>{index}"])
            self.nav.select_row(self.nav_rows["home"])

            path = Path("/usr/share/localzet/styles/settings.css")
            if not path.is_file():
                path = Path(__file__).resolve().parents[3] / "apps/localzet-settings/settings.css"
            if path.is_file():
                css = Gtk.CssProvider()
                css.load_from_path(str(path))
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                    )
            self.window.present()

    return SettingsApp().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
