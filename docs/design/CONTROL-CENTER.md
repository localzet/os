# Unified settings: Ubuntu package rebuild (engineering)

GNOME Control Center 50 is the only target for system settings. The first
step is a maintained rebuild of the signed Ubuntu source package, keeping
all Ubuntu patches, controls and dependency metadata. The reviewable
quilt patch forces the canonical original SVG for both light and dark
About panels, using the upstream Meson logo configuration. It fails closed
if those two assignments change. The build records the exact source
version, source archive digests, Debian rules and package checksums.
The revision uses +localzet1, not an artificial epoch or APT hold.
Subsequent Ubuntu security updates must be rebuilt and tested.

The isolated workflow installs the rebuilt binary/data pair, verifies the
compiled logo path, compares the stock panel inventory and captures the
real About window. Manual visual inspection is still required.
The packages are not added to the ISO by this PR. No overwriting files from
another distribution package or binary patching.

Next: integrate native Localzet pages for runtime, containers, connectivity
and update management; use actual service APIs and independent privilege
boundaries. The separate Components prototype is not the final settings UI.

First successful build: Ubuntu 1:50.3-0ubuntu0.2+localzet1, workflow
43635038458. Actual About screenshot revealed oversized intrinsic SVG
geometry that displaced the details. Keep the canonical SVG unchanged,
but constrain its GTK picture to a compact 144 logical pixel target.
Rebuild and inspect the result before ISO integration.

The compact 144 px About screenshot passed (43635926648). The next
engineering workflow hands the two rebuilt packages from its own successful
package job to a disposable ISO build. It validates both SHA-256 digests,
same checkout commit, exact package names/architecture and matching stock
Ubuntu source version inside the rootfs before installing. A newer archive
version requires a new rebuild rather than downgrading. The regular build
remains unchanged unless explicitly given LOCALZET_CONTROL_CENTER_BUNDLE.
No package is pinned or held. The exact image is tested via the interactive
USB/QEMU installation path, without uploading a public release. Actual
installed About screenshot and maintained signed repository are still gates.
