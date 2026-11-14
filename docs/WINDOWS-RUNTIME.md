# Localzet Windows Runtime

The prototype launches explicitly selected local Windows EXE or MSI files through
the Ubuntu Wine package as the current user. Each named profile gets a separate
Wine prefix under `$XDG_DATA_HOME/localzet/windows/prefixes` (or
`~/.local/share/localzet/windows/prefixes`).

The default operation only prints a launch plan. It does not create a prefix or
execute the program. To run a trusted file, explicitly add `--run`.

```sh
PYTHONPATH=src python3 -m localzet.windows_runtime ./example.exe --profile example
PYTHONPATH=src python3 -m localzet.windows_runtime ./example.exe --profile example --run
```

Wine prefixes separate configuration and installed Windows libraries; they
are **not a security sandbox**. Windows programs can access user files and the
network. File header inspection is not a malware scan. Never run untrusted
executables or run the runtime as root.

The prototype targets 64-bit Wine from the signed Ubuntu archive. CI compiles
a small native PE fixture and verifies its exit code under Wine. It does not
establish compatibility with specific commercial software, 32-bit applications,
Windows drivers, anti-cheat, DRM, DirectX or Proton games.

## Remaining work

- Native GUI for profile creation, execution consent and installed application shortcuts.
- Wine version management, 32-bit dependency policy and per-app compatibility catalog.
- File association integration without silent default changes.
- Proton/Steam and DXVK/VKD3D GPU testing, separate from desktop Wine.
- Actual sandboxing or explicit documented security boundaries.
- Integration into the desktop DEB and installed image after runtime checks.

## Native desktop entry

Localzet Windows Runtime is now packaged as a GTK application and registered
as an available EXE/MSI handler. Opening a file shows its path, a named Wine
profile and an explicit trust checkbox; no automatic execution or default
MIME association changes occur. The optional build flag
`LOCALZET_WINDOWS=1` adds the Ubuntu Wine packages to the image. The default
image remains unchanged until the combined image is verified.
