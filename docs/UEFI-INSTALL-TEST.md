# UEFI installation test (VM only)

The test image is deliberately separate from the normal Live ISO. It adds
installation tools and an opt-in, test-only boot service. The service refuses
to run unless booted with Casper, UEFI, a virtual machine, the explicit test
kernel parameter and two expected virtio disk identities. The target must be
a blank 32 GiB virtual SSD. Never boot the test image on a real computer.

The QEMU harness creates both disk files itself. The first boot uses the ISO
and both disks. The installer creates GPT, FAT32 ESP and ext4 root, extracts
the pristine SquashFS, purges Casper, removes the Live readiness service,
creates an authenticated test user with a random password, generates fstab
and installs GRUB on the target ESP with no NVRAM writes. It runs the existing
post-install audit before unmounting and signals completion.

The harness compares the untouched disk's SHA-256 before and after, then boots
the target alone, with fresh UEFI variables and no CD or secondary disk. The
installed-system probe requires an ext4 root, target ESP, real user password
status, no Live user, successful audit, GDM and a GNOME Shell process.

The second probe verifies the greeter, not a successful authenticated desktop
login. The test ISO and generated disks are never published by CI. Only logs
are retained. A passing test is evidence of the specific virtual installation
path, not authorization to use a physical drive. Calamares integration,
interactive consent, stable real-device binding, authentication testing,
encryption, Secure Boot and hardware coverage remain separate release gates.
