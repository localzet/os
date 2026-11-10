# Dedicated SSD selection — read-only identity plan

Use a unique WWN where present or a unique serial number. Device paths
can change between boots and must not be treated as persistent identifiers.

The resulting plan only describes a selected disk and all non-target disks.
It NEVER authorizes erasure or an installation. Real Calamares integration
must re-read hardware identity and mount state immediately before writes,
show irreversible consequences, and demand independent user confirmation.

The planned installation matrix must compare byte-for-byte checksums of
non-target QEMU disks before and after installing on the chosen virtual SSD.
