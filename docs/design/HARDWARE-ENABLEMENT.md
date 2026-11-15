# Hardware Enablement — automatic drivers and CUDA

User requirement: detect hardware automatically, fetch and configure applicable
drivers, and install a compatible CUDA Toolkit automatically when a supported
NVIDIA GPU is detected. Applies to installed Localzet OS, including Complete.
This is a release gate, not a promise that every device is supported.

## H1 — inventory and recommendation (current)
- Read PCI vendor/device/class and bound kernel driver without root. NVIDIA
  GPU class 03 / vendor 10de triggers CUDA planning; HDMI audio alone does not.
- Extend to USB, modaliases, CPU vendor, firmware missing in kernel logs,
  Secure Boot state, kernel ABI and hybrid graphics; distinguish absent
  hardware, missing firmware and unsupported devices.
- Resolve actual device aliases via Ubuntu ubuntu-drivers, signed archive
  candidates and exact kernel ABI. Do not hard-code the newest NVIDIA series.

## H2 — authorized installed-system transaction
- Installer option "Automatically install recommended drivers and CUDA"
  selected by default; show detected hardware, proposed packages, download
  and installed size, network and license requirements, and allow opt-out.
- Use Ubuntu's supported ubuntu-drivers workflow and APT signed repositories
  (resolute, updates/security, restricted/multiverse when necessary).
  No .run installers, random PPAs, curl | shell, automatic unsigned keys,
  disabled Secure Boot or blanket kernel blacklisting.
- Prefer compatible signed prebuilt kernel modules; if DKMS/MOK enrollment
  is necessary, explain and wait for explicit user enrollment. No automatic
  disabling of signature validation or enrollment of unknown keys.
- Install only in target or installed system, never on the host of an image
  build. No automatic reboot; keep previous bootable kernel and recovery entry.
- Resolve CPU microcode, linux-firmware, Wi-Fi/Bluetooth, sound, storage,
  printer/scanner and AMD/Intel Mesa/Vulkan (including gaming i386 as applicable).
- Support offline base install, missing-network retry, explicit recovery,
  idempotent transaction receipt, package-manager lock and free-space check.
  Nonessential driver failure must not render installation unbootable.

## H3 — NVIDIA compute and gaming
- Validate NVIDIA GPU PCI ID and compute architecture against supported driver
  and Toolkit release. Install driver first, reboot if required, validate
  module load and nvidia-smi, then automatically select compatible Toolkit.
- Signed Ubuntu 26.04 archive includes cuda-toolkit / cuda-toolkit-13-1
  (13.1) and nvidia-cuda-toolkit (12.4). These are candidates, not guarantees
  of compatibility. Select a tested branch for actual GPU and driver;
  do not install CUDA 13 on unsupported older GPU architectures.
- If official NVIDIA repository is required, review supported distribution,
  pinned keyring, origin priorities and package version. Prefer toolkit-only
  packages that do not silently replace Ubuntu's selected driver.
- Verify nvcc and a compiled CUDA kernel executing on the actual GPU;
  nvidia-smi alone is insufficient. Integrate Vulkan/PRIME/offload and
  suspend/resume for hybrid notebooks. Verify Steam/Proton/DXVK/VKD3D and
  The Witcher 3 on physical NVIDIA and AMD hardware.
- Complete: integrate NVIDIA Container Toolkit as a separately reviewed,
  explicit Docker GPU setup; test actual GPU access in a disposable container.
  Do not modify existing daemon configuration silently.
- Optional CUDA libraries (cuDNN, etc.) as workload-specific packages.

## H4 — settings and lifecycle
- GNOME Control Center hardware/driver integration, device inventory,
  current/recommended driver, CUDA status, progress, restart and recovery.
- Detect changed hardware on boot, replan without repeatedly reinstalling.
  Automatic security updates must preserve kernel/driver compatibility.
- Recovery mode: boot previous kernel/safe graphics, package transaction
  recovery and explicit rollback with no changes to other disks or EFI loaders.

## Acceptance matrix
- No GPU / virtual GPU / NVIDIA audio-only / AMD / Intel / hybrid Intel+NVIDIA.
- Modern NVIDIA, older supported NVIDIA, unsupported legacy NVIDIA, multiple
  GPUs, Secure Boot enabled/disabled, driver signing/MOK required.
- Offline install, insufficient space, interrupted download, broken APT,
  unsupported CUDA, kernel upgrade, rollback, reboot, suspend and resume.
- QEMU validates negative paths and package transactions only; GPU compute,
  actual Wayland graphics and gaming must be validated on physical hardware
  or explicitly provisioned GPU passthrough. No synthetic GPU success claims.

## Reference sources
- Ubuntu 26.04 release notes:
  https://documentation.ubuntu.com/release-notes/26.04/summary-for-lts-users/
- Ubuntu package inventory:
  https://packages.ubuntu.com/resolute/cuda-toolkit
  https://packages.ubuntu.com/resolute/nvidia-cuda-toolkit
- NVIDIA CUDA Linux installation guide:
  https://docs.nvidia.com/cuda/cuda-installation-guide-linux/

