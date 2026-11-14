# Interactive Localzet OS installation candidate

This is the first interactive, dedicated-disk installer candidate. It is
separate from the ordinary Live ISO and the disposable automated test ISO.

The native Russian GTK/libadwaita wizard shows the target model, capacity,
device and stable identity. It requires a new local account, matching password,
backup acknowledgement and explicit typed target confirmation. The backend
revalidates the device and partition layout, refuses filesystem signatures,
uses a stable by-id path and invokes the same installation engine used in the
virtual two-disk test.

The first candidate deliberately supports only:

- amd64, UEFI, Secure Boot disabled;
- an empty internal NVMe/SATA SSD of at least 32 GiB;
- all other disks disconnected except the direct ISO boot medium;
- GPT, an ESP on the same SSD, ext4, no encryption or dual boot;
- a directly written ISO9660 USB or optical medium, not a loop-based loader.

The engine copies the pristine SquashFS, creates an authenticated user, removes
Live-only code and passwordless access, purges Casper, installs a removable-path
EFI bootloader on the selected SSD without NVRAM changes, writes fstab and
audits the installed system. No auto-login or automatic physical-disk erasure.
Stable identifiers and repeated checks do not constitute an atomic hotplug lock:
never connect or disconnect drives during installation.

The candidate CI builds the exact image, boots it in QEMU with an emulated
NVMe SSD, opens the actual installer UI and exercises the real privileged backend using a
host-supplied request (the wizard's button-to-backend interaction is not yet automated),
boots the installed SSD without ISO or other drives, authenticates the test user
in GDM and requires an active Wayland session, Aurora extension, Settings, Windows Runtime and Localzet Connect.
Test input is provided by the QEMU host, not baked into the ISO.
The ISO is uploaded only if the candidate test succeeds. The independent
two-disk test must also pass before a release is considered.

Do not advertise a stable release or general hardware compatibility based on
these VM tests. Real-device testing, security review, localization polish,
package updates, recovery, Secure Boot, encryption and broader hardware support
remain separate tasks.

## Combined Aurora candidate

The candidate workflow includes Wine from the signed Ubuntu archive and the
native Windows Runtime and Connect setup applications. It compiles a harmless
64-bit PE fixture on the CI host, injects it only at test time and runs it as
the authenticated installed desktop user using Localzet Windows Runtime.
The upload requires exit code 42 from that fixture in addition to the installed
Wayland desktop checks. The upstream NectarLink binary is not bundled; phone
pairing and the on-demand transaction on installed hardware remain unverified.
