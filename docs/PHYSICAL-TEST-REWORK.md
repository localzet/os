# Physical test: release gate reset

The first real hardware test failed to present usable installation disks and
identified serious visual and usability problems. The previous QEMU success
is engineering evidence only, not a release approval. No public release
should be made until the following gates are satisfied.

## Storage and installer

- Distinguish invisible controllers/disks from disks rejected by policy.
- Include and verify VMD, NVMe, AHCI early boot drivers; never silently disable
  Intel RST or change firmware modes. Actual Intel VMD hardware is untested.
- Detect existing ESPs and inspect existing UEFI entries read-only. A firmware
  entry referencing shim or GRUB is only a hint, not proof of its contents.
- Replace the single-blank-disk wizard with a reviewed partitioning backend
  (evaluate Calamares vs. upstream Ubuntu installer). Do not extend the
  temporary shell writer by allowing arbitrary partitions.
- Separate SSD: its own ESP and loader, never format or write another disk.
- Alongside: use explicitly selected unallocated space; preserve partition
  boundaries, filesystems, ESP contents and Windows/Linux boot entries.
  Integrate via a new uniquely named EFI loader directory and explicit
  chainloading/boot-menu instructions; never overwrite EFI/BOOT/BOOTX64.EFI
  or another distribution's GRUB in a shared ESP. No automatic GRUB config
  rewriting. Test with before/after hashes and boot both operating systems.
- Test actual VMD hardware, existing Windows/GRUB, two SSDs, shared SSD,
  interruption, insufficient space, encryption and unsupported RAID.
  Until these pass, the original blank-disk restrictions remain.

## Desktop

- Replace the duplicated top-panel launcher with one coherent navigation
  model. Keep native accessible controls until replacements are tested.
- Use Papirus as an interim consistent icon set; commission/review actual
  brand artwork and application icons before calling the design final.
- Keep GNOME Control Center as the only system settings entry point. Rename
  the previous shortcut collection to Components; integrate Localzet-specific
  panels into an upstream-maintained Control Center build, rather than
  reimplement network, sound, display and accessibility controls.
- Implement real boot/greeter brand assets and verify About branding from
  the installed package, not only os-release. Quiet Plymouth first, final
  branded theme later. Keep an opt-in diagnostic boot.
- Add practical Live applications and storage tools. Check all desktop IDs,
  installed software, Russian/English layouts, DPI, keyboard access, and
  screenshots from the actual ISO, not only nested compositor tests.

## Release

Engineering PR builds may run full tests; candidate ISO uploads require
manual dispatch. No stable release based on synthetic tests or placeholder
artwork. A physical retest and explicit review of the visual baseline and
installer safety are required. The original Alpha artifacts remain historical
engineering builds and should not be used for installation on valuable disks.
