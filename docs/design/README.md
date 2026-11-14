# Aurora Professional — approved product and design baseline

**Approved by the project owner on 2026-11-14.** The fourth-panel Professional
poster (Desktop / Containers / Windows & Gaming / Network & Continuity) is
the approved visual direction. This is a product target, not current ISO
screenshots or a statement of implemented compatibility.

## Canonical reference

- Original file: `aurora-professional.png` (1536 × 1024)
- SHA-256: `0352fc93154997b1bb7e3510a797f2fc74a257477957b9a023ab6fe1261622af`
- The PNG must be added unchanged to this directory. The image is not yet
  present in Git; the current connector can write text, not access the
  local binary. The source artifact is the exact owner-approved poster.
- Use the written specification here as the normative source for behavior.
  The poster's demo CPU, memory, IP addresses, battery, game compatibility,
  version labels and connection indicators are illustrative, not measured
  results. Do not copy inaccurate text or generated brand variants.
- Source branding is the owner's original Localzet SVG; do not redraw the
  cat logo from generated artwork. NectarLink and NetBird retain their
  upstream names, icons and attribution.

## Aurora Professional

Dominant violet `#9B72F2`, orange accent `#FF7E00`, deep background
`#10091E`, tinted surface `#28183F`, elevated `#34234F`,
deep violet `#6436B5`, foreground `#F4EEFF`.
See [design tokens](../../assets/design-tokens.json).
Use a restrained, adult professional aesthetic, not playful giant cards.
Compact tables and information hierarchy; 32 px target top bar, 32–36 px
table rows, 6–8 px control radii and 12–14 px window radii (logical pixels;
larger accessible targets when requested). Subtle soft shadows, one coherent
type scale and aligned controls. Preserve readable contrast, keyboard focus,
HiDPI, RTL/localization compatibility and reduced motion/transparency.
No heavy uniform outline, glowing every element, or candy-colored chrome.
Orange for primary action and meaningful selection, not every slider,
icon or border. Green and red remain semantic status colors.

Real glass means compositor-backed background sampling/blur, restrained tint,
directional highlights and depth, optionally measured performant refraction.
Opaque fallback is preferable to cheap alpha-only imitation. Keep long-form
content and tables readable. Do not use web backdrop-filter syntax in Shell.
Verify on real GPU and software rendering, varied backgrounds and scaling.

### Desktop and system UX

- One coherent top bar: overview/workspaces, time, system status, integrated
  Quick Settings. No competing custom launcher, duplicate status buttons
  or permanent floating window overlapping full-screen content.
- Compact configurable dock: real app icons, running/focus state, context
  menus, keyboard access, favorites and full-screen handling. Professional
  icon family including Files/Nautilus; upstream brands unchanged.
- Aurora wallpaper, lock screen, GDM, GRUB and Plymouth share the same
  restrained brand. No default boot-log wall; diagnostics option remains.
- One settings entry point based on GNOME Control Center; integrate native
  Localzet panels without losing upstream settings. Remove stock Ubuntu logo
  in About. Settings: appearance, displays, sound, network, privacy,
  accessibility, updates, Windows, games, containers, phone, VPN and proxy.
- Software center, file manager, search, terminal, notifications, resource
  monitor and backup/recovery must work; no decorative inert controls.

## Full product scope

See [profiles and applications](PROFILES.md) and [acceptance gates](ACCEPTANCE.md).

### Containers

A first-class Localzet Containers app, with Docker Desktop / Portainer
as capability benchmarks, not a claim of present parity. Native Docker
Engine and Compose, rootless preference, explicit authorization for rootful
engine access; local and remote contexts (SSH/TLS), real inventory/status,
create/start/stop/restart, inspect/exec, live logs/metrics, images/builds,
registries, volumes, networks, Compose stacks/YAML editor, import/export,
backup/restore and safe destructive confirmations. Design is dense table
and split-pane workspace, not a tile launcher. No unrestricted socket
permissions, docker-group auto-enrollment, or root GUI. Test actual actions,
credentials redaction, resource usage and interruption/recovery.

### Windows and gaming

Per-app Wine prefixes, EXE/MSI install and uninstall, dependency/runtime
selection, 32/64-bit, DXVK/VKD3D, Winetricks, graphics/audio/input, file
associations via explicit user choice, native app menu, shortcuts, launch
logs and backups. Prefixes are not a security sandbox. Optional VM fallback.
Games: Steam/Proton and GOG/local installers, per-game configuration,
runtime compatibility and library management. The Witcher 3: Wild Hunt is
the required showcase acceptance scenario, using a legally acquired copy.
Install, first launch, graphics/audio/input, save/load, re-launch and
performance on physical supported GPU; no bundled game binaries, no universal
Windows or anti-cheat claim. Use verified compatible runtime rather than
copying version numbers printed in the concept.

### Network and continuity

NetBird (upstream) private networks, peers, routes, DNS, exit nodes and
connection status; UserNet proxy profiles/subscriptions/rules using reviewed
mihomo backend. One network policy model: per-app Direct, NetBird or
Proxy Only, explicitly defined precedence, DNS/IPv6/UDP handling and no
leakage if a required proxy is down. Telegram is mandatory in Standard
and Complete; Discord optional. Both use Proxy Only if that policy is
enabled, never silently fall back; no embedded credentials or bypass of
permissions. Reconcile NetBird and UserNet DNS/routes, prevent loops,
test failure and reconnect. UI must reflect actual service state.

NectarLink by thtbee: unmodified official client, explicit pairing,
real tray menu and supported status/actions in Quick Settings, no parallel
CLI identity. Phone name/battery only from a supported live interface.
Files, ring, camera, scan, notifications, screen and other actions only
where permitted and implemented upstream. No fake connection status;
no automatic grant of clipboard, camera, microphone or input permissions.

## Change control

Owner-approved reference + this specification govern subsequent visual work.
Track changes to exact design and scope in pull requests. Any change of
brand colors or major navigation requires owner review. Engineering
screenshots and automated tests are necessary but not sufficient for release.

### Current glass experiment (not release acceptance)

`panel.js` introduces the rectangular native top bar background effect using
`Shell.BlurEffect` in BACKGROUND mode. Default remains opaque until real
pixels, damage/repaint, performance and contrast are verified; only the
GNOME devkit CI session enables `LOCALZET_EXPERIMENTAL_GLASS=1`. High-contrast
mode reverts to native GNOME styling. CI captures before the phone test and
exercises disable/enable. The effect-creation marker is not a visual proof.
Rounded dock/popovers require a proper mask, not a rectangular blur leaking
outside rounded corners. No global redraw hacks, no forced transparency on
third-party windows. See upstream API:
https://gnome.pages.gitlab.gnome.org/gnome-shell/shell/class.BlurEffect.html
