# Development and installation

Source tests and development installs do not provision the host. The separate Live image builder is now implemented and verified in QEMU; see [ISO build and smoke tests](ISO-SMOKE.md).

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

The script refuses to overwrite an existing extension directory. GNOME may require a full logout/login for a new extension to be discovered. The extension provides the Aurora panel launcher and persistent dock.

Disable it in GNOME Extensions, then remove the folder if no longer needed:

```sh
rm -r -- "${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/localzet-shell@localzet.com"
```

**No `sudo apt`, partitioning, GRUB, UEFI or networking modifications are made by the bootstrap.** The separate ISO builder requires a disposable build VM. It has passed BIOS/UEFI Live boot tests; the VM-only UEFI installation test is documented separately in [UEFI installation test](UEFI-INSTALL-TEST.md). This does not authorize physical disk installation.

## GNOME extension packaging

Run `make extension-zip` on a system with the GNOME CLI. It uses the official `gnome-extensions pack` format and verifies the archive. A separate GitHub Actions job uses GNOME 50 tooling inside Ubuntu 26.04; packaging is not a substitute for a graphical boot test. See [GNOME 50 smoke test](GNOME-50-SMOKE.md).
