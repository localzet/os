# Localzet Settings — first native application

A minimal but functional GTK4/libadwaita **unprivileged** application.
It opens real GNOME control-center panels, Nautilus and Ptyxis via fixed
argv. It shows read-only system metrics and existing module manifests.
It does not promise Docker, NetBird, UserNet or Gaming are installed.
Nothing in the app can modify packages, disks, routes or system services.

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

The initial Aurora design uses a dark color scheme and explicitly scoped GTK CSS.
A user-facing light/dark theme switch is planned, not yet implemented.
