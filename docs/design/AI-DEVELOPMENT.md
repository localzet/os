# AI Development — Complete profile

Owner requirement: official Codex and Claude Code, MCP, developer tooling,
mandatory UserNet proxy with no direct fallback for agent networking.

## Current candidate

- Complete archive toolchain: Node.js/npm, Python venv, ripgrep, jq,
  bubblewrap and socat. Official CLI provisioning remains a pending upstream
  dependency; no unreviewed latest npm install at image-build time.
- Packaged localzet-ai launcher for fixed official client paths. Isolated
  network namespace, loopback proxy relay via Unix socket to the host's
  configured local HTTP proxy. No fallback to a direct internet connection
  if bwrap or the relay fails. No blanket environment changes on the desktop.
- GNOME manual loopback HTTP proxy and installed UserNet desktop entry
  are required. They do NOT attest ownership or Mihomo upstream route.
- Not a sandbox against malicious user code: writable project/home, local
  filesystem sockets and deliberately configured host services require
  additional boundary review. Agent-native sandbox remains enabled.
- GUI/browser OAuth, IDE extension routing, proxy loss mid-session,
  UserNet DIRECT rules, process ownership, DNS, websocket/streaming,
  and network namespace availability on Ubuntu 26.04 remain release gates.
  No claim of complete leak prevention until real network tests pass.
- MCP: native clients support local stdio and remote HTTP; local MCP subprocesses
  launched by the guarded CLI inherit its network namespace. Review each server,
  scope credentials, require consent for writes, never ship tokens. A remote
  cloud-side tool cannot be forced through the local UserNet proxy.
- Package provenance: pinned official releases, checksums/signatures and
  redistribution terms. Users sign in with their own accounts; no shared API
  keys. Provide browser/device login through a reviewed proxied flow.

References:
https://github.com/openai/codex
https://developers.openai.com/codex/mcp
https://code.claude.com/docs/en/setup
https://code.claude.com/docs/en/network-config
https://code.claude.com/docs/en/mcp
https://github.com/localzet/UserNet

## Local MCP server (implemented)
The desktop package ships /usr/bin/localzet-mcp, a local stdio server
with two read-only tools: system_info and gpu_inventory. It exposes no
shell, package install, arbitrary file, secrets or remote network tools.
Clients can register it explicitly using their native MCP settings
(command /usr/bin/localzet-mcp, no arguments). Existing user configuration
is not silently overwritten. Official remote docs MCP and workspace-specific
servers remain opt-in; no automatic execution of downloaded npm MCP packages.
Protocol unit tests and a real local network namespace/relay test are included.
The latter tests host loopback isolation and relay reachability, not UserNet's
upstream routing or authenticated provider traffic.

## User-owned client provisioning and workspace

Codex exact version 0.170.0 from the official GitHub release: validate tag, stable-release status, fixed asset name, reported size and GitHub-published SHA-256; extract only the expected regular binary. This digest is publisher-hosted metadata, not independent code signing. Claude Code resolves the official stable channel, then verifies the detached manifest signature against the sole documented Anthropic primary fingerprint 31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE and validates the linux-x64 binary checksum. A signed stable-channel version may change between separate installs; the exact resolved version and hash are recorded. Normal install requires a local UserNet proxy candidate and explicit confirmation of the version; curl explicitly uses that endpoint without NO_PROXY exceptions. No direct network fallback. No sudo, auto-login, arbitrary installer script, or existing CLI config modification. The versioned user-owned binary is published atomically; previous versions remain. Launch uses the existing network namespace, never the raw binary directly from the UI. CI downloads official clients separately and executes only --version in an offline namespace; no provider authentication. Runtime proxy ownership/route policy, authenticated login, actual provider requests, release pinning/redistribution and security review remain pending.
References: https://github.com/openai/codex/releases/tag/rust-v0.170.0 and https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing .

Artifact tests: original Codex and Claude Code binaries verified and executed offline in CI run 44349018987; no authenticated request was made. GUI initially failed on a missing GNOME proxy schema; now check schema availability before constructing Gio.Settings and fail closed with a visible status. Product deployment must also respect Anthropic's commercial terms and preserve its own authentication flow; no distribution approval is implied.
