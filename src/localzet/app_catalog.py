"""Curated application actions; never treat a download or launcher as installed."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class App:
    name: str
    group: str
    note: str
    icon: str
    flatpak_id: str | None = None
    native: str | None = None
    website: str | None = None


APPS = {
    "files": App("Файлы", "Система", "Файловый менеджер Aurora", "org.gnome.Nautilus", native="/usr/bin/nautilus"),
    "settings": App("Настройки", "Система", "Дисплеи, звук, сеть и устройства", "org.gnome.Settings", native="/usr/bin/gnome-control-center"),
    "components": App("Компоненты Localzet", "Система", "Системные интеграции и параметры", "com.localzet.Settings", native="/usr/bin/localzet-settings"),
    "hardware": App("Оборудование", "Система", "Драйверы, CUDA и диагностика", "com.localzet.Hardware", native="/usr/bin/localzet-hardware-manager"),
    "network": App("Сеть Localzet", "Система", "Управление VPN и прокси", "com.localzet.Network", native="/usr/bin/localzet-network"),
    "connect": App("Подключение телефона", "Связь и медиа", "Интеграция мобильных устройств", "com.localzet.Connect", native="/usr/bin/localzet-connect"),
    "vlc": App("VLC", "Связь и медиа", "Локальное воспроизведение аудио и видео", "localzet-catalog-vlc", native="/usr/bin/vlc"),
    "qbittorrent": App("qBittorrent", "Связь и медиа", "BitTorrent-клиент", "localzet-catalog-qbittorrent", native="/usr/bin/qbittorrent"),
    "loupe": App("Изображения", "Связь и медиа", "Просмотр фотографий", "org.gnome.Loupe", native="/usr/bin/loupe"),
    "gimp": App("GIMP", "Связь и медиа", "Редактирование изображений", "localzet-catalog-gimp", native="/usr/bin/gimp"),
    "terminal": App("Терминал", "Разработка и браузеры", "Ptyxis — терминал GNOME", "org.gnome.Ptyxis", native="/usr/bin/ptyxis"),
    "containers": App("Localzet Containers", "Разработка и браузеры", "Управление контейнерами, образами и Compose", "com.localzet.Containers", native="/usr/bin/localzet-containers"),
    "virtual-machines": App("Виртуальные машины", "Разработка и браузеры", "QEMU / libvirt", "virt-manager", native="/usr/bin/virt-manager"),
    "browser": App("Веб-браузер", "Разработка и браузеры", "GNOME Web", "org.gnome.Epiphany", native="/usr/bin/epiphany"),
    "windows": App("Windows Runtime", "Игры", "EXE, MSI и профили Wine", "com.localzet.WindowsRuntime", native="/usr/bin/localzet-windows"),
    "papers": App("Документы PDF", "Офис", "Просмотр PDF и других документов", "org.gnome.Papers", native="/usr/bin/papers"),
    "lutris": App("Lutris", "Игры", "Пакет Ubuntu; Wine и игровые библиотеки", "localzet-catalog-lutris", native="/usr/games/lutris"),
    "steam": App("Steam", "Игры", "Flathub: сборка сообщества, не поддерживается Valve; нужен аккаунт", "localzet-catalog-steam", flatpak_id="com.valvesoftware.Steam"),
    "heroic": App("Heroic Games Launcher", "Игры", "GOG / Epic; загрузка игр и Proton через Heroic", "localzet-catalog-heroic", flatpak_id="com.heroicgameslauncher.hgl"),
    "telegram": App("Telegram Desktop", "Связь и медиа", "Flathub; системная или пользовательская установка", "localzet-catalog-telegram", flatpak_id="org.telegram.desktop"),
    "discord": App("Discord", "Связь и медиа", "Flathub; ограничения интеграции с играми", "localzet-catalog-discord", flatpak_id="com.discordapp.Discord"),
    "music": App("Яндекс Музыка", "Связь и медиа", "Официальный Linux-клиент; подписка на сервис", "localzet-catalog-music", website="https://music.yandex.ru/download/"),
    "ai-workspace": App("Localzet AI", "Разработка и браузеры", "Установка проверенных Codex / Claude Code, запуск через локальный прокси", "com.localzet.AIWorkspace", native="/usr/bin/localzet-ai-workspace"),
    "vscode": App("Visual Studio Code", "Разработка и браузеры", "Официальный пакет Microsoft", "localzet-catalog-vscode", native="/usr/bin/code", website="https://code.visualstudio.com/download"),
    "chrome": App("Google Chrome", "Разработка и браузеры", "Официальный пакет Google", "localzet-catalog-chrome", native="/usr/bin/google-chrome-stable", website="https://www.google.com/chrome/"),
    "edge": App("Microsoft Edge", "Разработка и браузеры", "Официальный пакет Microsoft", "localzet-catalog-edge", native="/usr/bin/microsoft-edge-stable", website="https://www.microsoft.com/edge"),
    "office": App("ONLYOFFICE", "Офис", "Нативный редактор документов", "localzet-catalog-office", native="/usr/bin/onlyoffice-desktopeditors", website="https://www.onlyoffice.com/download-desktop"),
    "microsoft365": App("Microsoft 365", "Офис", "Веб-версия; настольная версия требует лицензии и Windows", "com.localzet.Microsoft365Web", website="https://www.microsoft365.com/"),
}
FLATPAK = "/usr/bin/flatpak"
PTYXIS = "/usr/bin/ptyxis"


def executable(path: str) -> bool:
    return Path(path).is_file() and os.access(path, os.X_OK)


def install_command(key: str) -> tuple[str, ...]:
    app = APPS[key]
    if not app.flatpak_id:
        raise ValueError("No curated Flatpak install action")
    # No arbitrary URLs, shell interpolation, root, noninteractive flag, or
    # auto-approval. Flatpak presents remote/permission confirmation itself.
    ref = "https://dl.flathub.org/repo/appstream/" + app.flatpak_id + ".flatpakref"
    return (FLATPAK, "install", "--user", "--from", ref)


def terminal_command(key: str) -> tuple[str, ...]:
    return (PTYXIS, "--new-window", "--title=" + APPS[key].name, "--", *install_command(key))


def flatpak_installed() -> frozenset[str]:
    if not executable(FLATPAK):
        return frozenset()
    result = subprocess.run([FLATPAK, "list", "--app", "--columns=application"],
                            text=True, capture_output=True, check=True, timeout=10)
    return frozenset(result.stdout.splitlines())


def action(key: str, installed: frozenset[str]) -> tuple[str, tuple[str, ...] | str]:
    app = APPS[key]
    if app.native and executable(app.native):
        if key == "office" and executable("/usr/bin/localzet-office"):
            return "launch", ("/usr/bin/localzet-office",)
        return "launch", (app.native,)
    if app.flatpak_id and app.flatpak_id in installed:
        return "launch", (FLATPAK, "run", app.flatpak_id)
    if app.flatpak_id and executable(FLATPAK) and executable(PTYXIS):
        return "install", terminal_command(key)
    if app.website:
        return "website", app.website
    if app.flatpak_id:
        return "website", "https://flathub.org/apps/" + app.flatpak_id
    return "missing", ()



def visible_keys(section: str, query: str, kinds: dict[str, str]) -> tuple[str, ...]:
    """Filter only the curated catalog; installed means a verified launch action."""
    words = query.casefold().split()
    return tuple(
        key for key, app in APPS.items()
        if (section == "all" or section == app.group
            or (section == "installed" and kinds.get(key) == "launch"))
        and all(word in f"{key} {app.name} {app.note}".casefold() for word in words)
    )


def action_source(key: str, kind: str, command: tuple[str, ...] | str) -> str:
    """Show detected delivery mechanism, not guessed installation status."""
    app = APPS[key]
    if kind == "launch":
        return "Flatpak" if isinstance(command, tuple) and command[:1] == (FLATPAK,) else "Локально"
    if kind == "install" or (app.flatpak_id and kind == "website"):
        return "Flathub"
    if kind == "website":
        return "Сайт"
    return "Нет пакета"
