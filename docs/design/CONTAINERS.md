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
