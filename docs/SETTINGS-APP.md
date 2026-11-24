# Localzet Settings — first native application

A GTK4/libadwaita **unprivileged** application.
It opens real GNOME control-center panels, Nautilus and Ptyxis via fixed
argv. It shows read-only system metrics and existing module manifests.
It does not promise Docker, NetBird, UserNet or Gaming are installed. The
Appearance page changes only the current user's GNOME GSettings values; it
does not modify packages, disks, routes or system services.

Runtime dependencies on Ubuntu 26.04:
- python3 >= 3.13
- python3-gi
- gir1.2-gtk-4.0
- gir1.2-adw-1
- gnome-control-center, nautilus and ptyxis for action buttons

Engineering gates:
1. Unit tests in ordinary CI (no GNOME session required).
2. Launch GTK4 app in a disposable graphical VM; inspect stdout/stderr.
3. Test keyboard, Cyrillic, actions, screenshots and 125%/150% scaling.
4. Only then add files to the Live ISO build scripts.

This is not the full Localzet Settings suite. An authorized backend must
be implemented and reviewed before showing installation toggles or writing
system state. No telemetry, network queries or privileged actions.

## Aurora Appearance

The page offers Blue (default), Purple and Black. A selection updates the
user's wallpaper, `org.gnome.desktop.interface` color scheme and icon theme,
plus the Localzet Shell accent when that schema is installed. It does not edit
`org.gnome.shell.extensions.user-theme`; the Localzet extension styles its own
actors and does not require User Themes. Without the Localzet Shell extension,
the wallpaper, icon theme and dark color scheme still apply, and the page says
that Shell accents are unavailable.

Before the first change, the app writes a mode-0600 snapshot at
`$XDG_STATE_HOME/localzet/appearance.json` or
`~/.local/state/localzet/appearance.json`. Later theme choices keep that
original snapshot. The selected Aurora name is also stored with mode 0600 in
`appearance-current.json` so Settings can display Purple/Black when the Shell
extension is absent. A relative `XDG_STATE_HOME` is rejected before changing
GNOME settings. **Restore previous appearance** reapplies the saved values
and removes the snapshot after all available settings succeed. If the optional
Localzet Shell schema disappeared, general GNOME settings are restored and its
saved value remains pending until the extension returns. A failed apply rolls
back settings already changed; the snapshot remains available for recovery.
Snapshot write failures are shown before settings change, and snapshot cleanup
failures are reported after restoration. Missing icon theme or wallpaper
assets fail before any write.

This first native implementation keeps all three variants dark. The custom
accent is applied to Localzet Settings and Localzet Shell; other GTK
applications keep their own supported GNOME styling. Real GNOME interaction,
screen-reader, scale and screenshot acceptance is tracked in
[`DESIGN_ACCEPTANCE.ru.md`](DESIGN_ACCEPTANCE.ru.md).
