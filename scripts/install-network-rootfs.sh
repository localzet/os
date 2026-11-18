#!/usr/bin/env bash
# Build-only: preinstall UserNet and stage verified NetBird for offline consent.
set -Eeuo pipefail
[[ $EUID == 0 && "${LOCALZET_DISPOSABLE_VM:-}" == 1 && "${LOCALZET_EXPERIMENTAL_NETWORK:-}" == 1 && "${LOCALZET_ARCHIVE_PROFILE:-}" == complete && $# == 1 ]]
root="$(realpath -e -- "$1")"
repo="$(cd "$(dirname "$0")/.." && pwd)"
[[ "$root" != / && -f "$root/var/lib/dpkg/status" ]]
work="$(mktemp -d)"
staged="$root/tmp/localzet-network-preload"
[[ ! -e "$staged" && ! -L "$staged" ]]
trap 'rm -rf -- "$work" "$staged"' EXIT
python3 "$repo/scripts/fetch-usernet.py" "$work/usernet"
python3 "$repo/scripts/fetch-netbird.py" "$work/netbird"
install -d -m 0755 "$staged"
install -m 0644 "$work/usernet/UserNet-linux.deb" "$staged/"
# Use explicitly reviewed dependencies and do not start the NetBird daemon
# in the chroot: its original package has an active postinstall.
runtime=(libgtk-4-1 libwebkitgtk-6.0-4 xdg-utils libayatana-appindicator3-1 libsecret-1-0 libegl1 libegl-mesa0 libgl1 libgl1-mesa-dri libgles2)
apt=(apt-get -o APT::Get::AllowUnauthenticated=false --no-remove --no-install-recommends)
chroot "$root" "${apt[@]}" --simulate install /tmp/localzet-network-preload/UserNet-linux.deb "${runtime[@]}" > "$work/apt-plan"
if grep -Eq '^(Remv |Inst (netbird|netbird-ui)( |:))' "$work/apt-plan"; then
    echo "Unreviewed network preload transaction" >&2
    exit 2
fi
chroot "$root" env DEBIAN_FRONTEND=noninteractive "${apt[@]}" -y install /tmp/localzet-network-preload/UserNet-linux.deb "${runtime[@]}"
test "$(chroot "$root" dpkg-query -W -f='${Version}' usernet)" = 0.5.12.2026110805
test -x "$root/opt/UserNet/UserNet"
test -s "$root/usr/share/applications/com.localzet.usernet.desktop"
if systemctl --root="$root" is-enabled --quiet usernet-helper.service; then
    echo "Unexpected enabled UserNet TUN helper" >&2; exit 2
fi
cache="$root/usr/share/localzet/network-preload"
[[ ! -e "$cache" && ! -L "$cache" ]]
install -d -m 0755 "$cache/netbird"
install -m 0644 "$work/netbird/"*.deb "$cache/netbird/"
# Check that future offline installation needs no additional archive package.
install -m 0644 "$work/netbird/"*.deb "$staged/"
chroot "$root" "${apt[@]}" --simulate --no-download install /tmp/localzet-network-preload/netbird_0.83.1_linux_amd64.deb /tmp/localzet-network-preload/netbird-ui_0.83.1_linux_amd64.deb > "$work/netbird-plan"
if grep -E '^Inst ' "$work/netbird-plan" | grep -Ev '^Inst (netbird|netbird-ui)( |:)'; then
    echo "NetBird offline dependencies incomplete" >&2; exit 2
fi
install -m 0644 "$work/apt-plan" "$cache/usernet-apt-plan.txt"
install -m 0644 "$work/netbird-plan" "$cache/netbird-apt-plan.txt"
install -m 0644 "$repo/config/upstream/netbird.json" "$repo/config/upstream/usernet.json" "$cache/"
echo 'PASS: exact UserNet installed, verified NetBird staged for offline consent; no VPN enrollment'
