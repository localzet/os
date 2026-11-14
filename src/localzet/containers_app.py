"""Native Localzet Containers local workspace. No root or fake inventory."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys

from localzet.containers import Engine, EngineError


def main() -> int:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw, Gio, GLib, Pango, GObject, Gdk

    class Row(GObject.Object):
        def __init__(self, item):
            super().__init__()
            self.item = item

    class Workspace(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Containers")
            self.window = None
            self.pool = ThreadPoolExecutor(max_workers=1)
            self.rows = ()
            self.busy = False
            self.rootful = False
            self.generation = 0
            self.detail_id = None
            self.last_error = False

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Containers")
            self.window.set_default_size(1100, 720)
            self.window.add_css_class("aurora-containers")
            style = Adw.StyleManager.get_default()
            def update_style(*_):
                if style.get_dark() and not style.get_high_contrast():
                    self.window.add_css_class("aurora-dark")
                else:
                    self.window.remove_css_class("aurora-dark")
            self.style = style
            self.style_handlers = [style.connect("notify::dark", update_style),
                                   style.connect("notify::high-contrast", update_style)]
            update_style()
            provider = Gtk.CssProvider()
            provider.load_from_data(b"""
                window.aurora-containers.aurora-dark { background-color: #171022; color: #f4eeff; }
                .aurora-dark headerbar { background-color: #20152f; color: #f4eeff; }
                .aurora-dark columnview { background-color: #21172f; }
                .aurora-dark columnview header button { background-color: #2a1d3b; color: #d3c3ec; }
                .aurora-dark columnview row:selected { background-color: #493064; color: #f4eeff; }
                .aurora-dark .container-detail { background-color: #21172f; border-radius: 8px; padding: 10px; }
                .aurora-dark textview, .aurora-dark textview text { background-color: #10091e; color: #f4eeff; }
                .aurora-dark button.suggested-action { background-color: #ff7e00; color: #10091e; }
            """)
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                       Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
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
            self.store = Gio.ListStore.new(Row)
            self.selection = Gtk.SingleSelection(model=self.store, autoselect=False, can_unselect=True)
            self.table = Gtk.ColumnView(model=self.selection, show_row_separators=True)
            for caption, field, expand in (("Имя", "name", True), ("Образ", "image", True),
                                           ("Состояние", "state", False), ("Порты", "ports", True)):
                factory = Gtk.SignalListItemFactory()
                def setup(_, list_item):
                    label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                      margin_top=6, margin_bottom=6, margin_start=8, margin_end=8)
                    list_item.set_child(label)
                def bind(_, list_item, field=field):
                    item = list_item.get_item().item
                    label = list_item.get_child()
                    value = getattr(item, field) or "—"
                    label.set_label(value)
                    label.set_tooltip_text(value)
                    if field == "state" and item.state == "running":
                        label.add_css_class("success")
                    else:
                        label.remove_css_class("success")
                factory.connect("setup", setup)
                factory.connect("bind", bind)
                column = Gtk.ColumnViewColumn.new(caption, factory)
                column.set_expand(expand)
                column.set_resizable(True)
                self.table.append_column(column)
            scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=140)
            scroll.set_child(self.table)
            self.table_stack = Gtk.Stack(vexpand=True)
            self.table_stack.add_named(scroll, "table")
            self.empty = Gtk.Label(label="Подключение к Docker…", wrap=True,
                                   justify=Gtk.Justification.CENTER, margin_top=24, margin_bottom=24)
            self.empty.add_css_class("dim-label")
            self.table_stack.add_named(self.empty, "empty")
            main.append(self.table_stack)
            detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            detail_box.add_css_class("container-detail")
            detail_header = Gtk.Box(spacing=8)
            self.detail = Gtk.Label(label="Выберите контейнер", xalign=0, wrap=True, selectable=True, hexpand=True)
            detail_header.append(self.detail)
            self.metrics_button = Gtk.Button(label="Метрики")
            self.logs_button = Gtk.Button(label="Логи")
            self.metrics_button.connect("clicked", lambda *_: self.read_detail("metrics"))
            self.logs_button.connect("clicked", lambda *_: self.read_detail("logs"))
            detail_header.append(self.metrics_button)
            detail_header.append(self.logs_button)
            detail_box.append(detail_header)
            self.detail_text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                           wrap_mode=Gtk.WrapMode.CHAR, top_margin=8, bottom_margin=8,
                                           left_margin=8, right_margin=8)
            detail_scroll = Gtk.ScrolledWindow(min_content_height=130)
            detail_scroll.set_child(self.detail_text)
            detail_box.append(detail_scroll)
            main.append(detail_box)
            self.selection.connect("notify::selected-item", lambda *_: self.update_actions())
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
            self.last_error = False
            self.clear_detail()
            self.render()
            self.load()

        def submit(self, action=None, cid=None):
            if self.busy:
                return
            self.busy = True
            self.clear_detail()
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
                self.last_error = False
                running = sum(row.state == "running" for row in self.rows)
                self.status.set_label(f"Контейнеров: {len(self.rows)}  ·  Запущено: {running}")
            except (EngineError, OSError, ValueError) as error:
                self.rows = ()
                self.last_error = True
                self.status.set_label(str(error))
            except Exception:
                self.rows = ()
                self.last_error = True
                self.status.set_label("Ошибка движка. Обновите список для проверки состояния.")
            self.render()
            return GLib.SOURCE_REMOVE

        def selected(self):
            row = self.selection.get_selected_item()
            return row.item if row else None

        def clear_detail(self):
            self.detail_id = None
            self.detail_text.get_buffer().set_text("")

        def render(self):
            old = self.selected()
            self.store.remove_all()
            query = self.search.get_text().casefold().strip()
            selected_index = None
            for item in self.rows:
                if query and query not in " ".join((item.name, item.image, item.id)).casefold():
                    continue
                if old and old.id == item.id:
                    selected_index = self.store.get_n_items()
                self.store.append(Row(item))
            if selected_index is not None:
                self.selection.set_selected(selected_index)
            if self.store.get_n_items():
                self.table_stack.set_visible_child_name("table")
            else:
                self.empty.set_label("Не удалось подключиться к выбранному движку.\nПроверьте Docker или выберите другой локальный сокет."
                                     if self.last_error else "Нет подходящих контейнеров." if query else "Контейнеров нет.")
                self.table_stack.set_visible_child_name("empty")
            self.update_actions()

        def read_detail(self, kind):
            item = self.selected()
            if self.busy or not item or kind not in ("metrics", "logs"):
                return
            self.clear_detail()
            self.busy = True
            self.generation += 1
            generation = self.generation
            rootful, cid = self.rootful, item.id
            self.detail_id = cid
            self.detail_text.get_buffer().set_text("Загрузка…")
            self.update_actions()
            def worker():
                engine = Engine(rootful=rootful)
                if kind == "metrics":
                    values = engine.metrics(cid)
                    return "\n".join(f"{label}: {values[key]}" for key, label in (
                        ("CPUPerc", "CPU"), ("MemUsage", "Память"), ("NetIO", "Сеть"),
                        ("BlockIO", "Диск"), ("PIDs", "Процессы")))
                data, truncated = engine.logs(cid)
                return (data or "Нет записей.") + ("\n[Достигнут лимит 256 КиБ]" if truncated else "")
            future = self.pool.submit(worker)
            future.add_done_callback(lambda f: GLib.idle_add(self.detail_finished, generation, cid, f))

        def detail_finished(self, generation, cid, future):
            if generation != self.generation or not self.window:
                return GLib.SOURCE_REMOVE
            self.busy = False
            if self.selected() and self.selected().id == cid:
                try:
                    self.detail_text.get_buffer().set_text(future.result())
                except (EngineError, OSError, ValueError) as error:
                    self.detail_text.get_buffer().set_text(str(error))
                except Exception:
                    self.detail_text.get_buffer().set_text("Не удалось получить данные.")
            else:
                self.clear_detail()
            self.update_actions()
            return GLib.SOURCE_REMOVE

        def update_actions(self):
            item = self.selected()
            self.refresh.set_sensitive(not self.busy)
            self.engine_button.set_sensitive(not self.busy)
            self.table.set_sensitive(not self.busy)
            self.search.set_sensitive(not self.busy)
            if self.detail_id and (not item or item.id != self.detail_id):
                self.clear_detail()
            running = bool(item and item.state == "running")
            startable = bool(item and item.state in ("created", "exited"))
            self.start_button.set_sensitive(not self.busy and startable)
            self.stop_button.set_sensitive(not self.busy and running)
            self.restart_button.set_sensitive(not self.busy and running)
            self.metrics_button.set_sensitive(not self.busy and running)
            self.logs_button.set_sensitive(not self.busy and bool(item))
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
            for handler in self.style_handlers:
                self.style.disconnect(handler)
            self.window = None
            self.pool.shutdown(wait=False, cancel_futures=True)
            super().do_shutdown()

    return Workspace().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
