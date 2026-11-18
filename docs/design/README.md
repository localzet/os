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

### Reference material: static wallpaper glass

1bbcd4e passed GNOME visual smoke and Live ISO, but the dynamic blur diagnostic
was 0.991: no meaningful optical detail reduction. Remove that experiment from
the launcher. Generate a separate 4K preblurred/tinted derivative of the exact
shipped Alpine Dusk wallpaper (same attribution), use a native rounded St
background image with monitor-aligned zoom coordinates, and reject it for
other wallpapers, visible windows, high contrast, multiple monitors and
non-1x scaling. No screenshots of private desktop content are captured or
stored by the extension. The existing dynamic panel experiment is unchanged.
This is wallpaper-only glass, not dynamic live-window glass. The CI now
requires actual optical detail reduction, not just successful effect
attachment; failures block visual acceptance. No full reference parity claim.

### Executive Complete engineering preview

The c8eadee optical test passed with a tint-normalized detail ratio 0.033
(versus 0.991 previously). The real image-backed menu still showed a
rectangular shadow halo; remove the shadow and outer arrow background
rather than claim a rounded dynamic compositor effect. Keep the genuine
native Nautilus, which now rendered dark in the devkit.

The separate integration/executive-complete-preview branch uses the
existing Complete archive + Containers + ONLYOFFICE + Wine installer
workflow, adds an installed-session wallpaper/material verification and
native lock-state check after the Wine fixture. Publish the exact ISO,
checksum, checked-out commit and actual archive plan only after a
successful trusted same-repository PR run. This is an engineering
candidate, not a release or physical SSD acceptance. Pending external
clients, GPU unlock and licensed desktop Microsoft Office are not
represented as installed. No lock bypass or authentication changes.

### Executive system actions and self-contained extension ZIP

PR 91 commit 486db7d passed the optical visual test (0.033). The reference
calls for network and continuity entry points in Quick Settings. Register
native GNOME QuickToggle widgets as non-toggle push buttons for the actual
installed Localzet Network and NectarLink Setup desktop applications. Never
present fictional VPN/proxy/phone state or expose actions on the locked
session. Respect the native high-contrast menu and clean up on extension
disable. CI installs the real desktop package, checks both items, clicks
Network and verifies the actual app launches. The separately distributed
extension ZIP now includes wallpaper-glass.js and quick-actions.js, and
validation rejects missing relative JS imports. This does not yet implement
live VPN toggle controls or native lock-screen styling.

### Executive native lock appearance

The Quick Actions visual check reached the genuine Network activation but
used the wrong Python module pattern; the installed executable is
/usr/bin/localzet-network. Check the actual command and focused dock state.

Separate visual-only extension localzet-lock@localzet.com uses GNOME's
documented user/unlock-dialog session modes, loads a small CSS sheet only
when locked, and unloads it for high contrast or on disable. Clock typography,
date and notification surfaces follow the first reference. No changes to
authentication, password widgets, parental controls or input handling.
The regular desktop extension remains user-session only. Package and enable
the separate stylesheet extension in new images. Installed VM acceptance
requires native lock state, the visual extension and no active desktop
extension, plus a journal marker and real lock screenshot. No physical
hardware or actual lock visual acceptance claimed yet.

### Native Files — Executive package review

The ae0a7db devkit run verified actual Localzet Network activation and a
focused window. Native Files remains visually too close to upstream. Rebuild
Nautilus 50 from signed Ubuntu source packages, retaining distro patches and
upstream tests. Append a stylesheet scoped to window.nautilus-window only in
normal-contrast dark appearance (GTK 4.20 media queries). Blue-gray sidebar,
header and file surface, compact breadcrumb, selected rows and reduced
corner radii follow the first reference. Preserve light/high-contrast,
user accent, navigation, tabs and actual file operations. CI captures real
windows in all three modes and checks palette pixels and navigation.
No global CSS override, no dpkg diversion, no replacement file manager.
Package experiment only: integration into the ISO and security-update path
require successful native build and visual review first. Complete candidate
continues separately on PR 91, without cancellation.

### Installed visual acceptance correction

PR 91's Complete engineering ISO passed USB install, authenticated Wayland,
archive package inventory, unprivileged Containers, a native ONLYOFFICE
window and Wine fixture exit 42. Artifact 14226327961 is an engineering
snapshot, not a release. On manual image review the ONLYOFFICE screenshot
was effectively blank white and the lock frame showed QEMU display inactive.
Those screenshots do not prove usable rendering or lock appearance. Require
a nonblank central application region, multiple detailed image tiles and
color diversity, plus actual lock display wake via pointer motion and a
second LockedHint check. These metrics reject obvious blank captures, not
all rendering faults. No password or unlock input is generated during lock
review. Keep the verified preview available while this separate branch runs.
The dock now reserves a native bottom workarea strip to prevent maximized
windows overlapping the floating dock; fullscreen behavior remains native
and needs visual verification.

### Native Files integration candidate

