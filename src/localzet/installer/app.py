"""Native interactive installer candidate; no privileged actions until confirmation."""
from __future__ import annotations

import json
import sys

from localzet.installer.interactive import (
    confirmation_for, eligible_plan, live_source_disk, validate_request
)
from localzet.installer.preflight import read_lsblk
from localzet.installer.target import identity


def main() -> int:
    import gi
    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gio, Gtk

    class Installer(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Installer",
                             flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
            self.plan = None
            self.running = False
            self.window = None

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Установка Localzet OS")
            self.window.set_default_size(740, 660)
            self.window.connect("close-request", lambda *_: self.running)
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            toolbar = Adw.ToolbarView()
            toolbar.add_top_bar(Adw.HeaderBar())
            self.window.set_content(toolbar)
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            toolbar.set_content(scroll)
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
            page.set_margin_top(24)
            page.set_margin_bottom(24)
            page.set_margin_start(32)
            page.set_margin_end(32)
            scroll.set_child(page)

            title = Gtk.Label(label="Установите Localzet OS")
            title.add_css_class("title-1")
            title.set_xalign(0)
            page.append(title)
            introduction = Gtk.Label(
                label="Первоначальная установка на отдельный пустой внутренний SSD. "
                      "Требуется UEFI без Secure Boot. Остальные накопители должны быть отключены.",
                wrap=True, xalign=0)
            introduction.add_css_class("dim-label")
            page.append(introduction)

            self.disk_group = Adw.PreferencesGroup(title="1. Целевой накопитель",
                                                  description="Проверка не изменяет разделы и данные.")
            self.disk_info = Adw.ActionRow(title="Накопитель не выбран")
            self.disk_group.add(self.disk_info)
            refresh = Gtk.Button(label="Проверить накопители")
            refresh.set_halign(Gtk.Align.START)
            refresh.connect("clicked", self.refresh)
            page.append(self.disk_group)
            page.append(refresh)
            self.refresh_button = refresh

            account = Adw.PreferencesGroup(title="2. Учётная запись")
            self.username = Adw.EntryRow(title="Имя пользователя")
            self.password = Adw.PasswordEntryRow(title="Пароль")
            self.repeat = Adw.PasswordEntryRow(title="Повторите пароль")
            for row in (self.username, self.password, self.repeat):
                account.add(row)
            page.append(account)

            confirmation = Adw.PreferencesGroup(title="3. Подтверждение установки",
                                                description="На выбранном SSD будет создана новая таблица разделов.")
            self.confirm = Adw.EntryRow(title="Введите указанную фразу")
            confirmation.add(self.confirm)
            self.phrase = Gtk.Label(wrap=True, selectable=True, xalign=0)
            confirmation.add(self.phrase)
            page.append(confirmation)
            self.backup = Gtk.CheckButton(label="Я проверил накопитель и сохранил важные данные")
            page.append(self.backup)

            buttons = Gtk.Box(spacing=12)
            self.install = Gtk.Button(label="Установить Localzet OS")
            self.install.add_css_class("suggested-action")
            self.install.connect("clicked", self.start)
            self.install.set_sensitive(False)
            self.spinner = Gtk.Spinner()
            buttons.append(self.install)
            buttons.append(self.spinner)
            page.append(buttons)
            self.status = Gtk.Label(wrap=True, xalign=0, selectable=True)
            page.append(self.status)
            for row in (self.username, self.password, self.repeat, self.confirm):
                row.connect("changed", lambda *_: self.update())
            self.backup.connect("toggled", lambda *_: self.update())
            self.refresh()
            self.window.present()

        def refresh(self, *_):
            self.plan = None
            self.confirm.set_text("")
            self.backup.set_active(False)
            try:
                payload = read_lsblk()
                boot_disk = live_source_disk()
                plans = []
                errors = []
                for disk in payload["blockdevices"]:
                    selected = identity(disk)
                    if not selected or disk.get("path") == boot_disk:
                        continue
                    try:
                        plans.append(eligible_plan(payload, selected, boot_disk))
                    except ValueError as error:
                        errors.append(str(error))
                if len(plans) != 1:
                    raise ValueError(errors[0] if errors else "Не найден единственный подходящий пустой SSD.")
                # Detection is not consent. The user must explicitly type the
                # stable identity and acknowledge backups before proceeding.
                self.plan = plans[0]
                target = self.plan["target"]
                self.disk_info.set_title(target["model"] or "SSD")
                self.disk_info.set_subtitle(
                    f'{self.plan["selected_identity"]} · {target["size_bytes"] / 1024**3:.1f} GiB · {target["path"]}')
                self.phrase.set_label(confirmation_for(self.plan))
                self.status.set_label("Введите данные учётной записи и подтвердите целевой диск.")
            except Exception as error:
                self.disk_info.set_title("Установка недоступна")
                self.disk_info.set_subtitle("")
                self.phrase.set_label("")
                self.status.set_label(str(error))
            self.update()

        def request(self):
            if not self.plan:
                raise ValueError("Нет подтверждённого SSD.")
            if self.password.get_text() != self.repeat.get_text():
                raise ValueError("Пароли не совпадают.")
            data = {
                "plan": self.plan,
                "confirmation": self.confirm.get_text(),
                "backup_acknowledged": self.backup.get_active(),
                "username": self.username.get_text(),
                "password": self.password.get_text(),
            }
            validate_request(data)
            return data

        def update(self):
            if self.running:
                self.install.set_sensitive(False)
                return
            try:
                self.request()
                self.install.set_sensitive(True)
            except ValueError:
                self.install.set_sensitive(False)

        def start(self, *_):
            try:
                data = self.request()
                self.running = True
                self.install.set_sensitive(False)
                for widget in (self.refresh_button, self.username, self.password,
                               self.repeat, self.confirm, self.backup):
                    widget.set_sensitive(False)
                self.spinner.start()
                self.status.set_label("Идёт установка. Не выключайте компьютер и не отключайте SSD.")
                process = Gio.Subprocess.new(
                    ["/usr/bin/sudo", "-n", "/usr/lib/localzet/installer-backend"],
                    Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_MERGE,
                )
                payload = json.dumps(data, ensure_ascii=False)
                process.communicate_utf8_async(payload, None, self.finished)
                self.password.set_text("")
                self.repeat.set_text("")
            except Exception as error:
                self.running = False
                self.spinner.stop()
                self.status.set_label(f"Не удалось запустить установку: {error}")
                self.refresh_button.set_sensitive(True)

        def finished(self, process, result):
            self.running = False
            self.spinner.stop()
            try:
                _, output, _ = process.communicate_utf8_finish(result)
                if process.get_successful():
                    self.status.set_label("Localzet OS установлена. Выключите компьютер, извлеките "
                                          "загрузочный носитель и загрузитесь с выбранного SSD.")
                else:
                    self.status.set_label("Установка остановлена. Не запускайте её повторно на этом "
                                          "диске без проверки.\n" + (output or "")[-2500:])
            except Exception as error:
                self.status.set_label(f"Не удалось получить результат: {error}")
            # Require a new read-only review after any attempt. Never retry
            # automatically on a possibly partially written disk.
            self.plan = None
            self.refresh_button.set_sensitive(True)
            for widget in (self.username, self.password, self.repeat, self.confirm, self.backup):
                widget.set_sensitive(True)
            self.update()

    return Installer().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
