#!/usr/bin/env bash
# Read-only guest diagnostics for disposable Localzet Live ISO.
set -u
OUT=/dev/ttyS0
[[ -c "$OUT" ]] || exit 0
{
  echo 'LOCALZET_BOOT_EVIDENCE_BEGIN'
  printf 'gdm_state='
  systemctl is-active gdm.service || true
  printf 'graphical_target='
  systemctl is-active graphical.target || true
  echo 'sessions:'
  loginctl list-sessions --no-legend 2>&1 || true
  echo 'GNOME processes:'
  ps -eo user,comm,args | grep -E '[g]nome-shell|[g]dm-session-worker|[g]dm-wayland-session' | head -15 || true
  echo 'GDM recent logs:'
  journalctl -u gdm.service -b --no-pager -n 20 2>&1 || true
  echo 'LOCALZET_BOOT_EVIDENCE_END'
} >> "$OUT" 2>&1
