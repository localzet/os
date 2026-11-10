# Temporary GDM 50.1 Live seat recovery

Ubuntu 26.04 GDM 50.1 can start a second greeter roughly one minute after
successful automatic login. The real user session remains on VT2, but the
greeter takes the active seat (Ubuntu LP #2162542).

This experimental service runs **only on a casper Live boot**, and activates
one already-existing Wayland user session created by the gdm-autologin service
on seat0 if a gdm-greeter is active. It does not authenticate, log in, create
sessions or partition disks. It exits on the first successful recovery.

This is a workaround, not an upstream fix. The user can briefly see the
greeter. It must be removed from any installed system. The unit tests cover
fail-closed session identity decisions, not the real systemd-logind behavior.
Only fresh ISO QEMU BIOS and UEFI tests with actual GUI captures may show
whether it solves the user-visible defect.

When GDM is fixed upstream, remove the service entirely.
