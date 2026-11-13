"""Localzet Settings: native GTK4/libadwaita app, not an installer.

The only actions here launch predefined unprivileged system applications.
Not-yet-implemented modules have informational rows, never fake switches.
"""
from __future__ import annotations

from pathlib import Path
import sys
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

    # Localzet Aurora is dark-first. Expose a theme switch in a later milestone.
    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)

    class SettingsApp(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Settings", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
            self.window = None

        def _start(self, command: list[str]) -> None:
            try:
                Gio.Subprocess.new(command, Gio.SubprocessFlags.NONE)
            except Exception as error:
                self.toasts.add_toast(Adw.Toast.new(f"Не удалось открыть приложение: {error}"))

        def _row(self, title: str, detail: str, command: list[str] | None = None):
            row = Adw.ActionRow(title=title, subtitle=detail)
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
                title="Localzet OS",
                description="Your workspace. Your rules.",
            )
            system.add_css_class("localzet-summary")
            for name, subtitle, command in (
                ("Сеть", "Wi-Fi, Ethernet и сетевые подключения", ["gnome-control-center", "network"]),
                ("Мониторы", "Разрешение, расположение и масштабирование", ["gnome-control-center", "display"]),
                ("Звук", "Устройства ввода и вывода", ["gnome-control-center", "sound"]),
                ("Питание", "Параметры энергопотребления", ["gnome-control-center", "power"]),
            ):
                system.add(self._row(name, subtitle, command))
            page.add(system)
            apps = Adw.PreferencesGroup(title="Приложения")
            apps.add(self._row("Файлы", "Папки и накопители", ["nautilus"]))
            apps.add(self._row("Терминал", "Командная строка", ["ptyxis"]))
            phone = Adw.PreferencesGroup(title="Localzet Connect")
            client = Gio.DesktopAppInfo.new("nectarlink.desktop")
            if client:
                phone.add(self._row("Связь с телефоном", "Android · NectarLink", ["/usr/bin/nectarlink-desktop"]))
            else:
                phone.add(self._row("Связь с телефоном", "NectarLink не установлен"))
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

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(
                application=self, title="Localzet Settings",
            )
            self.window.set_default_size(930, 650)
            self.window.add_css_class("localzet-settings")
            stack = Adw.ViewStack()
            for page, name, title, icon in (
                (self._overview_page(), "home", "Главная", "go-home-symbolic"),
                (self._modules_page(), "modules", "Модули", "application-x-addon-symbolic"),
                (self._system_page(), "system", "Система", "computer-symbolic"),
            ):
                stack.add_titled_with_icon(page, name, title, icon)
            header = Adw.HeaderBar()
            header.set_title_widget(Adw.ViewSwitcher(
                stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE,
            ))
            toolbar = Adw.ToolbarView()
            toolbar.add_top_bar(header)
            toolbar.set_content(stack)
            self.toasts = Adw.ToastOverlay()
            self.toasts.set_child(toolbar)
            self.window.set_content(self.toasts)

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
