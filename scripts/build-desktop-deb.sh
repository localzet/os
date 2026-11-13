#!/usr/bin/env bash
# Build an architecture-independent desktop overlay without root privileges.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="${1:-$repo/dist}"
version="${LOCALZET_PACKAGE_VERSION:-0.1.0~dev1}"
if ! dpkg --validate-version "$version"; then
    echo "Invalid Debian package version" >&2
    exit 2
fi
stage="$(mktemp -d)"
trap 'rm -rf -- "$stage"' EXIT
pkg="$stage/package"
mkdir -p "$pkg/DEBIAN" "$pkg/opt/localzet-os/src" "$pkg/opt/localzet-os/config" \
    "$pkg/usr/bin" "$pkg/usr/share/applications" "$pkg/usr/share/localzet/styles" \
    "$pkg/usr/share/backgrounds/localzet" "$pkg/usr/share/gnome-shell/extensions" \
    "$pkg/usr/share/doc/localzet-desktop"
cat > "$pkg/DEBIAN/control" <<EOF
Package: localzet-desktop
Version: $version
Architecture: all
Maintainer: Localzet OS <https://github.com/localzet/os>
Section: x11
Priority: optional
Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gnome-shell (>= 50), gnome-shell (<< 51)
Description: Localzet Aurora desktop components
 GNOME Shell extension, system settings, module catalog and Aurora wallpaper.
EOF
cp -a "$repo/src/localzet" "$pkg/opt/localzet-os/src/"
find "$pkg/opt/localzet-os/src" -type d -name __pycache__ -prune -exec rm -rf -- {} +
cp -a "$repo/config/modules" "$pkg/opt/localzet-os/config/"
cp -a "$repo/extensions/localzet-shell@localzet.com" "$pkg/usr/share/gnome-shell/extensions/"
install -m 0755 "$repo/apps/localzet-settings/localzet-settings" "$pkg/usr/bin/localzet-settings"
install -m 0644 "$repo/packaging/com.localzet.Settings.desktop" "$pkg/usr/share/applications/"
install -m 0644 "$repo/apps/localzet-settings/settings.css" "$pkg/usr/share/localzet/styles/"
install -m 0644 "$repo/assets/wallpapers/aurora.svg" "$pkg/usr/share/backgrounds/localzet/"
install -m 0644 "$repo/LICENSE" "$pkg/usr/share/doc/localzet-desktop/copyright"
mkdir -p "$out"
artifact="$out/localzet-desktop_${version}_all.deb"
dpkg-deb --root-owner-group --build "$pkg" "$artifact"
dpkg-deb --info "$artifact"
