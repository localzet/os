#!/usr/bin/env bash
# Disposable GitHub runner ONLY. Inspect Calamares; never install to a disk.
set -Eeuo pipefail
OUT="${1:-out/installer-probe}"
mkdir -p "$OUT"
{
  echo 'Ubuntu:'
  . /etc/os-release
  echo "$PRETTY_NAME"
  echo
  echo 'Calamares package metadata:'
  dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' calamares
  echo
  echo 'Packaged module and configuration paths:'
  dpkg -L calamares | grep -E '(^|/)(modules|calamares|settings\.conf)(/|$)' | sort
  echo
  echo 'Module descriptor locations:'
  find /usr/lib /usr/share -maxdepth 6 -name 'module.desc' -path '*calamares*' -print 2>/dev/null | sort || true
  echo
  echo 'Executable:'
  command -v calamares
  echo
  echo 'Installer staging remains disabled:'
  grep -E '^(enabled|ready_for_physical_disks|allow_unattended_erase) *=' config/installer/staging.toml
} > "$OUT/package-inventory.txt"
test -s "$OUT/package-inventory.txt"
grep -q 'enabled = false' "$OUT/package-inventory.txt"
echo 'Calamares inventory captured without invoking installer.'
