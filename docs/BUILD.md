# Development and installation

This is a source bootstrap, **not** an ISO builder. No machine provisioning is performed by test commands.

Test with Python >= 3.11:

```sh
make test
PYTHONPATH=src python3 -m localzet.cli list
PYTHONPATH=src python3 -m localzet.cli plan netbird
```

For a disposable Ubuntu 26.04 GNOME 50 VM only:

```sh
bash scripts/install-shell-dev.sh
# Log out and log back in; enable Localzet Shell in GNOME Extensions.
```

The script refuses to overwrite an existing extension directory. GNOME may require a full logout/login for a new extension to be discovered. The extension adds one panel indicator and a menu action; it does not modify the GNOME overview, dock or notifications yet.

Disable it in GNOME Extensions, then remove the folder if no longer needed:

```sh
rm -r -- "${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/localzet-shell@localzet.com"
```

**No `sudo apt`, partitioning, GRUB, UEFI or networking modifications are made by the bootstrap.** The full Ubuntu ISO image-building pipeline needs dedicated VM tests and supply-chain review, and is intentionally not pretended to exist here.
