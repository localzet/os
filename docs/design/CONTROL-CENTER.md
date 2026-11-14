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
