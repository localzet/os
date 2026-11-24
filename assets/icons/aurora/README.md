# Localzet Aurora icon family — v1.1

First-party semantic vector artwork, **not** replicas of Firefox, VS Code, Steam, Telegram or other trademarks. The preview formerly mixed third-party-like symbols, reused the launcher glyph for Containers, and lacked consistent stroke/optical size.

- Every application glyph uses editable 48×48 SVG, a 44×44 base tile, 10 px corners and common optical padding.
- App-specific hue but consistent lighting and line weight, with understated dark-blue/slate/violet palette.
- `assets/icons/status/*.svg` use a separate, monochrome 20×20 grid; visual glyphs are 15–20 CSS px in the top bar.
- Installed icon theme: `theme/icons/Localzet/scalable/apps/localzet-*.svg` plus existing places icons. Inherits `Adwaita,hicolor` for missing icons; this is **not** a comprehensive freedesktop icon theme yet.
- The browser demo includes no runtime app integration and must not use unofficial icons to imply one exists.
- Brand marks: do not clone third-party trademarks as a shortcut; native app integration should use real installed program icons where appropriate.
- `localzet-symbol.svg` is the reviewed first-party Aurora mark; the installed `localzet-symbol` icon is kept byte-identical.
