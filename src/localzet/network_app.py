"""Localzet network integration for the original NetBird client."""
from concurrent.futures import ThreadPoolExecutor
import sys

from localzet.netbird import status, installed, UI

LABELS = {"not-installed": "Клиент не установлен", "unavailable": "Служба недоступна",
          "Idle": "Отключён", "Connecting": "Подключение", "Connected": "Подключён",
          "NeedsLogin": "Требуется вход", "LoginFailed": "Ошибка входа",
          "SessionExpired": "Сессия истекла"}


def main():
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gio, GLib, Gtk

    class Network(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Network")
            self.window = None
            self.pool = ThreadPoolExecutor(max_workers=1)
            self.busy = False

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Network")
            self.window.set_default_size(680, 480)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Обновить")
            self.refresh_button.connect("clicked", lambda *_: self.refresh())
            header.pack_end(self.refresh_button)
            toolbar.add_top_bar(header)
            page = Adw.PreferencesPage()
            group = Adw.PreferencesGroup(title="Частная сеть · NetBird",
                description="Подключение, профили, DNS и маршруты настраиваются в оригинальном клиенте.")
            self.row = Adw.ActionRow(title="Статус", subtitle="Проверка…")
            self.row.set_use_markup(False)
            group.add(self.row)
            self.peer_row = Adw.ActionRow(title="Узлы", subtitle="—")
            group.add(self.peer_row)
            self.open_button = Gtk.Button(label="Открыть NetBird", halign=Gtk.Align.START)
            self.open_button.connect("clicked", self.open_client)
            group.add(self.open_button)
            link = Gtk.LinkButton(uri="https://docs.netbird.io/get-started/install/linux",
                                  label="Официальная установка NetBird", halign=Gtk.Align.START)
            group.add(link)
            page.add(group)
            settings = Adw.PreferencesGroup(title="Системная сеть",
                description="Настройки GNOME остаются основным интерфейсом сетевых адаптеров.")
            button = Gtk.Button(label="Настройки сети", halign=Gtk.Align.START)
            button.connect("clicked", lambda *_: self.launch(["/usr/bin/gnome-control-center", "network"]))
            settings.add(button)
            page.add(settings)
            toolbar.set_content(page)
            self.window.set_content(toolbar)
            self.window.present()
            self.refresh()
            self.timer = GLib.timeout_add_seconds(15, self.refresh)

        def launch(self, argv):
            try:
                Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)
            except Exception:
                self.row.set_subtitle("Не удалось открыть приложение")

        def open_client(self, *_):
            if installed(UI):
                self.launch(["/usr/bin/env", "WEBKIT_DISABLE_DMABUF_RENDERER=1", str(UI)])

        def refresh(self):
            if self.busy:
                return GLib.SOURCE_CONTINUE
            self.busy = True
            self.refresh_button.set_sensitive(False)
            self.open_button.set_sensitive(installed(UI))
            future = self.pool.submit(status)
            def finished():
                if self.window is None:
                    return GLib.SOURCE_REMOVE
                self.busy = False
                self.refresh_button.set_sensitive(True)
                try:
                    result = future.result()
                    self.row.set_subtitle(LABELS[result["state"]])
                    self.peer_row.set_subtitle(f'{result["connected"]} / {result["total"]}' if "total" in result else "—")
                except Exception:
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