Current implementation is H1 read-only. localzet-hardware --resolve observes
Ubuntu's actual recommended packages and signed-kernel-module candidates,
running kernel, Secure Boot efivar state and python3-apt candidate version,
size and origin metadata. It queries only the existing cache; missing tools,
unknown firmware state and untrusted/mixed origins are explicit. Non-root
recommendations may be incomplete. Package origin is only a screening signal,
not a pinned-key verification of a full dependency transaction. CUDA candidate
availability is not GPU compatibility. No package transaction or automatic
installation is enabled yet.

Reference: https://ubuntu.com/desktop/docs/en/latest/how-to/graphics/install-nvidia-drivers/


H2.1: localzet-hardware --simulate resolves one actual desktop NVIDIA
recommendation to the generic kernel flavour metapackage, exact running ABI
prebuilt module package and driver metapackage. It blocks unknown Secure Boot,
ambiguous recommendations, unsupported kernel flavours, missing candidates,
APT recovery requirements, removals, downgrades, DKMS and unreviewed origins.
python3-apt marks dependencies in memory, reports versions and aggregate sizes,
checks conservative free-space headroom, and clears marks. No update, commit,
module loading or reboot. The simulation does not prove a signature will load,
reserve disk space, lock package state, validate CUDA, or authorize installation.
CI exercises real archive resolution for mesa-utils and unchanged dpkg status;
actual NVIDIA transaction and physical acceptance remain open.

H2.2: experimental installed-system administrator CLI
sudo /usr/sbin/localzet-install-drivers requires a real interactive terminal,
Localzet identity and supported non-Live root. No arbitrary package parameters,
no unattended mode. It reviews the actual driver transaction under APT system
lock, releases the lock for explicit fingerprint confirmation, then acquires
it again and commits the same revalidated in-memory marks with unauthenticated
downloads disabled. Root-owned receipt in /var/lib/localzet/hardware records
installing, failed-recovery-required or installed-reboot-verification-required.
Interrupted/failed receipts block retry pending administrator review. No
unattended reboot, rollback, CUDA, GUI, APT cache refresh or installer default
enablement yet. Existing system APT configuration is trusted; candidate origin
screening is not independent key pinning. CI exercises real commit with a
small signed hello package on a disposable runner, not a GPU installation.
Physical NVIDIA, Secure Boot signing and kernel recovery acceptance remain open.

H3.1: localzet-hardware --cuda queries actual nvidia-smi PCI bus IDs,
compute capabilities and running driver version. Every detected NVIDIA GPU
must be bound to nvidia and match runtime inventory. The resolver selects
reviewed Ubuntu cuda-toolkit-13-1 (13.1) or nvidia-cuda-toolkit (12.4) using
explicit compiler target sets and conservative full toolkit driver minima
590.44.01 and 550.54.15 respectively, not minor compatibility mode. Unknown
architectures or mixed GPUs with no common toolkit block installation.
The interactive administrator CLI accepts the fixed --cuda phase and uses
the same locked, fingerprint-confirmed APT transaction, with runtime identity
and a separate CUDA receipt. Driver/kernel changes are blocked; an incomplete
prior transaction blocks retry. No automatic reboot or unattended install.
Candidate selection is not an actual compute test. CI compares synthetic
architectures with real archive metadata; physical GPU, dependency acceptance,
compiler and CUDA kernel execution remain unverified.
References:
- https://docs.nvidia.com/cuda/archive/13.1.0/cuda-toolkit-release-notes/index.html
- https://docs.nvidia.com/cuda/archive/13.1.1/cuda-compiler-driver-nvcc/index.html
- https://docs.nvidia.com/cuda/archive/12.4.1/cuda-compiler-driver-nvcc/index.html
- https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html

H3.2: localzet-hardware --verify-cuda runs only as the desktop user. It
locates a supported nvcc, checks all NVIDIA GPUs and driver compatibility,
compiles a fixed original CUDA C++ probe with an explicit sm target per
architecture, allocates device memory, executes a kernel, synchronizes,
copies the computed value 42 to host memory and verifies exact PCI coverage.
Temporary files are private and removed, compiler and runtime have timeouts.
Failure exits nonzero. Unit tests simulate process results, not actual GPU
execution. Physical acceptance must run this command on the installed machine
and retain the JSON output; no GPU success claim until then. No privileged
receipt update, automatic setup orchestration or container GPU integration yet.

H4.1: first-boot NVIDIA/CUDA orchestration is available only in explicitly
experimental installer builds (LOCALZET_EXPERIMENTAL_HARDWARE_AUTO=1 and
LOCALZET_INSTALLER=1). The checkbox is off by default until physical acceptance;
only the selected target receives a root-owned policy and enabled timer.
The timer starts after boot without waiting for packages in the desktop boot
path. It refreshes signed archive indexes, detects NVIDIA graphics and either
installs the reviewed driver or uses an already working runtime. Following a
driver transaction it waits for a different boot ID and verifies the runtime
before selecting/installing CUDA. No automatic reboot. Offline refresh is
retryable next boot; interrupted/failed installation, changed PCI identity or
unsupported runtime stops for review. Terminal states do not reinstall on
later boots. State: /var/lib/localzet/hardware/first-boot.json (root only);
logs: journalctl -u localzet-hardware-firstboot.service. CUDA completion requires
an unprivileged compute probe, not an automatic success claim. Other hardware,
GUI progress, post-install verification automation and safe recovery remain
pending; no unattended default for production or physical GPU acceptance yet.
