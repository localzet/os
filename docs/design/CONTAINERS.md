# Localzet Containers — implementation stage 1

The first adapter lists real local containers and performs explicitly selected
start, stop and restart operations by full immutable ID. No GUI or Complete
profile is enabled by this PR. Default endpoint is the user's rootless Docker
socket; the privileged system socket requires explicit selection and existing
access. No sudo, socket chmod, docker group enrollment, remote environment
override or arbitrary command execution. Docker access is not a sandbox.

The CI fixture builds a scratch image from a signed Ubuntu busybox-static
package; no game, user data, network access or registry image is required.
Tests assert real engine state after each operation. Rootful CI alone does not
prove rootless setup or authorization UX; these are separate gates.

Next: GTK4/libadwaita split-pane UI with real inventory and confirmed actions,
live logs and metrics, Compose stacks, images, volumes, networks, build and
registry management, remote contexts with SSH/TLS, credential handling and
backups. Docker Desktop/Portainer parity remains a target, not a claim.

Stage 2 adds a native GTK4/libadwaita local workspace: asynchronous inventory,
search, actual selection/details, confirmed lifecycle actions and explicit
engine selection. Errors clear stale inventory rather than showing fabricated
state. Experimental packaging is opt-in; default ISO remains unchanged.
The initial GTK test captures actual startup; full GUI action automation,
rootless validation, design refinement and parity features remain required.

Stage 3 replaces the list with a native column view, scoped Professional dark
palette (light/high-contrast system styling preserved), real status counts,
readable connection error states and selected-container diagnostics. Metrics
are a one-shot Docker stats snapshot, not live graphs. Logs are explicit
snapshots (last 100 lines, 256 KiB maximum, 20 seconds), never cached or
uploaded by the app. The CI uses only its own synthetic fixture message.
Live streaming and Compose remain subsequent milestones.

Stage 4: read-only Compose project inventory via the official Compose CLI.
Test creates an isolated project with the locally built fixture image and
checks real status; no registry pull or host mounts. Config paths returned
by Docker are metadata only, not trusted paths to execute. Compose editing,
validation and explicit start/stop/deploy with reviewed project files remain
later milestones. This is not a complete Compose management interface.

Stage 5 exposes the existing Compose inventory in a native GTK dialog. It uses
the selected local engine and the same serialized worker as container actions.
Paths are plain selectable metadata, not links or executable inputs. Empty
inventories and engine errors are distinct. No Compose mutations or profile
changes; actual GUI interaction and rootless acceptance remain required.

Stage 6 adds read-only image, volume and network inventories with native GTK
views. Only allowlisted metadata is displayed; labels, mount paths, secrets
and environment variables are not requested for display. No create, remove,
pull, prune or network changes are exposed. The disposable Docker CI creates
its own isolated fixtures and checks actual inventory. Interactive resource
view and rootless acceptance are still required.

Stage 7 adds explicitly confirmed local volume and internal bridge creation,
plus image and local network removal by full ID without force or prune.
Built-in networks and multiply referenced images are rejected. Volume removal
is intentionally absent. Docker remains the authority on in-use resources;
name checks before creation are not atomic against other clients. GUI and
rootless acceptance remain required. No profile or installer changes.

Stage 8 adds explicit registry pulls with tag or SHA-256 digest and a bounded
10-minute timeout, plus creation from a full local image ID without starting
or pulling implicitly. The first deployment profile uses no network, no host
mounts or published ports, read-only rootfs, UID/GID 65534, dropped capabilities,
no-new-privileges, 512 MiB memory and 256 PID limit. Image-declared volumes may
still be created by Docker; this is not a sandbox. Arbitrary images may be
incompatible with this profile. Port mappings, environment, named mounts and
network selection remain future work. Unit tests cover pull argument validation;
real CI creates a local fixture and checks its actual engine configuration,
without depending on an external registry. Live registry, interactive GTK and
rootless acceptance remain pending. No profile or installer changes.

Stage 9 adds explicit localhost TCP/UDP mappings, non-secret environment,
existing default local named volumes under /data, network selection (none,
bridge or existing local bridge ID), CPU/RAM and restart policy. The restricted
UID, read-only rootfs and capability settings remain mandatory. A native form
shows a second confirmation with environment names only. Environment values
are visible to Docker and may be visible in process arguments; do not use
for secrets. Volume driver options are rejected, but name-based volume checks
are not atomic against other clients. No arbitrary bind mounts or host mode.
CI inspects the actual advanced container configuration, not service reachability.
Interactive GTK, rootless, live registry and deployment runtime QA remain open.

Stage 10 introduces Compose Studio with a native split editor and generated
configuration preview. The first input format is a strict JSON subset of YAML:
1–16 named services with a full local image ID per service. All other fields
are rejected; the generator inserts the restricted profile. Compose config
validation runs on a private temporary file with no project env file, external
includes, builds or host paths. No user-provided file is executed or opened.
Edits invalidate previous previews. CI exercises actual Compose validation
without deployment. Full YAML parsing/highlighting, persistent projects,
local image existence checks, deployment and project lifecycle are subsequent
milestones, as are interactive GTK and rootless acceptance.

