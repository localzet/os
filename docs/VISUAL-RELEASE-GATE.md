# Localzet OS visual release gate

**The published installer ISO must not look like a stock GNOME session with a new wallpaper.** This is a product requirement, not a promise that this PR already implements it.

## Consistency targets

- Brand system: Localzet Aurora Dark tokens, deliberate light-mode alternative, unified typography and icon system.
- Shell: top bar, launcher with application search, dock, workspace overview, quick settings, grouped notifications, lock screen.
- Native experiences: Nautilus integration, terminal profile, settings, software center, resource monitor, installer, welcome screen.
- Full functionality and keyboard/mouse support; not static mockups, not a fake desktop rendered over GNOME.
- Animations must degrade gracefully under software rendering and reduced motion settings.
- GNOME extension code should use supported shell APIs as far as possible, avoid patching private internals, and include clear disable/uninstall recovery.

## Visual quality test matrix

1. GNOME Shell 50 on Wayland in Ubuntu 26.04; 1920×1080 and 2560×1440.
2. Full screen capture of desktop, open launcher, search results, Nautilus, terminal, settings, quick settings, lock screen and installer.
3. Cyrillic and English input, high DPI (125%, 150%, 200%), multi-monitor, light and dark backgrounds.
4. No clipped labels, missing icons, broken hit targets, unreadable text, inaccessible actions or mismatched spacing.
5. Keyboard-only launch/search/navigation; mouse click and touchpad scrolling; screen-reader basics where supported.
6. Nightly QEMU boot test with real screenshot **from the freshly built ISO**, not a mockup; test on physical hardware before release.
7. No wallpaper-only alpha release. Installer must pass all data-safety checks from \`INSTALLER-SSD-SAFETY.md\`.

## Milestones

| Milestone | Gate |
| --- | --- |
| Design language | Tokens, icon set, reusable GTK4/libadwaita components |
| Shell launcher | Search, launch, keyboard focus, application categories, polished panel |
| Desktop | Configurable dock, workspace overview, hotkeys and notifications |
| Core apps | File manager integration, terminal, settings, monitor |
| Install | Calamares integration, bootloader confined to selected SSD, standalone boot |
| Release | Signed artifacts, checksum, BIOS/UEFI/Secure Boot handling and real hardware QA |

## Scope of this change

A GNOME 50 searchable launcher with a branded menu replaces the temporary four-action popup. It still needs live GUI acceptance, screenshot review and interaction tests; it is *not* a completed graphical shell or final visual design.
