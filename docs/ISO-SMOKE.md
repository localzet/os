# ISO boot smoke testing

The harness tests a supplied x86-64 ISO, not a source checkout. It uses QEMU TCG, no network, no host disk passthrough, and a temporary copy of UEFI NVRAM. It fails if the guest does not emit the exact expected serial line before the timeout.

## Guest contract

A future Live image must enable serial output on ttyS0 and emit a unique line such as LOCALZET_LIVE_READY only after its boot readiness checks pass. Do not emit this line from the bootloader or unconditionally at service startup. At minimum, check the expected OS identity, Live root filesystem and graphical session readiness. A staged producer and systemd unit are provided in `packaging/live/`. The experimental ISO builder installs the Python file at `/usr/lib/localzet/localzet-live-ready.py`, install the unit in `/usr/lib/systemd/system/`, and enable it only in the Live root. The probe requires `boot=casper`, an overlay root, `ID=localzet`, an active display manager and a local active Wayland GNOME session for `localzet`. It does not verify rendering or the shell extension. Remove the unit, enablement symlink and script from the installed root.

## Run

On a Linux host with qemu-system-x86 and ovmf installed, use the matching OVMF CODE and VARS pair from your distribution (paths below are examples).

```sh
python3 scripts/qemu-iso-smoke.py dist/localzet.iso \
  --firmware bios --marker LOCALZET_LIVE_READY --log dist/bios.log
python3 scripts/qemu-iso-smoke.py dist/localzet.iso \
  --firmware uefi --ovmf-code /usr/share/OVMF/OVMF_CODE_4M.fd \
  --ovmf-vars /usr/share/OVMF/OVMF_VARS_4M.fd \
  --marker LOCALZET_LIVE_READY --log dist/uefi.log
```

Use a disposable output directory. The log is overwritten on each run. An exit code of 0 means the marker was observed, not that installation, Secure Boot, networking, graphics performance or hardware compatibility were tested. A timeout or early QEMU exit without the marker fails the test. CI should publish both logs even on failure.

## Remaining release gates

- Validate the experimental ISO build and integrated guest marker producer.
- Run both firmware modes against that exact artifact.
- Separately exercise installation into disposable virtual disks, reboot from the installed disk, and run the post-install audit.
- Test graphics and physical hardware before claiming installation readiness.

## Desktop package stage

Run `make desktop-deb` to package the source tree into a rootless build of
`localzet-desktop_0.1.0~dev1_all.deb`. Inspect with `dpkg-deb --info` and
`dpkg-deb --contents`. Install only into a disposable Ubuntu 26.04 image.
It includes the extension, Settings, module manifests and wallpaper, but does
not enable the extension, configure GDM, build a Live root or install a bootloader.
Keep the Live readiness service separate from the persistent desktop package.

## Experimental end-to-end build

Run only in a disposable amd64 Ubuntu build VM. The first run can consume
substantial disk space; use a new directory with at least 35 GiB free.
This is a Live-only developer image, **not an installer**.

```sh
sudo apt-get update
sudo apt-get install mmdebstrap ubuntu-keyring squashfs-tools xorriso grub-common grub-pc-bin grub-efi-amd64-bin mtools
sudo env LOCALZET_DISPOSABLE_VM=1 bash scripts/build-live-rootfs.sh /var/tmp/localzet-root
sudo bash scripts/assemble-live-iso.sh /var/tmp/localzet-root /var/tmp/localzet-dev.iso
```

The bootstrap uses signed Ubuntu Resolute release, updates and security
archives, not a frozen snapshot. It installs the local desktop DEB, Russian
and English locales, GNOME 50, Casper, the kernel and the readiness service.
The ISO uses GRUB BIOS and UEFI boot entries, with Russian selected by default.
No physical disks are accessed for installation. Secure Boot, graphical
rendering, localization coverage, actual boot and device installation are
not proven by successful ISO assembly. Do not publish as a release until the
firmware smoke tests and licensing/security review pass.
