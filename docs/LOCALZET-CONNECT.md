# Localzet Connect

Localzet Connect is the OS-facing entry point to the upstream NectarLink Android
integration. It is not a fork or a separate protocol implementation.

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
