"""Shared, process-local Aurora Professional appearance for native Localzet applications."""
from __future__ import annotations

MIDNIGHT_CSS = b"""
@define-color window_bg_color #10091E;
@define-color window_fg_color #F4EEFF;
@define-color headerbar_bg_color #1A1028;
@define-color headerbar_fg_color #F4EEFF;
@define-color view_bg_color #10091E;
@define-color view_fg_color #F4EEFF;
@define-color card_bg_color #34234F;
@define-color card_fg_color #F4EEFF;
@define-color accent_bg_color #FF7E00;
@define-color accent_fg_color #10091E;
@define-color accent_color #9B72F2;
window.localzet-midnight {
    background-color: #10091E;
    color: #F4EEFF;
}
.localzet-midnight headerbar {
    background-color: #1A1028;
    color: #F4EEFF;
    border-bottom: none;
    box-shadow: none;
}
.localzet-midnight .boxed-list {
    background-color: #34234F;
    color: #F4EEFF;
    border-radius: 8px;
    border: none;
}
.localzet-midnight .boxed-list > row {
    border-radius: 6px;
}
.localzet-midnight .boxed-list > row:hover {
    background-color: #3F2B5B;
}
.localzet-midnight selection {
    background-color: #6436B5;
    color: #F4EEFF;
}
.localzet-midnight .boxed-list > row .subtitle,
.localzet-midnight .dim-label {
    color: #B9A5D5;
    opacity: 1;
}
.localzet-midnight .boxed-list > row + row {
    border-top: 1px solid rgba(155, 114, 242, .18);
}
.localzet-midnight .boxed-list > row:focus-visible {
    outline: 2px solid #FF7E00;
    outline-offset: -2px;
}
.localzet-midnight .boxed-list > row image {
    color: #B9A5D5;
}
.localzet-midnight entry {
    background-color: #10091E;
    color: #F4EEFF;
    border-radius: 8px;
}
.localzet-midnight button.suggested-action {
    background-color: #FF7E00;
    color: #10091E;
}
.localzet-midnight button.suggested-action:hover {
    background-color: #E86F00;
    color: #10091E;
}
"""


def apply_midnight(window):
    """Apply the dark Aurora surface only for dark/default preference.

    Explicit light mode and high contrast remain owned by the desktop toolkit.
    The Adw override is process-local; this never writes a system preference.
    """
    from gi.repository import Adw, Gio, Gtk

    style = Adw.StyleManager.get_default()
    interface = Gio.Settings.new("org.gnome.desktop.interface")
    accessibility = Gio.Settings.new("org.gnome.desktop.a11y.interface")
    provider = Gtk.CssProvider()
    provider.load_from_data(MIDNIGHT_CSS)
    display = window.get_display()
    active = False

    def refresh(*_):
        nonlocal active
        high_contrast = style.get_high_contrast() or accessibility.get_boolean("high-contrast")
        wanted = style.get_dark() and not high_contrast
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

    def update_color_scheme(*_):
        # Aurora is dark by default, but an explicit system light choice wins.
        preference = interface.get_string("color-scheme")
        scheme = (Adw.ColorScheme.PREFER_LIGHT if preference == "prefer-light"
                  else Adw.ColorScheme.PREFER_DARK)
        style.set_color_scheme(scheme)
        refresh()

    handlers = [
        (style, style.connect("notify::dark", refresh)),
        (style, style.connect("notify::high-contrast", refresh)),
        (interface, interface.connect("changed::color-scheme", update_color_scheme)),
        (accessibility, accessibility.connect("changed::high-contrast", refresh)),
    ]

    def cleanup(*_):
        nonlocal active
        for source, handler in handlers:
            source.disconnect(handler)
        if active:
            Gtk.StyleContext.remove_provider_for_display(display, provider)
            active = False
        window.remove_css_class("localzet-midnight")

    window.connect("destroy", cleanup)
    update_color_scheme()
    refresh()
    return provider