Stage 11 adds confirmed lifecycle actions for a restricted Studio document.
Project name and container labels derive from the generated document digest;
existing containers must match the fingerprint and service names. Up uses local
images only, no pull/build/recreate. Start/stop/restart and Down target verified
full container IDs; Down removes containers without deleting volumes or networks.
Labels are not an authorization boundary and concurrent Docker clients can race.
Operations may partially succeed; refresh actual state after errors. Projects
can be re-addressed by the same document, but persistent editor storage, ordinary
YAML, syntax highlighting and interactive GTK/rootless testing remain outstanding.

Stage 12 stores validated Studio source in private per-user content-addressed
files under ~/.local/share/localzet/compose. Atomic replacement, strict file
permissions, bounded reads and fingerprint verification protect against stale
or malformed files; this is not protection against the same user modifying
parent directories. Saved projects can be reopened and must be revalidated.
A read-only status action lists matching actual containers by both project and
document labels. Storage is shared across local engine choices, so actions use
the explicitly selected engine. No general YAML/highlighting, automatic
startup, project deletion or migration yet. CI covers storage and real state;
interactive GTK and rootless acceptance remain outstanding.

Stage 13 adds an explicitly opened monitoring dialog with sequential polling,
CPU/RAM history (60 samples), latest network/disk/PID readings and a filter
for the last 100 log lines (256 KiB maximum). Updates are scheduled five
seconds after each completed sample; pause stops new requests, not an active
request. Closing clears in-memory history and stops scheduling; bounded active
CLI requests may finish. Logs are not stored or uploaded. This is polling, not
Docker log streaming; network and disk charts, interactive GTK and rootless
acceptance remain pending. CI exercises real metric parsing and existing logs.

Stage 14 adds a native Dockerfile editor, explicit local context picker, local
tag and second confirmation. The reviewed Dockerfile bytes are passed via
stdin; context files can change and are sent according to Docker ignore rules.
Trusted inputs only: build executes Dockerfile instructions and is not a
sandbox. RUN networking is disabled; base images/frontend/remote sources may
still be fetched. Existing tags are rejected before build, but this check is
not atomic against concurrent clients. Build output is discarded in this
initial version; status and resulting tag are verified. A ten-minute CLI
limit does not guarantee daemon cancellation. CI builds the actual scratch
fixture through this adapter. Build arguments, streaming diagnostics, layer
history, interactive GTK and rootless acceptance remain pending.

Stage 15 adds explicit non-secret build arguments, opt-in build output (last
256 KiB, shown after completion), and image history limited to 256 entries
with ID, age and size only. Commands and comments are excluded from history.
Build arguments may be visible in process arguments and image metadata; they
are not a secret mechanism. Output is kept in memory only and can contain
sensitive data. CI checks real build argument propagation, diagnostics and
history. Streaming progress, cancellation, interactive GTK and rootless QA
remain outstanding.

Stage 16 adds explicit local image tagging and confirmed publication to a fully
qualified registry repository/tag. Docker CLI uses its existing credentials;
Localzet does not inspect or store auth data. Users authenticate separately.
Existing local destinations are rejected, and push checks the selected full
image ID against the local tag. These checks are not atomic against concurrent
Docker clients. Push transfers image layers and may replace a remote tag.
CI checks actual local tagging and mocked push command/guards; it never pushes
to an external registry. Live registry authentication/publication, GUI credential
management, tag removal, remote catalog and interactive/rootless QA remain open.

Stage 17 introduces an explicit VTE GTK4 terminal for running local containers.
The full container ID is revalidated; only /bin/sh or /bin/bash is selected.
Docker exec uses a fixed local socket and clean environment, without privileged
or user overrides. VTE supplies the interactive PTY and 2000-line scrollback;
no terminal history is persisted. Close cancels spawn and signals the local CLI
when possible, not the container; in-container processes can survive disconnect.
The experimental desktop package depends on gir1.2-vte-3.91. CI exercises the
shared VTE adapter with a real disposable Docker shell and verifies TTY and UID.
Full interactive dialog, resize/disconnect and rootless acceptance remain open.

Stage 18 adds a separate read-only SSH inventory using OpenSSH and a fixed
remote Docker command on unix:///var/run/docker.sock. Existing host keys and
keys/agent are required; BatchMode and strict host verification are enabled,
user SSH config and forwarding disabled. No remote mutations, auto-trust,
passwords or saved connections. Local engine selection remains unchanged.
Unit tests verify command construction and rejection; actual remote SSH,
TLS, remote rootless and interactive acceptance remain pending. Output length
is checked after capture; streaming output bounds are future work.

Stage 18 follow-up adds explicit remote start/stop/restart after fresh full-ID
and state validation. Each operation confirms the remote host and container
in the separate SSH dialog; errors require refresh. A disposable loopback
OpenSSH fixture exercises real remote lifecycle and rejects unknown host keys.
The local engine remains selected throughout. Saved connections, TLS, remote
rootless, live non-loopback deployment and interactive QA are still pending.
The VTE spawn adapter also supplies the GI child-setup data argument required
by the Ubuntu runner binding, correcting the previous real-engine failure.

