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
