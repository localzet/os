"""Shared, process-local Executive Soft Graphite appearance for native Localzet applications."""
from __future__ import annotations

MIDNIGHT_CSS = b"""
@define-color window_bg_color #202124;
@define-color window_fg_color #f0f0f2;
@define-color headerbar_bg_color #292a2e;
@define-color headerbar_fg_color #f0f0f2;
@define-color view_bg_color #202124;
@define-color view_fg_color #f0f0f2;
@define-color card_bg_color #2f3034;
@define-color card_fg_color #f0f0f2;
@define-color accent_bg_color #2874c8;
@define-color accent_fg_color #ffffff;
@define-color accent_color #78b8ff;
window.localzet-midnight {
    background-color: #202124;
    color: #f0f0f2;
}
.localzet-midnight headerbar {
    background-color: #292a2e;
    color: #f0f0f2;
    border-bottom: none;
    box-shadow: none;
}
.localzet-midnight .boxed-list {
    background-color: #2f3034;
    color: #f0f0f2;
    border-radius: 10px;
    border: none;
}
.localzet-midnight .boxed-list > row {
    border-radius: 8px;
}
.localzet-midnight .boxed-list > row:hover {
    background-color: #3c3d42;
}
.localzet-midnight .boxed-list > row .subtitle,
.localzet-midnight .dim-label {
    color: #c4c5ca;
    opacity: 1;
}
.localzet-midnight .boxed-list > row + row {
    border-top: 1px solid #3b3c40;
}
.localzet-midnight .boxed-list > row:focus-visible {
    outline: 2px solid #78b8ff;
    outline-offset: -2px;
}
.localzet-midnight .boxed-list > row image {
    color: #d2d3d8;
}
.localzet-midnight entry {
    background-color: #202124;
    color: #f0f0f2;
    border-radius: 8px;
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
