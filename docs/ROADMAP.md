# Roadmap — Aurora Complete product acceptance

Status: engineering candidate, not a stable release. Individual CI passes do not imply Complete acceptance. The owner's design references are binding; technical boot success is not design approval.

## P0 — installation and release safety
- [x] Ubuntu 26.04 / GNOME 50, BIOS and UEFI Live boot including software emulation (577508a, run 44111089277).
- [x] Blank dedicated NVMe installation, reboot without ISO, authenticated GNOME in separate interactive candidate (44111089771).
- [x] VM-only installation engine and foreign disk integrity test (separate VM path).
- [ ] Exact unified Complete ISO install + all applications and real screenshots.
- [ ] Multi-disk interactive installation: currently intentionally refuses additional disks; do not remove guard without design review and verified non-target preservation. First-release workflow tests refusal, then a separate disconnected-disk install.
- [ ] Real SSD, Secure Boot, encryption, recovery boot, update/rollback, production signing and redistribution review.

## P1 — design is a release gate (not accepted)
- [ ] Aurora Executive / Soft Graphite: actual 1440p/4K desktop, not GNOME overview or mockup; restrained graphitic surfaces, subtle depth, compact dock, no oversized round tiles or glowing decoration.
- [ ] Cohesive original icon family across built-in, system and third-party app entry points, light/dark and high contrast; no claim that fallback Adwaita is a completed icon set.
- [ ] Native compact command hub, panel, quick settings, notifications, native Files, Settings, terminal, lock/login, Plymouth, GRUB and installer all visibly aligned with owner references.
- [ ] Screenshot acceptance: empty desktop, launcher, Files list/grid, Settings, quick settings, notifications, lock/greeter, installer, Office, Containers, Windows and network apps. Actual default session at 1080p, 1440p and 4K, light/dark and accessible high contrast. No special experimental environment to pass design review.
- [ ] Owner acceptance of actual running system; current screenshots are not approved.

## P2 — Complete functionality
| Requirement | Current evidence / remaining work |
| --- | --- |
| Windows applications | Wine x86/x64 and original MSI fixture passed separately; user-owned menu shortcuts with saved profile and explicit trust prompt passed source/GTK/Wine fixture CI; real app matrix, installer UX, default file associations and lifecycle still pending. Wine prefixes are not sandboxes. |
| Windows gaming / Witcher 3 | Lutris, GameMode, MangoHud, Vulkan Tools and Mesa Vulkan declared as actual signed archive dependencies for Complete. App center supports user-initiated Steam/Heroic installation. No verified game launch; Proton, DXVK/VKD3D, GPU/controller tests required. |
| ONLYOFFICE | Native pinned package and offline rendering verified; exact Complete and redistribution review still open. |
| Microsoft Office | Microsoft 365 web entry and optional licensed Windows-guest path only; no native desktop installation or verified Office compatibility. No license bypass or unauthorized activation. |
| NVIDIA CUDA | Experimental installer-authorized first-boot driver + CUDA orchestration, architecture selection and real compute probe exist. No physical NVIDIA execution evidence, opt-in default off. |
| Other hardware | Baseline firmware, microcode, Mesa/Vulkan planning/transactions; actual devices, hybrid graphics, printers and suspend/resume unverified. |
| GPU Unlocker | Read-only compatibility/readiness for Zagitta/gpu-unlock; no activation or privileged firmware exploit integration. |
| Containers | Native GTK application + real Docker/Compose lifecycle tested; Docker Desktop/Portainer parity, registry, Compose stacks, logs, resource metrics, storage and GPU container acceptance still open. |
| NetBird | GUI and backend integration prototype; real peer enrollment, routes, DNS, auth, daemon installation and lifecycle still pending. |
| UserNet | Upstream review and network GUI; real UserNet endpoint, setup, lifecycle and policy acceptance pending. Proxy-only namespace experiment is not integrated desktop policy. |
| Codex / Claude Code | AI namespace/proxy fixture, package planning; actual CLI install/auth and real UserNet path pending. |
| NectarLink | Pinned package verification and installer entry point; real Android pairing pending. |
| Telegram, Yandex Music, VS Code, browser choice, Discord | Telegram and Discord have a user-local Flatpak install path; VS Code, Chrome, Edge and Yandex Music point to publisher downloads. No claim of preinstallation; exact installed first-run and redistribution review pending. |
| Media and development | Archive packages in Standard/Complete; separate installed checks passed, full UX acceptance pending. |
| Updates/recovery | Read-only recovery diagnostic and kernel menu entries verified; real recovery boot, updates and rollback pending. |

