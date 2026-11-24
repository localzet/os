"""Localzet Settings: native GTK4/libadwaita app, not an installer.

The only actions here launch predefined unprivileged system applications.
Not-yet-implemented modules have informational rows, never fake switches.
"""
from __future__ import annotations

from pathlib import Path
import sys
import os
from localzet.settings.appearance import (
    AppearanceError,
    EXTENSION_SCHEMA,
    apply_appearance,
    current_appearance,
    restore_appearance,
)
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

    # Aurora variants are dark; Adwaita follows the user's preferred dark mode.
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
            apps.add(self._row("Windows-приложения", "Localzet Windows Runtime · Wine", ["localzet-windows"]))
            phone = Adw.PreferencesGroup(title="Localzet Connect")
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

        def _appearance_page(self):
            page = Adw.PreferencesPage()
            current = current_appearance()
            self._appearance_buttons = {}
            group = Adw.PreferencesGroup(
                title="Aurora",
                description="Выберите одну из трёх утверждённых тёмных тем.",
            )
            choices = (
                ("blue", "Aurora Blue", "Сине-графитовые поверхности и голубые акценты"),
                ("purple", "Aurora Purple", "Сливовые поверхности и мягкие фиолетовые акценты"),
                ("black", "Aurora Black", "Почти чёрные поверхности и приглушённый фиолетовый акцент"),
            )
            for key, title, detail in choices:
                row = self._row(title, detail)
                selected = key == current
                button = Gtk.Button(label="Выбрано" if selected else "Применить")
                button.add_css_class("suggested-action" if selected else "flat")
                button.set_valign(Gtk.Align.CENTER)
                button.set_tooltip_text(
                    f"Текущая тема {title}" if selected else f"Применить тему {title}"
                )
                button.connect("clicked", lambda _button, value=key: self._choose_appearance(value))
                row.add_suffix(button)
                group.add(row)
                self._appearance_buttons[key] = button

            self._appearance_status = self._row(
                "Область применения",
                (
                    f"Активна Aurora {current.title()}. Обои, значки и Localzet Shell; "
                    "User Themes не требуется."
                ),
            )
            group.add(self._appearance_status)
            page.add(group)

            recovery = Adw.PreferencesGroup(
                title="Восстановление",
                description="Сохраняется снимок значений GNOME до первого изменения.",
            )
            restore = Gtk.Button(label="Восстановить исходный вид")
            restore.set_valign(Gtk.Align.CENTER)
            restore.connect("clicked", lambda _button: self._restore_appearance())
            row = self._row(
                "Предыдущие параметры GNOME",
                "Обои, цветовая схема, тема значков и доступные параметры Localzet Shell",
            )
            row.add_suffix(restore)
            recovery.add(row)
            page.add(recovery)
            return page

        def _refresh_appearance_selection(self):
            selected = current_appearance()
            for theme, button in self._appearance_buttons.items():
                active = theme == selected
                button.set_label("Выбрано" if active else "Применить")
                button.set_tooltip_text(
                    f"Текущая тема Aurora {theme.title()}"
                    if active else f"Применить тему Aurora {theme.title()}"
                )
                button.remove_css_class("suggested-action")
                button.remove_css_class("flat")
                button.add_css_class("suggested-action" if active else "flat")

        def _refresh_appearance_css(self):
            if not self.window:
                return
            for theme in ("blue", "purple", "black"):
                self.window.remove_css_class(f"aurora-{theme}")
            self.window.add_css_class(f"aurora-{current_appearance()}")

        def _choose_appearance(self, theme: str):
            try:
                changed = apply_appearance(theme)
            except AppearanceError as error:
                self.toasts.add_toast(Adw.Toast.new(str(error)))
                return
            self._refresh_appearance_css()
            self._refresh_appearance_selection()
            if f"{EXTENSION_SCHEMA} appearance" in changed:
                detail = "Localzet Shell обновится, если расширение включено; User Themes не требуется."
            else:
                detail = "Расширение Localzet Shell недоступно; применены обои, значки и тёмная схема."
            self._appearance_status.set_subtitle(f"Aurora {theme.title()} активна. {detail}")
            self.toasts.add_toast(Adw.Toast.new(f"Aurora {theme.title()} применена"))

        def _restore_appearance(self):
            try:
                result = restore_appearance()
            except AppearanceError as error:
                self.toasts.add_toast(Adw.Toast.new(str(error)))
                return
            self._refresh_appearance_css()
            self._refresh_appearance_selection()
            if result.pending:
                self._appearance_status.set_subtitle(
                    "Основные параметры восстановлены. Настройка Localzet Shell сохранена "
                    "до появления расширения."
                )
                self.toasts.add_toast(Adw.Toast.new(
                    f"Восстановлено: {result.restored}; ожидает Shell: {result.pending}"
                ))
                return
            self._appearance_status.set_subtitle(
                "Восстановлены исходные параметры GNOME. User Themes не изменялся."
            )
            self.toasts.add_toast(Adw.Toast.new(f"Восстановлено параметров: {result.restored}"))

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(
                application=self, title="Localzet Settings",
            )
            self.window.set_default_size(930, 650)
            self.window.add_css_class("localzet-settings")
            self.window.add_css_class(f"aurora-{current_appearance()}")
            stack = Adw.ViewStack()
            for page, name, title, icon in (
                (self._overview_page(), "home", "Главная", "go-home-symbolic"),
                (self._appearance_page(), "appearance", "Оформление", "preferences-desktop-theme-symbolic"),
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
