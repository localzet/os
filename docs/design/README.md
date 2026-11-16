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
- Source branding is the owner's original [Localzet SVG](../../assets/brand/localzet.svg); do not redraw the
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

### Boot branding implementation

The separate `localzet-aurora` Plymouth theme uses the upstream two-step
renderer and its existing prompt/message animation resources, with a new
palette and watermark rendered from the canonical Localzet SVG. The build
checks the theme and logo in initramfs. This does not establish that the
splash is visible on every GPU/firmware; capture boot and verify password
prompts/recovery before acceptance. No foreign bootloader is modified.

## Midnight desktop correction (2026-11-16)

The owner supplied a blue/graphite desktop reference and rejected the flat
violet/grey engineering screenshot. This supersedes the earlier palette for
this candidate, not the functional acceptance contract. The proposed visual
baseline uses midnight blue surfaces, clear blue selection, a four-column
application grid with category navigation, larger identifiable color icons,
and a compact native panel. Preserve XTerm, original Localzet logo, actual
GNOME controls and installed app actions. Do not copy the reference's invented
hardware values, version labels or logos. A detailed alpine wallpaper, unified
native GTK/libadwaita windows, glass clipping, lock screen and installer remain
separate acceptance work. This change is not visual approval or a finished ISO.

### Midnight native application and boot palette

All seven Localzet GTK/libadwaita windows use a shared process-local provider
in dark mode only. Light mode and high contrast retain upstream colors;
no global GTK CSS, GTK_THEME override or external application patch is used.
Containers retains its compact workspace layout. GRUB and Plymouth use the
same blue/graphite palette and canonical logo; disk/authentication logic is
unchanged. Settings CI checks actual painted surface colors. External GTK
applications (including Nautilus) and lock-screen glass still need separate
review. This is a candidate, not a claim of finished visual acceptance.

### Executive command hub — implementation tranche 1

The supplied final poster is an appearance reference, not a screenshot or a
source of hardware facts. The command hub is a native GNOME Shell popup:
search first, category navigation, responsive app grid, actual favorites,
keyboard arrows/Home/End and real Settings/overview actions. No fake recent
files, power state or unsupported actions. System icons use filled silhouettes
and restrained material shading; third-party brand artwork remains upstream.
The remaining landscape wallpaper, rounded compositor glass, lock screen,
third-party window styling and actual hardware acceptance are not complete.

### Executive landscape — interim signed-archive asset

New installations and the GNOME devkit use the same Mt Shuksan photograph by
ezspain (CC BY-SA 4.0) from Ubuntu 26.04's signed archive package
`budgie-wallpapers-resolute`. The file is unmodified and the package's original
copyright is retained. No mutable external wallpaper download occurs during
installation. The existing original Aurora SVG is still available in GNOME's
background chooser; user overrides are not reset by the extension.
Source: https://discourse.ubuntubudgie.org/t/ubuntu-budgie-26-04-wallpaper-contest/8474/13
License: https://creativecommons.org/licenses/by-sa/4.0/
Archive: https://packages.ubuntu.com/resolute/all/budgie-wallpapers-resolute/filelist

This is a real 4K landscape candidate, not the final sunset/lake hero artwork.
The devkit now installs actual Nautilus, Epiphany and Settings packages and
uses the same four favorites as the installed image, rather than accidental
runner applications. Native icon theme and compositor behavior remain intact.

### Executive system controls and file manager review

Native GNOME Quick Settings now uses explicit split-toggle geometry,
RTL-aware corners, separate checked/hover/disabled/focus states, compact
sliders and notification actions. No fake controls or hardware states are
introduced. Dock separates the launcher from actual favorite/running tasks,
with an explicit high-contrast outline. New profiles use GNOME's supported
blue accent (not global GTK CSS). Visual smoke requires all four default
favorites and captures the real Nautilus window with disposable folders.
Nautilus keeps upstream libadwaita window chrome; no full custom window theme
or rounded compositor blur is claimed. Fresh visual acceptance required.

### Executive visual review correction

The aa1fdec devkit artifact 14222776153 captured actual launcher, Quick Settings,
notifications and XTerm, with four real pinned applications. The Nautilus
check failed because it launched via the outer Xvfb display, not nested Shell.
Launch Nautilus through the Command Hub and verify its real focused dock state
before navigating to the disposable folder and capturing. The launcher now
anchors to the full dock, icon size is 38 logical px, dock height 62, and the
launcher uses a filled, blue-neutral four-cell mark. Reduce oversized shadow
extents and align the native Quick Settings header controls. The landscape
is still brighter than the target artwork; this iteration does not assert
final visual parity or genuine rounded blur.

