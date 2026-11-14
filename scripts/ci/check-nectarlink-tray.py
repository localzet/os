"""Check actual upstream menu export over the session bus, no pairing."""
import time
from gi.repository import Gio, GLib

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def call(name, path, interface, method, args):
    return bus.call_sync(name, path, interface, method, args, None,
                         Gio.DBusCallFlags.NONE, 4000, None).unpack()


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


deadline = time.monotonic() + 65
while time.monotonic() < deadline:
    try:
        items = prop("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
                     "org.kde.StatusNotifierWatcher", "RegisteredStatusNotifierItems")
        for item in items:
            name, sep, suffix = item.partition("/")
            path = "/" + suffix if sep else "/StatusNotifierItem"
            menu = prop(name, path, "org.kde.StatusNotifierItem", "Menu")
            _, tree = call(name, menu, "com.canonical.dbusmenu", "GetLayout",
                           GLib.Variant("(iias)", (0, -1, ["label", "enabled"])))
            labels = list(menu_labels(tree))
            if any("nectarlink" in label.lower() for label in labels):
                print("PASS: upstream NectarLink exported an actual tray menu")
                print("\n".join(labels))
                raise SystemExit(0)
    except (GLib.Error, ValueError, TypeError) as error:
        print(f"Waiting for tray: {error}", flush=True)
    time.sleep(2)
raise SystemExit("NectarLink StatusNotifier menu was not discovered")
