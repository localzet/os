# Localzet OS recovery and maintenance diagnostics

Run `localzet-recovery` on the installed system. For full visibility of
root-owned GRUB configuration and hardware transaction receipts, run
`sudo localzet-recovery` from an administrator's local terminal.

The command is read-only: it inventories running and alternate kernel/initrd
pairs, explicit normal/recovery kernel lines in the generated GRUB config,
root and EFI mount types, dpkg audit status, and coarse hardware transaction
receipt states. It prints JSON and does not expose raw hardware receipt
contents, passwords, or command-line contents. Unknown information is
reported as unknown, not clean. It does not modify files, refresh APT,
change EFI variables, mount partitions, repair dpkg, reboot, or roll back
packages. Root is not needed for the parts that are publicly readable.

## If an update or driver transaction fails

1. Keep the current bootable kernel and take a current backup of your files.
2. Review the diagnostic's issues and the administrator-only transaction
   receipts. A receipt requiring reboot/compute verification is not evidence
   that a driver or CUDA works.
3. If boot fails, use the Localzet disk's GRUB advanced menu and recovery
   entry, or an already verified alternate kernel if available. Do not select
   a foreign disk to repair or format. Recovery may require local console
   authentication. Never disable Secure Boot to work around an unexplained
   signature failure.
4. A missing alternate kernel is expected on a fresh single-kernel image;
   it is not a verified fallback. Preserve an existing tested kernel before
   performing a later kernel update.
5. If package state is inconsistent, stop automatic hardware setup and
   inspect the actual dpkg/APT failure before authorizing a repair. The
   diagnostic deliberately performs no automatic repair or rollback.

Installer GRUB configuration keeps recovery entries enabled and os-prober
disabled. CI requires normal/recovery entries for the running installed
kernel, matching nonempty kernel/initrd files and clean dpkg audit in a
real booted image. This checks the availability of entries, not whether
booting recovery succeeds. A previous-kernel boot, interrupted update and
rollback/recovery on physical hardware remain production acceptance gates.
