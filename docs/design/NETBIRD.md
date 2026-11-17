# NetBird integration

Use the official NetBird CLI and GTK4/WebKit desktop UI rather than a forked VPN implementation. The pinned v0.83.1 official release assets are checked by size and SHA-256, Debian package identity and exact maintainer script comparison to the tagged upstream source. The CLI postinstall installs/starts a system service; the UI postinstall can restart a running UI. Therefore these packages are not silently installed in the live rootfs. The first review runs extraction, CLI version/status help and APT simulation in disposable CI, without enrolling a peer, starting the daemon or changing routes.

Localzet Network reads the installed CLI's status JSON unprivileged; it exposes only daemon state and peer counts. It launches the existing official UI for profiles, SSO, DNS and routes, with a fixed command. No peer details, endpoint addresses or keys are retained. Without the client it reports not installed and links to official installation instructions. The new native application and upstream icon aliases use Aurora. No arbitrary command or root access is exposed.

Next gate: actual service install and GTK UI against a fresh unregistered peer, explicit installed-system provisioning with admin approval, followed by authenticated connection/routing tests with a dedicated test deployment. UserNet/mihomo route and DNS coordination is not yet implemented. No release or redistribution authorization is implied.

References: https://github.com/netbirdio/netbird/releases/tag/v0.83.1 and https://docs.netbird.io/get-started/install/linux

Experimental installed-system provisioning: Localzet Network offers a fixed administrator-authenticated install action when the pinned client is absent. The helper refuses Live/foreign OS, uses private root-owned staging, exact upstream checks, signed APT dependencies, no removal or downgrade, and never calls login/up. Real route/peer enrollment and installed-image polkit acceptance remain pending.
