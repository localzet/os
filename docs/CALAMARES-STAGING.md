# Localzet OS Calamares integration - STAGING ONLY

Calamares 3.3.x ships in Ubuntu 26.04. The example files in this directory
are not copied into the ISO and cannot perform an installation.

Release blockers:
1. Verify Ubuntu Calamares modules and setup on a disposable QEMU VM.
2. Prepare Localzet branding and consistent interface with translations.
3. Bind disk choice to stable serial/WWN and revalidate before every write.
4. Guarantee ESP and bootloader writes stay on the chosen SSD.
5. Remove live user, empty password, passwordless sudo, GDM autologin,
   serial diagnostics and Live services from the installed rootfs.
6. Test installation with two virtual drives. Check that the untouched
   drive's SHA256 remains unchanged.
7. Boot installed SSD without installation medium or secondary drives.
8. Test errors, interruptions, UEFI/BIOS, Secure Boot policies and updates.

No installable ISO is ready until all tests are implemented and passed.

## Module inventory check

The Calamares staging contract workflow downloads the signed-archive Ubuntu
package, extracts it without installing or running the installer, and checks
every referenced show/exec module against the packaged module descriptors.
Missing modules fail the check and the inventory is uploaded for review.
This checks module presence only, not configuration schemas, execution order,
partition safety or installability.