Next milestone: verified Complete engineering ISO and reference-driven desktop acceptance in parallel. No final release until required product and safety gates pass.

Application center workspace: compact native navigation, installed-only view based on detected executables/Flatpak IDs, search and explicit action/source state. GTK navigation and screenshot tests cover dark/light, games and search. This does not constitute final visual acceptance.

Managed rootless Docker: explicit user service start/stop passed real Ubuntu package CI, including BusyBox container and image persistence across service restart (44344220408). Exact installed-image engine test remains required. Windows shortcuts, rootless engine and app workspace are integrated in the next candidate; no design or release acceptance claim.

Telegram engineering preload: explicitly opted-in Standard/Complete build downloads a system-wide stable x86_64 Flatpak from the official Flathub remote with GPG verification enabled, records exact app/runtime commits, and installs into the actual image, not the build host's desktop. The installed-image gate checks commit, exported desktop entry, catalog detection and actual unprivileged offline sandbox launch. This is not a redistribution approval; final source/license review, download size and reproducibility/pinning of the resolved app and runtime remain open. Native installed VS Code, Chrome and Edge are detected in the catalog; their delivery is not yet preinstalled.

Compact application workspace adds actual system tools, media, virtualization and Windows Runtime entries to the same curated catalog, with detected launch state and delivery mechanism. Compact rows and navigation, reduced corner radii and margins, graphite sidebar only in normal dark appearance; high-contrast and light styling remain toolkit-controlled. Existing GTK screenshot workflow captures the System category and invokes the preloaded Telegram test as a reusable workflow for the corresponding development branches. Not a claim of visual acceptance or actual preload success.

The first system Telegram build (44404859616) failed in the customize hook immediately after the desktop package, before any Flatpak download. The preload now allows a package-initialized empty system repo, refuses existing deployed refs or unknown remotes, validates the exact official HTTPS origin and GPG verification, and emits explicit phase/line diagnostics. The original guard is a plausible cause, not confirmed until the revised image passes. Separately the b8a23a8 unified engineering candidate passed all 19 CI workflows and published its exact image; later managed Docker, AI and preloaded apps are not covered by that result.

Revised Telegram build 44407036040 successfully deployed the signed app and runtime, then failed because the installed Flatpak list command lacks a commit column. Record each deployed ref with flatpak info --show-commit and --show-origin instead. Compact Apps 44407036197 produced all requested screenshots but raised NameError while refreshing delivery labels; the row binding is corrected, and CI now emits the full GUI log on failure. Neither previous failing run is accepted as release evidence.

Executive desktop refinement: preserve the real upstream panel controls and high-contrast fallback; use the same packaged Aurora application glyph in the panel and dock, a separated command entry, restrained graphite borders, reduced dock corner radius and distinct focused task styling. No new compositor effect or changed window/lock behavior. Visual acceptance remains subject to GNOME 50 real screenshots.

Unified preloaded candidate branch integration/aurora-complete-preloaded combines the current exact tree of shell refinement, corrected office launcher, rootless engine, AI workspace, compact Apps, Telegram and network preload. It builds the exact branded Nautilus and Control Center packages and one ISO, checks BIOS/UEFI, foreign-disk refusal, authenticated desktop, offline preloaded Telegram and network provisioning, actual rootless container lifecycle, office document ink, x64/x86/MSI Wine and lock. Artifact publication remains after successful required gates, with explicit engineering-only inventory and preload receipts. b8a23a8 remains the separately verified earlier engineering image; do not conflate it with this newer candidate.
