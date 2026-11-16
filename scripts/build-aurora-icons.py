#!/usr/bin/env python3
"""Build the original Aurora icon theme; no external art or theme downloads."""
from pathlib import Path
import argparse
import re

# Consistent 64-unit optical grid. Application tiles use a graphite surface,
# a single restrained accent and a unique pictogram. Places/devices use
# freestanding silhouettes rather than putting every file in a square.
GLYPHS = {
    "browser": ('#9e9ccd', '<circle cx="32" cy="32" r="18"/><path d="M14 32h36M32 14c-9 10-9 26 0 36m0-36c9 10 9 26 0 36"/>'),
    "chrome": ('#9eaf93', '<circle cx="32" cy="32" r="20"/><circle cx="32" cy="32" r="8"/><path d="M14 23h18m4 16 9 15M42 15l-10 17"/>'),
    "edge": ('#85b4cb', '<path d="M49 43c-4 5-10 8-18 8-12 0-20-9-20-19s8-20 20-20c11 0 20 8 20 19H23c0 7 4 11 11 11 5 0 9-2 15-5z"/>'),
    "firefox": ('#d0ad84', '<circle cx="33" cy="33" r="17"/><path d="M17 15c-7 9-8 21-1 30 8 10 26 11 34-1M13 24l10 3 6-9m14-3c7 5 10 10 10 17"/>'),
    "telegram": ('#85b4cb', '<path d="m12 29 41-16-10 39-13-13-8 6 1-13zM23 32l21-12-14 19"/>'),
    "discord": ('#9e9ccd', '<path d="M20 17c-6 5-9 14-10 26l11 6 4-6m19-26c6 5 9 14 10 26l-11 6-4-6M19 21c7-5 19-5 26 0M20 42c7 5 17 5 24 0"/><circle cx="25" cy="32" r="3" fill="currentColor"/><circle cx="39" cy="32" r="3" fill="currentColor"/>'),
    "steam": ('#85b4cb', '<circle cx="42" cy="22" r="12"/><circle cx="42" cy="22" r="6"/><circle cx="24" cy="43" r="7"/><path d="m11 36 13 7 18-21M28 36l5-10"/>'),
    "netbird": ('#8fb7aa', '<path d="M13 22l20 12 17-15-8 25-20 7 7-17M13 22l16 4 21-7"/>'),
    "usernet": ('#b1a1d0', '<circle cx="19" cy="18" r="5"/><circle cx="45" cy="18" r="5"/><circle cx="32" cy="47" r="5"/><path d="M24 18h16M22 23l8 19m12-19-8 19"/>'),
    "files": ('#b1a1d0', '<path d="M12 23v-5a3 3 0 0 1 3-3h13l5 5h16a3 3 0 0 1 3 3v24a3 3 0 0 1-3 3H15a3 3 0 0 1-3-3z"/><path d="M12 28h40"/>'),
    "terminal": ('#8fb7aa', '<rect x="12" y="15" width="40" height="34" rx="4"/><path d="m19 25 8 7-8 7m14 0h12"/>'),
    "settings": ('#b1a1d0', '<path d="M14 20h36M14 32h36M14 44h36"/><circle cx="25" cy="20" r="4" fill="#262831"/><circle cx="39" cy="32" r="4" fill="#262831"/><circle cx="28" cy="44" r="4" fill="#262831"/>'),
    "components": ('#b1a1d0', '<rect x="13" y="13" width="16" height="16" rx="2"/><rect x="35" y="13" width="16" height="16" rx="2"/><rect x="13" y="35" width="16" height="16" rx="2"/><path d="M43 35v16m-8-8h16"/>'),
    "hardware": ('#8fb7aa', '<rect x="19" y="19" width="26" height="26" rx="3"/><rect x="26" y="26" width="12" height="12" rx="1"/><path d="M24 12v7m8-7v7m8-7v7M24 45v7m8-7v7m8-7v7M12 24h7m-7 8h7m-7 8h7m26-16h7m-7 8h7m-7 8h7"/>'),
    "containers": ('#85b4cb', '<path d="m32 11 19 11v21L32 54 13 43V22zM13 22l19 11 19-11M32 33v21M22 17l19 11"/>'),
    "windows": ('#8ba8ce', '<path d="m14 19 16-3v15H14zm21-4 15-3v19H35zm-21 21h16v15l-16-3zm21 0h15v19l-15-3z" fill="currentColor" stroke="none"/>'),
    "connect": ('#8fb7aa', '<rect x="16" y="12" width="23" height="40" rx="4"/><path d="M23 18h9m-6 27h3m17-24 7 7-7 7m-6-7h13"/>'),
    "installer": ('#d0ad84', '<rect x="13" y="35" width="38" height="15" rx="3"/><path d="M32 12v22m-9-9 9 9 9-9M21 42h4m6 0h4"/>'),
    "store": ('#b1a1d0', '<path d="M15 23h34l4 27H11zM24 24v-5a8 8 0 0 1 16 0v5"/><path d="M27 36h10m-5-5v10"/>'),
    "monitor": ('#8fb7aa', '<rect x="12" y="15" width="40" height="34" rx="3"/><path d="M16 35h8l5-12 7 18 5-9h7"/>'),
    "editor": ('#d0ad84', '<path d="M16 12h23l10 10v30H16zM39 12v10h10M23 31h19m-19 8h19m-19 8h12"/>'),
    "calculator": ('#b1a1d0', '<rect x="17" y="12" width="30" height="40" rx="4"/><rect x="23" y="18" width="18" height="8" rx="1"/><path d="M24 34h4m8 0h4m-16 8h4m8 0h4"/>'),
    "image": ('#a9b88d', '<rect x="12" y="14" width="40" height="36" rx="3"/><circle cx="40" cy="24" r="4"/><path d="m13 43 13-15 10 10 6-5 10 10"/>'),
    "camera": ('#a9b88d', '<path d="M12 22h11l4-7h10l4 7h11v26H12z"/><circle cx="32" cy="35" r="10"/>'),
    "document": ('#d0ad84', '<path d="M17 12h21l10 10v30H17zM38 12v10h10M24 31h17m-17 7h17m-17 7h10"/>'),
    "archive": ('#d0ad84', '<rect x="14" y="14" width="36" height="36" rx="4"/><path d="M14 25h36M29 14v16h6v8h-6v12m0-31h6"/>'),
    "disk": ('#a5a9ba', '<rect x="13" y="13" width="38" height="38" rx="5"/><circle cx="32" cy="31" r="12"/><circle cx="32" cy="31" r="3"/><path d="m42 42-10-11"/>'),
    "media": ('#d0ad84', '<rect x="12" y="16" width="40" height="32" rx="4"/><path d="m27 23 15 9-15 9z" fill="currentColor" stroke="none"/>'),
    "music": ('#b1a1d0', '<path d="M26 42V20l22-5v23M26 26l22-5"/><ellipse cx="20" cy="43" rx="6" ry="5"/><ellipse cx="42" cy="39" rx="6" ry="5"/>'),
    "torrent": ('#85b4cb', '<path d="M32 12v30m-10-10 10 10 10-10M13 42v10h38V42"/><path d="M15 21h9m16 0h9"/>'),
    "paint": ('#c694ba', '<path d="M32 13c-12 0-21 8-21 20s9 18 19 18c5 0 6-3 4-6-2-4 2-6 6-5 8 2 14-4 13-11-1-9-10-16-21-16z"/><circle cx="22" cy="27" r="2"/><circle cx="32" cy="21" r="2"/><circle cx="43" cy="26" r="2"/><circle cx="19" cy="38" r="2"/>'),
    "scanner": ('#a5a9ba', '<path d="m16 28 5-12h22l5 12M12 31h40v18H12zM20 40h24"/><path d="M24 22h16"/>'),
    "printer": ('#a5a9ba', '<path d="M20 24V12h24v12M17 44H12V25h40v19h-5M20 36h24v16H20zM42 31h4"/>'),
    "office": ('#c78f85', '<path d="M18 13h28v38H18zM25 22h14m-14 8h14m-14 8h14"/><path d="M14 18v37h27"/>'),
    "chat": ('#85b4cb', '<path d="M13 15h38v29H31L20 52v-8h-7zM21 26h22m-22 8h15"/>'),
    "code": ('#8fb7aa', '<path d="m23 21-12 11 12 11m18-22 12 11-12 11M36 15l-8 34"/>'),
    "vm": ('#a5a9ba', '<rect x="12" y="14" width="40" height="31" rx="3"/><path d="M24 51h16m-8-6v6"/><rect x="20" y="21" width="24" height="17" rx="2"/>'),
    "vpn": ('#8fb7aa', '<path d="m32 11 19 7v15c0 9-9 17-19 21-10-4-19-12-19-21V18zM22 32l7 7 13-14"/>'),
    "games": ('#b1a1d0', '<path d="M21 21h22c8 0 10 8 12 20 1 7-5 9-10 4l-5-6H24l-5 6c-5 5-11 3-10-4 2-12 4-20 12-20zM18 30h12m-6-6v12"/><circle cx="43" cy="28" r="2"/><circle cx="48" cy="34" r="2"/>'),
    "capture": ('#c694ba', '<rect x="13" y="15" width="38" height="34" rx="4"/><circle cx="32" cy="32" r="10"/><circle cx="32" cy="32" r="4" fill="currentColor" stroke="none"/>'),
    "help": ('#a5a9ba', '<circle cx="32" cy="32" r="19"/><path d="M25 25a7 7 0 1 1 10 6c-3 2-3 4-3 6"/><circle cx="32" cy="44" r="1.5" fill="currentColor"/>'),
    "clock": ('#a5a9ba', '<circle cx="32" cy="32" r="20"/><path d="M32 19v14l10 6"/>'),
    "calendar": ('#c78f85', '<rect x="13" y="17" width="38" height="35" rx="3"/><path d="M13 27h38M23 12v10m18-10v10M22 35h5m10 0h5m-20 9h5m10 0h5"/>'),
    "mail": ('#85b4cb', '<rect x="12" y="17" width="40" height="30" rx="3"/><path d="m12 19 20 16 20-16"/>'),
    "network": ('#85b4cb', '<circle cx="32" cy="16" r="6"/><circle cx="16" cy="47" r="6"/><circle cx="48" cy="47" r="6"/><path d="M32 22v10H16v9m16-9h16v9"/>'),
    "trash": ('#a5a9ba', '<path d="M16 20h32l-3 31H19zM12 20h40M25 20v-6h14v6m-12 9v14m10-14v14"/>'),
    "home": ('#b1a1d0', '<path d="m12 30 20-17 20 17v20H39V36H25v14H12z"/>'),
    "download": ('#85b4cb', '<path d="M32 12v29m-10-10 10 10 10-10M13 43v8h38v-8"/>'),
    "desktop": ('#a5a9ba', '<rect x="11" y="14" width="42" height="33" rx="3"/><path d="M32 47v6m-12 0h24"/>'),
    "usb": ('#8fb7aa', '<rect x="23" y="11" width="18" height="14" rx="2"/><rect x="18" y="25" width="28" height="29" rx="5"/><path d="M29 15v5m6-5v5M26 36h12"/>'),
    "optical": ('#a5a9ba', '<circle cx="32" cy="32" r="23"/><circle cx="32" cy="32" r="6"/><path d="m16 16 9 9m14 14 9 9"/>'),
    "audio": ('#b1a1d0', '<path d="M13 27h10l13-11v32L23 37H13zM43 23c7 5 7 13 0 18m6-24c11 8 11 22 0 30"/>'),
    "bluetooth": ('#85b4cb', '<path d="M30 10v44l16-14L18 18m0 28 28-24-16-12"/>'),
    "wifi": ('#85b4cb', '<path d="M10 23a35 35 0 0 1 44 0M17 32a24 24 0 0 1 30 0M25 41a12 12 0 0 1 14 0"/><circle cx="32" cy="50" r="2" fill="currentColor"/>'),
    "battery": ('#8fb7aa', '<rect x="12" y="21" width="38" height="22" rx="3"/><path d="M50 28h5v8h-5M20 28h21v8H20z" fill="currentColor"/>'),
    "lock": ('#d0ad84', '<rect x="16" y="28" width="32" height="24" rx="3"/><path d="M22 28V20a10 10 0 0 1 20 0v8m-10 10v6"/>'),
}

