"""Shared Aurora Professional appearance for native Localzet applications."""
from __future__ import annotations

# One palette for every first-party GTK workspace. tests/test_assets.py checks
# these values against assets/design-tokens.json so the runtime cannot drift.
PALETTE = {
    "background": "#10091E",
    "surface": "#28183F",
    "surface_elevated": "#34234F",
    "header": "#1A1028",
    "primary": "#9B72F2",
    "accent": "#FF7E00",
    "selection": "#6436B5",
    "text": "#F4EEFF",
    "text_secondary": "#B9A5D5",
    "hover": "#3F2B5B",
    "accent_hover": "#E86F00",
    "on_accent": "#10091E",
}


def palette_css(template: bytes) -> bytes:
    """Resolve only named, fixed palette placeholders in first-party CSS."""
    for name, value in PALETTE.items():
        template = template.replace(
            f"__{name.upper()}__".encode("ascii"), value.encode("ascii"))
    if b"__" in template:
        raise ValueError("Unresolved Aurora Professional CSS palette token")
    return template


PROFESSIONAL_CSS = palette_css(b"""
@define-color window_bg_color __BACKGROUND__;
@define-color window_fg_color __TEXT__;
@define-color headerbar_bg_color __HEADER__;
@define-color headerbar_fg_color __TEXT__;
@define-color view_bg_color __BACKGROUND__;
@define-color view_fg_color __TEXT__;
@define-color card_bg_color __SURFACE_ELEVATED__;
@define-color card_fg_color __TEXT__;
@define-color accent_bg_color __ACCENT__;
@define-color accent_fg_color __ON_ACCENT__;
@define-color accent_color __PRIMARY__;
window.localzet-midnight {
    background-color: __BACKGROUND__;
    color: __TEXT__;
}
.localzet-midnight headerbar {
    background-color: __HEADER__;
    color: __TEXT__;
    border-bottom: none;
    box-shadow: none;
}
.localzet-midnight .boxed-list {
    background-color: __SURFACE_ELEVATED__;
    color: __TEXT__;
    border-radius: 8px;
    border: none;
}
.localzet-midnight .boxed-list > row {
    border-radius: 6px;
}
.localzet-midnight .boxed-list > row:hover {
    background-color: __HOVER__;
}
.localzet-midnight .boxed-list > row .subtitle,
.localzet-midnight .dim-label {
    color: __TEXT_SECONDARY__;
    opacity: 1;
}
.localzet-midnight .boxed-list > row + row {
    border-top: 1px solid rgba(155, 114, 242, .18);
}
.localzet-midnight .boxed-list > row:focus-visible {
    outline: 2px solid __ACCENT__;
    outline-offset: -2px;
}
.localzet-midnight .boxed-list > row image {
    color: __TEXT_SECONDARY__;
}
.localzet-midnight entry {
    background-color: __BACKGROUND__;
    color: __TEXT__;
    border-radius: 8px;
}
.localzet-midnight button.suggested-action {
    background-color: __ACCENT__;
    color: __ON_ACCENT__;
}
.localzet-midnight button.suggested-action:hover {
    background-color: __ACCENT_HOVER__;
    color: __ON_ACCENT__;
}
""")

# Compatibility for modules and tests from the earlier internal name.
MIDNIGHT_CSS = PROFESSIONAL_CSS


def apply_professional(window):
    """Use Violet × Ember only for system dark mode; respect light and high contrast."""
    from gi.repository import Adw, Gtk

    # libadwaita follows the desktop's color-scheme portal. Never pin a
    # per-process scheme: doing so would override the user's live choice.
    style = Adw.StyleManager.get_default()
    provider = Gtk.CssProvider()
    provider.load_from_data(PROFESSIONAL_CSS)
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
    refresh()

    def cleanup(*_):
        nonlocal active
        for handler in handlers:
            style.disconnect(handler)
        if active:
            Gtk.StyleContext.remove_provider_for_display(display, provider)
            active = False

    window.connect("destroy", cleanup)
    return provider


def apply_midnight(window):
    """Backward-compatible alias for apply_professional."""
    return apply_professional(window)
