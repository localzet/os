"""Check actual upstream menu export over the session bus, no pairing."""
import time
from gi.repository import Gio, GLib

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def call(name, path, interface, method, args):
    result = bus.call_sync(name, path, interface, method, args, None,
                           Gio.DBusCallFlags.NONE, 2000, None)
    if result is None:
        raise ValueError("Empty D-Bus response")
    return result.unpack()


def prop(name, path, interface, key):
    return call(name, path, "org.freedesktop.DBus.Properties", "Get",
                GLib.Variant("(ss)", (interface, key)))[0]


def menu_labels(node):
    _, props, children = node
    if "label" in props:
        label = props["label"]
        yield label.unpack() if isinstance(label, GLib.Variant) else str(label)
    for child in children:
        yield from menu_labels(child.unpack() if isinstance(child, GLib.Variant) else child)


def candidates(items):
    # Watchers can return bus names, bus+path, or just a path (Qt registers
    # via invocation sender). Never pass an empty string as a D-Bus name.
    names = call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                 "org.freedesktop.DBus", "ListNames", None)[0]
    names = [n for n in names if n.startswith("org.kde.StatusNotifierItem") or n.startswith(":")]
    for item in items:
        name, sep, suffix = item.partition("/")
        path = "/" + suffix if sep else "/StatusNotifierItem"
        if name and Gio.dbus_is_name(name):
            yield name, path
        elif item.startswith("/"):
            for candidate in names:
                yield candidate, path


deadline = time.monotonic() + 65
while time.monotonic() < deadline:
    try:
        items = prop("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
                     "org.kde.StatusNotifierWatcher", "RegisteredStatusNotifierItems")
        print("Registered items:", items, flush=True)
        for name, path in candidates(items):
            try:
                menu = prop(name, path, "org.kde.StatusNotifierItem", "Menu")
                _, tree = call(name, menu, "com.canonical.dbusmenu", "GetLayout",
                               GLib.Variant("(iias)", (0, -1, ["label", "enabled"])))
                labels = list(menu_labels(tree))
                if any("nectarlink" in label.lower() for label in labels):
                    print("PASS: upstream NectarLink exported an actual tray menu")
                    print("\n".join(labels))
                    raise SystemExit(0)
            except (GLib.Error, ValueError, TypeError):
                continue
    except (GLib.Error, ValueError, TypeError) as error:
        print(f"Waiting for tray: {error}", flush=True)
    time.sleep(2)
raise SystemExit("NectarLink StatusNotifier menu was not discovered")
