# Localzet OS — dedicated SSD installer safety contract

**Status: design and read-only disk preflight only. This does not install an OS.**

The final Localzet OS must install to an explicitly chosen **separate physical SSD** from a signed, verified USB installation medium. Do not expose an "Install" button in the Live ISO until this contract has been tested in QEMU with multiple virtual disks, UEFI and BIOS modes, reboot, updates and failure recovery.

## Intended installer

Use the Ubuntu 26.04 Calamares 3.3.x package as a starting point, with independently versioned Localzet configuration in \`/etc/calamares\`. Never adopt a distribution's preconfigured partitioning, \`unpackfs\` or bootloader modules without reviewing every command and target path. Calamares' \`settings.conf\` and modules constitute the real installer; the preflight program in this repository cannot prevent Calamares from writing disks.

## Required sequence (not yet implemented)

1. Boot the signed installation ISO in UEFI or BIOS and make a **separate backup**.
2. Show all physical disks by persistent ID (WWN/serial), size, model, topology and current partitions; highlight every mounted and system disk.
3. Default to **no selection**. Do not auto-target an "empty" drive or infer the SSD from device order (\`/dev/sdX\`, \`/dev/nvmeXnY\` can change).
4. Require explicit selection of the dedicated SSD. Re-read its WWN/serial, partitions and mount state immediately before any write.
5. If multiple physical disks exist, display clearly which will be **untouched**. For an EFI install, never silently write the bootloader or ESP to another disk.
6. Show a complete dry-run partition/format/bootloader plan, with irreversible data-loss warning. Ask for a final deliberate confirmation that identifies the selected disk.
7. Only after independent preflight, full Calamares plan review and final confirmation may any write occur.
8. GPT + EFI System Partition + ext4 (or selected Btrfs) root. Secure Boot, encryption, dual-boot and reuse of existing ESPs need **separate** validated flows.
9. Installed user must have a real password, no Live autologin, no passwordless sudo and no serial debug service.
10. Verify the resulting SSD boots standalone, **with the other virtual disks absent**. Confirm GNOME login, networking, updates, reboot and logout.
11. Only then allow a manually downloaded release ISO and carefully reviewed USB writing instructions.

## Test matrix before release

| Scenario | Required outcome |
| --- | --- |
| One empty target SSD and a second OS disk | Only selected target changes |
| Multiple NVMe with misleading device ordering | Selection by persistent identity, not device path |
| Target contains existing filesystems | User sees explicit irreversible warning |
| Root or EFI partition mounted on candidate | Candidate blocked |
| USB/live installation medium appears as disk | Cannot be selected as target |
| Existing LUKS/RAID/LVM or unknown topology | Fail closed or require independent expert path |
| Power loss midway / bootloader install failure | Preserve other disks, show recovery guidance |
| Installed system with the Live medium removed | Boots independently |
| Installed system login | No automatic login, real authentication required |
| UEFI and BIOS | Both independently tested |
| Installer network offline | Clear error or supported offline installation |
| SSD size below minimum or read-only | Blocked |

## Read-only preflight

The inspector runs \`lsblk --json --bytes\` without root or writes. It does **not** select, partition, format or mount any device. A \`manual_review_only\` result is **not** permission to erase the disk:

\`\`\`bash
PYTHONPATH=src python3 -m localzet.installer.preflight
\`\`\`

Its output is diagnostic only. Final disk safeguards must live in the actual installer, not merely in a launcher or script invoked once before Calamares starts.

## Modules

Docker, Gaming, NetBird, UserNet and other optional components are not pulled into the minimal installation. Package selection and system integration will be developed and validated separately, with a user-visible list of changed services, permissions and packages.

**Release gate:** No installable ISO until the installer is end-to-end tested against disposable QEMU target disks with cryptographically checked backup images, and manual review of actual partition layout and boot location.
