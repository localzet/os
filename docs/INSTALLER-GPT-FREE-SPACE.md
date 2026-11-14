# Read-only GPT free-space planner (staging)

The next installer must distinguish a visible, already partitioned SSD
from an invisible controller. This module is an independent read-only
planning step for a reviewed future Calamares/Ubuntu backend. It is not
connected to the current installer writer; existing blank-SSD restrictions
remain unchanged.

Given explicit disk WWN/serial and two separately captured JSON inventories
(lsblk --json --bytes with preflight.LSBLK_COLUMNS, and sfdisk --json for
the identified disk), the planner cross-checks device, GPT partition
UUID/type/size and bounds, reports aligned half-open free extents in logical
sectors (512 and 4096 tested), and lists existing EFI partitions to preserve.
No commands are executed by the planner. The CLI reads saved fixtures only.
An extent meeting 32 GiB is only a root capacity hint, not an installation
decision: reserve EFI space as required and verify all other requirements.

Next gates: verify live boot provenance and consistent read-only inventory
in a privileged fixed-command backend; independent GPT CRC/backup health,
logical sector geometry and stable device binding; explicit extent selection;
read-only inspection of existing EFI contents and firmware entries; review
new loader path and preserve other entries; prove before/after byte
preservation of every existing partition, both GPT headers and foreign EFI
files except explicitly planned metadata changes. Do not auto-format an
ESP, overwrite foreign GRUB, silently shrink NTFS or support ambiguous RAID
or encrypted volumes. Test with disposable QEMU disks before wiring writes.
A planner cannot guarantee a race-free installation.
