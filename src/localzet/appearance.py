"""Shared, process-local Midnight appearance for native Localzet applications."""
from __future__ import annotations

MIDNIGHT_CSS = b"""
@define-color window_bg_color #091321;
@define-color window_fg_color #e7edf7;
@define-color headerbar_bg_color #101b2d;
@define-color headerbar_fg_color #e7edf7;
@define-color view_bg_color #0b1524;
@define-color view_fg_color #e7edf7;
@define-color card_bg_color #192a40;
@define-color card_fg_color #e7edf7;
@define-color accent_bg_color #2874c8;
@define-color accent_fg_color #ffffff;
@define-color accent_color #78b8ff;
window.localzet-midnight {
    background-color: #091321;
    color: #e7edf7;
}
.localzet-midnight headerbar {
    background-color: #101b2d;
    color: #e7edf7;
    border-bottom: 1px solid #273950;
}
.localzet-midnight .boxed-list {
    background-color: #192a40;
    color: #e7edf7;
}
.localzet-midnight button.suggested-action {
    background-color: #2874c8;
    color: #ffffff;
}
.localzet-midnight button.suggested-action:hover {
    background-color: #205ea8;
    color: #ffffff;
}
"""


def apply_midnight(window):
    """Keep the provider alive and react to system appearance changes."""
    from gi.repository import Adw, Gtk

    style = Adw.StyleManager.get_default()
    # Dark-first when the system has no preference, never force against
    # explicit light preference. Preserve native high-contrast styling.
    style.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
    provider = Gtk.CssProvider()
    provider.load_from_data(MIDNIGHT_CSS)
    display = window.get_display()
    active = False

    def refresh(*_):
        nonlocal active
        wanted = style.get_dark() and not style.get_high_contrast()
        if wanted == active:
            return
        if wanted:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            window.add_css_class("localzet-midnight")
        else:
            Gtk.StyleContext.remove_provider_for_display(display, provider)
            window.remove_css_class("localzet-midnight")
        active = wanted

    handlers = [style.connect("notify::dark", refresh),
                style.connect("notify::high-contrast", refresh)]

    def cleanup(*_):
        nonlocal active
        for handler in handlers:
            style.disconnect(handler)
        if active:
            Gtk.StyleContext.remove_provider_for_display(display, provider)
            active = False

    window.connect("destroy", cleanup)
    refresh()
    return provider
