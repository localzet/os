#!/usr/bin/env python3
"""Generate the semantic, first-party parts of the Localzet icon theme."""
from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "theme/icons/Localzet/scalable"

SYMBOLS = {
    "add": '<path d="M12 4v16M4 12h16"/>',
    "archive": '<path d="M4 5h16v4H4zM6 9v10h12V9M10 13h4"/>',
    "audio": '<path d="M4 10v4h4l5 4V6l-5 4zM17 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12"/>',
    "volume-muted": '<path d="M4 10v4h4l5 4V6l-5 4zM17 9l5 6m0-6-5 6"/>',
    "volume-low": '<path d="M4 10v4h4l5 4V6l-5 4zM17 10a3 3 0 0 1 0 4"/>',
    "volume-medium": '<path d="M4 10v4h4l5 4V6l-5 4zM17 9a4 4 0 0 1 0 6M19 7a7 7 0 0 1 0 10"/>',
    "volume-high": '<path d="M4 10v4h4l5 4V6l-5 4zM17 8a6 6 0 0 1 0 8m2-11a10 10 0 0 1 0 14"/>',
    "battery": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4M6 10h7v4H6z"/>',
    "battery-100": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4M5.5 9.5h11v5h-11z"/>',
    "battery-80": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4M5.5 9.5h8.5v5H5.5z"/>',
    "battery-60": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4M5.5 9.5h6v5h-6z"/>',
    "battery-40": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4M5.5 9.5h4v5h-4z"/>',
    "battery-20": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4M5.5 9.5h2v5h-2z"/>',
    "battery-10": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4M5.5 9.5h1v5h-1z"/>',
    "battery-empty": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4"/>',
    "battery-charging": '<rect x="3" y="7" width="16" height="10" rx="2"/><path d="M21 10v4M6 9.5h7v5H6zm5-6-2 4h3l-2 4"/>',
    "bluetooth": '<path d="M12 2v20l7-6-12-9m0 10 12-9-7-6"/>',
    "bluetooth-off": '<path d="M12 2v20l7-6-12-9m0 10 12-9-7-6M4 4l16 16"/>',
    "box": '<path d="m12 3 9 5v8l-9 5-9-5V8zM3 8l9 5 9-5M12 13v8"/>',
    "camera": '<path d="M4 8h4l2-3h4l2 3h4v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
    "close": '<path d="M5 5l14 14M19 5 5 19"/>',
    "code": '<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-2-12-3 14"/>',
    "copy": '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h2"/>',
    "cut": '<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="m8 8 12 12M8 16 20 4"/>',
    "document": '<path d="M6 3h8l4 4v14H6zM14 3v5h5M9 13h6M9 17h6"/>',
    "controller": '<path d="M7 9h10c2 0 3.5 1.2 4.2 3.5l1.1 4.1c.6 2.3-1.6 3.5-3.3 2l-3-2.4H8l-3 2.4c-1.7 1.5-3.9.3-3.3-2l1.1-4.1C3.5 10.2 5 9 7 9Z"/><path d="M7 12v4m-2-2h4m6-2h.01m3 3h.01"/>',
    "disk": '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "down": '<path d="M12 4v15m-6-6 6 6 6-6"/>',
    "file-new": '<path d="M6 3h8l4 4v8M14 3v5h5M6 3v18h8m1-4h8m-4-4v8"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "apps": (
        '<circle cx="5" cy="5" r="1.35"/><circle cx="12" cy="5" r="1.35"/>'
        '<circle cx="19" cy="5" r="1.35"/><circle cx="5" cy="12" r="1.35"/>'
        '<circle cx="12" cy="12" r="1.35"/><circle cx="19" cy="12" r="1.35"/>'
        '<circle cx="5" cy="19" r="1.35"/><circle cx="12" cy="19" r="1.35"/>'
        '<circle cx="19" cy="19" r="1.35"/>'
    ),
    "grid": '<rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/>',
    "headphones": '<path d="M4 13v-2a8 8 0 0 1 16 0v2M4 13h3v6H5a2 2 0 0 1-2-2v-2a2 2 0 0 1 1-2zm16 0h-3v6h2a2 2 0 0 0 2-2v-2a2 2 0 0 0-1-2z"/>',
    "home": '<path d="m3 11 9-8 9 8M5 10v10h14V10M9 20v-6h6v6"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9" r="1.5"/><path d="m4 18 5-5 3 3 3-4 5 6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/>',
    "keyboard": '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M6 9h.01M9 9h.01M12 9h.01M15 9h.01M18 9h.01M6 12h.01M9 12h.01M12 12h.01M15 12h.01M18 12h.01M8 15h8"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v3"/>',
    "maximize": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 4v4H4m11 0h5m-5 0V4M9 20v-5H4m11 0h5m-5 0v5"/>',
    "minimize": '<path d="M4 18h16"/>',
    "mouse": '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 3v6m-6 1h12"/>',
    "network": '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="m7 7 4 9m6-9-4 9M7 6h10"/>',
    "next": '<path d="m9 5 7 7-7 7"/>',
    "paste": '<rect x="5" y="5" width="14" height="16" rx="2"/><path d="M9 5V3h6v2M9 12h6m-6 4h6"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M10 5h4m-3 13h2"/>',
    "power": '<path d="M12 3v9m-5.5-6a8 8 0 1 0 11 0"/>',
    "previous": '<path d="m15 5-7 7 7 7"/>',
    "printer": '<path d="M6 8V3h12v5M6 17H4V9h16v8h-2M6 14h12v7H6zM17 11h.01"/>',
    "refresh": '<path d="M20 7v5h-5M4 17v-5h5m-4-2a7 7 0 0 1 12-4l3 3M4 14l3 3a7 7 0 0 0 12-4"/>',
    "redo": '<path d="M20 11a7 7 0 0 0-12-4L5 10m0-5v5h5m-6 3a7 7 0 0 0 12 4l3-3m0 5v-5h-5"/>',
    "remove": '<path d="M4 12h16"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    "settings": '<path d="m10 3 4 0 1 3 2 1 3-1 2 4-2 2v2l2 2-2 4-3-1-2 1-1 3h-4l-1-3-2-1-3 1-2-4 2-2v-2l-2-2 2-4 3 1 2-1z"/><circle cx="12" cy="12" r="3"/>',
    "shield": '<path d="M12 3 20 6v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6zM9 12l2 2 4-4"/>',
    "shield-warning": '<path d="M12 3 20 6v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6zM12 8v5m0 3h.01"/>',
    "spreadsheet": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M4 8h16M4 13h16M10 8v13M15 8v13"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3m6 0h4"/>',
    "undo": '<path d="M4 11a7 7 0 0 1 12-4l3 3m0-5v5h-5m6 3a7 7 0 0 1-12 4l-3-3m0 5v-5h5"/>',
    "up": '<path d="M12 20V5m6 6-6-6-6 6"/>',
    "video": '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3z"/>',
    "wifi": '<path d="M2.5 8a14 14 0 0 1 19 0M5.5 11.5a9 9 0 0 1 13 0M8.5 15a4.5 4.5 0 0 1 7 0"/><circle cx="12" cy="19" r="1" fill="#eff6ff" stroke="none"/>',
    "wifi-good": '<path d="M2.5 8a14 14 0 0 1 19 0M5.5 11.5a9 9 0 0 1 13 0"/><circle cx="12" cy="19" r="1" fill="#eff6ff" stroke="none"/>',
    "wifi-ok": '<path d="M5.5 11.5a9 9 0 0 1 13 0"/><circle cx="12" cy="19" r="1" fill="#eff6ff" stroke="none"/>',
    "wifi-weak": '<circle cx="12" cy="19" r="1" fill="#eff6ff" stroke="none"/>',
    "wifi-none": '<path d="M4 10a13 13 0 0 1 16 0M5 5l14 14"/><circle cx="12" cy="19" r="1" fill="#eff6ff" stroke="none"/>',
    "wired": '<rect x="5" y="3" width="14" height="10" rx="2"/><path d="M8 8h2m2 0h2m2 0h.01M12 13v6m-4 0h8"/>',
    "offline": '<path d="M3 9a14 14 0 0 1 18 0M7 13a8 8 0 0 1 10 0M10 17a3 3 0 0 1 4 0M4 4l16 16"/>',
    "user-available": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 13-6m1 3 2 2 3-4"/>',
    "user-busy": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 13-6m1 3h4"/>',
    "window": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18m-14-2h.01m3 0h.01"/>',
}

