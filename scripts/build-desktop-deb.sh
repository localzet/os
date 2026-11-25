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
    "$pkg/usr/share/backgrounds/localzet" "$pkg/usr/share/icons" \
    "$pkg/usr/share/localzet/ptyxis-palettes" \
    "$pkg/usr/share/themes" \
    "$pkg/usr/share/glib-2.0/schemas" \
    "$pkg/usr/share/metainfo" "$pkg/usr/share/gnome-shell/extensions" \
    "$pkg/usr/share/doc/localzet-desktop" "$pkg/opt/localzet-os/scripts" \
    "$pkg/opt/localzet-os/packaging/nectarlink" "$pkg/usr/lib/localzet" "$pkg/usr/share/polkit-1/actions"
cat > "$pkg/DEBIAN/control" <<EOF
Package: localzet-desktop
Version: $version
Architecture: all
Maintainer: Localzet OS <https://github.com/localzet/os>
Section: x11
Priority: optional
Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gtk-update-icon-cache, libglib2.0-bin, yaru-theme-gtk, gnome-shell (>= 50), gnome-shell (<< 51), pkexec
Description: Localzet Aurora desktop components
 GNOME Shell extension, settings, icon theme, module catalog and Aurora wallpapers.
EOF
cp -a "$repo/src/localzet" "$pkg/opt/localzet-os/src/"
find "$pkg/opt/localzet-os/src" -type d -name __pycache__ -prune -exec rm -rf -- {} +
cp -a "$repo/config/modules" "$pkg/opt/localzet-os/config/"
cp -a "$repo/extensions/localzet-shell@localzet.com" "$pkg/usr/share/gnome-shell/extensions/"
glib-compile-schemas --strict "$pkg/usr/share/gnome-shell/extensions/localzet-shell@localzet.com/schemas"
install -m 0644 "$repo/extensions/localzet-shell@localzet.com/schemas/com.localzet.shell.gschema.xml" \
    "$pkg/usr/share/glib-2.0/schemas/"
install -m 0644 "$repo/packaging/99-localzet-ptyxis.gschema.override" \
    "$pkg/usr/share/glib-2.0/schemas/"
cp -a "$repo/theme/icons/Localzet" "$pkg/usr/share/icons/"
for theme in Blue Purple Black; do
    gtk_theme="Localzet-Aurora-$theme"
    install -D -m 0644 "$repo/theme/gtk/$gtk_theme/gtk-4.0/gtk.css" \
        "$pkg/usr/share/themes/$gtk_theme/gtk-4.0/gtk.css"
done
mkdir -p "$pkg/usr/share/icons/hicolor/scalable/apps"
for icon in localzet-settings localzet-connect localzet-windows; do
    install -m 0644 "$repo/theme/icons/Localzet/scalable/apps/$icon.svg" \
        "$pkg/usr/share/icons/hicolor/scalable/apps/$icon.svg"
done
install -m 0755 "$repo/apps/localzet-settings/localzet-settings" "$pkg/usr/bin/localzet-settings"
install -m 0644 "$repo/packaging/com.localzet.Settings.desktop" "$pkg/usr/share/applications/"
install -m 0644 "$repo/packaging/com.localzet.Settings.metainfo.xml" "$pkg/usr/share/metainfo/"
install -m 0755 "$repo/apps/localzet-windows/localzet-windows" "$pkg/usr/bin/localzet-windows"
install -m 0644 "$repo/packaging/com.localzet.WindowsRuntime.desktop" "$pkg/usr/share/applications/"
install -m 0644 "$repo/packaging/com.localzet.WindowsRuntime.metainfo.xml" "$pkg/usr/share/metainfo/"
install -m 0644 "$repo/apps/localzet-settings/settings.css" "$pkg/usr/share/localzet/styles/"
install -m 0644 "$repo/assets/wallpapers/aurora.svg" "$pkg/usr/share/backgrounds/localzet/"
install -m 0644 "$repo/assets/wallpapers/aurora-blue.webp" "$repo/assets/wallpapers/aurora-purple.webp" \
    "$repo/assets/wallpapers/aurora-black.webp" "$pkg/usr/share/backgrounds/localzet/"
install -m 0644 "$repo/assets/terminal-palettes/"*.palette \
    "$pkg/usr/share/localzet/ptyxis-palettes/"
install -m 0644 "$repo/LICENSE" "$pkg/usr/share/doc/localzet-desktop/copyright"
install -m 0755 "$repo/apps/localzet-connect/localzet-connect" "$pkg/usr/bin/localzet-connect"
install -m 0644 "$repo/packaging/com.localzet.Connect.desktop" "$pkg/usr/share/applications/"
install -m 0644 "$repo/packaging/com.localzet.Connect.metainfo.xml" "$pkg/usr/share/metainfo/"
install -m 0755 "$repo/packaging/nectarlink/install-nectarlink" "$pkg/usr/lib/localzet/"
install -m 0644 "$repo/packaging/nectarlink/org.localzet.install-nectarlink.policy" "$pkg/usr/share/polkit-1/actions/"
install -m 0644 "$repo/packaging/nectarlink/release.toml" "$pkg/opt/localzet-os/packaging/nectarlink/"
install -m 0644 "$repo/scripts/fetch-nectarlink-deb.py" "$repo/scripts/check-nectarlink-control.py" "$pkg/opt/localzet-os/scripts/"
cat > "$pkg/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -eu
glib-compile-schemas --strict /usr/share/glib-2.0/schemas
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache --force --quiet /usr/share/icons/Localzet || true
    gtk-update-icon-cache --force --quiet /usr/share/icons/hicolor || true
fi
exit 0
EOF
cat > "$pkg/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -eu
rm -f /usr/share/icons/Localzet/icon-theme.cache
if test -d /usr/share/glib-2.0/schemas; then
    glib-compile-schemas --strict /usr/share/glib-2.0/schemas || true
fi
if test -f /usr/share/icons/Localzet/index.theme \
        && command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache --force --quiet /usr/share/icons/Localzet || true
fi
if test -d /usr/share/icons/hicolor \
        && command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache --force --quiet /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 0755 "$pkg/DEBIAN/postinst" "$pkg/DEBIAN/postrm"
mkdir -p "$out"
artifact="$out/localzet-desktop_${version}_all.deb"
dpkg-deb --root-owner-group --build "$pkg" "$artifact"
dpkg-deb --info "$artifact"
