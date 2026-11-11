# Calamares Ubuntu 26.04 integration probe

This CI job installs the packaged Calamares application only on a disposable
GitHub runner to inspect package, module, and configuration metadata.
It never starts installation, invokes partitioning modules, or touches disks.

Review the CI inventory before drafting real Calamares configuration.
A complete two-disk QEMU installation test, verified target selection,
non-target disk checksum and standalone reboot are mandatory prior to any
physical SSD installation.