Stage 18 context follow-up adds private named SSH/TLS endpoint metadata under
~/.local/share/localzet/remote-engines (0600 files, no overwrite, bounded reads,
no symlink reads). Saved profiles are reopened explicitly; a successful
inventory precedes saving. No private key or password contents are stored.
TLS inventory uses the fixed Docker CLI with --tlsverify and explicit
ca.pem, cert.pem and key.pem; the key must be private and user-owned. No
insecure fallback or TLS mutation. Unit tests cover transport configuration
and persistence; real TLS server/certificate acceptance and GUI validation
remain pending. Saved endpoint editing/removal, remote rootless and streaming
bounds remain open.

Stage 19 adds volume metadata, actual container references (including stopped
and created containers), and typed-name confirmation for deletion of unused
default local volumes. Deletion is irreversible and creates no backup. No force,
prune, driver options or mountpoint access. References are checked again on
execution; the daemon rejects in-use volume removal, but names are not immutable
identifiers and concurrent clients can replace a volume. Backup/restore, clone,
content browsing, size accounting and interactive/rootless QA remain pending.

Stage 19.2 adds offline TAR export of unreferenced default local volumes and
restore into a new named volume. Explicit trusted local BusyBox image with
/bin/busybox required; no pull, host bind mounts, or network. Helper runs with
limited capabilities (DAC_OVERRIDE), root inside the container; not a sandbox.
Archives are bounded to 128 MiB / 10000 entries, rewritten to USTAR with regular
files/directories only; no links, special files, traversal or special mode bits.
UID/GID are normalized to zero; ACL/xattrs and full metadata are not preserved.
Backup is private (0600), atomic no-overwrite publication; restore never
intentionally replaces existing volume, and partial new volumes remain on error.
Concurrent clients can race name checks; do not use during concurrent volume
management. Not database-consistent backup, no encryption, no large volumes.
CI exercises actual file roundtrip and overwrite refusal; clone, browsing,
full-fidelity backup and interactive/rootless acceptance remain pending.

Stage 20 replaces transient inventory dialogs with a persistent Aurora workspace:
compact sidebar, five navigable sections, filtered column tables, selection
inspectors, real container counters, shared status bar and engine selector.
Operations retain explicit review dialogs and existing backend guards. Palette
uses muted graphite/purple, modest corners, no glow; light/high-contrast modes
retain native system colors. Ctrl+1–5 selects sections. GTK CI captures dark/light
and navigates all five sections without fake inventory. Compose editor, terminal,
monitoring and operation forms remain dialogs. Full populated/rootless, responsive
and visual acceptance still required; this is not a final Aurora design sign-off.

Stage 21 integration gate: the real engine workflow now exercises the production
GTK application factory, explicit system-engine response, actual fixture rows,
selection and five workspace screenshots. This is widget-level integration,
not end-to-end mouse automation. A partial Complete archive ISO can be built
with LOCALZET_ARCHIVE_PROFILE=complete and LOCALZET_EXPERIMENTAL_CONTAINERS=1;
Docker, Compose and VTE packages are verified in the rootfs, system daemon/socket
and containerd are disabled, and no Docker group access is granted. The live
workflow builds this candidate on the consolidated PR or by manual input and
checks BIOS/UEFI boot; manual successful runs may upload a development ISO.
Rootless setup, installed-system launch and full Complete external components
remain acceptance gates. Do not label this a stable or complete release.

## NVIDIA GPU integration — stage 1

Local rootful engine only, with existing socket permission, working host NVIDIA
runtime and configured nvidia Docker runtime. `python3 -m localzet.containers
--rootful gpu-status` reports runtime configuration, not verified compute.
`gpu-probe sha256:<full-local-image-id>` runs a user-selected trusted local
CUDA image with fixed nvidia-smi entrypoint, no pull, no network, read-only
root, dropped capabilities and no elevation. It requires exact host/container
PCI GPU agreement. The probe verifies visibility, not CUDA kernel execution;
image output is not attestation and a timeout may leave a container running.
GPU device exposure is not a sandbox. No rootless or remote GPU support yet.
No NVIDIA repository, toolkit installation, daemon mutation or restart is
performed. NVIDIA documents separate rootful/rootless runtime configuration:
https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
Future work: review signed upstream packages and key fingerprint, explicit
administrator installation, preview/backup runtime configuration, no implicit
daemon restart, GPU-specific deployment options and physical compute test.

## Managed rootless engine — experimental

The optional Containers package includes an unenabled systemd user unit using Ubuntu's packaged dockerd-rootless.sh and rootlesskit. The GUI explicitly starts/stops only this unit, checks subordinate UID/GID allocation, refuses Live, existing user Docker units or foreign sockets, and verifies the daemon reports rootless. Separate data directory ~/.local/share/localzet/docker, no Docker context mutation, no linger, no system daemon or group changes. Stop retains data. No AppArmor/sysctl weakening. Disposable CI exercises a real imported BusyBox image under the rootless daemon and verifies the system daemon remains stopped. Installed-image GUI and GPU acceptance remain open.
