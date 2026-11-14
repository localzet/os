# Installation profiles and applications

Owner-approved direction, 2026-11-14. Profiles are target manifests, not
currently installable profiles. All are selectively configurable. No
implicit external accounts or downloads; show source, size and consent.
Core OS and recovery work offline. Standard and Complete must be usable
without manually hunting for software.

| Capability | Minimal | Standard | Complete |
| --- | --- | --- | --- |
| Aurora, settings, browser, files, terminal, archive/PDF, recovery | yes | yes | yes |
| ONLYOFFICE Desktop Editors (office default; not LibreOffice) | optional | yes | yes |
| Telegram | optional | yes | yes |
| VLC, image viewer/editor, qBittorrent, print/scan | optional | yes | yes |
| Yandex Music official Linux app | optional | optional | yes |
| Chrome or Edge (user choice, one default browser) | optional | choice | choice |
| Discord | optional | optional | optional |
| NectarLink by thtbee | optional | yes | yes |
| Windows Runtime | optional | optional | yes |
| Steam/Proton, GOG/local games | optional | optional | yes |
| NetBird, UserNet and routing policies | optional | optional | yes |
| Docker Engine/Compose, Localzet Containers | optional | optional | yes |
| Git, VS Code, SSH, build tools, QEMU/KVM, OBS | optional | optional | yes |

GParted, disks, PCI/NVMe/SMART tools are mandatory on Live/recovery even if
the installed profile is Minimal. Keep dependencies, package sources, licenses,
checksums/signing, installed bytes, update path and rollback in a reviewed
manifest. Do not bundle proprietary binaries or copyrighted game assets until
redistribution terms are verified; use explicit official-source provisioning
where required. No silent remote shell installers. App selection is not a
guarantee of compatibility or successful integration.

## Office decision

ONLYOFFICE Desktop Editors replaces LibreOffice as default, supports documents,
spreadsheets, presentations and PDF offline. Native Linux package from the
official upstream (AGPLv3); inspect redistribution/branding terms, dependency
and signature provenance before bundling. No need for a server or cloud
account. Verify DOCX/XLSX/PPTX open/edit/save/reopen, PDF, printing, Cyrillic,
file associations and theme. Use official source:
https://www.onlyoffice.com/download-desktop
https://helpcenter.onlyoffice.com/desktop/installation/linux-version/desktop-install-ubuntu
https://github.com/ONLYOFFICE/DesktopEditors
Do not add unverified APT keys or a global trusted repository. Package id:
`onlyoffice-desktopeditors`. Integration remains planned until actual package
installation and desktop/file-open tests pass.
