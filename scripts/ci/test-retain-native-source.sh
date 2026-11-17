#!/usr/bin/env bash
# Exercise a genuine 3.0 (quilt) source package, including an epoch.
set -Eeuo pipefail
[[ $EUID != 0 ]]
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
cd "$work"
mkdir fixture-1.0
printf 'original\n' > fixture-1.0/message.txt
tar -czf fixture_1.0.orig.tar.gz fixture-1.0
cd fixture-1.0
mkdir -p debian/source debian/patches
printf '3.0 (quilt)\n' > debian/source/format
printf 'fixture (1:1.0-1+localzet1) resolute; urgency=medium\n\n  * Original synthetic fixture.\n\n -- Localzet CI <ci@example.invalid>  Tue, 17 Nov 2026 00:00:00 +0000\n' > debian/changelog
cat > debian/control <<'EOF'
Source: fixture
Section: misc
Priority: optional
Maintainer: Localzet CI <ci@example.invalid>
Standards-Version: 4.7.0

Package: fixture
Architecture: all
Description: Localzet source retention fixture
 Original synthetic test data.
EOF
printf 'Original CI fixture; not a distribution package.\n' > debian/copyright
printf 'localzet-fixture.patch\n' > debian/patches/series
cat > debian/patches/localzet-fixture.patch <<'EOF'
--- a/message.txt
+++ b/message.txt
@@ -1 +1 @@
-original
+modified
EOF
QUILT_PATCHES=debian/patches quilt push -a
LOCALZET_DISPOSABLE_VM=1 bash "$repo/scripts/ci/retain-native-source.sh" "$work/retained" fixture '1:1.0-1+localzet1' localzet-fixture.patch
cd "$work/retained"
test -s fixture_1.0-1+localzet1.dsc
test "$(cat SOURCE-VERSION)" = '1:1.0-1+localzet1'
sha256sum -c SHA256SUMS
test "$(find . -maxdepth 1 -name '*.dsc' | wc -l)" -eq 1
dpkg-source -x fixture_1.0-1+localzet1.dsc "$work/extracted"
test "$(cat "$work/extracted/message.txt")" = modified
echo 'PASS: corresponding modified source reconstructed independently'
