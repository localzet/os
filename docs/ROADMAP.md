# Roadmap

## P0 — bootstrap (current)
- [x] Establish Ubuntu 26.04 + GNOME 50 target and repository boundaries.
- [x] Add minimal GNOME extension source; **runtime unverified**.
- [x] Add design tokens and original wallpaper.
- [x] Add read-only module catalog/resolver with tests.
- [x] Add CI checks (workflow execution not yet verified).
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
