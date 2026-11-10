# Roadmap

## P0 — bootstrap (current)
- [x] Establish Ubuntu 26.04 + GNOME 50 target and repository boundaries.
- [x] Add minimal GNOME extension source; **runtime unverified**.
- [x] Add design tokens and original wallpaper.
- [x] Add read-only module catalog/resolver with tests.
- [x] Add CI source checks (first run succeeded on 2026-11-10).
- [ ] Build and validate a GNOME 50 extension ZIP in CI.
- [ ] Verify shell extension enable/disable in a clean Ubuntu 26.04 GNOME VM.
- [ ] Capture genuine desktop screenshots and extension logs.

## P1 — first bootable release
- [ ] Build a clean Ubuntu 26.04 desktop live image from verified sources.
- [ ] Verify checksum, UEFI + BIOS boot, networking, GNOME login and shutdown in QEMU.
- [ ] Produce a licensing/redistribution inventory before publishing an ISO.
- [ ] Add reproducible packages and a signed artifact pipeline.
- [ ] Make the installer non-destructive in dry-run mode.

## P2 — coherent desktop
- [ ] Implement shell styling, dock, launcher, notifications and overview incrementally.
- [ ] Build Localzet Settings and unified package/module UI.
- [ ] Validate accessibility, low-power behaviour and reduced motion.

## P3 — optional services
- [ ] Implement authorized package transactions with polkit, rollback and removal.
- [ ] Containers module, network policy module, NetBird, UserNet and Gaming.
- [ ] Document Wine/Proton compatibility testing; no universal compatibility claims.

### Latest progress (2026-11-10)
- [x] GNOME 50.1/Mutter devkit session started in CI with Localzet Shell enabled; real diagnostic screenshot captured (not a full OS boot).
- [ ] Build experimental Ubuntu 26.04 Live ISO in CI (PR #4).
- [ ] Independently verify BIOS and UEFI startup in QEMU before any USB instructions or release.
- [ ] Validate GNOME session, Localzet wallpaper, app menu, storage read-only behavior.