### Executive launcher composition

Separate real pinned apps from the catalogue on the default view. The remaining
installed apps appear once, in a smaller and denser grid. Search is global
across categories and includes desktop keywords. No fabricated recommendations
or recent history. Keyboard navigation accounts for the pinned row. The visual
smoke verifies that the actual four favorites are rendered separately.

### Executive Alpine Dusk

The brighter Mt Shuksan review was not accepted as the final look. New images
use a deterministic 3840×2160 dusk colorway of Mont Blanc from Arpy Lake by
puffettacicciottella, sourced from the same signed Ubuntu package. The
photograph is cropped and color-graded, not AI-generated or a copy of the
reference. Source and derived artwork are CC BY-SA 4.0; explicit attribution
ships with the package. The original Aurora and Mt Shuksan backgrounds remain
selectable. The build and devkit run the same offline generator; actual visual
acceptance is pending. The desktop package now generates the derived asset in postinst after its
archive and Pillow dependencies are configured; removal cleans up only the
generated asset. Existing preferences are unchanged.

### Executive native window language — Settings

Localzet Settings uses a real persistent navigation sidebar, separate page
headings and concise native preference rows. Home, Components and System
are keyboard-accessible via Ctrl+1/2/3; appearance launches the upstream
GNOME settings panel. No fake installation switches or telemetry. Shared
process-local dark provider adds restrained card borders, compact corners
and readable secondary text; explicit light and high contrast continue to
use the native style. No user-wide GTK stylesheet is installed. The actual
GTK smoke checks navigation and captures all three views. This is not a
Nautilus or third-party window theme.

### Executive material experiment and readability

The 97089bf GNOME visual run passed, including real Nautilus, and 9bc96c0
Settings GTK navigation passed. Review revealed low-contrast secondary text
and poorly legible stroke-based symbolic icons. Use filled monochrome shapes,
larger category symbols, explicit secondary text opacity, real row separators
and consistent Settings icons. The Command Hub can now attach a real
Shell.BlurEffect BACKGROUND to its rectangular menu content allocation in the
existing opt-in experimental session. No default enablement or rounded
clipping claim: the experiment is explicitly square and reverts to opaque
on high contrast or effect initialization failure. CI verifies effect
lifecycle and captures the actual menu; pixel-level blur validation,
physical GPU performance, lock-screen styling and final rounded glass remain
outstanding.

### Direct reference alignment — first poster / mountain Executive

Reopened both owner-supplied design references. The first is the shell target:
compact category sidebar and four-column application grid; central dock with
terminal, browser, folders, images, settings and trash; dark file manager
with smaller blue folders. The second supplies the application information
architecture (Containers, Windows/Gaming, Network), not a competing palette.
The prior pinned-card section diverged from the first reference; remove it,
retain real favorite ordering and global search. Add a real non-destructive
trash URI shortcut and five default app favorites. No fake VS Code icon when
it is not installed. Nautilus uses smaller upstream zoom and the proper
GNOME Settings portal in the image. Devkit dark preference is an explicit
CI-only libadwaita override because its session is not the installed session;
verify real dark pixels, not just process existence. This does not yet
implement bespoke Nautilus chrome, the exact hero wallpaper, or lock design.

### Glass optical verification correction

cf38abf's visual test passed the effect attachment/lifecycle checks, but the
actual screenshot showed essentially unblurred wallpaper: a blank-menu ROI
had tint-normalized horizontal edge standard-deviation ratio about 1.02 and
luminance correlation 0.996 against the idle frame. This is not accepted as
true visual glass. Attach the experimental effect to the outer PopupMenu
actor (matching the panel's top-level background sampling) and capture an
empty-menu diagnostic against the idle image. Record a tint-normalized
spatial-detail metric; it is diagnostic, not a validated acceptance threshold.
No default enablement until optical and hardware validation. The devkit-only
GTK dark/icon settings are inherited by D-Bus activation, and the trash
shortcut explicitly opens the installed Nautilus app with a trash URI.

### Extension lifecycle correction

The de6512d visual run failed before its first capture: duplicate extension
activation registered localzetExecutive twice. Five real pinned apps did
resolve. Configure the devkit's extensions before GNOME starts, remove the
initial racing enable requests, retain the deliberate disable/re-enable
check, and reject indicator conflicts in the log. The extension now owns
one complete instance per panel and rolls back its own actors on a failed
activation; the panel constructor cleans up on failure. No new visual
acceptance claim is made until the corrected run passes.
