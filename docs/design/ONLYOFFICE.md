# ONLYOFFICE native package review

ONLYOFFICE Desktop Editors remains mandatory in Standard and Complete.
Official upstream 10.0.0 provides amd64 DEB and x86_64 AppImage assets
with SHA-256 digests at https://github.com/ONLYOFFICE/DesktopEditors/releases/tag/v10.0.0.
The engineering manifest pins exact sizes and digests; no latest URL,
unverified repository key, silent license acceptance or third-party repack.
SHA-256 identifies the published artifact, not independent publisher signing.

The CI downloads the original DEB, checks metadata, inventories its files
and control scripts without executing them, and simulates the dependency
plan against the signed Ubuntu archive. Font EULA dependencies or package
removal stop review. The AppImage smoke exposed missing XCB dependencies and then failed to find
an editor window in Xvfb. For the desired native distribution path, CI now
installs the exact DEB after the metadata/dependency checks, verifies no
preinst/postinst/prerm/config scripts, saves the upstream license and runs
the original desktop launcher unprivileged. This is only disposable CI,
not ISO distribution approval. The upstream postrm purge branch deletes
preferences in /home/*: never auto-purge on an installed user system.

Next inspect the control scripts, license and font provenance, verify the
official update/signature mechanism, then install the native package in
disposable rootfs with no unreviewed external repositories. Verify offline
DOCX/XLSX/PPTX open, edit, save and reopen, PDF, printing, Cyrillic and file
associations. Only after actual native package and license gates pass
enable Standard/Complete provisioning. Do not ship the 10.0.0 version
indefinitely; update review must track security releases.

## Native installed-image engineering review

LOCALZET_EXPERIMENTAL_ONLYOFFICE=1 is accepted only with a disposable build
root and Standard/Complete archive profile. The exact reviewed 10.0.0-169
DEB is downloaded with the pinned size and SHA-256, rechecked for control
scripts, installed with no recommended fonts or package removals and no new
repositories. The target stores a version, original manifest and dependency
plan, and retains the original license. The separate CI workflow assembles
an ISO, installs it from USB in QEMU with networking disabled and launches
the native editor in the authenticated GNOME user session. It uploads only
logs and screenshots, not the image. This does not satisfy the AGPL source
and third-party attribution/redistribution review, nor DOCX/XLSX/PPTX editing
and update acceptance. The default profile remains planning-only.

## Installed runtime isolation, November 18

The 7edbc53 unified image passed BIOS/UEFI boot, explicit foreign-disk refusal with identical SHA-256 and installation to the blank NVMe. Its named DOCX window showed a loading skeleton with no fixture heading ink. The separate non-executive smoke additionally lacked xprop/xwininfo. Add x11-utils and compare the default real GNOME path with a fresh profile inside a separate Xvfb/Openbox display on an installed diagnostic image. Require actual blue fixture heading ink in both standalone and installed render tests. Isolated-X11 evidence is not release acceptance, and neither test disables the editor sandbox. The unified image retains the native default path.

## Independent installed diagnostics

The combined 239fcc5 image failed at managed rootless Docker before Office (44349355810). Office-specific diagnostic images omit optional Containers to isolate the editor; unified acceptance still requires both. Four modes: authenticated GNOME/Xwayland, software graphics, fresh profile in same real session, and separate Xvfb. All require actual fixture ink and preserve editor sandbox. No diagnostic pass is unified release acceptance.

## Normal menu and document launch

The native installed diagnostic on product-next b8a23a8 (44384520726) rendered the DOCX heading (1399 matching pixels), passed Wine and lock checks; repeated software/fresh-profile variants did not render, so the success is not yet a stability guarantee. The target now installs /usr/bin/localzet-office only when the actual vendor editor is installed, using the exact successful process-local X11 and C.UTF-8 environment, keeping the vendor sandbox and acceleration. This scopes locale to the editor process (the system locale is unchanged; editor language preference remains a separate review). A /usr/local/share/applications override retains the original vendor desktop ID, MIME associations and known desktop action arguments, leaves vendor files intact and rejects unknown Exec commands. Installed tests invoke the real product launcher; the catalog falls back to vendor executable for manually installed editions. Redistribution remains pending.
