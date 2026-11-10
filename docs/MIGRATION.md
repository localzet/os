# Legacy prototype migration

Previous experiments: https://github.com/localzet/localzet-os

The legacy project is based on Debian Trixie, labwc, LightDM and custom Rust/GTK4 layer-shell programs. It has useful knowledge but is **not** the base of the GNOME/Ubuntu rebuild.

Potentially reusable, after review:
- Read-only installer disk inventory design and failure handling (`scripts/installer-preflight.py`).
- QEMU smoke-test ideas and diagnostic evidence gathering.
- Threat model and security test cases.
- Rust service boundaries, after checking authorization and API requirements.

Avoid wholesale migration of labwc session bootstrap, Waybar, LightDM, preinstalled Wine, or direct ISO scripts: they reflect a different architecture. Keep the old history intact and move only independently reviewed features.

This new repository skeleton deliberately has no old file history. Archive the old repository only after the new canonical repository and migration notes are publicly accessible.
