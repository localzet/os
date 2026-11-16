#!/usr/bin/env bash
# Engineering-only disposable target root, never install on build host.
set -Eeuo pipefail
[[ $EUID == 0 && "${LOCALZET_DISPOSABLE_VM:-}" == 1 && $# == 1 ]]
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
root="$(realpath -e "$1")"
[[ "$root" != / && -f "$root/etc/debian_version" && -d "$root/var/lib/dpkg" ]]
[[ "${LOCALZET_ARCHIVE_PROFILE:-}" == standard || "${LOCALZET_ARCHIVE_PROFILE:-}" == complete ]]
work="$(mktemp -d)"
asset="$root/tmp/localzet-onlyoffice-review.deb"
[[ ! -e "$asset" && ! -L "$asset" ]]
cleanup() {
    rm -f -- "$asset"
    rm -rf -- "$work"
}
trap cleanup EXIT
deb="$(python3 "$repo/scripts/fetch-onlyoffice.py" deb "$work")"
test "$(dpkg-deb -f "$deb" Package)" = onlyoffice-desktopeditors
test "$(dpkg-deb -f "$deb" Architecture)" = amd64
version="$(dpkg-deb -f "$deb" Version)"
test "$version" = 10.0.0-169
dpkg-deb -e "$deb" "$work/control"
test -f "$work/control/postrm"
for script in preinst postinst prerm config; do
    test ! -e "$work/control/$script"
done
install -m 0644 "$deb" "$asset"
# No external source/key or recommends, including proprietary font EULAs.
chroot "$root" apt-get -o APT::Get::AllowUnauthenticated=false --simulate --no-install-recommends install /tmp/localzet-onlyoffice-review.deb > "$work/plan"
if grep -Eq '^(Remv |Inst (ttf-mscorefonts-installer|ubuntu-restricted-extras)( |:))' "$work/plan"; then
    echo "Unreviewed office dependency transaction" >&2
    exit 2
fi
chroot "$root" env DEBIAN_FRONTEND=noninteractive apt-get -o APT::Get::AllowUnauthenticated=false --no-install-recommends --no-remove -y install /tmp/localzet-onlyoffice-review.deb
test "$(chroot "$root" dpkg-query -W -f='${Version}' onlyoffice-desktopeditors)" = "$version"
test -x "$root/usr/bin/onlyoffice-desktopeditors"
test -s "$root/opt/onlyoffice/desktopeditors/LICENSE.txt"
install -d -m 0755 "$root/usr/share/localzet/office-review"
install -m 0644 "$work/plan" "$root/usr/share/localzet/office-review/apt-plan.txt"
install -m 0644 "$repo/config/upstream/onlyoffice.json" "$root/usr/share/localzet/office-review/upstream.json"
printf '%s\n' "$version" > "$root/usr/share/localzet/office-review/version.txt"
echo "PASS: pinned native ONLYOFFICE installed into disposable rootfs; redistribution not approved"
