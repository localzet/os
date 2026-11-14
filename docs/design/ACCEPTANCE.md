# Implementation and release acceptance

No production release until approved visual direction and actual functionality
are demonstrated. The physical alpha failed; do not treat QEMU-only evidence
as product readiness. See [physical-test rework](../PHYSICAL-TEST-REWORK.md).

| Area | Acceptance evidence |
| --- | --- |
| Storage | VMD/RST/NVMe and AHCI detection on real hardware; distinguish controller absence from safety policy rejection; no unsafe RST toggles. |
| Installer | Review Calamares/Ubuntu installer backend. Explicit stable disk ID, separate SSD or explicitly selected unallocated space, before/after plan; preserve existing partition contents and EFI/GRUB/Windows Boot Manager. Existing ESP never formatted; unique EFI loader path, no overwrite of shared fallback or foreign GRUB. Boot both OSes, hash non-target data, fail safely on interruption/encryption/RAID/ambiguity. |
| Desktop | Actual fresh ISO screenshots matching Professional design, multiple DPI/screens, keyboard, mouse, no clipped icons/labels, no duplicated UI, normal/fullscreen dock behavior, contrast and performance. |
| Glass | Compare detailed, bright and dark backgrounds; demonstrate real blur and fallback, verify GPU and CPU rendering, no severe animation/frame regressions. |
| Settings | One Control Center entry, all upstream panels intact, working Localzet integrations and About branding. |
| Office/apps | Installed profiles and verified official sources, all selected desktop IDs, launch/open/save tests, Telegram mandatory in Standard/Complete, proxy failure tests. |
| Containers | Actual rootless and rootful authorization tests; live Compose lifecycle, image/volume/network management, logs, metrics, terminal, remote contexts and rollback; no fake stats or insecure API. |
| Windows | EXE/MSI, 32/64-bit, graphics, profile isolation of configuration, menu integration, backup/uninstall, Windows Runtime test evidence. |
| Gaming | Legally acquired Witcher 3: installation, launch, in-game operation, save/load, GPU performance, relaunch; Steam/Proton/GOG sources and constraints. |
| Network | NetBird + UserNet route/DNS coexistence; Telegram/Discord proxy-only no direct bypass including IPv6/UDP/DNS and reconnect; no credentials in logs. |
| NectarLink | Actual upstream tray menu, Android pairing, revoke/reconnect, real status and permission-aware actions. |
| Release | Signed update/build provenance, redistribution review, boot/recovery/physical QA, owner review of fresh screenshots and feature matrix. |

Milestones: hardware and safe installer foundations; desktop design system
and real compositor glass; profile provisioning; container/network backends;
Windows/gaming; integrated QA. Keep each milestone truthful and separately
testable; don't ship an alpha with placeholder features enabled by default.
