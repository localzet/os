# UserNet integration

Use the original localzet/UserNet application, pinned Linux DEB v0.5.12, rather than a second Mihomo frontend. The package review verifies SHA-256, size, package identity, actual desktop entry, dependency plan and extracts all maintainer scripts without executing them. The upstream GPL-3.0 and third-party notices must remain intact. No bundled subscription or account credentials.

Localzet Network presents the GNOME proxy mode and counts of configured loopback and external endpoints, without revealing addresses or inferring which application owns a proxy. It opens com.localzet.usernet.desktop and uses the Aurora icon. NetBird connected plus manual/auto proxy is an advisory, not proof of conflict or connectivity. No changes to routes, DNS, proxy settings or TUN are performed by this panel.

UserNet upstream installs its privileged TUN helper on demand, with invoking-user authorization. Do not install or enable that helper in Live rootfs. Next gate: reviewed native package installation and launch, explicit administrator provisioning on installed OS, isolated tests for proxy lifecycle and TUN, NetBird coexistence with split routes and DNS. No actual VPN account or subscription is used in CI. No claim of complete integration yet.
