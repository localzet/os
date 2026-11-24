# GNOME 50 smoke test — disposable VM

The CI packaging job uses the GNOME 50 `gnome-extensions pack` command from Ubuntu 26.04, then verifies the ZIP. **It does not prove that GNOME Shell starts or that the extension works.**
The visual workflow separately launches the GTK Settings app under Xvfb and
captures its window, then runs GNOME Shell devkit captures. The GTK capture
checks a real GTK window but is not a full GNOME session; devkit screenshots
must be labeled separately from full-session evidence.

## Test environment

- Fresh Ubuntu **26.04 LTS** virtual machine with standard GNOME 50 on Wayland.
- Regular non-root user; create a VM snapshot before installing the extension.
- Do not perform this first test on a production workstation.

## Manual test

1. Clone `localzet/os` in a disposable Ubuntu 26.04 VM and run `gnome-shell --version`; expect GNOME Shell 50.x. `scripts/ci/gnome50-visual-smoke.sh` can capture a separate GNOME Shell devkit matrix at 1536×1024 and 1920×1080; label those files **GNOME Shell devkit**, not a full desktop session.
2. Run `bash scripts/install-shell-dev.sh`. It must refuse to overwrite existing installations.
3. Log out and log back in. Enable **Localzet Shell** in GNOME Extensions.
4. Run `bash scripts/check-gnome-session.sh`; expect `PASS` with the expected UUID.
5. Click the Localzet icon on the top panel, choose **Настройки системы** and confirm GNOME Settings opens.
6. Disable the extension in GNOME Extensions. Confirm the indicator disappears and the desktop stays responsive.
7. Enable again, confirm exactly one indicator. Review `journalctl --user -b --no-pager` locally for related errors; logs may contain sensitive information.
8. Capture a **genuine** VM desktop screenshot and record GNOME, Ubuntu, screen resolution and GPU/renderer details.
9. Open Localzet Settings → Оформление. Select Blue, Purple and Black in turn; confirm the wallpaper, desktop icon theme and Localzet Dock/launcher accent follow the selection. Confirm there is no theme selector in the top bar.
10. Restore the saved appearance. Confirm the previous wallpaper, icon theme and color scheme return. Repeat with the Localzet Shell extension disabled; appearance must report the missing Shell integration without failing or changing privileged/system settings.
11. In Nautilus, inspect folders and common MIME icons. Confirm third-party applications retain their own upstream logos through Adwaita fallback.

## Acceptance criteria

- Extension discovered, enabled and disabled without a GNOME Shell crash.
- The Localzet menu and its Settings action function correctly.
- No duplicate indicators after disabling/enabling and re-login.
- A real screenshot and test notes are reviewed before the runtime milestone is marked complete.
- The GNOME 50 package job passes separately; it is not runtime evidence.
- Record Blue/Purple/Black captures separately at 1536×1024 and 1920×1080, including the scale factor and screenshot provenance.

## Recovery

Use GNOME Extensions to disable the extension. If the test VM cannot start a graphical session, recover from its VM snapshot or, using a VM recovery console, remove the user-scoped directory at `~/.local/share/gnome-shell/extensions/localzet-shell@localzet.com`. Do not alter a host OS.
