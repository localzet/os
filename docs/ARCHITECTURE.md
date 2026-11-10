# Architecture decision record: foundation

**Decided:** Ubuntu 26.04 LTS, GNOME 50/Wayland and GDM. Avoid a custom compositor and a Debian/Ubuntu package mix.

## Trust boundaries

- **User session:** GNOME Shell extension, settings UI, launcher, monitor and desktop integration; no root permissions.
- **Catalog and planner:** declarative `.toml` manifests and a read-only resolver. Its output cannot execute package operations.
- **Future privileged service:** narrowly scoped Rust D-Bus service with polkit authorization, transaction journal, sandboxed helpers and explicit user approval for every package/service modification. Design and implement only after security review.
- **OS packages:** signed Ubuntu and verified third-party repositories. Do not bundle proprietary software without redistributable rights.
- **User data:** distinct from uninstallable modules; never silently erase container volumes, Wine prefixes or Steam libraries.

## Modules

States: `planned` means not installable, `prototype` means engineering proof only, `supported` requires signed packages, integration tests and a stable removal path. Until then, ALL plans are read-only.

The manifest defines identifiers and candidate dependencies. Future metadata needs schema-version, package sources, exact versions, architecture support, conflicts, services, licenses, disk estimates, uninstall semantics and recovery. It must not contain shell snippets executed as root.

## Networking

NetworkManager and systemd-resolved remain the base. UserNet/mihomo and NetBird are opt-in. A future `localzet-network-policy` service coordinates routing and DNS; do not run two independent default-route managers without tests.

## Visual identity

Keep a single token source and an accessible dark/light system. A shell extension is allowed to augment GNOME; do not monkey-patch private APIs indiscriminately. Visual screenshots are design references, not evidence of functional builds.

## Packaging milestones

1. GNOME extension verified on a disposable Ubuntu 26.04 VM.
2. A signed, installable `localzet-shell` .deb and clean uninstallation.
3. Ubuntu package overlays and deterministic live image pipeline (UEFI+BIOS smoke tests).
4. Customized installer with disk safety verification and explicit confirmation.
5. Secure module service, rollback and signed updates.
