"""Read-only GNOME proxy summary. Never infer ownership or VPN routing."""
from __future__ import annotations

import ipaddress


def classify(mode, endpoints):
    if mode not in ("none", "auto", "manual"):
        return {"mode": "unavailable", "local": 0, "remote": 0}
    local = remote = 0
    if mode == "manual":
        for host, port in endpoints:
            if not isinstance(host, str) or not host.strip() or type(port) is not int or not 1 <= port <= 65535:
                continue
            host = host.strip().lower()
            try:
                loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                loopback = host == "localhost"
            if loopback:
                local += 1
            else:
                remote += 1
    return {"mode": mode, "local": local, "remote": remote}


def proxy_status():
    try:
        from gi.repository import Gio
        source = Gio.SettingsSchemaSource.get_default()
        if not source or not source.lookup("org.gnome.system.proxy", True):
            return classify(None, ())
        settings = Gio.Settings.new("org.gnome.system.proxy")
        mode = settings.get_string("mode")
        endpoints = []
        if mode == "manual":
            for protocol in ("http", "https", "socks", "ftp"):
                name = "org.gnome.system.proxy." + protocol
                if not source.lookup(name, True):
                    continue
                child = Gio.Settings.new(name)
                endpoints.append((child.get_string("host"), child.get_int("port")))
        return classify(mode, endpoints)
    except (ImportError, ValueError, RuntimeError):
        return classify(None, ())
