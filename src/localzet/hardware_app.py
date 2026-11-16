"""Native Hardware Manager. Reads diagnostics and runs an unprivileged CUDA probe."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import platform
import sys

from localzet.hardware import inventory, plan, secure_boot, resolve_local
from localzet.hardware_status import read_status

LABELS = {
    "base-installing": ("Настройка оборудования", "Устанавливаются firmware, микрокод и графические библиотеки."),
    "base-ready": ("Базовое оборудование настроено", "Проверяется необходимость настройки NVIDIA."),
    "base-awaiting-reboot": ("Требуется перезагрузка", "Сохраните работу: обновлены базовые драйверы или firmware."),
    "base-complete": ("Базовая настройка завершена", "Пакеты установлены; работоспособность устройств требует проверки."),
    "no-record": ("Автоматическая настройка не запущена", "Проверьте оборудование и рекомендации."),
    "unavailable": ("Статус недоступен", "Не удалось прочитать состояние настройки."),
    "not-applicable": ("NVIDIA не обнаружена", "Автоматическая настройка NVIDIA/CUDA не требуется."),
    "refreshing": ("Обновление списка пакетов", "Проверяются репозитории Ubuntu."),
    "driver-installing": ("Установка драйвера", "Не выключайте компьютер. Операция выполняется системной службой."),
    "awaiting-reboot": ("Требуется перезагрузка", "Сохраните работу и перезагрузитесь через системное меню."),
    "cuda-installing": ("Установка CUDA", "Загружаются и устанавливаются совместимые пакеты."),
    "compute-verification-required": ("CUDA: требуется проверка", "Запустите проверку вычислений от обычного пользователя."),
    "offline": ("Репозитории недоступны", "Проверьте сеть. Настройка повторится после следующей загрузки."),
    "blocked": ("Настройка остановлена", "Изменилось оборудование или не подтверждена совместимость."),
    "recovery-required": ("Требуется восстановление", "Не повторяйте установку без проверки журнала администратором."),
}
VENDORS = {"10de": "NVIDIA", "1002": "AMD", "8086": "Intel"}


def diagnostics():
    devices = inventory()
    report = resolve_local(devices)
    runtime = []
    runtime_error = None
    if report["nvidia_gpu_detected"]:
        from localzet.hardware_cuda import running_gpus
        try:
            runtime = running_gpus(devices)
        except ValueError as error:
            runtime_error = str(error)
    return report, runtime, runtime_error


def create_application():
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gio, GLib, Gtk

    class HardwareApp(Adw.Application):
        def __init__(self):
            super().__init__(application_id="com.localzet.Hardware")
            self.pool = ThreadPoolExecutor(max_workers=1)
            self.window = None
            self.busy = False
            self.generation = 0
            self.last_state = None

        def do_activate(self):
            from localzet.appearance import apply_midnight
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title="Localzet Hardware")
            self.appearance = apply_midnight(self.window)
            self.window.set_default_size(780, 640)
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Обновить диагностику")
            self.refresh_button.connect("clicked", lambda *_: self.refresh())
            header.pack_end(self.refresh_button)
            toolbar.add_top_bar(header)
            self.page = Adw.PreferencesPage()
            self.status_group = Adw.PreferencesGroup(title="Настройка оборудования")
            self.status_row = Adw.ActionRow(title="Получение состояния…")
            self.status_row.set_use_markup(False)
            self.status_group.add(self.status_row)
            self.page.add(self.status_group)
            self.graphics_group = Adw.PreferencesGroup(title="Графические устройства")
            self.page.add(self.graphics_group)
            self.system_group = Adw.PreferencesGroup(title="Драйверы и ядро")
            self.page.add(self.system_group)
            self.cuda_group = Adw.PreferencesGroup(title="CUDA", description="Проверка компилятора и вычислений на GPU. Без административных прав.")
            self.verify_button = Gtk.Button(label="Проверить вычисления CUDA", halign=Gtk.Align.START)
            self.verify_button.connect("clicked", lambda *_: self.verify_cuda())
            self.verify_button.set_sensitive(False)
            self.cuda_group.add(self.verify_button)
            self.result_row = Adw.ActionRow(title="Результат", subtitle="Проверка не выполнялась")
            self.result_row.set_use_markup(False)
            self.cuda_group.add(self.result_row)
            self.page.add(self.cuda_group)
            self.help_group = Adw.PreferencesGroup(title="Восстановление", description="При сбое не запускайте повторную установку вслепую.")
            self.help_group.add(self.row("Журнал для администратора", "journalctl -u localzet-hardware-firstboot.service"))
            self.page.add(self.help_group)
            toolbar.set_content(self.page)
            self.window.set_content(toolbar)
            self.window.present()
            self.rows = []
            self.nvidia = False
            self.refresh()
            self.timer = GLib.timeout_add_seconds(3, self.poll_status)

        @staticmethod
        def row(title, subtitle):
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            row.set_use_markup(False)
            return row

        def poll_status(self):
            state = read_status()["state"]
            title, detail = LABELS[state]
            self.status_row.set_title(title)
            self.status_row.set_subtitle(detail)
            if self.last_state is not None and state != self.last_state and not self.busy:
                self.refresh()
            self.last_state = state
            return GLib.SOURCE_CONTINUE

        def submit(self, work, callback):
            if self.busy:
                return
            self.busy = True
            self.generation += 1
            generation = self.generation
            self.refresh_button.set_sensitive(False)
            self.verify_button.set_sensitive(False)
            future = self.pool.submit(work)
            def finished():
                if self.window is None or generation != self.generation:
                    return GLib.SOURCE_REMOVE
                self.busy = False
                self.refresh_button.set_sensitive(True)
                self.verify_button.set_sensitive(self.nvidia)
                callback(future)
                return GLib.SOURCE_REMOVE
            future.add_done_callback(lambda _: GLib.idle_add(finished))

        def refresh(self):
            self.submit(diagnostics, self.render_diagnostics)

        def render_diagnostics(self, future):
            for group, row in self.rows:
                group.remove(row)
            self.rows.clear()
            def add(group, title, detail):
                row = self.row(title, detail)
                group.add(row)
                self.rows.append((group, row))
            try:
                report, runtime, error = future.result()
                self.nvidia = report["nvidia_gpu_detected"]
                for gpu in report["graphics"]:
                    add(self.graphics_group, VENDORS.get(gpu["vendor"], gpu["vendor"]) + " · " + gpu["device"],
                        gpu["address"] + " · " + (gpu["driver"] or "Драйвер не привязан"))
                if not report["graphics"]:
                    add(self.graphics_group, "Графические устройства не обнаружены", "PCI")
                add(self.system_group, "Ядро Linux", report["kernel"])
                add(self.system_group, "Secure Boot", report["secure_boot"])
                recommended = report["recommendations"]
                add(self.system_group, "Рекомендации Ubuntu",
                    ", ".join(" ".join(row) for row in recommended["packages"]) or
                    ("Нет рекомендаций" if recommended["status"] == "observed" else "Недоступны"))
                if self.nvidia:
                    for gpu in runtime:
                        add(self.cuda_group, gpu.address, "Compute " + gpu.capability + " · NVIDIA " + gpu.driver_version)
                    if error:
                        add(self.cuda_group, "Runtime не подтверждён", error)
                else:
                    add(self.cuda_group, "NVIDIA GPU не обнаружена", "CUDA не требуется")
            except Exception as error:
                self.nvidia = False
                add(self.system_group, "Диагностика недоступна", str(error))
            self.verify_button.set_sensitive(self.nvidia)

        def verify_cuda(self):
            if self.busy or not self.nvidia:
                return
            from localzet.hardware_compute import verify
            self.result_row.set_subtitle("Компиляция и выполнение тестового ядра…")
            def completed(future):
                try:
                    result = future.result()
                    self.result_row.set_subtitle("Проверено: CUDA " + result["toolkit"] +
                        " · GPU: " + str(len(result["devices"])) + " · результат 42")
                except Exception as error:
                    self.result_row.set_subtitle("Проверка не пройдена: " + str(error))
            self.submit(verify, completed)

        def do_shutdown(self):
            self.generation += 1
            if hasattr(self, "timer"):
                GLib.source_remove(self.timer)
            self.window = None
            self.pool.shutdown(wait=False, cancel_futures=True)
            super().do_shutdown()

    return HardwareApp()


def main():
    return create_application().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