SYMBOLIC = {
    "actions": {
        "document-new-symbolic": "file-new", "document-open-symbolic": "folder",
        "document-save-symbolic": "document", "edit-copy-symbolic": "copy",
        "edit-cut-symbolic": "cut", "edit-paste-symbolic": "paste",
        "edit-delete-symbolic": "remove", "edit-undo-symbolic": "undo",
        "edit-redo-symbolic": "redo", "go-home-symbolic": "home",
        "go-up-symbolic": "up", "go-down-symbolic": "down",
        "go-previous-symbolic": "previous", "go-next-symbolic": "next",
        "list-add-symbolic": "add", "list-remove-symbolic": "remove",
        "view-refresh-symbolic": "refresh", "view-grid-symbolic": "grid",
        "view-app-grid-symbolic": "apps", "system-search-symbolic": "search",
        "preferences-system-symbolic": "settings", "applications-system-symbolic": "settings",
        "help-about-symbolic": "info", "window-close-symbolic": "close",
        "window-maximize-symbolic": "maximize", "window-minimize-symbolic": "minimize",
    },
    "status": {
        "network-wireless-symbolic": "wifi", "network-wireless-signal-excellent-symbolic": "wifi",
        "network-wireless-signal-good-symbolic": "wifi-good", "network-wireless-signal-ok-symbolic": "wifi-ok",
        "network-wireless-signal-weak-symbolic": "wifi-weak", "network-wireless-signal-none-symbolic": "wifi-none",
        "network-wired-symbolic": "wired", "network-offline-symbolic": "offline",
        "audio-volume-muted-symbolic": "volume-muted", "audio-volume-low-symbolic": "volume-low",
        "audio-volume-medium-symbolic": "volume-medium", "audio-volume-high-symbolic": "volume-high",
        "audio-volume-overamplified-symbolic": "volume-high", "bluetooth-active-symbolic": "bluetooth",
        "bluetooth-disabled-symbolic": "bluetooth-off", "battery-symbolic": "battery",
        "battery-level-100-symbolic": "battery-100", "battery-level-80-symbolic": "battery-80",
        "battery-level-60-symbolic": "battery-60", "battery-level-40-symbolic": "battery-40",
        "battery-level-20-symbolic": "battery-20", "battery-level-10-symbolic": "battery-10",
        "battery-level-0-symbolic": "battery-empty", "battery-level-100-charged-symbolic": "battery-100",
        "battery-level-100-charging-symbolic": "battery-charging", "power-profile-balanced-symbolic": "power",
        "power-profile-performance-symbolic": "power", "power-profile-power-saver-symbolic": "power",
        "system-lock-screen-symbolic": "lock", "system-shutdown-symbolic": "power",
        "security-high-symbolic": "shield", "security-medium-symbolic": "shield-warning",
        "user-available-symbolic": "user-available", "user-busy-symbolic": "user-busy",
    },
}

