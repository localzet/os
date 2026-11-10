# Post-install safety audit (read-only)

The initial Live image has a passwordless session, an autologin account,
and diagnostic services. NONE of those may be inherited by an installed OS.

This audit reads an extracted target root filesystem and exits with code 1
if any unsafe Live-only artifact remains. It does NOT scrub files, mount
disks, choose devices, or grant installation permission.

It rejects a copied NOPASSWD sudo rule, local seat guard, boot diagnostics,
the Live home, empty passwords, GDM autologin and disabled global screen
lock settings. It also fails closed if required identity files are absent,
unreadable or symlinks to outside the supplied root.

The real installer must *first* remove those artifacts safely in a verified
installation environment, create an authenticated user, set up bootloader
on the selected SSD and then run this audit before reboot. Passing this
audit alone is never proof of installation correctness.

Usage (extracted VM image only):

    PYTHONPATH=src python3 -m localzet.installer.audit /tmp/installed-root

Never point unreviewed install or partition commands at physical disks.
