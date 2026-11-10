#!/usr/bin/env bash
# Read-only diagnostics on a disposable Live ISO. Output is sent to QEMU's
# serial console and archived only in CI. Do not run on a normal installation.
set -Eeuo pipefail
OUT=/dev/ttyS0
[[ -c "$OUT" ]] || exit 0

snapshot() {
  local phase="$1"
  {
    printf 'LOCALZET_BOOT_EVIDENCE_BEGIN\n'
    printf 'phase=%s\n' "$phase"
    printf 'gdm_state='
    systemctl is-active gdm.service || true
    printf 'graphical_target='
    systemctl is-active graphical.target || true
    echo 'sessions:'
    loginctl list-sessions --no-legend 2>&1 || true
    echo 'GNOME processes:'
    ps -eo user,comm,args | grep -E '[g]nome-shell|[g]dm-session-worker|[g]dm-wayland-session|[g]nome-session|[g]nome-settings-daemon' | head -25 || true
    echo 'Active display session:'
    loginctl show-user localzet -p State -p Sessions -p Display 2>&1 || true
    echo 'systemd pending jobs:'
    systemctl list-jobs --no-pager 2>&1 | tail -15 || true
    echo 'GDM recent logs:'
    journalctl -u gdm.service -b --no-pager -n 35 2>&1 || true
    echo 'GNOME user recent logs:'
    journalctl -b _UID=1000 --no-pager -n 90 2>&1 || true
    echo 'GNOME errors:'
    journalctl -b --no-pager --grep='gnome-shell|gnome-session|mutter|gdm|segfault|core dumped' -n 70 2>&1 || true
    printf 'LOCALZET_BOOT_EVIDENCE_END\n'
  } >> "$OUT" 2>&1
}

sleep 40
snapshot initial
sleep 90
snapshot later
sleep 90
snapshot late
