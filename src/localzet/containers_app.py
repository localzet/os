"""Native Localzet Containers local workspace. No root or fake inventory."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys

from localzet import rootless_docker
from localzet.containers import Deployment, Engine, EngineError, RemoteEngine, RemoteStore, TLSEngine, StudioStore, deployment_args, metric_sample, build_argument_flags


def spawn_terminal(terminal, argv, cancellable, callback):
    from gi.repository import GLib, Vte
    terminal.spawn_async(Vte.PtyFlags.DEFAULT, "/", list(argv), None,
                         GLib.SpawnFlags.DO_NOT_REAP_CHILD, None, None, 10000,
                         cancellable, callback, None)


def create_application():
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
            from localzet.appearance import apply_midnight, palette_css
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Containers")
            self.appearance = apply_midnight(self.window)
            self.window.set_default_size(1120, 680)
            self.window.set_size_request(900, 540)
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
            provider.load_from_data(palette_css(b"""
                 .aurora-containers .workspace-sidebar { padding: 12px 8px; border-right: 1px solid alpha(currentColor, .12); }
                .aurora-containers .workspace-sidebar button { border-radius: 5px; padding: 7px 9px; }
                .aurora-containers .workspace-sidebar button.active { background-color: alpha(currentColor, .12); font-weight: 600; }
                .aurora-containers .workspace-heading { font-size: 19px; font-weight: 600; }
                .aurora-containers .container-detail { border: 1px solid alpha(currentColor, .12); border-radius: 6px; padding: 10px; }
                .aurora-containers columnview { border: 1px solid alpha(currentColor, .12); }
                window.aurora-containers.aurora-dark { background-color: __BACKGROUND__; color: __TEXT__; }
                .aurora-dark headerbar { background-color: __HEADER__; color: __TEXT__; }
                .aurora-dark .workspace-sidebar { background-color: __SURFACE__; color: __TEXT__; }
                .aurora-dark columnview, .aurora-dark .container-detail { background-color: __SURFACE_ELEVATED__; }
                .aurora-dark columnview header button { background-color: __SURFACE__; color: __TEXT_SECONDARY__; }
                .aurora-dark columnview row:selected { background-color: __SELECTION__; color: __TEXT__; }
                .aurora-dark .workspace-sidebar button.active { background-color: __SELECTION__; color: __TEXT__; }
                .aurora-dark textview, .aurora-dark textview text { background-color: __BACKGROUND__; color: __TEXT__; }
                .aurora-dark button.suggested-action { background-color: __ACCENT__; color: __ON_ACCENT__; }
                .aurora-containers columnview row { min-height: 32px; }
                .aurora-containers columnview header button { min-height: 28px; }
                .aurora-containers .container-detail button { min-height: 28px; border-radius: 6px; }
            """))
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                       Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            title = Adw.WindowTitle(title="Containers", subtitle="Localzet OS")
            header.set_title_widget(title)
            self.refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Обновить")
            self.refresh.connect("clicked", lambda *_: self.refresh_page())
            header.pack_end(self.refresh)
            toolbar.add_top_bar(header)
            self.window.set_content(toolbar)
            shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            workspace = Gtk.Box(hexpand=True, vexpand=True)
            shell.append(workspace)
            toolbar.set_content(shell)
            sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, width_request=176)
            sidebar.set_hexpand(False)
            sidebar.add_css_class("workspace-sidebar")
            workspace.append(sidebar)
            brand = Gtk.Label(label="РАБОЧАЯ ОБЛАСТЬ", xalign=0, margin_start=8, margin_bottom=8)
            brand.add_css_class("dim-label")
            sidebar.append(brand)
            self.nav_buttons = {}
            self.resource_buttons = []
            for page, caption, icon in (("containers", "Контейнеры", "application-x-executable-symbolic"),
                ("compose", "Compose", "view-list-symbolic"), ("images", "Образы", "drive-harddisk-symbolic"),
                ("volumes", "Тома", "folder-symbolic"), ("networks", "Сети", "network-wired-symbolic")):
                button = Gtk.Button()
                row = Gtk.Box(spacing=9)
                row.append(Gtk.Image.new_from_icon_name(icon))
                row.append(Gtk.Label(label=caption, xalign=0, hexpand=True))
                button.set_child(row)
                button.add_css_class("flat")
                button.connect("clicked", lambda _, page=page: self.navigate(page))
                sidebar.append(button)
                self.nav_buttons[page] = button
                if page == "compose":
                    self.stacks_button = button
                elif page != "containers":
                    self.resource_buttons.append(button)
                action = Gio.SimpleAction.new("page-" + page, None)
                action.connect("activate", lambda *_args, page=page: self.navigate(page))
                self.add_action(action)
                self.set_accels_for_action("app.page-" + page, ["<Control>" + str(len(self.nav_buttons))])
            spacer = Gtk.Box(vexpand=True)
            sidebar.append(spacer)
            self.engine_label = Gtk.Label(label="Локальный rootless Docker", xalign=0, wrap=True, margin_start=8)
            self.engine_label.add_css_class("dim-label")
            sidebar.append(self.engine_label)
            self.engine_button = Gtk.Button(label="Выбрать движок")
            self.engine_button.connect("clicked", self.choose_engine)
            sidebar.append(self.engine_button)
            self.rootless_button = Gtk.Button(label="Настроить rootless")
            self.rootless_button.connect("clicked", self.rootless_dialog)
            sidebar.append(self.rootless_button)
            self.pages = Gtk.Stack(hexpand=True, vexpand=True)
            workspace.append(self.pages)
            self.active_page = "containers"
            main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                           margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
            self.pages.add_named(main, "containers")
            heading = Gtk.Label(label="Контейнеры", xalign=0)
            heading.add_css_class("workspace-heading")
            main.append(heading)
            self.overview = Gtk.Label(label="Контейнеров: —   ·   Запущено: —", xalign=0)
            self.overview.add_css_class("dim-label")
            main.append(self.overview)
            self.resource_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                                         margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
            self.pages.add_named(self.resource_page, "resources")
            self.resource_selection = None
            self.status = Gtk.Label(label="Подключение…", xalign=0, wrap=True, selectable=True,
                                    margin_start=14, margin_end=14, margin_top=6, margin_bottom=6)
            self.status.add_css_class("dim-label")
            shell.append(Gtk.Separator())
            shell.append(self.status)
            self.nav_buttons["containers"].add_css_class("active")
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
            detail_box.append(self.detail)
            self.metrics_button = Gtk.Button(label="Метрики")
            self.logs_button = Gtk.Button(label="Логи")
            self.metrics_button.connect("clicked", lambda *_: self.read_detail("metrics"))
            self.logs_button.connect("clicked", lambda *_: self.read_detail("logs"))
            detail_header.append(self.metrics_button)
            detail_header.append(self.logs_button)
            self.monitor_button = Gtk.Button(label="Мониторинг")
            self.monitor_button.connect("clicked", self.open_monitor)
            detail_header.append(self.monitor_button)
            self.terminal_button = Gtk.Button(label="Терминал")
            self.terminal_button.connect("clicked", self.open_terminal)
            detail_header.append(self.terminal_button)
            detail_box.append(detail_header)
            self.detail_text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                           wrap_mode=Gtk.WrapMode.CHAR, top_margin=8, bottom_margin=8,
                                           left_margin=8, right_margin=8)
            detail_scroll = Gtk.ScrolledWindow(min_content_height=110)
            detail_scroll.set_child(self.detail_text)
            detail_box.append(detail_scroll)
            main.append(detail_box)
            self.selection.connect("notify::selected-item", lambda *_: self.update_actions())
            self.window.present()
            self.load()

        def navigate(self, page):
            if self.busy or page not in self.nav_buttons:
                return
            self.active_page = page
            for key, button in self.nav_buttons.items():
                (button.add_css_class if key == page else button.remove_css_class)("active")
            caption = {"containers": "Контейнеры", "compose": "Compose", "images": "Образы", "volumes": "Тома", "networks": "Сети"}[page]
            self.window.set_title("Localzet Containers — " + caption)
            self.pages.set_visible_child_name("containers" if page == "containers" else "resources")
            self.clear_detail()
            if page == "containers":
                self.load()
            else:
                self.clear_resource_page(caption, "Загрузка…")
                if page == "compose":
                    self.show_stacks()
                else:
                    self.show_resources(None, page, caption)

        def refresh_page(self):
            self.navigate(self.active_page)

        def clear_resource_page(self, caption, summary):
            self.resource_selection = None
            child = self.resource_page.get_first_child()
            while child is not None:
                self.resource_page.remove(child)
                child = self.resource_page.get_first_child()
            heading = Gtk.Label(label=caption, xalign=0)
            heading.add_css_class("workspace-heading")
            self.resource_page.append(heading)
            label = Gtk.Label(label=summary, xalign=0, wrap=True, selectable=True)
            label.add_css_class("dim-label")
            self.resource_page.append(label)
            return self.resource_page

        def resource_table(self, content, rows, fields):
            store = Gio.ListStore.new(Row)
            selection = Gtk.SingleSelection(model=store, autoselect=False, can_unselect=True)
            table = Gtk.ColumnView(model=selection, show_row_separators=True, vexpand=True)
            for key, caption in fields:
                factory = Gtk.SignalListItemFactory()
                def setup(_, item):
                    item.set_child(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                             margin_start=8, margin_end=8, margin_top=6, margin_bottom=6))
                def bind(_, item, key=key):
                    value = item.get_item().item[key] or "—"
                    item.get_child().set_label(value)
                    item.get_child().set_tooltip_text(value)
                factory.connect("setup", setup)
                factory.connect("bind", bind)
                column = Gtk.ColumnViewColumn.new(caption, factory)
                column.set_expand(True)
                column.set_resizable(True)
                table.append_column(column)
            search = Gtk.SearchEntry(placeholder_text="Фильтр ресурсов")
            content.append(search)
            def filter_rows(*_):
                query = search.get_text().casefold()
                store.remove_all()
                for row in rows:
                    if not query or any(query in str(value).casefold() for value in row.values()):
                        store.append(Row(row))
            search.connect("search-changed", filter_rows)
            filter_rows()
            scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=140)
            scroll.set_child(table)
            content.append(scroll)
            self.resource_selection = selection
            return selection

        def show_resources(self, _, kind, caption):
            if self.busy:
                return
            self.busy = True
            self.generation += 1
            generation = self.generation
            rootful = self.rootful
            self.update_actions()
            future = self.pool.submit(lambda: Engine(rootful=rootful).resources(kind))
            future.add_done_callback(lambda f: GLib.idle_add(self.resources_finished, generation, kind, caption, f))

        def resources_finished(self, generation, kind, caption, future):
            if generation != self.generation or not self.window:
                return GLib.SOURCE_REMOVE
            self.busy = False
            self.update_actions()
            try:
                rows = future.result()
                summary = f"Ресурсов: {len(rows)}"
            except (EngineError, OSError, ValueError) as error:
                rows = ()
                summary = str(error)
            except Exception:
                rows = ()
                summary = "Не удалось получить список ресурсов."
            content = self.clear_resource_page(caption, summary)
            parent = self.window
            fields = {"images": (("Repository", "Репозиторий"), ("Tag", "Тег"), ("Size", "Размер"), ("ID", "ID")),
                      "volumes": (("Name", "Имя"), ("Driver", "Драйвер"), ("Scope", "Область")),
                      "networks": (("Name", "Имя"), ("Driver", "Драйвер"), ("Scope", "Область"), ("ID", "ID"))}[kind]
            controls = Gtk.Box(spacing=6)
            content.append(controls)
            def button(label, callback):
                widget = Gtk.Button(label=label)
                widget.connect("clicked", callback)
                controls.append(widget)
                return widget
            if kind in ("volumes", "networks"):
                button("Создать том" if kind == "volumes" else "Создать сеть",
                       lambda *_: self.confirm_resource(parent, kind, caption, None))
                if kind == "volumes":
                    button("Восстановить", lambda *_: self.open_volume_archive(parent, None))
            else:
                button("Загрузить образ", lambda *_: self.confirm_deployment(parent, None))
                button("Собрать образ", lambda *_: self.open_builder(parent))
            selection = self.resource_table(content, rows, fields)
            inspector = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            inspector.add_css_class("container-detail")
            detail = Gtk.Label(label="Выберите ресурс", xalign=0, wrap=True, selectable=True)
            inspector.append(detail)
            actions = Gtk.Box(spacing=6)
            inspector.append(actions)
            content.append(inspector)
            def chosen(*_):
                child = actions.get_first_child()
                while child is not None:
                    actions.remove(child)
                    child = actions.get_first_child()
                selected = selection.get_selected_item()
                if selected is None:
                    detail.set_label("Выберите ресурс")
                    return
                item = selected.item
                detail.set_label(" · ".join(str(item[key]) for key, _ in fields))
                def add(label, callback, destructive=False):
                    widget = Gtk.Button(label=label)
                    if destructive:
                        widget.add_css_class("destructive-action")
                    widget.connect("clicked", callback)
                    actions.append(widget)
                if kind == "volumes":
                    add("Сведения", lambda *_: self.show_volume(parent, item["Name"]))
                    add("Экспорт TAR", lambda *_: self.open_volume_archive(parent, item["Name"]))
                if kind == "images":
                    add("Создать контейнер", lambda *_: self.confirm_deployment(parent, item))
                    add("История слоёв", lambda *_: self.show_image_history(parent, item["ID"]))
                    add("Тег / Публикация", lambda *_: self.open_registry(parent, item))
                if kind in ("images", "networks") and not (kind == "networks" and
                        (item["Name"] in ("bridge", "host", "none") or item["Scope"] != "local")):
                    add("Удалить", lambda *_: self.confirm_resource(parent, kind, caption, item), True)
            selection.connect("notify::selected-item", chosen)
            chosen()
            self.status.set_label(summary)
            return GLib.SOURCE_REMOVE

        def open_registry(self, parent, item):
            if self.busy:
                return
            generation, rootful = self.generation, self.rootful
            identity = item["ID"]
            prompt = Adw.AlertDialog(heading="Registry",
                body="Docker Hub, GHCR и приватные реестры. Вход выполните заранее через Docker CLI. Приложение не читает и не хранит пароли или токены.")
            form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            form.append(Gtk.Label(label=identity, selectable=True, wrap=True))
            reference = Gtk.Entry(placeholder_text="ghcr.io/owner/image:v1")
            form.append(reference)
            form.append(Gtk.Label(label="Для публикации сначала создайте тег выбранного образа. Укажите полный адрес реестра.", wrap=True, xalign=0))
            prompt.set_extra_child(form)
            prompt.add_response("cancel", "Отмена")
            prompt.add_response("tag", "Создать тег")
            prompt.add_response("push", "Публиковать")
            prompt.set_default_response("cancel")
            prompt.set_close_response("cancel")
            def review(_, action):
                if action not in ("tag", "push") or self.busy or generation != self.generation or rootful != self.rootful:
                    return
                from localzet.containers import validate_registry_tag
                target = reference.get_text()
                try:
                    validate_registry_tag(target, qualified=action == "push")
                except EngineError as error:
                    invalid = Adw.AlertDialog(heading="Проверьте адрес", body=str(error))
                    invalid.add_response("close", "Закрыть")
                    invalid.present(parent)
                    return
                confirm = Adw.AlertDialog(heading="Подтвердить публикацию?" if action == "push" else "Подтвердить тег?",
                    body=target + "\n" + identity + ("\nОбраз и его слои будут переданы указанному реестру. Удалённый тег может быть изменён. Проверьте содержимое и права доступа." if action == "push" else "\nСоздаётся дополнительный локальный тег. Существующий тег не заменяется."))
                confirm.add_response("cancel", "Отмена")
                confirm.add_response("confirm", "Публиковать" if action == "push" else "Создать тег")
                confirm.set_default_response("cancel")
                confirm.set_close_response("cancel")
                def run(_, choice):
                    if choice != "confirm" or self.busy or generation != self.generation or rootful != self.rootful:
                        return
                    if parent is not self.window:
                        parent.close()
                    self.busy = True
                    self.generation += 1
                    current = self.generation
                    self.status.set_label("Публикация образа (до 10 минут)…" if action == "push" else "Создание тега…")
                    self.update_actions()
                    def worker():
                        engine = Engine(rootful=rootful)
                        return engine.push_image(identity, target) if action == "push" else engine.tag_image(identity, target)
                    future = self.pool.submit(worker)
                    def complete():
                        if current != self.generation or not self.window:
                            return GLib.SOURCE_REMOVE
                        self.status.set_label("Операция завершена." if future.exception() is None else "Операция не подтверждена; проверьте состояние реестра и локальных образов.")
                        return self.resources_finished(current, "images", "Образы", future)
                    future.add_done_callback(lambda _: GLib.idle_add(complete))
                confirm.connect("response", run)
                confirm.present(parent)
            prompt.connect("response", review)
            prompt.present(parent)

        def show_image_history(self, parent, identity):
            if self.busy:
                return
            self.busy = True
            self.generation += 1
            generation, rootful = self.generation, self.rootful
            self.update_actions()
            future = self.pool.submit(lambda: Engine(rootful=rootful).image_history(identity))
            def complete():
                if generation != self.generation or not self.window:
                    return GLib.SOURCE_REMOVE
                self.busy = False
                self.update_actions()
                dialog = Adw.Dialog(title="История слоёв", content_width=760, content_height=480)
                toolbar = Adw.ToolbarView()
                toolbar.add_top_bar(Adw.HeaderBar())
                view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.CHAR)
                scroll = Gtk.ScrolledWindow(vexpand=True)
                scroll.set_child(view)
                toolbar.set_content(scroll)
                dialog.set_child(toolbar)
                try:
                    rows = future.result()
                    value = "\n\n".join(f"{row['ID']}\n{row['CreatedSince']} · {row['Size']}" for row in rows)
                    view.get_buffer().set_text(value or "Нет данных.")
                except (EngineError, OSError, ValueError) as error:
                    view.get_buffer().set_text(str(error))
                except Exception:
                    view.get_buffer().set_text("Не удалось получить историю.")
                dialog.present(parent)
                return GLib.SOURCE_REMOVE
            future.add_done_callback(lambda _: GLib.idle_add(complete))

        def open_builder(self, parent):
            if self.busy:
                return
            from pathlib import Path
            generation, rootful = self.generation, self.rootful
            prompt = Adw.AlertDialog(heading="Image Builder",
                body="Используйте только доверенный Dockerfile и каталог проекта. Docker получает контекст целиком с учётом .dockerignore; проверьте секреты. RUN без сети, но базовые образы и frontend могут загружаться.")
            form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            tag = Gtk.Entry(placeholder_text="my-app:dev")
            context = Gtk.Entry(placeholder_text="Абсолютный путь к каталогу проекта")
            choose = Gtk.Button(label="Выбрать каталог")
            def choose_folder(*_):
                picker = Gtk.FileDialog(title="Контекст сборки")
                def chosen(dialog, result):
                    try:
                        folder = dialog.select_folder_finish(result)
                        if folder and folder.get_path():
                            context.set_text(folder.get_path())
                    except GLib.Error:
                        pass
                picker.select_folder(self.window, None, chosen)
            choose.connect("clicked", choose_folder)
            editor = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.NONE)
            editor.get_buffer().set_text("FROM scratch\n")
            scroll = Gtk.ScrolledWindow(min_content_height=180, min_content_width=340)
            scroll.set_child(editor)
            arguments = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.CHAR, height_request=64)
            capture = Gtk.CheckButton(label="Показать последние 256 КиБ вывода (может содержать секреты)")
            for widget in (Gtk.Label(label="Локальный тег", xalign=0), tag,
                           Gtk.Label(label="Контекст", xalign=0), context, choose,
                           Gtk.Label(label="Dockerfile", xalign=0), scroll,
                           Gtk.Label(label="Build ARG: KEY=value, одна строка. Не для секретов.", xalign=0, wrap=True),
                           arguments, capture):
                form.append(widget)
            prompt.set_extra_child(form)
            prompt.add_response("cancel", "Отмена")
            prompt.add_response("review", "Проверить")
            prompt.set_default_response("cancel")
            prompt.set_close_response("cancel")
            def review(_, choice):
                if choice != "review" or self.busy or generation != self.generation or rootful != self.rootful:
                    return
                buffer = editor.get_buffer()
                source = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
                target, directory = tag.get_text(), context.get_text()
                arg_buffer = arguments.get_buffer()
                values = tuple(line for line in arg_buffer.get_text(arg_buffer.get_start_iter(), arg_buffer.get_end_iter(), True).splitlines() if line)
                try:
                    build_argument_flags(values)
                except EngineError as error:
                    invalid = Adw.AlertDialog(heading="Проверьте аргументы", body=str(error))
                    invalid.add_response("close", "Закрыть")
                    invalid.present(parent)
                    return
                collect = capture.get_active()
                keys = ", ".join(value.split("=", 1)[0] for value in values) or "—"
                confirm = Adw.AlertDialog(heading="Подтвердить сборку",
                    body=f"Тег: {target}\nКаталог: {directory}\nDockerfile: {len(source.encode('utf-8'))} байт.\nARG: {keys}. Сборка выполняет команды из Dockerfile; она не является песочницей.")
                confirm.add_response("cancel", "Отмена")
                confirm.add_response("build", "Собрать")
                confirm.set_default_response("cancel")
                confirm.set_close_response("cancel")
                def run(_, response):
                    if response != "build" or self.busy or generation != self.generation or rootful != self.rootful:
                        return
                    if parent is not self.window:
                        parent.close()
                    self.busy = True
                    self.generation += 1
                    current = self.generation
                    self.status.set_label("Сборка образа (до 10 минут)…")
                    self.update_actions()
                    diagnostics = []
                    future = self.pool.submit(lambda: Engine(rootful=rootful).build_image(
                        target, source, Path(directory), build_args=values,
                        output=diagnostics.append if collect else None))
                    def complete():
                        if current != self.generation or not self.window:
                            return GLib.SOURCE_REMOVE
                        self.status.set_label("Сборка завершена; тег найден." if future.exception() is None
                                              else "Сборка не подтверждена; проверьте образы.")
                        result = self.resources_finished(current, "images", "Образы", future)
                        if diagnostics:
                            report = Adw.Dialog(title="Вывод сборки", content_width=800, content_height=480)
                            layout = Adw.ToolbarView()
                            layout.add_top_bar(Adw.HeaderBar())
                            view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.CHAR)
                            view.get_buffer().set_text(diagnostics.pop())
                            scroll = Gtk.ScrolledWindow(vexpand=True)
                            scroll.set_child(view)
                            layout.set_content(scroll)
                            report.set_child(layout)
                            report.present(self.window)
                        return result
                    future.add_done_callback(lambda _: GLib.idle_add(complete))
                confirm.connect("response", run)
                confirm.present(parent)
            prompt.connect("response", review)
            prompt.present(parent)

        def confirm_deployment(self, parent, item):
            if self.busy:
                return
            generation, rootful = self.generation, self.rootful
            fields = {}
            if item is None:
                prompt = Adw.AlertDialog(heading="Загрузить образ?",
                    body="Укажите доверенный registry и явный тег или digest. Загрузка обращается к сети и может изменить локальный тег. Образ не запускается.")
                entry = Gtk.Entry(placeholder_text="docker.io/library/alpine:3.22")
                action = "Загрузить"
            else:
                prompt = Adw.AlertDialog(heading="Создать контейнер?",
                    body=item["ID"] + "\nБез автоматического запуска. Read-only rootfs, UID 65534, без capabilities. Порты только localhost; окружение не предназначено для секретов. Используйте доверенный образ.")
                entry = Gtk.Entry(placeholder_text="Имя контейнера")
                action = "Проверить"
                form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                form.append(entry)
                for key, label, default in (
                    ("network", "Сеть: none, bridge или полный ID", "none"),
                    ("ports", "Порты через пробел: 8080:80/tcp", ""),
                    ("environment", "Окружение: KEY=value (одна строка на переменную)", ""),
                    ("mounts", "Тома через пробел: name:/data:ro", ""),
                    ("memory", "RAM, МиБ", "512"),
                    ("cpus", "CPU: например 1.5", ""),
                    ("restart", "Restart: no, on-failure, unless-stopped, always", "no"),
                ):
                    form.append(Gtk.Label(label=label, xalign=0, wrap=True))
                    if key == "environment":
                        field = Gtk.TextView(wrap_mode=Gtk.WrapMode.CHAR, height_request=60)
                    else:
                        field = Gtk.Entry(text=default)
                    fields[key] = field
                    form.append(field)
                scroll = Gtk.ScrolledWindow(min_content_height=380, max_content_height=460, propagate_natural_height=True)
                scroll.set_child(form)
            prompt.set_extra_child(entry if item is None else scroll)
            prompt.add_response("cancel", "Отмена")
            prompt.add_response("confirm", action)
            prompt.set_close_response("cancel")
            prompt.set_default_response("cancel")
            prompt.set_response_appearance("confirm", Adw.ResponseAppearance.SUGGESTED)

            def response(_, choice):
                if choice != "confirm" or self.busy or generation != self.generation or rootful != self.rootful:
                    return
                target = entry.get_text()
                if item is not None:
                    try:
                        buffer = fields["environment"].get_buffer()
                        env = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
                        options = Deployment(
                            network=fields["network"].get_text(),
                            ports=tuple(fields["ports"].get_text().split()),
                            environment=tuple(line for line in env.splitlines() if line),
                            mounts=tuple(fields["mounts"].get_text().split()),
                            memory_mib=int(fields["memory"].get_text()),
                            cpus=fields["cpus"].get_text(),
                            restart=fields["restart"].get_text())
                        deployment_args(options)
                    except (EngineError, ValueError) as error:
                        invalid = Adw.AlertDialog(heading="Проверьте настройки", body=str(error))
                        invalid.add_response("ok", "Закрыть")
                        invalid.present(parent)
                        return
                    review = Adw.AlertDialog(heading="Подтвердить конфигурацию",
                        body=f"Имя: {target}\nОбраз: {item['ID']}\nСеть: {options.network}\nПорты (localhost): {', '.join(options.ports) or '—'}\nПеременные: {', '.join(v.split('=', 1)[0] for v in options.environment) or '—'}\nТома: {', '.join(options.mounts) or '—'}\nRAM: {options.memory_mib} МиБ · CPU: {options.cpus or 'без лимита'}\nRestart: {options.restart}\nКонтейнер не запускается автоматически.")
                    review.add_response("cancel", "Отмена")
                    review.add_response("confirm", "Создать")
                    review.set_default_response("cancel")
                    review.set_close_response("cancel")
                    review.connect("response", lambda _, result: deploy(target, options) if result == "confirm" else None)
                    review.present(parent)
                    return
                deploy(target, None)

            def deploy(target, options):
                if self.busy or generation != self.generation or rootful != self.rootful:
                    return
                if parent is not self.window:
                    parent.close()
                self.busy = True
                self.generation += 1
                current = self.generation
                self.status.set_label("Загрузка образа (до 10 минут)…" if item is None else "Создание контейнера…")
                self.update_actions()
                def worker():
                    engine = Engine(rootful=rootful)
                    return engine.pull_image(target) if item is None else engine.create_container(target, item["ID"], options)
                future = self.pool.submit(worker)
                if item is None:
                    future.add_done_callback(lambda f: GLib.idle_add(self.pull_finished, current, f))
                else:
                    future.add_done_callback(lambda f: GLib.idle_add(self.finished, current, f))
            prompt.connect("response", response)
            prompt.present(parent)

        def pull_finished(self, generation, future):
            if generation != self.generation or not self.window:
                return GLib.SOURCE_REMOVE
            self.status.set_label("Загрузка завершена; список образов обновлён." if future.exception() is None
                                  else "Загрузка не подтверждена. Проверьте список образов.")
            return self.resources_finished(generation, "images", "Образы", future)

        def open_volume_archive(self, parent, name):
            if self.busy:
                return
            from pathlib import Path
            generation, rootful = self.generation, self.rootful
            backup = name is not None
            prompt = Adw.AlertDialog(heading="Экспорт тома" if backup else "Восстановить в новый том",
                body="Только доверенный локальный BusyBox-образ с /bin/busybox. До 128 МиБ, только обычные файлы и каталоги. UID/GID, ACL и расширенные атрибуты не сохраняются. Для экспорта том должен быть свободен от контейнеров.")
            form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            target = Gtk.Entry(text=name or "", placeholder_text="Имя нового тома", editable=not backup)
            helper = Gtk.Entry(placeholder_text="sha256: полный ID доверенного BusyBox")
            path = Gtk.Entry(placeholder_text="/home/user/backup.tar")
            picker = Gtk.Button(label="Выбрать файл")
            def choose(*_):
                file_dialog = Gtk.FileDialog(title="Архив тома")
                def selected(dialog, result):
                    try:
                        file = dialog.save_finish(result) if backup else dialog.open_finish(result)
                        if file and file.get_path():
                            path.set_text(file.get_path())
                    except GLib.Error:
                        pass
                if backup:
                    file_dialog.set_initial_name(name + ".tar")
                    file_dialog.save(self.window, None, selected)
                else:
                    file_dialog.open(self.window, None, selected)
            picker.connect("clicked", choose)
            for label, widget in (("Том", target), ("BusyBox", helper), ("TAR", path), ("", picker)):
                form.append(Gtk.Label(label=label, xalign=0))
                form.append(widget)
            prompt.set_extra_child(form)
            prompt.add_response("cancel", "Отмена")
            prompt.add_response("review", "Проверить")
            prompt.set_default_response("cancel")
            prompt.set_close_response("cancel")
            def review(_, choice):
                if choice != "review" or self.busy or generation != self.generation or rootful != self.rootful:
                    return
                volume, image, filename = target.get_text(), helper.get_text(), path.get_text()
                confirm = Adw.AlertDialog(heading="Подтвердить экспорт?" if backup else "Подтвердить восстановление?",
                    body=f"Том: {volume}\nОбраз: {image}\nФайл: {filename}\n"
                         + ("Архив содержит конфиденциальные данные. Существующий файл не заменяется." if backup else
                            "Создаётся новый том; при сбое он может содержать неполные данные. Существующие тома не перезаписываются намеренно."))
                confirm.add_response("cancel", "Отмена")
                confirm.add_response("yes", "Выполнить")
                confirm.set_default_response("cancel")
                confirm.set_close_response("cancel")
                def execute(_, result):
                    if result != "yes" or self.busy or generation != self.generation or rootful != self.rootful:
                        return
                    if parent is not self.window:
                        parent.close()
                    self.busy = True
                    self.generation += 1
                    current = self.generation
                    self.status.set_label("Экспорт тома…" if backup else "Восстановление тома…")
                    self.update_actions()
                    def worker():
                        engine = Engine(rootful=rootful)
                        if backup:
                            engine.backup_volume(volume, image, Path(filename))
                            return engine.resources("volumes")
                        return engine.restore_volume(volume, image, Path(filename))
                    future = self.pool.submit(worker)
                    def finished():
                        if current != self.generation or not self.window:
                            return GLib.SOURCE_REMOVE
                        self.status.set_label("Операция завершена." if future.exception() is None else "Операция не подтверждена; проверьте данные.")
                        return self.resources_finished(current, "volumes", "Тома", future)
                    future.add_done_callback(lambda _: GLib.idle_add(finished))
                confirm.connect("response", execute)
                confirm.present(parent)
            prompt.connect("response", review)
            prompt.present(parent)

        def show_volume(self, parent, name):
            if self.busy:
                return
            self.busy = True
            self.generation += 1
            generation, rootful = self.generation, self.rootful
            self.update_actions()
            future = self.pool.submit(lambda: Engine(rootful=rootful).volume_info(name))
            def complete():
                if generation != self.generation or not self.window:
                    return GLib.SOURCE_REMOVE
                self.busy = False
                self.update_actions()
                dialog = Adw.AlertDialog(heading="Том · " + name)
                dialog.add_response("close", "Закрыть")
                dialog.set_close_response("close")
                dialog.set_default_response("close")
                try:
                    info = future.result()
                    references = info["references"]
                    details = "\n".join(f"{row.name} · {row.state} · {row.id[:12]}" for row in references)
                    dialog.set_body(f"Драйвер: {info['driver']} · {info['scope']}\nСоздан: {info['created']}\n"
                                    + f"Подключений: {len(references)} (включая остановленные)\n"
                                    + (details or "Нет подключений."))
                    if info["default_local"] and not references:
                        dialog.add_response("remove", "Удалить том")
                        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
                        dialog.connect("response", lambda _, choice: self.confirm_volume_delete(parent, name, generation, rootful)
                                       if choice == "remove" else None)
                except (EngineError, OSError, ValueError) as error:
                    dialog.set_body(str(error))
                except Exception:
                    dialog.set_body("Не удалось получить сведения о томе.")
                dialog.present(parent)
                return GLib.SOURCE_REMOVE
            future.add_done_callback(lambda _: GLib.idle_add(complete))

        def confirm_volume_delete(self, parent, name, generation, rootful):
            if self.busy or generation != self.generation or rootful != self.rootful:
                return
            prompt = Adw.AlertDialog(heading="Безвозвратно удалить данные?",
                body="Том " + name + " будет удалён вместе со всем содержимым. Резервная копия не создаётся. Введите точное имя тома.")
            entry = Gtk.Entry(placeholder_text=name)
            prompt.set_extra_child(entry)
            prompt.add_response("cancel", "Отмена")
            prompt.add_response("confirm", "Удалить")
            prompt.set_response_enabled("confirm", False)
            prompt.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
            prompt.set_default_response("cancel")
            prompt.set_close_response("cancel")
            entry.connect("changed", lambda field: prompt.set_response_enabled("confirm", field.get_text() == name))
            def confirmed(_, choice):
                if choice != "confirm" or entry.get_text() != name or self.busy or generation != self.generation or rootful != self.rootful:
                    return
                if parent is not self.window:
                    parent.close()
                self.busy = True
                self.generation += 1
                current = self.generation
                self.update_actions()
                future = self.pool.submit(lambda: Engine(rootful=rootful).remove_volume(name))
                future.add_done_callback(lambda f: GLib.idle_add(self.resources_finished, current, "volumes", "Тома", f))
            prompt.connect("response", confirmed)
            prompt.present(parent)

        def confirm_resource(self, parent, kind, caption, item):
            if self.busy:
                return
            generation = self.generation
            rootful = self.rootful
            entry = None
            if item is None:
                prompt = Adw.AlertDialog(heading="Создать ресурс?", body="Том: локальный драйвер. Сеть: внутренний bridge без внешнего доступа. Имя: 2–63 ASCII-символа.")
                entry = Gtk.Entry(placeholder_text="Имя ресурса")
                prompt.set_extra_child(entry)
                action = "Создать"
            else:
                prompt = Adw.AlertDialog(heading="Удалить ресурс?", body=item["ID"] +
                    "\nОбраз может потребоваться скачать заново. Сеть удаляется только если Docker разрешит операцию. Без принудительного удаления.")
                action = "Удалить"
            prompt.add_response("cancel", "Отмена")
            prompt.add_response("confirm", action)
            prompt.set_close_response("cancel")
            prompt.set_default_response("cancel")
            prompt.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE if item else Adw.ResponseAppearance.SUGGESTED)

            def response(_, choice):
                if choice != "confirm" or self.busy or generation != self.generation or rootful != self.rootful:
                    return
                target = item["ID"] if item else entry.get_text()
                if parent is not self.window:
                    parent.close()
                self.busy = True
                self.generation += 1
                current = self.generation
                self.update_actions()
                def worker():
                    engine = Engine(rootful=rootful)
                    return engine.remove_resource(kind, target) if item else engine.create_resource(kind, target)
                future = self.pool.submit(worker)
                future.add_done_callback(lambda f: GLib.idle_add(self.resources_finished, current, kind, caption, f))
            prompt.connect("response", response)
            prompt.present(parent)

        def show_stacks(self, *_):
            if self.busy:
                return
            self.busy = True
            self.generation += 1
            generation = self.generation
            rootful = self.rootful
            self.update_actions()
            future = self.pool.submit(lambda: Engine(rootful=rootful).stacks())
            future.add_done_callback(lambda f: GLib.idle_add(self.stacks_finished, generation, f))

        def stacks_finished(self, generation, future):
            if generation != self.generation or not self.window:
                return GLib.SOURCE_REMOVE
            self.busy = False
            self.update_actions()
            try:
                rows = tuple({"name": row.name, "status": row.status, "files": row.config_files} for row in future.result())
                summary = f"Проектов: {len(rows)} · Внешние проекты доступны для просмотра"
            except (EngineError, OSError, ValueError) as error:
                rows = ()
                summary = str(error)
            except Exception:
                rows = ()
                summary = "Не удалось получить список Compose-проектов."
            content = self.clear_resource_page("Compose", summary)
            studio = Gtk.Button(label="Открыть Compose Studio", halign=Gtk.Align.START)
            studio.add_css_class("suggested-action")
            studio.connect("clicked", lambda *_: self.compose_studio(self.window))
            content.append(studio)
            self.resource_table(content, rows, (("name", "Проект"), ("status", "Состояние"), ("files", "Файлы конфигурации")))
            self.status.set_label(summary)
            return GLib.SOURCE_REMOVE

        def compose_studio(self, parent):
            if self.busy:
                return
            if parent is not self.window:
                parent.close()
            dialog = Adw.Dialog(title="Compose Studio", content_width=940, content_height=640)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            toolbar.add_top_bar(header)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                          margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
            box.append(Gtk.Label(label="JSON-подмножество YAML · services → image (полный локальный SHA-256 ID). Проверка и управление собственными проектами.",
                                 wrap=True, xalign=0))
            editor = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.NONE)
            editor.get_buffer().set_text('{\n  "services": {\n    "app": {\n      "image": "sha256:..."\n    }\n  }\n}')
            preview = Gtk.TextView(monospace=True, editable=False, cursor_visible=False)
            panels = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True, wide_handle=True)
            for setter, view in ((panels.set_start_child, editor), (panels.set_end_child, preview)):
                scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True, min_content_width=250)
                scroll.set_child(view)
                setter(scroll)
            panels.set_position(440)
            box.append(panels)
            status = Gtk.Label(label="Введите конфигурацию и нажмите «Проверить».", wrap=True, xalign=0)
            box.append(status)
            validate = Gtk.Button(label="Проверить")
            validate.add_css_class("suggested-action")
            header.pack_end(validate)
            toolbar.set_content(box)
            dialog.set_child(toolbar)
            state = {"closed": False, "revision": 0, "validated": None}
            store = StudioStore()
            storage = Gtk.Box(spacing=6)
            saved = Gtk.DropDown.new_from_strings([])
            saved.set_hexpand(True)
            open_saved = Gtk.Button(label="Открыть")
            save = Gtk.Button(label="Сохранить", sensitive=False)
            storage.append(saved)
            storage.append(open_saved)
            storage.append(save)
            box.prepend(storage)
            def refresh_saved():
                try:
                    ids = store.projects()
                    saved.set_model(Gtk.StringList.new(list(ids)))
                    open_saved.set_sensitive(bool(ids))
                except (EngineError, OSError) as error:
                    open_saved.set_sensitive(False)
                    status.set_label(str(error))
            def load_saved(*_):
                if self.busy:
                    return
                selected = saved.get_selected_item()
                if selected is None:
                    return
                try:
                    source = store.load(selected.get_string())
                    editor.get_buffer().set_text(source)
                    status.set_label("Проект открыт. Повторите проверку перед развёртыванием.")
                except (EngineError, OSError, ValueError) as error:
                    status.set_label(str(error))
            def save_current(*_):
                if self.busy or state["validated"] is None:
                    return
                try:
                    identity = store.save(state["validated"])
                    refresh_saved()
                    status.set_label("Сохранён проект: " + identity[:16])
                except (EngineError, OSError, ValueError) as error:
                    status.set_label(str(error))
            open_saved.connect("clicked", load_saved)
            save.connect("clicked", save_current)
            refresh_saved()
            actions = Gtk.Box(spacing=6)
            buttons = []
            for action, caption in (("up", "Развернуть"), ("start", "Старт"), ("stop", "Стоп"),
                                    ("restart", "Рестарт"), ("down", "Down")):
                button = Gtk.Button(label=caption, sensitive=False)
                button.connect("clicked", lambda _, action=action: confirm(action))
                actions.append(button)
                buttons.append(button)
            inspect = Gtk.Button(label="Состояние сервисов", sensitive=False)
            actions.append(inspect)
            box.append(actions)
            def inspect_project(*_):
                source = state["validated"]
                if source is None or self.busy or state["closed"]:
                    return
                self.busy = True
                self.generation += 1
                generation = self.generation
                rootful = self.rootful
                self.update_actions()
                enable(False)
                validate.set_sensitive(False)
                editor.set_editable(False)
                status.set_label("Получение состояния сервисов…")
                future = self.pool.submit(lambda: Engine(rootful=rootful).studio_status(source))
                def complete():
                    if generation != self.generation or not self.window:
                        return GLib.SOURCE_REMOVE
                    self.busy = False
                    self.update_actions()
                    if state["closed"]:
                        return GLib.SOURCE_REMOVE
                    enable(True)
                    validate.set_sensitive(True)
                    editor.set_editable(True)
                    try:
                        rows = future.result()
                        status.set_label(f"Контейнеров проекта: {len(rows)}")
                        details = Adw.AlertDialog(heading="Контейнеры проекта",
                            body="\n".join(f"{row.name} · {row.state} · {row.status}" for row in rows) or "Нет контейнеров.")
                        details.add_response("close", "Закрыть")
                        details.present(dialog)
                    except (EngineError, OSError, ValueError) as error:
                        status.set_label(str(error))
                    except Exception:
                        status.set_label("Не удалось получить состояние проекта.")
                    return GLib.SOURCE_REMOVE
                future.add_done_callback(lambda _: GLib.idle_add(complete))
            inspect.connect("clicked", inspect_project)
            def enable(value):
                inspect.set_sensitive(value)
                save.set_sensitive(value)
                for button in buttons:
                    button.set_sensitive(value)
            def confirm(action):
                source = state["validated"]
                if source is None or self.busy or state["closed"]:
                    return
                revision = state["revision"]
                prompt = Adw.AlertDialog(heading="Выполнить Compose " + action + "?",
                    body="Только проект с отпечатком этой конфигурации. Down удаляет контейнеры и их записываемые слои; тома не удаляются.")
                prompt.add_response("cancel", "Отмена")
                prompt.add_response("confirm", "Выполнить")
                prompt.set_default_response("cancel")
                prompt.set_close_response("cancel")
                if action == "down":
                    prompt.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
                def response(_, choice):
                    if choice != "confirm" or self.busy or state["closed"] or revision != state["revision"]:
                        return
                    self.busy = True
                    self.generation += 1
                    generation = self.generation
                    rootful = self.rootful
                    self.update_actions()
                    enable(False)
                    validate.set_sensitive(False)
                    editor.set_editable(False)
                    status.set_label("Выполнение Compose " + action + "…")
                    future = self.pool.submit(lambda: Engine(rootful=rootful).managed_compose(source, action))
                    def complete():
                        if generation != self.generation or not self.window:
                            return GLib.SOURCE_REMOVE
                        self.busy = False
                        self.update_actions()
                        if not state["closed"]:
                            enable(True)
                            validate.set_sensitive(True)
                            editor.set_editable(True)
                            try:
                                project = future.result()
                                status.set_label(f"Compose {action}: {project}")
                            except (EngineError, OSError, ValueError) as error:
                                status.set_label(str(error))
                            except Exception:
                                status.set_label("Операция не подтверждена.")
                        return GLib.SOURCE_REMOVE
                    future.add_done_callback(lambda _: GLib.idle_add(complete))
                prompt.connect("response", response)
                prompt.present(dialog)
            def changed(*_):
                state["revision"] += 1
                state["validated"] = None
                enable(False)
                preview.get_buffer().set_text("")
                status.set_label("Конфигурация изменена; требуется повторная проверка.")
            editor.get_buffer().connect("changed", changed)
            def closed(*_):
                state["closed"] = True
            dialog.connect("closed", closed)
            def check(*_):
                if self.busy:
                    return
                buffer = editor.get_buffer()
                source = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
                revision = state["revision"]
                self.busy = True
                self.generation += 1
                generation = self.generation
                rootful = self.rootful
                self.update_actions()
                validate.set_sensitive(False)
                editor.set_editable(False)
                state["validated"] = None
                enable(False)
                status.set_label("Проверка Docker Compose…")
                preview.get_buffer().set_text("")
                future = self.pool.submit(lambda: Engine(rootful=rootful).validate_compose(source))
                def finished():
                    if generation != self.generation or not self.window:
                        return GLib.SOURCE_REMOVE
                    self.busy = False
                    self.update_actions()
                    if state["closed"]:
                        return GLib.SOURCE_REMOVE
                    validate.set_sensitive(True)
                    editor.set_editable(True)
                    if revision != state["revision"]:
                        return GLib.SOURCE_REMOVE
                    try:
                        preview.get_buffer().set_text(future.result())
                        state["validated"] = source
                        enable(True)
                        status.set_label("Конфигурация принята Docker Compose. Ничего не запущено.")
                    except (EngineError, OSError, ValueError) as error:
                        status.set_label(str(error))
                    except Exception:
                        status.set_label("Не удалось проверить конфигурацию.")
                    return GLib.SOURCE_REMOVE
                future.add_done_callback(lambda _: GLib.idle_add(finished))
            validate.connect("clicked", check)
            dialog.present(self.window)

        def rootless_dialog(self, *_):
            if self.busy:
                return
            dialog = Adw.AlertDialog(heading="Пользовательский Docker",
                body="Управляемый движок работает от вашего пользователя, без группы docker и без системного демона. Данные хранятся в ~/.local/share/localzet/docker. Запуск не меняет контекст Docker CLI. Остановка завершит работу контейнеров этого движка; данные сохранятся. Движок не включается при входе автоматически.")
            dialog.add_response("cancel", "Отмена")
            dialog.add_response("start", "Запустить")
            dialog.add_response("stop", "Остановить")
            dialog.set_response_appearance("start", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_response_appearance("stop", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_close_response("cancel")
            dialog.set_default_response("cancel")
            dialog.connect("response", self.rootless_chosen)
            dialog.present(self.window)

        def rootless_chosen(self, _, response):
            if self.busy or response not in ("start", "stop"):
                return
            self.busy = True
            self.generation += 1
            generation = self.generation
            self.update_actions()
            self.status.set_label("Настройка пользовательского движка…")
            future = self.pool.submit(rootless_docker.change, response)

            def complete():
                if generation != self.generation or not self.window:
                    return GLib.SOURCE_REMOVE
                self.busy = False
                self.update_actions()
                try:
                    result = future.result()
                    self.rootful = False
                    self.engine_label.set_label("Локальный rootless Docker")
                    self.navigate("containers")
                    self.status.set_label("Движок: " + result)
                except (OSError, ValueError, EngineError) as error:
                    self.status.set_label(str(error))
                return GLib.SOURCE_REMOVE

            future.add_done_callback(lambda _: GLib.idle_add(complete))

        def choose_engine(self, *_):
            if self.busy:
                return
            dialog = Adw.AlertDialog(heading="Локальный Docker Engine",
                body="Rootless использует пользовательский сокет. Системный Docker даёт практически полный доступ к компьютеру; используйте только при существующем разрешении. Приложение не повышает привилегии.")
            dialog.add_response("cancel", "Отмена")
            dialog.add_response("rootless", "Rootless")
            dialog.add_response("rootful", "Системный Docker")
            dialog.add_response("remote", "Удалённый SSH / TLS")
            dialog.set_response_appearance("rootful", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_close_response("cancel")
            dialog.connect("response", self.engine_chosen)
            dialog.present(self.window)

        def engine_chosen(self, _, response):
            if response == "remote" and not self.busy:
                self.open_remote()
                return
            if response not in ("rootless", "rootful") or self.busy:
                return
            self.rootful = response == "rootful"
            self.engine_label.set_label("Системный Docker · привилегированный доступ" if self.rootful
                                        else "Локальный rootless Docker")
            self.rows = ()
            self.last_error = False
            self.clear_detail()
            self.render()
            self.navigate("containers")

        def open_remote(self):
            if self.busy:
                return
            prompt = Adw.AlertDialog(heading="Удалённый Docker · SSH / TLS",
                body="Управление удалёнными контейнерами. Заранее настройте ключи и проверьте ключ сервера в known_hosts. Никаких паролей, автоматического принятия ключей или повышения привилегий.")
            form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            host = Gtk.Entry(placeholder_text="server.example.org")
            user = Gtk.Entry(placeholder_text="SSH user")
            port = Gtk.SpinButton.new_with_range(1, 65535, 1)
            port.set_value(22)
            protocol = Gtk.DropDown.new_from_strings(["SSH", "TLS · только просмотр"])
            certificate = Gtk.Entry(placeholder_text="/path/to/certificates")
            connection_name = Gtk.Entry(placeholder_text="Имя для сохранения (необязательно)")
            store = RemoteStore()
            saved = Gtk.DropDown.new_from_strings([])
            load = Gtk.Button(label="Открыть сохранённое подключение")
            try:
                saved.set_model(Gtk.StringList.new(list(store.names())))
            except (EngineError, OSError):
                load.set_sensitive(False)
            def protocol_changed(*_):
                tls = protocol.get_selected() == 1
                user.set_sensitive(not tls)
                certificate.set_sensitive(tls)
                port.set_value(2376 if tls else 22)
            protocol.connect("notify::selected", protocol_changed)
            protocol_changed()
            def load_endpoint(*_):
                item = saved.get_selected_item()
                if item is None:
                    return
                try:
                    endpoint = store.load(item.get_string())
                    tls = isinstance(endpoint, TLSEngine)
                    protocol.set_selected(1 if tls else 0)
                    host.set_text(endpoint.host)
                    port.set_value(endpoint.port)
                    user.set_text("" if tls else endpoint.user)
                    certificate.set_text(endpoint.certificate_dir if tls else "")
                    connection_name.set_text("")
                except (EngineError, OSError, ValueError) as error:
                    self.status.set_label(str(error))
            load.connect("clicked", load_endpoint)
            for label, widget in (("Сохранённые подключения", saved), ("", load),
                                  ("Протокол", protocol), ("Хост", host), ("Пользователь SSH", user),
                                  ("Порт", port), ("TLS: ca.pem, cert.pem, key.pem", certificate),
                                  ("Сохранить как", connection_name)):
                form.append(Gtk.Label(label=label, xalign=0))
                form.append(widget)
            prompt.set_extra_child(form)
            prompt.add_response("cancel", "Отмена")
            prompt.add_response("connect", "Подключиться")
            prompt.set_default_response("cancel")
            prompt.set_close_response("cancel")
            def connect(_, choice):
                if choice != "connect" or self.busy:
                    return
                remote = (TLSEngine(host.get_text(), port.get_value_as_int(), certificate.get_text())
                          if protocol.get_selected() == 1 else RemoteEngine(host.get_text(), user.get_text(), port.get_value_as_int()))
                name = connection_name.get_text()
                endpoint_label = (f"TLS · {remote.host}:{remote.port}" if isinstance(remote, TLSEngine)
                                  else f"SSH · {remote.user}@{remote.host}:{remote.port}")
                def connect_worker():
                    rows = remote.inventory()
                    if name:
                        store.save(name, remote)
                    return rows
                self.busy = True
                self.generation += 1
                generation = self.generation
                self.update_actions()
                self.status.set_label("Получение удалённого списка…")
                future = self.pool.submit(connect_worker)
                def complete():
                    if generation != self.generation or not self.window:
                        return GLib.SOURCE_REMOVE
                    self.busy = False
                    self.update_actions()
                    dialog = Adw.Dialog(title=endpoint_label,
                                        content_width=920, content_height=540)
                    layout = Adw.ToolbarView()
                    layout.add_top_bar(Adw.HeaderBar())
                    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                                  margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
                    box.append(Gtk.Label(label="Удалённый Docker · локальный движок не изменён",
                                         wrap=True, xalign=0))
                    view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.CHAR)
                    scroll = Gtk.ScrolledWindow(vexpand=True)
                    scroll.set_child(view)
                    box.append(scroll)
                    layout.set_content(box)
                    dialog.set_child(layout)
                    controls = Gtk.Box(spacing=6)
                    selector = Gtk.DropDown.new_from_strings([])
                    selector.set_hexpand(True)
                    controls.append(selector)
                    box.append(controls)
                    state = {"rows": (), "closed": False}
                    dialog.connect("closed", lambda *_: state.update(closed=True))
                    buttons = []
                    def render(rows):
                        state["rows"] = rows
                        selector.set_model(Gtk.StringList.new([row.name + " · " + row.state for row in rows]))
                        value = "\n\n".join(f"{row.name} · {row.state} · {row.status}\n{row.image} · {row.ports}\n{row.id}" for row in rows)
                        view.get_buffer().set_text(value or "Нет контейнеров.")
                    def perform(action):
                        if self.busy or state["closed"]:
                            return
                        index = selector.get_selected()
                        if action != "refresh" and index >= len(state["rows"]):
                            return
                        row = state["rows"][index] if action != "refresh" else None
                        def execute():
                            if self.busy or state["closed"]:
                                return
                            self.busy = True
                            self.generation += 1
                            current = self.generation
                            self.update_actions()
                            for button in buttons:
                                button.set_sensitive(False)
                            task = self.pool.submit(remote.inventory if row is None else lambda: remote.action(action, row.id))
                            def finished():
                                if current != self.generation or not self.window:
                                    return GLib.SOURCE_REMOVE
                                self.busy = False
                                self.update_actions()
                                if state["closed"]:
                                    return GLib.SOURCE_REMOVE
                                for button in buttons:
                                    button.set_sensitive(True)
                                try:
                                    render(task.result())
                                except (EngineError, OSError, ValueError) as error:
                                    render(())
                                    view.get_buffer().set_text(str(error) + "\nОбновите состояние.")
                                return GLib.SOURCE_REMOVE
                            task.add_done_callback(lambda _: GLib.idle_add(finished))
                        if row is None:
                            execute()
                            return
                        confirm = Adw.AlertDialog(heading="Удалённая операция: " + action,
                            body=f"{endpoint_label}\n{row.name}\n{row.id}")
                        confirm.add_response("cancel", "Отмена")
                        confirm.add_response("yes", "Выполнить")
                        confirm.set_default_response("cancel")
                        confirm.set_close_response("cancel")
                        confirm.connect("response", lambda _, choice: execute() if choice == "yes" else None)
                        confirm.present(dialog)
                    choices = (("refresh", "Обновить"),) if isinstance(remote, TLSEngine) else (("refresh", "Обновить"), ("start", "Старт"), ("stop", "Стоп"), ("restart", "Рестарт"))
                    for action, label in choices:
                        button = Gtk.Button(label=label)
                        button.connect("clicked", lambda _, action=action: perform(action))
                        controls.append(button)
                        buttons.append(button)
                    try:
                        rows = future.result()
                        render(rows)
                        self.status.set_label("Удалённый список получен. Локальный движок не изменён.")
                    except (EngineError, OSError, ValueError) as error:
                        view.get_buffer().set_text(str(error))
                        self.status.set_label("Удалённое подключение не подтверждено.")
                    except Exception:
                        view.get_buffer().set_text("Не удалось получить список.")
                    dialog.present(self.window)
                    return GLib.SOURCE_REMOVE
                future.add_done_callback(lambda _: GLib.idle_add(complete))
            prompt.connect("response", connect)
            prompt.present(self.window)

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
                self.overview.set_label(f"Контейнеров: {len(self.rows)}   ·   Запущено: {running}   ·   Остальные: {len(self.rows) - running}")
                self.status.set_label("Локальный движок · список обновлён")
            except (EngineError, OSError, ValueError) as error:
                self.rows = ()
                self.last_error = True
                self.overview.set_label("Контейнеров: —   ·   Движок недоступен")
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

        def open_terminal(self, *_):
            item = self.selected()
            if self.busy or not item or item.state != "running":
                return
            try:
                gi.require_version("Vte", "3.91")
                from gi.repository import Vte
            except (ImportError, ValueError):
                alert = Adw.AlertDialog(heading="Терминал недоступен", body="Требуется gir1.2-vte-3.91.")
                alert.add_response("close", "Закрыть")
                alert.present(self.window)
                return
            cid, rootful, generation = item.id, self.rootful, self.generation
            prompt = Adw.AlertDialog(heading="Открыть shell контейнера?",
                body=item.name + "\n" + cid + "\nКоманды выполняются внутри контейнера от его настроенного пользователя. Изменения могут быть необратимыми. Доверяйте выбранному контейнеру.")
            prompt.add_response("cancel", "Отмена")
            prompt.add_response("sh", "/bin/sh")
            prompt.add_response("bash", "/bin/bash")
            prompt.set_default_response("cancel")
            prompt.set_close_response("cancel")
            def chosen(_, response):
                if response not in ("sh", "bash") or self.busy or generation != self.generation or rootful != self.rootful:
                    return
                selected = self.selected()
                if not selected or selected.id != cid:
                    return
                self.busy = True
                self.generation += 1
                current = self.generation
                self.update_actions()
                future = self.pool.submit(lambda: Engine(rootful=rootful).terminal_argv(cid, "/bin/" + response))
                def ready():
                    if current != self.generation or not self.window:
                        return GLib.SOURCE_REMOVE
                    self.busy = False
                    self.update_actions()
                    try:
                        argv = future.result()
                    except (EngineError, OSError, ValueError) as error:
                        self.status.set_label(str(error))
                        return GLib.SOURCE_REMOVE
                    except Exception:
                        self.status.set_label("Не удалось подготовить терминал.")
                        return GLib.SOURCE_REMOVE
                    self.present_terminal(Vte, item.name, argv)
                    return GLib.SOURCE_REMOVE
                future.add_done_callback(lambda _: GLib.idle_add(ready))
            prompt.connect("response", chosen)
            prompt.present(self.window)

        def present_terminal(self, Vte, name, argv):
            import os
            import signal
            dialog = Adw.Dialog(title="Терминал · " + name, content_width=940, content_height=620)
            layout = Adw.ToolbarView()
            layout.add_top_bar(Adw.HeaderBar())
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          margin_top=8, margin_bottom=8, margin_start=8, margin_end=8)
            status = Gtk.Label(label="Подключение к контейнеру…", xalign=0, wrap=True)
            box.append(status)
            terminal = Vte.Terminal()
            terminal.set_scrollback_lines(2000)
            terminal.set_allow_hyperlink(False)
            terminal.set_input_enabled(False)
            terminal.set_hexpand(True)
            terminal.set_vexpand(True)
            scroll = Gtk.ScrolledWindow(vexpand=True)
            scroll.set_child(terminal)
            box.append(scroll)
            layout.set_content(box)
            dialog.set_child(layout)
            cancellable = Gio.Cancellable()
            state = {"closed": False, "exited": False, "pidfd": None}
            def release():
                fd = state["pidfd"]
                if fd is not None:
                    os.close(fd)
                    state["pidfd"] = None
            def exited(_, code):
                state["exited"] = True
                release()
                terminal.set_input_enabled(False)
                if not state["closed"]:
                    status.set_label("Сессия завершена · статус " + str(os.waitstatus_to_exitcode(code)))
            def spawned(_terminal, pid, error, *_):
                if state["closed"] or state["exited"]:
                    return
                if error is not None or pid <= 0:
                    status.set_label("Не удалось запустить Docker CLI.")
                    return
                try:
                    state["pidfd"] = os.pidfd_open(pid)
                except OSError:
                    pass
                terminal.set_input_enabled(True)
                terminal.grab_focus()
                status.set_label("Интерактивный shell · exit для завершения")
            def closed(*_):
                state["closed"] = True
                cancellable.cancel()
                fd = state["pidfd"]
                if fd is not None:
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGHUP)
                    except OSError:
                        pass
                release()
                terminal.set_input_enabled(False)
                terminal.set_pty(None)
                terminal.reset(True, True)
            terminal.connect("child-exited", exited)
            dialog.connect("closed", closed)
            dialog.present(self.window)
            spawn_terminal(terminal, argv, cancellable, spawned)

        def open_monitor(self, *_):
            item = self.selected()
            if self.busy or not item or item.state != "running":
                return
            from collections import deque
            from concurrent.futures import ThreadPoolExecutor
            from time import monotonic
            cid, rootful = item.id, self.rootful
            dialog = Adw.Dialog(title="Мониторинг · " + item.name, content_width=940, content_height=650)
            toolbar = Adw.ToolbarView()
            toolbar.add_top_bar(Adw.HeaderBar())
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                          margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
            status = Gtk.Label(label="Ожидание первой выборки…", xalign=0, wrap=True)
            box.append(status)
            history = deque(maxlen=60)
            plot = Gtk.DrawingArea(content_height=180, hexpand=True)
            def draw(_, cr, width, height):
                if width < 20 or height < 20:
                    return
                left, top, w, h = 8, 8, width - 16, height - 16
                cr.set_source_rgba(.5, .5, .5, .4)
                for ratio in (0, .25, .5, .75, 1):
                    cr.move_to(left, top + h * ratio)
                    cr.line_to(left + w, top + h * ratio)
                cr.stroke()
                if len(history) < 2:
                    return
                scale = max(100, *(sample.cpu for _, sample in history))
                for color, getter, maximum in (((.25, .65, 1), lambda s: s.cpu, scale),
                                                ((.95, .55, .25), lambda s: s.memory, 100)):
                    cr.set_source_rgb(*color)
                    cr.set_line_width(2)
                    first, last = history[0][0], history[-1][0]
                    for i, (stamp, sample) in enumerate(history):
                        x = left + w * (stamp - first) / max(.001, last - first)
                        y = top + h * (1 - getter(sample) / maximum)
                        (cr.move_to if i == 0 else cr.line_to)(x, y)
                    cr.stroke()
            plot.set_draw_func(draw)
            box.append(Gtk.Label(label="CPU — синяя линия (масштаб от 100%); RAM — оранжевая (0–100%). Последние 60 выборок.", xalign=0, wrap=True))
            box.append(plot)
            search = Gtk.SearchEntry(placeholder_text="Фильтр строк журнала")
            box.append(search)
            logs = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.CHAR)
            scroll = Gtk.ScrolledWindow(vexpand=True)
            scroll.set_child(logs)
            box.append(scroll)
            controls = Gtk.Box(spacing=8)
            pause = Gtk.ToggleButton(label="Пауза")
            controls.append(pause)
            controls.append(Gtk.Label(label="Обновление каждые 5 секунд после завершения предыдущего запроса", wrap=True))
            box.append(controls)
            toolbar.set_content(box)
            dialog.set_child(toolbar)
            pool = ThreadPoolExecutor(max_workers=1)
            state = {"closed": False, "pending": False, "timer": None, "logs": "", "truncated": False}
            def filter_logs(*_):
                query = search.get_text().casefold()
                lines = state["logs"].splitlines()
                text = "\n".join(line for line in lines if query in line.casefold())
                if state["truncated"]:
                    text += "\n[Достигнут лимит 256 КиБ]"
                logs.get_buffer().set_text(text or "Нет записей.")
            search.connect("search-changed", filter_logs)
            def close(*_):
                if state["closed"]:
                    return
                state["closed"] = True
                if state["timer"] is not None:
                    GLib.source_remove(state["timer"])
                    state["timer"] = None
                state["logs"] = ""
                history.clear()
                logs.get_buffer().set_text("")
                pool.shutdown(wait=False, cancel_futures=True)
            def tick():
                state["timer"] = None
                if state["closed"]:
                    return GLib.SOURCE_REMOVE
                current = self.selected()
                if not self.window or self.rootful != rootful or not current or current.id != cid:
                    close()
                    dialog.close()
                    return GLib.SOURCE_REMOVE
                if pause.get_active():
                    state["timer"] = GLib.timeout_add_seconds(5, tick)
                    return GLib.SOURCE_REMOVE
                state["pending"] = True
                def worker():
                    engine = Engine(rootful=rootful)
                    values = engine.metrics(cid)
                    sample = metric_sample(values)
                    data, truncated = engine.logs(cid)
                    return values, sample, data, truncated
                future = pool.submit(worker)
                def complete():
                    state["pending"] = False
                    if state["closed"]:
                        return GLib.SOURCE_REMOVE
                    try:
                        values, sample, data, truncated = future.result()
                        history.append((monotonic(), sample))
                        state["logs"], state["truncated"] = data, truncated
                        filter_logs()
                        plot.queue_draw()
                        status.set_label("CPU: " + values["CPUPerc"] + " · RAM: " + values["MemUsage"] +
                            " · Сеть: " + values["NetIO"] + " · Диск: " + values["BlockIO"] +
                            " · PID: " + values["PIDs"])
                    except (EngineError, OSError, ValueError) as error:
                        status.set_label(str(error) + " · Мониторинг остановлен.")
                        pause.set_active(True)
                    except Exception:
                        status.set_label("Не удалось получить выборку. Мониторинг остановлен.")
                        pause.set_active(True)
                    state["timer"] = GLib.timeout_add_seconds(5, tick)
                    return GLib.SOURCE_REMOVE
                future.add_done_callback(lambda _: GLib.idle_add(complete))
                return GLib.SOURCE_REMOVE
            dialog.connect("closed", close)
            dialog.present(self.window)
            tick()

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
            for button in self.nav_buttons.values():
                button.set_sensitive(not self.busy)
            self.resource_page.set_sensitive(not self.busy)
            self.engine_button.set_sensitive(not self.busy)
            self.rootless_button.set_sensitive(not self.busy)
            self.stacks_button.set_sensitive(not self.busy)
            for button in self.resource_buttons:
                button.set_sensitive(not self.busy)
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
            self.monitor_button.set_sensitive(not self.busy and running)
            self.terminal_button.set_sensitive(not self.busy and running)
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
            Adw.Application.do_shutdown(self)

    return Workspace()


def main() -> int:
    return create_application().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
