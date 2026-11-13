# Dedicated SSD selection — read-only identity plan

Use a unique WWN where present or a unique serial number. Device paths
can change between boots and must not be treated as persistent identifiers.

The resulting plan only describes a selected disk and all non-target disks.
It NEVER authorizes erasure or an installation. Real Calamares integration
must re-read hardware identity and mount state immediately before writes,
show irreversible consequences, and demand independent user confirmation.

The planned installation matrix must compare byte-for-byte checksums of
non-target QEMU disks before and after installing on the chosen virtual SSD.

## Fresh revalidation

`revalidate_target(fresh_lsblk_payload, reviewed_plan)` compares the hardware
and observed partition layout fingerprints, including filesystem UUIDs,
partition UUIDs and offsets. Device-path renumbering does not invalidate the
plan; a changed layout, hardware or newly blocked target does. USB-attached
SSDs are excluded from this initial policy, even when the removable bit is unset.
This remains a read-only advisory check, not an atomic device lock or permission
to write. A real installer must enforce exclusive device binding independently.
