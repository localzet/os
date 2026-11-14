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
