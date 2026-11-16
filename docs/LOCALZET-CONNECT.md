# NectarLink integration

[NectarLink](https://github.com/thtbee/nectarlink) is an independent project by thtbee. Localzet OS provides only a setup entry point for the original upstream client, not a fork or a separate protocol implementation. The integration uses the upstream name and explicitly credits its developer. The setup entry point is labeled NectarLink Setup to distinguish it from the client.

- Aurora launcher exposes the official desktop application when installed.
- Localzet Settings shows a phone row without requiring privileged actions.
- The phone module remains a prototype; the package planner does not install it.
- The upstream desktop entry already advertises tel/sms/geo and NectarLink URI
  handlers. Do not change default handlers without the user's consent.

The pinned v0.1.5 amd64 DEB and Android APK are listed in
`packaging/nectarlink/release.toml`. SHA-256 values come from GitHub's release
asset metadata; checksums are not an independent signature. Review artifacts,
dependencies, maintainer scripts, exact corresponding source (including bundled
Qt and third-party code), licenses and redistribution terms before bundling.
The release is not automatically downloaded or installed by this change.

Desktop and CLI are GPL-3.0-or-later; core libraries are MPL-2.0. Upstream
trademark policy permits unmodified official builds under the NectarLink name;
modified builds must use a different name and logo.

## Privilege and privacy

Run the client as the logged-in user; no root daemon, no blanket firewall
opening, no automatic uinput permission, ADB debugging, microphone, camera,
clipboard or remote command grants. Do not run upstream curl-to-shell setup
during image creation. Pairing must be user-initiated. Never bake device keys,
paired identities or personal data into the ISO. Linux upstream currently
protects keys with filesystem permissions. Review update behavior before
integrating with the OS package manager.

## Release gates

- [ ] Inspect pinned package and license inventory; validate amd64 dependencies.
- [ ] Test Ubuntu 26.04 GNOME 50 Wayland and XWayland behavior.
- [ ] Test actual Android pairing, revoke/unpair, reconnect and notifications.
- [ ] Test clipboard, files, messages and calls; document platform limitations.
- [ ] Test optional portal-mediated screen capture, audio, webcam and input.
- [ ] Add explicit per-device permission UX, status and battery integration only
  through a reviewed upstream interface; do not invent a D-Bus API.
- [ ] Disable duplicate island/overlay UI where supported; verify theme integration.
- [ ] Establish signed package updates and redistribution compliance before ISO inclusion.

iOS is not supported by this Android integration.

## Package verification

Run `python3 scripts/fetch-nectarlink-deb.py --output out/nectarlink` as an
unprivileged user. It checks the locked release URL, SHA-256, package name,
version and architecture, then atomically publishes the downloaded file.
It does not execute the installer or any maintainer script. CI extracts
control metadata and the file list for review; it does not upload the DEB.
A matching hash establishes artifact identity, not trust or licensing compliance.

## Native setup

The NectarLink setup entry point opens from the application list or Components. The ISO contains the setup UI and fixed polkit-authenticated installer, not the upstream binary. After installation to SSD, the user may explicitly download the pinned NectarLink package, verify its SHA-256 and reviewed maintainer scripts, and install with administrator authorization. Live sessions do not install it. Actual Android pairing is not yet verified; the upstream client launch passed in Ubuntu CI. No redistribution of NectarLink is enabled.

## GNOME top panel

Use the maintained AppIndicator/StatusNotifier GNOME extension and the original
NectarLink Qt tray menu, not a second client or a competing status icon. The
v0.1.5 desktop source exports Open, Command Palette, File Shelf, Take Photo,
Scan Document, Find Phone, Open Copied Link and Quit; availability is controlled
by the upstream client. The CLI has its own separate identity, so it is not a
status or action API for the already paired desktop. Nectar Island is optional
and defaults to off in upstream; do not force it or modify private settings.

CI must verify an active StatusNotifier host in installed GNOME and discover
an actual upstream D-Bus menu from the pinned official package. No device
pairing, notifications, files or battery values are fabricated. A future native
Quick Settings tile requires an upstream-supported live device-state interface
and permission review; coordinate with thtbee rather than scraping private data.
