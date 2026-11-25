# GNOME 50 live-session visual review

The visual gate uses a freshly built Ubuntu 26.04 Live ISO booted as a regular
GNOME 50 Wayland session in QEMU. `scripts/qemu-live-visual.py` drives the UI
through QMP and saves the virtual display framebuffer; it does not call the
GNOME Shell screenshot D-Bus API. The capture artifact records QEMU version,
guest resolution, scene, theme and SHA-256 for each PNG.

Earlier DevKit/Xvfb captures are rejected as visual evidence. The previous
Blue/Purple/Black captures differed only around a small panel glyph and did not
establish that the full interface follows the selected theme. A successful
capture run means only that frames were obtained; it is not a visual quality or
design-acceptance result.

## Required capture matrix

At 1536×1024, capture each theme after applying it in Localzet Settings:

- Desktop with the approved mountain wallpaper and the complete Localzet Dock.
- Nautilus, Localzet launcher, GNOME Quick Settings, Appearance, Settings home,
  Ptyxis with the selected Aurora palette, and a visible notification.
- The original pre-change Appearance and desktop after restore.

The first-login Blue desktop must also be captured before changing the session.
The scenario then sets a distinct user-scoped restore source, applies all three
themes through the Appearance UI, and restores the source. This makes restore
observable while preserving evidence of the installed first-login defaults.
The test-only guest helper starts Ptyxis as a separate instance for each
capture and requests the current profile UUID explicitly. Readiness includes
the selected profile and palette; QMP then checks the rendered framebuffer
background against that Aurora palette before accepting the capture.

## Inspecting the result

1. Download the `localzet-gnome-50-qemu-screens` artifact from the pull request
   workflow and read `manifest.json` for capture provenance.
2. Inspect every Blue, Purple and Black scene at native resolution. Confirm
   that the mountain wallpaper and all installed Dock entries are visible on
   the desktop; compare shell colors, GTK surfaces, spacing, icon geometry and
   glass treatment against the matching approved PNG.
3. Check that Appearance visibly marks the active theme, applying each choice
   changes the full interface, and Restore returns the distinct saved source.
4. Inspect `installed-icon-resolution-page-1.png` through `-page-4.png`. The GTK
   check resolves all 120 names against the active installed theme; the frames
   show the resolved file paths for each name and upstream Nautilus/Ptyxis.
   Confirm Localzet artwork resolves inside `Localzet`, while application icons
   resolve outside that directory. Inspect Nautilus at rendered size too.
5. Inspect `shell-log-check.png` after the theme changes and restore; it must
   show `LOCALZET_SHELL_LOG_RESULT PASS js_errors=0`.
6. Record concrete mismatches and fix them before asking the owner to accept the
   design. Do not infer visual quality from filenames, hashes, or pixel-change
   percentages alone.

## Acceptance criteria

- The full GNOME 50 Wayland Live session reaches the QEMU readiness marker.
- All required scenes for Blue/Purple/Black and restore have recorded provenance.
- Human review confirms distinct styling across the full interface and compares
  it with the approved references.
- Nautilus shows resolved installed icon names and upstream third-party icons.
- No `JS ERROR` appears during the captured session.
- The owner accepts the visual result before the PR gate is marked complete.

The capture VM is disposable and has no network interface. If a run fails,
inspect its uploaded serial log and keep the PR draft. Never weaken GNOME
screenshot or D-Bus protections to obtain a frame.