PR 93 built and installed all three Nautilus 50.2.2 packages and verified
actual dark palette pixels and directory navigation. The test failed after
navigation during tab/quit handling in the unmanaged Xvfb session; light and
high-contrast were not reached. Use a disposable Openbox window manager,
verify two real tab locations and treat teardown separately from acceptance.
Only after all three visual tests pass, build an exact source-matched Complete
candidate using the same workflow's Nautilus package artifact and checksum.
Reject version drift; keep Ubuntu updates unpinned. Verify installed versions
and process launch, Wine, office visual gate and lock state before upload.
The already published PR 91 snapshot is unchanged. New installed lock logs
from PR 92 confirm the visual-only extension active and desktop extension
inactive, but its screen capture was still inactive; office remains blank.
Neither is considered visually accepted.

### Office render isolation and installed test integrity

PR 91 and PR 92 installed official pinned ONLYOFFICE but captured a blank
window. Avoid repeated full ISO rebuilds while isolating that rendering issue.
Test default and software graphics independently on disposable Ubuntu 26.04
Xvfb sessions, in a separate network namespace, using a generated original
local DOCX fixture. Require a document-named window and nonblank pixels.
This is an X11 diagnostic, not a Wayland or QEMU acceptance substitute.
The software path uses scoped Mesa/Qt software rendering and --disable-gpu;
no global rendering override or sandbox bypass. Official guidance explains
graphics acceleration settings: https://helpcenter.onlyoffice.com/desktop/getting-started
No default flags are changed before comparing real evidence. Add source tests
for generated installed-script assertions, and fail if injection markers
are absent or duplicated. Preserve the active Native Files ISO build.

### Native rendering dependency and navigation correction

The first isolated office run failed before graphics initialization:
libxcb-shape.so.0 was missing. Reuse the full explicit Ubuntu graphical
runtime already exercised by the upstream office workflow, in both the
isolated test and rootfs dependency transaction. Record ldd output and
reject missing libraries; the white installed window is not yet diagnosed
by this fact alone. Capture missing-window diagnostics and fail fast if
editor exits. No sandbox changes or forced software mode in the image.
The Native Files build validated dark navigation and two tabs, and light
palette contained zero Executive pixels. Its light navigation then failed.
Use Nautilus 50's explicit Alt+1/Alt+2 tab shortcuts and bounded title polling,
with failure screenshots. The latest branch can run the same trusted
Nautilus installed-image gate after all three modes pass.

### Office window evidence: exact drawable, not overlapping screen

144cf70 passed both offline document render modes with identical metrics
(0.7534 dominance, 25 detail tiles, 32 colors), and the real screenshot shows
the fixture document. No software rendering default is needed. PR 94 passed
its numeric screen gate and native lock wake/recheck; manual review confirmed
the real lock clock but the alleged office screenshot instead shows Hardware
over a white editor. Reject this as an office false positive. Open the same
synthetic DOCX in the installed guest, stop only earlier transient test units,
require its title and focus, capture the exact X11 drawable, require the blue
heading ink inside the page region, and transfer the bounded PNG to the host
for independent validation. Do not inspect real user files or change security
settings. Existing PR 96 runs remain intact; this branch can build a new
Native Files candidate only after all gates succeed. The QEMU document gate
is still pending; isolated X11 success alone is not installed OS acceptance.

### Soft graphite — owner screenshot correction

The owner supplied their Ubuntu Files screenshot and preferred the softer
Ubuntu/Zorin style. Actual dominant screenshot colors are approximately
#1d1d20 content, #393939 sidebar and #3b3b3d selection. Replace the previous
saturated navy Native Files material with slightly cool graphite #202124,
#343539, #303136, and a nearly neutral accent-tinted selection. Restore
9px corners, remove the hard header and breadcrumb borders, retain native
spacing and user accent. Keep light/high contrast untouched. Add actual
list-view captures in addition to grids and tab navigation. This is a
source-level visual correction, pending real package screenshots. The shell
and other application palettes are unchanged until the Files review.
The preceding PR96 installed-image job failed inside the rootfs hook
without a specific diagnostic. Add explicit checkout, checksum and source
version mismatch errors; do not bypass verification. The exact rootfs
failure cause remains unconfirmed. Preserve existing document-gate runs.

### Soft native applications and canonical package manifest

The actual owner screenshot has dominant colors #1d1d20, #393939 and
#3b3b3d. Extend the Soft Graphite approach to process-local native Localzet
applications using the existing appearance provider: neutral graphite
background, quiet cards, subtle row separators and blue primary actions/focus.
Settings uses the same lighter sidebar and soft selection as Files. Keep
upstream light/high contrast, keyboard focus and text legibility. CI tests
must confirm actual Settings pixels; other native applications share the
provider but remain pending their own visual review.

PR96 and PR97 package jobs passed but their rootfs hooks failed before the
Nautilus version log. The downloaded PR97 artifact proves the mismatch:
SHA256SUMS uses ./libnautilus-extension4... while the installer generates
libnautilus-extension4... without ./; the string manifests differ despite
identical hashes. Use a single canonical basename generator in both paths,
reject symlinks and unexpected file count, and test tampering. No checksum,
source version or exact checkout checks are relaxed. This separate branch
preserves PR98's actual Files appearance review.

### Soft shell correction and real list-view evidence

