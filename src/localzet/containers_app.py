"""Native Localzet Containers local workspace. No root or fake inventory."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys

from localzet.containers import Container, Engine, EngineError


def main() -> int:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw, Gio, GLib, Pango

    class Workspace(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Containers")
            self.window = None
            self.pool = ThreadPoolExecutor(max_workers=1)
            self.rows = ()
            self.busy = False
            self.rootful = False
            self.generation = 0

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Containers")
            self.window.set_default_size(1050, 650)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            title = Adw.WindowTitle(title="Containers", subtitle="Localzet OS")
            header.set_title_widget(title)
            self.refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Обновить")
            self.refresh.connect("clicked", lambda *_: self.load())
            header.pack_end(self.refresh)
            toolbar.add_top_bar(header)
            self.window.set_content(toolbar)
            main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                           margin_top=16, margin_bottom=16, margin_start=18, margin_end=18)
            toolbar.set_content(main)
            top = Gtk.Box(spacing=12)
            self.engine_label = Gtk.Label(label="Локальный rootless Docker", xalign=0, hexpand=True)
            self.engine_label.add_css_class("heading")
            top.append(self.engine_label)
            self.engine_button = Gtk.Button(label="Выбрать движок")
            self.engine_button.connect("clicked", self.choose_engine)
            top.append(self.engine_button)
            main.append(top)
            self.status = Gtk.Label(label="Подключение…", xalign=0, wrap=True, selectable=True)
            self.status.add_css_class("dim-label")
            main.append(self.status)
            columns = Gtk.Box(spacing=12)
            self.search = Gtk.SearchEntry(placeholder_text="Поиск по имени, образу, ID", hexpand=True)
            self.search.connect("search-changed", lambda *_: self.render())
            columns.append(self.search)
            for action, caption in (("start", "Запустить"), ("stop", "Остановить"), ("restart", "Перезапустить")):
                button = Gtk.Button(label=caption)
                button.connect("clicked", self.confirm_action, action)
                columns.append(button)
                setattr(self, action + "_button", button)
            main.append(columns)
            self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
            self.list.add_css_class("boxed-list")
            self.list.connect("row-selected", lambda *_: self.update_actions())
            scroll = Gtk.ScrolledWindow(vexpand=True)
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.set_child(self.list)
            main.append(scroll)
            self.detail = Gtk.Label(label="Выберите контейнер", xalign=0, wrap=True, selectable=True)
            self.detail.add_css_class("dim-label")
            main.append(self.detail)
            self.window.present()
            self.load()

        def choose_engine(self, *_):
            if self.busy:
                return
            dialog = Adw.AlertDialog(heading="Локальный Docker Engine",
                body="Rootless использует пользовательский сокет. Системный Docker даёт практически полный доступ к компьютеру; используйте только при существующем разрешении. Приложение не повышает привилегии.")
            dialog.add_response("cancel", "Отмена")
            dialog.add_response("rootless", "Rootless")
            dialog.add_response("rootful", "Системный Docker")
            dialog.set_response_appearance("rootful", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_close_response("cancel")
            dialog.connect("response", self.engine_chosen)
            dialog.present(self.window)

        def engine_chosen(self, _, response):
            if response not in ("rootless", "rootful") or self.busy:
                return
            self.rootful = response == "rootful"
            self.engine_label.set_label("Системный Docker · привилегированный доступ" if self.rootful
                                        else "Локальный rootless Docker")
            self.rows = ()
            self.render()
            self.load()

        def submit(self, action=None, cid=None):
            if self.busy:
                return
            self.busy = True
            self.generation += 1
            generation = self.generation
            rootful = self.rootful
            self.status.set_label("Выполнение операции…" if action else "Обновление списка…")
            self.update_actions()

            def worker():
                engine = Engine(rootful=rootful)
                return engine.action(action, cid) if action else engine.inventory()

            future = self.pool.submit(worker)
            future.add_done_callback(lambda f: GLib.idle_add(self.finished, generation, f))

        def load(self):
            self.submit()

        def finished(self, generation, future):
            if generation != self.generation or not self.window:
                return GLib.SOURCE_REMOVE
            self.busy = False
            try:
                self.rows = future.result()
                self.status.set_label(f"Контейнеров: {len(self.rows)}" if self.rows
                                      else "Движок доступен. Контейнеров нет.")
            except (EngineError, OSError, ValueError) as error:
                self.rows = ()
                self.status.set_label(str(error))
            except Exception:
                self.rows = ()
                self.status.set_label("Ошибка движка. Обновите список для проверки состояния.")
            self.render()
            return GLib.SOURCE_REMOVE

        def selected(self):
            row = self.list.get_selected_row()
            return getattr(row, "container", None) if row else None

        def render(self):
            old = self.selected()
            self.list.remove_all()
            query = self.search.get_text().casefold().strip()
            for item in self.rows:
                if query and query not in " ".join((item.name, item.image, item.id)).casefold():
                    continue
                row = Gtk.ListBoxRow()
                row.container = item
                line = Gtk.Box(spacing=12, margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
                name = Gtk.Label(label=item.name, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
                name.add_css_class("heading")
                name.set_tooltip_text(item.name)
                line.append(name)
                image = Gtk.Label(label=item.image, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
                image.set_tooltip_text(item.image)
                image.add_css_class("dim-label")
                line.append(image)
                state = Gtk.Label(label=item.state, xalign=0, width_chars=12)
                if item.state == "running":
                    state.add_css_class("success")
                line.append(state)
                row.set_child(line)
                self.list.append(row)
                if old and old.id == item.id:
                    self.list.select_row(row)
            self.update_actions()

        def update_actions(self):
            item = self.selected()
            self.refresh.set_sensitive(not self.busy)
            self.engine_button.set_sensitive(not self.busy)
            running = bool(item and item.state == "running")
            startable = bool(item and item.state in ("created", "exited"))
            self.start_button.set_sensitive(not self.busy and startable)
            self.stop_button.set_sensitive(not self.busy and running)
            self.restart_button.set_sensitive(not self.busy and running)
            self.detail.set_label(f"{item.name} · {item.id[:12]} · {item.status}\n{item.image} · {item.ports or 'Порты не опубликованы'}"
                                  if item else "Выберите контейнер")

        def confirm_action(self, _, action):
            item = self.selected()
            if not item or self.busy:
                return
            labels = {"start": "Запустить", "stop": "Остановить", "restart": "Перезапустить"}
            dialog = Adw.AlertDialog(heading=f"{labels[action]} контейнер?",
                                     body=f"{item.name}\n{item.id[:12]} · {item.image}")
            dialog.add_response("cancel", "Отмена")
            dialog.add_response("confirm", labels[action])
            dialog.set_close_response("cancel")
            dialog.set_response_appearance("confirm", Adw.ResponseAppearance.SUGGESTED if action == "start"
                                           else Adw.ResponseAppearance.DESTRUCTIVE)
            generation = self.generation

            def response(_, choice):
                if choice == "confirm" and generation == self.generation:
                    self.submit(action, item.id)

            dialog.connect("response", response)
            dialog.present(self.window)

        def do_shutdown(self):
            self.generation += 1
            self.window = None
            self.pool.shutdown(wait=False, cancel_futures=True)
            super().do_shutdown()

    return Workspace().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