COLORFUL = {
    "categories": {
        "applications-accessories": ("terminal", "#405879", "#80b8ed"),
        "applications-development": ("code", "#244d7a", "#73b6ff"),
        "applications-education": ("document", "#3f5575", "#a4d5ff"),
        "applications-games": ("controller", "#473368", "#d1a5ff"),
        "applications-graphics": ("image", "#3b5474", "#9bd8ff"),
        "applications-internet": ("network", "#245e77", "#8fe8e7"),
        "applications-multimedia": ("audio", "#533a75", "#dab4ff"),
        "applications-office": ("spreadsheet", "#355b75", "#9dd5ff"),
        "applications-science": ("network", "#354b73", "#b6c4ff"),
        "applications-system": ("settings", "#485772", "#d1e2ff"),
        "applications-utilities": ("window", "#42556d", "#c5d7f3"),
    },
    "devices": {
        "audio-headphones": ("headphones", "#365d78", "#b6e8ff"),
        "audio-speakers": ("audio", "#365d78", "#b6e8ff"),
        "camera-photo": ("camera", "#405478", "#cad8ff"),
        "computer": ("window", "#42556d", "#c5d7f3"),
        "drive-harddisk": ("disk", "#43536b", "#c7d7ed"),
        "input-keyboard": ("keyboard", "#43536b", "#c7d7ed"),
        "input-mouse": ("mouse", "#43536b", "#c7d7ed"),
        "printer": ("printer", "#43536b", "#c7d7ed"),
        "phone": ("phone", "#365d78", "#b6e8ff"),
    },
    "mimetypes": {
        "application-pdf": ("document", "#61435d", "#f6c1c7"),
        "application-x-archive": ("archive", "#58546f", "#d4c6ff"),
        "application-x-executable": ("code", "#304f77", "#91c9ff"),
        "application-x-ms-dos-executable": ("window", "#304f77", "#91c9ff"),
        "application-x-msi": ("window", "#304f77", "#91c9ff"),
        "audio-x-generic": ("audio", "#533a75", "#dab4ff"),
        "font-x-generic": ("document", "#4d536b", "#d4d7ef"),
        "image-x-generic": ("image", "#3b5474", "#9bd8ff"),
        "text-x-generic": ("document", "#3b5474", "#9bd8ff"),
        "video-x-generic": ("video", "#533a75", "#dab4ff"),
        "x-office-document": ("document", "#365a78", "#a3d6ff"),
        "x-office-presentation": ("window", "#61485f", "#ffd0bc"),
        "x-office-spreadsheet": ("spreadsheet", "#355f58", "#9de2c8"),
    },
    "places": {
        "folder": ("", "#3679b5", "#d2edff"),
        "folder-open": ("", "#3679b5", "#d2edff"),
        "folder-desktop": ("window", "#3679b5", "#d2edff"),
        "folder-documents": ("document", "#3679b5", "#d2edff"),
        "folder-download": ("down", "#3679b5", "#d2edff"),
        "folder-music": ("audio", "#3679b5", "#d2edff"),
        "folder-pictures": ("image", "#3679b5", "#d2edff"),
        "folder-videos": ("video", "#3679b5", "#d2edff"),
        "user-home": ("home", "#3679b5", "#d2edff"),
    },
    "emblems": {
        "emblem-default": ("shield", "#315d63", "#a6e7d3"),
        "emblem-important": ("info", "#6a4552", "#ffd0c2"),
        "emblem-shared": ("network", "#315d63", "#a6e7d3"),
        "emblem-symbolic-link": ("network", "#355e7c", "#a7dbff"),
        "emblem-synchronizing": ("refresh", "#355e7c", "#a7dbff"),
    },
}

