"""Project launcher for the guarded official clients."""
from pathlib import Path
import os
import subprocess
import sys

from localzet.ai_network import client_path, usernet_port

PTYXIS = "/usr/bin/ptyxis"


def project_path(path):
    home = Path.home().resolve()
    project = Path(path).resolve(strict=True)
    if not project.is_dir() or not (project.is_relative_to(home) or project.is_relative_to("/workspace")):
        raise ValueError("Выберите каталог проекта в домашней папке или /workspace")
    return project


def terminal_argv(tool, install=False):
    if tool not in ("codex", "claude"):
        raise ValueError("Unknown client")
    return (PTYXIS, "--new-window", "--title=Localzet AI · " + tool, "--",
            "/usr/bin/localzet-ai-install" if install else "/usr/bin/localzet-ai", tool)


def main():
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw, Gio
    from localzet.appearance import apply_midnight

    class Workspace(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.AIWorkspace")
            self.window = None
            self.project = Path.home()

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet AI")
            self.window.set_default_size(740, 520)
            self.appearance = apply_midnight(self.window)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            refresh = Gtk.Button(icon_name="view-refresh-symbolic")
            refresh.connect("clicked", lambda *_: self.refresh())
            header.pack_end(refresh)
            toolbar.add_top_bar(header)
            self.window.set_content(toolbar)
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                           margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
            scroll = Gtk.ScrolledWindow()
            scroll.set_child(page)
            toolbar.set_content(scroll)
            heading = Gtk.Label(label="AI Development", xalign=0)
            heading.add_css_class("title-1")
            page.append(heading)
            notice = Gtk.Label(label="Официальные клиенты. Установите нужный CLI, выберите проект и запустите через локальный прокси UserNet. Требуется собственная учётная запись. Проверка владения прокси и реального маршрута ещё не завершена.", wrap=True, xalign=0)
            notice.add_css_class("dim-label")
            page.append(notice)
            group = Adw.PreferencesGroup(title="Рабочая папка")
            self.project_row = Adw.ActionRow(title="Проект", subtitle=str(self.project))
            self.project_row.set_use_markup(False)
            choose = Gtk.Button(label="Выбрать", valign=Gtk.Align.CENTER)
            choose.connect("clicked", self.choose)
            self.project_row.add_suffix(choose)
            group.add(self.project_row)
            page.append(group)
            clients = Adw.PreferencesGroup(title="Клиенты")
            self.buttons = {}
            for tool, name in (("codex", "OpenAI Codex"), ("claude", "Claude Code")):
                row = Adw.ActionRow(title=name)
                install = Gtk.Button(label="Установить", valign=Gtk.Align.CENTER)
                launch = Gtk.Button(label="Запустить", valign=Gtk.Align.CENTER)
                install.connect("clicked", lambda _, t=tool: self.run(t, True))
                launch.connect("clicked", lambda _, t=tool: self.run(t, False))
                row.add_suffix(install)
                row.add_suffix(launch)
                clients.add(row)
                self.buttons[tool] = (row, install, launch)
            page.append(clients)
            self.status = Gtk.Label(wrap=True, xalign=0, selectable=True)
            page.append(self.status)
            self.refresh()
            self.window.present()

        def choose(self, *_):
            dialog = Gtk.FileDialog(title="Выберите папку проекта")
            dialog.select_folder(self.window, None, self.chosen)

        def chosen(self, dialog, result):
            try:
                self.project = project_path(dialog.select_folder_finish(result).get_path())
                self.project_row.set_subtitle(str(self.project))
                self.refresh()
            except Exception as error:
                self.status.set_label(str(error))

        def refresh(self):
            try:
                port = usernet_port()
                status = f"Локальный HTTP-прокси: 127.0.0.1:{port}. Маршрут не аттестован."
                ready = os.geteuid() != 0 and Path(PTYXIS).is_file()
            except Exception as error:
                status = str(error)
                ready = False
            for tool, (row, install, launch) in self.buttons.items():
                path = Path(client_path(tool))
                exists = path.is_file() and os.access(path, os.X_OK)
                row.set_subtitle("CLI обнаружен" if exists else "CLI не установлен")
                install.set_sensitive(ready)
                launch.set_sensitive(ready and exists)
            self.status.set_label(status)

        def run(self, tool, install):
            try:
                if os.geteuid() == 0:
                    raise ValueError("Запуск от root запрещён")
                usernet_port()
                project = project_path(self.project)
                subprocess.Popen(terminal_argv(tool, install), cwd=project, start_new_session=True)
                self.status.set_label("Подтвердите операцию в терминале. Затем обновите состояние.")
            except (OSError, ValueError, RuntimeError) as error:
                self.status.set_label(str(error))

    return Workspace().run([sys.argv[0]])
