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