PR99 Settings visual smoke passed, all three pages and real neutral palette
pixels. Source checks failed because an old test still required the boot
Midnight palette in the native provider. Split native application, shell
surface and boot token assertions; retain the original boot/GRUB colors.
Apply neutral graphite to dock, panel, launcher, quick settings and calendar
surfaces, leaving real enabled controls, focus and active window indicators
blue. The wallpaper-only blurred derivative receives the same graphite tint;
the optical test must still pass. No dynamic blur claim.
PR98 dark and light palette/tab checks passed, but high-contrast navigation
failed with an autocomplete-generated Documents... typo. Its dark list
capture was actually a grid. Require four blue folder glyph rows before
accepting list evidence, and use clipboard paste rather than per-character
typing in the location field. Keep high-contrast palette and navigation
checks. Update PR99 in place since its source gate is already red. Earlier
PR97 installed test remains separate. New appearance still needs visual CI.

### Installed Office hang diagnosis

PR99 shell optical test passed with 0.028 detail ratio; Settings and shell
are confirmed Soft Graphite. PR97's failed installed screenshot shows a
real ONLYOFFICE skeleton/loading screen and GNOME's not-responding dialog.
The blue heading test detects 1463 pixels on the actual successful offline
document screenshot (minimum 250); keep its threshold. The previous
installed fixture lived in a root-owned /run directory; make a new writable
test-user-owned directory instead, record memory, /dev/shm and GPU info,
collect application journal and kernel denial/OOM evidence on failure,
and retain the actual failed drawable without flooding CI output.
The office-only workflow on this branch is an explicit scoped software
render diagnostic (same switches as successful X11 matrix); the Native Files
installed candidate continues to require default rendering. No sandbox
disable, no global renderer override. A diagnostic success is not a release
pass. Host wait now allows the bounded guest test to finish. PR99 package
build remains independent; no earlier test is cancelled.

### Reliable native list review

PR100 rebuilt the signed-source Nautilus 50.2.2-0ubuntu0.2+localzet1
successfully, with canonical checksum manifest. The dark palette was
confirmed, but the visual list check rejected six identical grid captures.
The two PNGs are byte-for-byte identical. Do not weaken this gate.
Instead, launch a fresh Nautilus process on a fresh directory using the
upstream default-folder-viewer=list-view setting, independently of the
grid process, and require changed content pixels plus four vertical blue
folder rows in the dark capture. Keep the list open for actual directory
navigation and tab switching. Light and high contrast still require
distinct grid/list captures and native navigation. No user preference is
changed by the shipped image; this is a disposable runner test only.
The current installed office diagnostic remains in progress on PR100.

### Reference correction — unified desktop material and command hub

The owner explicitly rejected the latest graphite panel/dock review. The stored written reference specifies a compact central dock and a four-column catalogue, identifiable color icons, softened layered material and a mountain/lake dusk composition. The original PNG is not available in the current repository, so this is a design iteration from the recorded specification, not a pixel match. Reuse the optically verified wallpaper-only material for both launcher and dock at their actual allocation; switch to opaque with a visible window, unsupported wallpaper, scale, monitor layout or high contrast. Larger 36px dock icons and 40px launcher icons remain compact; four rows fit normal desktop heights, with distinct sidebar, two-line labels and real software center entry. Preserve native panel, authentic application actions and lock behavior. The visual test must observe the dock material transition and retain the actual optical menu test. No dynamic compositor glass or final owner approval claimed.

### Network workspace — actual application composition

The c2f436f visual gate passed (44414495397, optical ratio .031), but the actual Network capture shows a long single settings form with stacked buttons and excessive scrolling. Recompose into a fixed navigation sidebar and three real views (NetBird VPN, UserNet proxy, system/install status), compact horizontal actions, common visible provisioning feedback and Ctrl+1/2/3 navigation. No fabricated status, enrollment or privileged policy changes; preserve actual asynchronous status and install behavior. Improve launcher two-line label height. Native GTK screenshot/navigation acceptance is required before integration; no final design claim.

### Containers Soft Graphite correction

The native Containers window still overrode the common appearance with the old navy palette. Align actual table/header/sidebar/detail surfaces to Files and Network; use restrained selection, a fixed 176px sidebar, compact table rows and smaller default workspace. Existing Docker commands, authorization and data retrieval are unchanged. Network 44415387599 navigated all three pages and produced real screenshots, but its Xvfb session lacked the accessibility bus and the log filter misidentified a GDBus warning as an exception. Use the existing CI-only GTK_A11Y=none convention and reject actual Python exceptions/critical messages; never disable accessibility in shipped apps. Require all three captures explicitly. Visual acceptance remains pending.

### Windows Runtime workspace

Move the real EXE/MSI launch form ahead of optional Office links, and separate saved shortcuts and licensed Office information into their own native pages. Match the 176px graphite navigation/sidebar and shared status footer of Network. Selection from the saved library returns to the launch page with the trust confirmation reset; no autorun, no installation or compatibility claim, no activation changes. All existing Wine planning and shortcut safety rules remain in place. Test genuine GTK navigation and screenshots; backend Wine fixture acceptance is independent.