# Each alias is an actual freedesktop icon name or application ID, not a
# replacement desktop launcher. Absolute-path upstream icons remain intact.
GROUPS = {
    "apps": {
        "browser": "org.gnome.Epiphany web-browser epiphany",
        "chrome": "google-chrome google-chrome-stable",
        "edge": "microsoft-edge microsoft-edge-stable",
        "firefox": "firefox org.mozilla.firefox",
        "files": "org.gnome.Nautilus system-file-manager nautilus",
        "terminal": "org.gnome.Ptyxis org.gnome.Terminal utilities-terminal ptyxis",
        "settings": "org.gnome.Settings preferences-system gnome-control-center language-selector",
        "components": "com.localzet.Settings localzet-components",
        "hardware": "com.localzet.Hardware localzet-hardware",
        "containers": "com.localzet.Containers localzet-containers docker",
        "windows": "com.localzet.WindowsRuntime localzet-windows wine",
        "connect": "com.localzet.Connect localzet-connect nectarlink nectarlink-desktop",
        "installer": "com.localzet.Installer localzet-installer",
        "store": "org.gnome.Software system-software-install gnome-software",
        "monitor": "org.gnome.SystemMonitor utilities-system-monitor htop",
        "editor": "org.gnome.TextEditor org.gnome.gedit accessories-text-editor",
        "calculator": "org.gnome.Calculator accessories-calculator",
        "image": "org.gnome.Loupe org.gnome.eog org.gnome.Shotwell image-viewer display-im7.q16 imagemagick",
        "camera": "org.gnome.Snapshot camera-photo",
        "document": "org.gnome.Papers org.gnome.Evince document-viewer",
        "archive": "org.gnome.FileRoller file-roller utilities-archive-manager",
        "disk": "org.gnome.DiskUtility org.gnome.GParted gparted",
        "media": "vlc org.videolan.VLC org.gnome.Totem multimedia-video-player",
        "music": "yandex-music org.gnome.Music multimedia-audio-player",
        "torrent": "qbittorrent org.qbittorrent.qBittorrent",
        "paint": "gimp gimp-3.0 org.gimp.GIMP",
        "scanner": "org.gnome.SimpleScan simple-scan",
        "printer": "system-config-printer",
        "office": "onlyoffice-desktopeditors desktopeditors ONLYOFFICE",
        "telegram": "org.telegram.desktop telegram telegram-desktop",
        "discord": "discord com.discordapp.Discord",
        "code": "code visual-studio-code com.visualstudio.code gvim vim CMakeSetup",
        "vm": "virt-manager org.virt_manager.virt-manager",
        "netbird": "netbird netbird-ui org.wails.netbird",
        "network": "com.localzet.Network localzet-network",
        "usernet": "usernet localzet-usernet com.localzet.usernet",
        "steam": "steam com.valvesoftware.Steam",
        "games": "lutris net.lutris.Lutris",
        "capture": "com.obsproject.Studio obs obs-studio",
        "help": "org.gnome.Yelp help-browser dialog-information",
        "clock": "org.gnome.clocks",
        "calendar": "org.gnome.Calendar",
        "mail": "org.gnome.Evolution thunderbird",
    },
    "places": {
        "files": "folder folder-open folder-documents folder-publicshare folder-templates",
        "home": "user-home folder-home",
        "download": "folder-download",
        "image": "folder-pictures",
        "music": "folder-music",
        "media": "folder-videos",
        "desktop": "user-desktop folder-desktop",
        "network": "network-workgroup folder-remote",
        "trash": "user-trash user-trash-full",
    },
    "devices": {
        "disk": "drive-harddisk drive-harddisk-solidstate drive-harddisk-system drive-harddisk-usb",
        "usb": "drive-removable-media media-flash media-flash-usb",
        "optical": "drive-optical media-optical media-optical-dvd",
        "desktop": "computer video-display",
        "connect": "phone multimedia-player",
        "printer": "printer",
        "scanner": "scanner",
        "audio": "audio-card audio-speakers audio-headphones",
    },
    "categories": {
        "components": "applications-other applications-utilities",
        "settings": "applications-system preferences-desktop",
        "code": "applications-development",
        "games": "applications-games",
        "image": "applications-graphics",
        "network": "applications-internet",
        "media": "applications-multimedia",
        "office": "applications-office",
        "help": "applications-education",
    },
    "mimetypes": {
        "document": "text-x-generic text-plain application-pdf x-office-document",
        "office": "x-office-spreadsheet x-office-presentation",
        "archive": "package-x-generic application-zip application-x-tar",
        "windows": "application-x-ms-dos-executable application-x-msi",
        "image": "image-x-generic",
        "music": "audio-x-generic",
        "media": "video-x-generic",
        "code": "text-x-script application-x-executable",
    },
    "status": {
        "wifi": "network-wireless",
        "bluetooth": "bluetooth-active",
        "battery": "battery",
        "lock": "security-high",
        "audio": "audio-volume-high",
    },
}
CONTEXTS = {"apps": "Applications", "places": "Places", "devices": "Devices",
            "categories": "Categories", "mimetypes": "MimeTypes", "status": "Status"}


