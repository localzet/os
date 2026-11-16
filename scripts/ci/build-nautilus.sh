#!/usr/bin/env bash
# Build only on a disposable Ubuntu 26.04 CI VM from signed Ubuntu sources.
set -Eeuo pipefail
[[ ${LOCALZET_DISPOSABLE_VM:-} == 1 && $EUID != 0 ]]
. /etc/os-release
[[ "$VERSION_CODENAME" == resolute && "$(dpkg --print-architecture)" == amd64 ]]
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
out="$repo/out/nautilus"
mkdir -p "$out"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
sudo tee /etc/apt/sources.list.d/localzet-nautilus-source.sources >/dev/null <<'EOF'
Types: deb-src
URIs: https://archive.ubuntu.com/ubuntu
Suites: resolute resolute-updates
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb-src
URIs: https://security.ubuntu.com/ubuntu
Suites: resolute-security
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
sudo apt-get -o Acquire::Retries=3 update
version="$(apt-cache policy nautilus | awk '/Candidate:/{print $2}')"
[[ "$version" =~ ^([0-9]+:)?50\. ]]
printf 'Ubuntu source version: %s\n' "$version" | tee "$out/provenance.txt"
sudo apt-get install -y build-essential devscripts quilt xvfb xauth xdotool imagemagick dbus-x11 python3-pil gvfs
sudo apt-get -y build-dep "nautilus=$version"
cd "$work"
apt-get source "nautilus=$version"
shopt -s nullglob
dirs=(nautilus-*/)
[[ ${#dirs[@]} == 1 ]]
sha256sum ./*.dsc ./*.tar.* >> "$out/provenance.txt"
cd "${dirs[0]}"
[[ "$(dpkg-parsechangelog -S Version)" == "$version" ]]
grep -F 'gtk_widget_add_css_class (GTK_WIDGET (window), "nautilus-window")' src/nautilus-window.c
export QUILT_PATCHES=debian/patches
quilt new localzet-executive-style.patch
quilt add src/resources/style.css
python3 "$repo/scripts/patch-nautilus-style.py" src/resources/style.css "$repo/assets/styles/nautilus-executive.css"
quilt refresh
cp debian/patches/localzet-executive-style.patch "$out/"
export DEBFULLNAME="Localzet OS" DEBEMAIL="build@localzet.com"
new_version="${version}+localzet1"
dch --newversion "$new_version" --distribution resolute "Scope Executive styling to the Nautilus dark window."
DEB_BUILD_OPTIONS="parallel=2" xvfb-run -a dbus-run-session -- dpkg-buildpackage -b -us -uc 2>&1 | tee "$out/build.log"
cd "$work"
debs=()
for f in ./*.deb; do
    name="$(dpkg-deb -f "$f" Package)"
    case "$name" in
        nautilus|nautilus-data|libnautilus-extension4)
            test "$(dpkg-deb -f "$f" Version)" = "$new_version"
            debs+=("$f")
            cp "$f" "$out/"
            ;;
    esac
done
[[ ${#debs[@]} == 3 ]]
(cd "$out"; sha256sum ./*.deb) > "$out/SHA256SUMS"
git -C "$repo" rev-parse HEAD > "$out/BUILD-COMMIT"
sudo apt-get install -y "${debs[@]}"
test "$(dpkg-query -W -f='${Version}' nautilus)" = "$new_version"
python3 "$repo/scripts/build-aurora-icons.py" "$HOME/.local/share/icons"
export OUT="$out"
for mode in dark light contrast; do
    xvfb-run -a -s '-screen 0 1440x900x24' dbus-run-session -- bash "$repo/scripts/ci/nautilus-appearance-smoke.sh" "$mode"
done
echo 'PASS: exact Ubuntu source package; native dark/light/high contrast visual review'