APP_ICONS = {
    "localzet-connect": ("phone", "#287b98", "#a2f2f2"),
    "localzet-windows": ("window", "#405e90", "#c2e2ff"),
}


def svg_symbol(fragment: str, view_box: int = 24) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{view_box}" height="{view_box}" '
        f'viewBox="0 0 {view_box} {view_box}" fill="none" stroke="#eff6ff" '
        'stroke-width="2.0" stroke-linecap="round" stroke-linejoin="round">'
        f'{fragment}</svg>\n'
    )


def svg_colorful(name: str, symbol: str, base: str, line: str, context: str) -> str:
    if context == "places":
        folder = (
            '<path d="M5 16V12a3 3 0 0 1 3-3h10l5 5h16a3 3 0 0 1 3 3v16a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4z" '
            'fill="#79b7eb" stroke="#d4edff" stroke-width="1.4"/>'
            '<path d="M5 19h38l-4 17a4 4 0 0 1-4 3H9a4 4 0 0 1-4-4z" '
            'fill="url(#folder)" stroke="#d4edff" stroke-width="1.4"/>'
        )
        if name == "folder-open":
            folder += '<path d="m7 20-2 15h34l4-15z" fill="#438bc2" stroke="#d4edff" stroke-width="1.2"/>'
        badge = ""
        if symbol:
            badge = f'<g transform="translate(16 20) scale(.67)" stroke="{line}" stroke-width="1.8">{SYMBOLS[symbol]}</g>'
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
            '<defs><linearGradient id="folder" x1="0" y1="0" x2="0" y2="1">'
            '<stop stop-color="#75b7eb"/><stop offset="1" stop-color="#28639a"/>'
            '</linearGradient></defs>'
            f'{folder}<g fill="none" stroke-linecap="round" stroke-linejoin="round">{badge}</g></svg>\n'
        )

    if context == "devices":
        glyph = f'<g transform="translate(9 9) scale(1.25)" stroke="{line}" stroke-width="1.8">{SYMBOLS[symbol]}</g>'
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
            f'<g fill="none" stroke-linecap="round" stroke-linejoin="round">{glyph}</g></svg>\n'
        )

    if context == "mimetypes":
        glyph = f'<g transform="translate(14 17) scale(.84)" stroke="{line}" stroke-width="1.8">{SYMBOLS[symbol]}</g>'
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
            f'<path d="M10 4h18l10 10v28H10a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z" fill="{base}" stroke="{line}" stroke-width="1.5"/>'
            f'<path d="M28 4v10h10" fill="none" stroke="{line}" stroke-width="1.5"/>'
            f'<g fill="none" stroke-linecap="round" stroke-linejoin="round">{glyph}</g></svg>\n'
        )

    if context == "emblems":
        glyph = f'<g transform="translate(9 9) scale(.75)" stroke="{line}" stroke-width="1.8">{SYMBOLS[symbol]}</g>'
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
            f'<circle cx="24" cy="24" r="19" fill="{base}" stroke="{line}" stroke-width="2"/>'
            f'<g fill="none" stroke-linecap="round" stroke-linejoin="round">{glyph}</g></svg>\n'
        )

    glyph = f'<g transform="translate(12 12)" stroke="{line}" stroke-width="1.8">{SYMBOLS[symbol]}</g>'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
        '<defs><linearGradient id="folder" x1="0" y1="0" x2="0" y2="1">'
        f'<stop stop-color="{base}"/><stop offset="1" stop-color="#1b3659"/>'
        '</linearGradient></defs>'
        f'<rect x="2" y="2" width="44" height="44" rx="10" fill="{base}"/>'
        '<rect x="2.8" y="2.8" width="42.4" height="42.4" rx="9.3" '
        'fill="none" stroke="#ffffff" stroke-opacity=".23" stroke-width="1.4"/>'
        f'<g fill="none" stroke="{line}" stroke-linecap="round" stroke-linejoin="round">{glyph}</g>'
        '</svg>\n'
    )


def generate(theme_root: Path) -> list[Path]:
    scalable = theme_root / "scalable"
    written: list[Path] = []
    for context, icons in SYMBOLIC.items():
        for name, symbol in icons.items():
            path = scalable / context / f"{name}.svg"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg_symbol(SYMBOLS[symbol]), encoding="utf-8")
            written.append(path)

    for context, icons in COLORFUL.items():
        for name, (symbol, base, line) in icons.items():
            path = scalable / context / f"{name}.svg"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg_colorful(name, symbol, base, line, context), encoding="utf-8")
            written.append(path)

    app_dir = scalable / "apps"
    app_dir.mkdir(parents=True, exist_ok=True)
    for name, (symbol, base, line) in APP_ICONS.items():
        path = app_dir / f"{name}.svg"
        path.write_text(svg_colorful(name, symbol, base, line, "apps"), encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme-root", type=Path, default=ROOT / "theme/icons/Localzet")
    args = parser.parse_args()
    files = generate(args.theme_root)
    print(f"Generated {len(files)} scalable Localzet icons in {args.theme_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