def render(kind, group, name):
    tile = group == "apps"
    accent, glyph = GLYPHS[kind]
    background = ('<rect x="3" y="3" width="58" height="58" rx="11" fill="#262831" '
                  'stroke="#434653" stroke-width="1.5"/>') if tile else ''
    if group == "places" and name.startswith("folder") and kind != "files":
        # Keep the folder silhouette recognizable in file managers.
        background = ('<path d="M5 19a4 4 0 0 1 4-4h19l6 6h21a4 4 0 0 1 4 4v29H5z" '
                      'fill="#30313d" stroke="' + accent + '" stroke-width="2.5"/>')
        glyph = '<g transform="translate(19 17) scale(.45)">' + glyph + '</g>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
            f'<title>Aurora {kind}</title>{background}'
            f'<g color="{accent}" stroke="{accent}" fill="none" stroke-width="3" '
            f'stroke-linecap="round" stroke-linejoin="round">{glyph}</g></svg>\n')


def build(destination):
    theme = Path(destination) / "Aurora"
    theme.mkdir(parents=True, exist_ok=False)
    directories = [f"scalable/{group}" for group in GROUPS]
    lines = ["[Icon Theme]", "Name=Aurora", "Comment=Original Localzet OS icon theme",
             "Inherits=Adwaita,hicolor", "Directories=" + ",".join(directories), ""]
    count = 0
    seen = set()
    for group, kinds in GROUPS.items():
        directory = theme / "scalable" / group
        directory.mkdir(parents=True)
        lines += [f"[scalable/{group}]", "Size=64", "MinSize=16", "MaxSize=512",
                  "Type=Scalable", "Context=" + CONTEXTS[group], ""]
        for kind, names in kinds.items():
            for name in names.split():
                if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in seen:
                    raise ValueError("Duplicate or invalid icon name: " + name)
                seen.add(name)
                (directory / (name + ".svg")).write_text(render(kind, group, name), encoding="utf-8")
                count += 1
    (theme / "index.theme").write_text("\n".join(lines), encoding="utf-8")
    print(f"Aurora: {count} icon names, {len(GLYPHS)} original glyphs")
    return theme


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    build(parser.parse_args().destination)
