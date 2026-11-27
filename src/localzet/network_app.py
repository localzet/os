"""Localzet network integration for the original NetBird client."""
from concurrent.futures import ThreadPoolExecutor
import sys

from localzet.netbird import status, installed, UI
from localzet.usernet import policy_notice, proxy_status
from localzet.network_provision import available, command, usernet_installed

LABELS = {"not-installed": "Клиент не установлен", "unavailable": "Служба недоступна",
          "Idle": "Отключён", "Connecting": "Подключение", "Connected": "Подключён",
          "NeedsLogin": "Требуется вход", "LoginFailed": "Ошибка входа",
          "SessionExpired": "Сессия истекла"}


def main():
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gio, GLib, GObject, Gtk

    class Network(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Network")
            self.window = None
            self.pool = ThreadPoolExecutor(max_workers=1)
            self.busy = False
            self.installing = False

        def do_activate(self):
            from localzet.appearance import apply_midnight
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Network")
            self.appearance = apply_midnight(self.window)
            self.window.set_default_size(940, 580)
            self.window.set_size_request(680, 420)
            self.window.add_css_class("network-workspace")
            self.css = Gtk.CssProvider()
            self.css.load_from_data(b"""
                .network-workspace .network-sidebar { padding: 12px 8px; border-right: 1px solid alpha(currentColor,.12); }
                .localzet-midnight .network-sidebar { background-color: #343539; }
                .network-workspace .network-sidebar button { padding: 8px 10px; border-radius: 6px; }
                .network-workspace .network-sidebar button.selected { background-color: alpha(currentColor,.12); font-weight: 600; }
                .network-workspace .network-content { padding: 16px 20px; }
                .network-workspace .network-heading { font-size: 21px; font-weight: 600; }
                .network-workspace .network-actions { margin-top: 7px; }
                .network-workspace .network-actions button { border-radius: 6px; min-height: 28px; }
                .network-workspace .boxed-list > row { min-height: 44px; border-radius: 6px; }
            """)
            Gtk.StyleContext.add_provider_for_display(self.window.get_display(), self.css,
                                                       Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.window.connect("close-request", lambda *_: self.installing)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Обновить")
            self.refresh_button.connect("clicked", lambda *_: self.refresh())
            header.pack_end(self.refresh_button)
            toolbar.add_top_bar(header)
            header.set_title_widget(Adw.WindowTitle(title="Сеть", subtitle="Localzet Network"))
            workspace = Gtk.Box()
            sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, width_request=176)
            sidebar.set_hexpand(False)
            sidebar.add_css_class("network-sidebar")
            label = Gtk.Label(label="ПОДКЛЮЧЕНИЯ", xalign=0, margin_start=9, margin_bottom=8)
            label.add_css_class("dim-label")
            sidebar.append(label)
            workspace.append(sidebar)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
            content.add_css_class("network-content")
            workspace.append(content)
            self.heading = Gtk.Label(xalign=0)
            self.heading.add_css_class("network-heading")
            content.append(self.heading)
            self.description = Gtk.Label(xalign=0, wrap=True)
            self.description.add_css_class("dim-label")
            content.append(self.description)
            self.stack = Gtk.Stack(vexpand=True, hexpand=True)
            content.append(self.stack)
            self.nav = {}
            sections = (
                ("vpn", "Частная сеть", "NetBird · VPN и узлы", "network-vpn-symbolic"),
                ("proxy", "Прокси", "UserNet · системные параметры", "network-workgroup-symbolic"),
                ("system", "Система", "Установка клиентов и настройки адаптеров", "preferences-system-network-symbolic"),
            )
            pages = {}
            for index, (key, title, description, icon) in enumerate(sections, 1):
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
                page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                               margin_bottom=8, margin_end=6)
                scroll.set_child(page)
                self.stack.add_named(scroll, key)
                pages[key] = page
            sidebar.append(Gtk.Box(vexpand=True))
            note = Gtk.Label(label="NetBird · UserNet\nLocalzet OS", xalign=0, margin_start=9)
            note.add_css_class("dim-label")
            sidebar.append(note)
            page = pages["vpn"]
            group = Adw.PreferencesGroup(title="Частная сеть · NetBird",
                description="Подключение, профили, DNS и маршруты настраиваются в оригинальном клиенте.")
            self.row = Adw.ActionRow(title="Статус", subtitle="Проверка…")
            self.row.set_use_markup(False)
            group.add(self.row)
            self.peer_row = Adw.ActionRow(title="Узлы", subtitle="—")
            group.add(self.peer_row)
            self.open_button = Gtk.Button(label="Открыть NetBird", halign=Gtk.Align.START)
            self.open_button.connect("clicked", self.open_client)
            self.install_netbird = Gtk.Button(label="Установить NetBird", halign=Gtk.Align.START)
            self.install_netbird.connect("clicked", lambda *_: self.provision("netbird"))
            link = Gtk.LinkButton(uri="https://docs.netbird.io/get-started/install/linux",
                                  label="Документация", halign=Gtk.Align.START)
            page.append(group)
            vpn_actions = Gtk.Box(spacing=8, halign=Gtk.Align.START)
            vpn_actions.add_css_class("network-actions")
            self.install_netbird.add_css_class("suggested-action")
            vpn_actions.append(self.open_button)
            vpn_actions.append(self.install_netbird)
            vpn_actions.append(link)
            page.append(vpn_actions)
            page = pages["proxy"]
            proxy = Adw.PreferencesGroup(title="UserNet · системный прокси",
                description="Оригинальный клиент UserNet управляет Mihomo. Состояние прокси не подтверждает активный туннель.")
            self.proxy_row = Adw.ActionRow(title="Режим GNOME", subtitle="Проверка…")
            proxy.add(self.proxy_row)
            self.endpoint_row = Adw.ActionRow(title="Настроенные протоколы", subtitle="—")
            proxy.add(self.endpoint_row)
            self.usernet_button = Gtk.Button(label="Открыть UserNet", halign=Gtk.Align.START)
            self.usernet_button.connect("clicked", self.open_usernet)
            self.install_usernet = Gtk.Button(label="Установить UserNet", halign=Gtk.Align.START)
            self.install_usernet.connect("clicked", lambda *_: self.provision("usernet"))

            self.warning = Adw.ActionRow(title="Совместная работа VPN и прокси",
                subtitle="Proxy Only не применяется. Маршруты и DNS не изменяются автоматически.")
            proxy.add(self.warning)
            page.append(proxy)
            proxy_actions = Gtk.Box(spacing=8, halign=Gtk.Align.START)
            proxy_actions.add_css_class("network-actions")
            self.install_usernet.add_css_class("suggested-action")
            proxy_actions.append(self.usernet_button)
            proxy_actions.append(self.install_usernet)
            proxy_actions.append(Gtk.LinkButton(uri="https://github.com/localzet/UserNet/releases",
                                                label="Релизы UserNet", halign=Gtk.Align.START))
            page.append(proxy_actions)
            page = pages["system"]
            provision_group = Adw.PreferencesGroup(title="Установка клиентов", description="Закреплённые DEB с GitHub, проверка SHA-256 и подтверждение администратора. NetBird запускает незарегистрированную службу; UserNet не включает TUN автоматически.")
            self.provision_status = Adw.ActionRow(title="Состояние", subtitle="Готово к проверке")
            self.provision_status.set_use_markup(False)
            provision_group.add(self.provision_status)
            page.append(provision_group)
            settings = Adw.PreferencesGroup(title="Системная сеть",
                description="Настройки GNOME остаются основным интерфейсом сетевых адаптеров.")
            button = Gtk.Button(label="Настройки сети", halign=Gtk.Align.START)
            button.connect("clicked", lambda *_: self.launch(["/usr/bin/gnome-control-center", "network"]))
            settings.add(button)
            page.append(settings)
            # Provisioning feedback must remain visible on every page.
            self.provision_feedback = Gtk.Label(xalign=0, wrap=True, selectable=True,
                                                max_width_chars=75)
            self.provision_feedback.add_css_class("dim-label")
            self.provision_status.bind_property("subtitle", self.provision_feedback, "label", GObject.BindingFlags.SYNC_CREATE)
            content.append(self.provision_feedback)
            toolbar.set_content(workspace)
            self.navigate("vpn")
            self.window.set_content(toolbar)
            self.window.present()
            self.refresh()
            self.timer = GLib.timeout_add_seconds(15, self.refresh)

        def navigate(self, key):
            self.stack.set_visible_child_name(key)
            for name, (button, title, description) in self.nav.items():
                if name == key:
                    button.add_css_class("selected")
                    self.heading.set_label(title)
                    self.description.set_label(description)
                    self.window.set_title("Localzet Network — " + title)
                else:
                    button.remove_css_class("selected")

        def launch(self, argv):
            try:
                Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)
            except Exception:
                self.row.set_subtitle("Не удалось открыть приложение")

        def open_client(self, *_):
            if installed(UI):
                self.launch(["/usr/bin/env", "WEBKIT_DISABLE_DMABUF_RENDERER=1", str(UI)])

        @staticmethod
        def usernet_app():
            # PyGObject raises TypeError for a NULL constructor result when
            # the optional desktop entry is not installed.
            try:
                return Gio.DesktopAppInfo.new("com.localzet.usernet.desktop")
            except TypeError:
                return None

        def open_usernet(self, *_):
            app = self.usernet_app()
            if app:
                try:
                    app.launch([], None)
                except Exception:
                    self.proxy_row.set_subtitle("Не удалось открыть UserNet")

        def provision(self, kind):
            if self.installing or not available(kind):
                return
            self.installing = True
            self.install_netbird.set_sensitive(False)
            self.install_usernet.set_sensitive(False)
            self.provision_status.set_subtitle("Подтвердите установку администратором. Не закрывайте окно до завершения.")
            try:
                process = Gio.Subprocess.new(command(kind), Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
                process.communicate_utf8_async(None, None, self.provision_finished)
            except Exception as error:
                self.installing = False
                self.provision_status.set_subtitle(str(error))
                self.refresh()

        def provision_finished(self, process, result):
            self.installing = False
            try:
                _, output, _ = process.communicate_utf8_finish(result)
                if not process.get_successful():
                    self.provision_status.set_subtitle("Установка не завершена. " + (output or "")[-1200:])
                else:
                    self.provision_status.set_subtitle("Пакет установлен. Откройте оригинальный клиент для настройки подключения.")
            except Exception as error:
                self.provision_status.set_subtitle(str(error))
            self.refresh()

        def refresh(self):
            if self.busy:
                return GLib.SOURCE_CONTINUE
            self.busy = True
            self.refresh_button.set_sensitive(False)
            self.open_button.set_sensitive(installed(UI))
            self.usernet_button.set_sensitive(self.usernet_app() is not None)
            self.install_netbird.set_visible(not installed(UI))
            self.install_usernet.set_visible(not usernet_installed())
            self.install_netbird.set_sensitive(not self.installing and available("netbird"))
            self.install_usernet.set_sensitive(not self.installing and available("usernet"))
            proxy = proxy_status()
            self.proxy_row.set_subtitle({'none': 'Выключен', 'auto': 'Автоматический (PAC)', 'manual': 'Ручной', 'unavailable': 'Недоступен'}[proxy['mode']])
            self.endpoint_row.set_subtitle(f"Локальные: {proxy['local']} · внешние: {proxy['remote']}" if proxy['mode'] == 'manual' else '—')
            self.warning.set_subtitle(policy_notice(None, proxy))
            future = self.pool.submit(status)
            def finished():
                if self.window is None:
                    return GLib.SOURCE_REMOVE
                self.busy = False
                self.refresh_button.set_sensitive(True)
                try:
                    result = future.result()
                    self.row.set_subtitle(LABELS[result["state"]])
                    self.warning.set_subtitle(policy_notice(result["state"], proxy))
                    self.peer_row.set_subtitle(f'{result["connected"]} / {result["total"]}' if "total" in result else "—")
                except Exception:
                    self.warning.set_subtitle(policy_notice(None, proxy))
                    self.row.set_subtitle("Статус недоступен")
                    self.peer_row.set_subtitle("—")
                return GLib.SOURCE_REMOVE
            future.add_done_callback(lambda _: GLib.idle_add(finished))
            return GLib.SOURCE_CONTINUE

        def do_shutdown(self):
            self.window = None
            if hasattr(self, "timer"):
                GLib.source_remove(self.timer)
            self.pool.shutdown(wait=False, cancel_futures=True)
            super().do_shutdown()

    return Network().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
