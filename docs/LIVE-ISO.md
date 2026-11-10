# P1: experimental Localzet OS Live ISO

We are building the first **Ubuntu 26.04 / GNOME 50 Live environment**, not a disk installer. The system uses Ubuntu's `casper` initramfs to mount a compressed squashfs and GRUB `grub-mkrescue` to generate an ISO.

## What is included

- AMD64, GNOME Shell / Wayland, GDM, Nautilus, GNOME Settings, Ptyxis, NetworkManager and PipeWire.
- Original Localzet wallpaper, initial GNOME extension and dark mode.
- A temporary `localzet` live account with GDM autologin.
- Passwordless sudo exists **only in this disposable Live image** and must NEVER carry over into an installed OS.

## What is not included

No hard-drive installer, partitioning, disk writes, permanent accounts, custom package repository, Docker, NetBird, UserNet, Steam or Edge. Live changes are not persistent.

This build is NOT a validated release until CI produces an ISO and a genuine VM boot passes. Do not claim full UEFI/BIOS compatibility solely from the presence of boot records.

## Build (disposable Ubuntu 26.04 AMD64 VM only)

```bash
sudo apt-get update
sudo apt-get install -y debootstrap squashfs-tools xorriso mtools \
  grub-pc-bin grub-efi-amd64-bin grub-common
sudo bash scripts/build-live-iso.sh
bash scripts/verify-live-iso.sh out/live/localzet-os-p1-amd64.iso
```

The script refuses to overwrite existing image directories. For another build, set `LOCALZET_BUILD_DIR` to a new, empty location. Never invoke the root build script on a production workstation.

## Acceptance milestones

1. Static syntax and source tests pass.
2. Rootfs created with packages solely from official Ubuntu 26.04 archives.
3. GNOME, kernel, casper initramfs and squashfs present in ISO.
4. GRUB BIOS and UEFI boot records identified.
5. Successful BIOS + UEFI QEMU boot with logs.
6. Real screenshot of GNOME Shell with Localzet extension enabled.
7. Safe shutdown and networking checks.

A genuine installer, removable USB support, Secure Boot, signed update feed and redistributable release are later gates. Public redistribution needs a separate trademark/license review. `localzet-os-p1-amd64.iso` is strictly an experimental engineering artifact.

## Automated QEMU boot gates

The ISO build workflow runs direct-kernel, BIOS GRUB and UEFI GRUB tests on **the same newly built ISO**. The separate retest workflow uses an archived image and must not be taken as validation of a newer ISO.

GRUB tests capture multiple frames and require both serial evidence of an active graphical target and visual evidence of the Localzet desktop. A GDM login greeter is not sufficient.

In this experimental, non-installable Live image, `plymouth-quit-wait.service` is masked to avoid blocking `graphical.target` under slow QEMU software emulation. This is not the final branded boot animation configuration.

## Local graphical VM test (once the image passes CI)

The `scripts/run-live-qemu.sh` helper boots the Live ISO in a disposable graphical QEMU instance without attaching a physical or virtual hard disk. It supports BIOS and UEFI; it uses KVM only when the caller has access to `/dev/kvm`, otherwise TCG. It does **not** install the system.

The script is prepared but **the full BIOS/UEFI boot requirement is still not confirmed**. Do not rely on the image for regular work, installation or recovery.

## Guest session evidence

QEMU must demonstrate a usable guest session and actual desktop pixels; merely detecting `gdm.service`, `graphical.target` or `gnome-shell` in a process list is insufficient. The disposable image sends snapshots of GDM status, loginctl sessions, GNOME processes and user journal messages over a serial device for diagnosis. Serial logs can include system information; review them before publication. Boot diagnostics are for experiments only and should not be included in a production installed system.

The image includes GNOME Settings Daemon and Keyring support, and disables automatic locking only for the passwordless temporary Live account. Normal installed accounts must retain authentication and lock security policies.

A dedicated `build` job uploads an ISO; three independent QEMU jobs then download **that exact artifact** and test direct-kernel, BIOS GRUB and UEFI GRUB startup concurrently. The old retest workflow still uses archival ISO artifacts and is not proof for newer builds.
