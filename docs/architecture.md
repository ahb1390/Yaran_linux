# Yaran Linux build architecture

**English** ([architecture.md](architecture.md)) | فارسی ([architecture.fa.md](architecture.fa.md))

This document explains how the pieces of this repository fit together: what
`build.py` does, what the JSON manifests describe, when hooks run, and where
outputs and temporary files end up. It reflects the actual implementation in
`build.py`; nothing here is aspirational.

## Overview

Yaran Linux images are Debian live systems. A manifest selects an upstream
Debian suite, a package set, and a list of customization hooks. `build.py`
drives `debootstrap`, APT, and `chroot` to produce a root filesystem, then
packs it into SquashFS and assembles a BIOS+UEFI-bootable ISO with GRUB.

The builder itself is distribution-agnostic: it contains no Yaran Linux
branding. All branding, packages, and configuration live in the manifests,
`hooks/`, and `assets/`.

## Repository components

| Path | Role |
|---|---|
| `build.py` | The builder: configuration loading and validation, bootstrap, package installation, hook execution, SquashFS and ISO assembly |
| `Yaran-2.0-*.json`, `Yaran-Server-2.0-amd64.json` | Image manifests: one JSON file per published edition |
| `Yaran-2.0-amd64.json` | Legacy single desktop manifest, kept for compatibility, not built by CI |
| `hooks/common/` | Hooks shared by desktop and server images (Calamares, Fastfetch, CA certificates, asset cleanup) |
| `hooks/desktop/` | Desktop-only hooks (Plasma assets, SDDM autologin, firewall, sysctl, vendor repositories, external apps) |
| `hooks/server/` | Server-only hooks (CLI installer, journald, password policy, firewall, sysctl) |
| `scripts/ci-build.sh` | The single Debian build script CI runs inside a privileged container; installs dependencies, tests, validates, builds |
| `assets/` | Branding files copied into images by hooks: Plasma/SDDM theme, wallpapers, Calamares config, Fastfetch config, server installer files |
| `examples/` | Starting-point manifests for other Debian-family distributions |
| `tests/` | Unit tests for configuration and assembly, plus the optional QEMU boot smoke test |
| `.github/workflows/` | CI: `build.yml` (validation + edition builds), `image.yml` (reusable build job), `release.yml` (release builds) |

## The build pipeline

`LiveBuilder.build()` executes these steps in order. Each step prints a
banner with its name, so build logs show exactly where a failure happened.

1. **Prepare directories** (`prepare_dirs`) — reject overlapping or nonempty
   work/output paths, create `chroot/`, `iso/live/`, `iso/boot/grub/`, and
   `iso/.disk/` under the work directory.
2. **Bootstrap** (`run_debootstrap`) — run `debootstrap` into `chroot/` with
   the configured suite, mirror, components, variant, and architecture.
   `ca-certificates` is installed in the bootstrap step so that later HTTPS
   vendor repository fetches work.
3. **Mount pseudo filesystems** — bind-mount `/dev`, `/proc`, `/sys`, and
   `/run` into the chroot; all chroot steps need them.
4. **Pre-chroot hooks** (`pre_chroot_scripts`) — your `pre_chroot_scripts`
   run **on the host**, with the `ROOTFS` environment variable pointing at
   the chroot and the manifest's directory as working directory. This is
   where Yaran Linux stages assets and installs signed vendor repository
   keys before the first APT update.
5. **Configure APT** (`configure_apt`) — write `apt_sources` into
   `sources.list`, run `apt-get update`.
6. **Install packages** (`install_packages`) — apply `exclude_packages` as
   negative APT pins, run APT's dependency simulation, then install
   `live_packages` + `kernel_package` + `packages` with recommends disabled
   unless `install_recommends` is true.
7. **Configure users** (`configure_users`) — create the live user and groups,
   set or lock passwords per the manifest, lock root unless a root password
   is given.
8. **Configure system** (`configure_system`) — hostname, locale, timezone,
   `os_release` overrides, and the `services` enable/disable/mask lists.
9. **Post-install hooks** (`post_install_scripts`) — your hooks run
   **inside the chroot** as `bash -eu` scripts. Yaran Linux applies the
   desktop/server configuration here.
10. **Apply services** — run `systemctl` for each nonempty
    `services.enable` / `disable` / `mask` list.
11. **Regenerate initramfs** — `update-initramfs -u -k all` so hook-installed
    configuration is included in the boot image.
12. **Cleanup chroot** — remove caches and temporary hook files, clear logs
    and machine-id state, so the live system starts clean.
13. **Export kernel and initrd** — copy the newest kernel and its matching
    initramfs into `iso/live/` for the GRUB entries.
14. **Build SquashFS** (`build_squashfs`) — pack the chroot into
    `iso/live/filesystem.squashfs` with the configured compression (`xz` by
    default). `/boot` is retained inside the image so an installer that
    copies the live filesystem has a kernel and initramfs for the installed
    system.
15. **Write boot configs** (`write_boot_configs`) — generate
    `grub.cfg` with the default `live`, `live, nomodeset`, and
    `live, debug` entries (plus any custom `grub_menu.entries`), and build
    the BIOS and UEFI GRUB images, including El Torito boot images for
    BIOS-bootable media.
16. **Build ISO** (`build_iso`) — assemble the image with `xorriso`, write
    it to a temporary `.partial` file in the output directory, compute its
    SHA-256, and publish the ISO plus an `.iso.sha256` file atomically.

## Hooks: pre-chroot versus post-install

The two hook lists run at different stages, in different environments:

| | `pre_chroot_scripts` | `post_install_scripts` |
|---|---|---|
| Runs | On the host, before APT is configured | Inside the chroot, after packages and system configuration |
| Environment | Host toolchain and network; `$ROOTFS` set to the chroot | The target system itself |
| Typical use | Stage assets, install third-party repository keys | Install and configure applications, themes, services files |
| Yaran Linux examples | `hooks/desktop/stage-assets.sh`, `hooks/desktop/vendor-repos.sh` | `hooks/desktop/plasma-assets.sh`, `hooks/common/install-calamares.sh` |

Hook entries may be paths (resolved relative to the manifest directory) or
inline scripts. Pre-chroot hooks also run with the manifest directory as
their working directory, so invoking the builder from another directory does
not break relative asset copies. Hooks execute with Bash and `-eu`; they are
trusted code executed as root, and failures abort the build. Chroot hooks
are copied into temporary files and removed even on failure.

## Assets

`assets/` holds everything the hooks copy into images:

- `assets/yaran-plasma-theme/` — Plasma look-and-feel, SDDM greeter, color
  scheme, and defaults, laid out as an FHS tree (`usr/`, `etc/`) that hooks
  copy into the chroot; see the [theme guide](theme.md).
- `assets/wallpapers/` — wallpaper packages, also used as the GRUB
  background via `grub_menu.background`.
- `assets/calamares/` — the Calamares installer configuration and branding
  (`settings.conf`, `modules/`, `branding/`, and the `yaran-grub-install`
  helper).
- `assets/fastfetch/` — the Fastfetch configuration and logo shown in
  interactive Bash sessions.
- `assets/server/` — the server CLI installer: `/usr/local/bin/install-yaran`,
  its sudoers rule, and the `yaran-installer.service` unit that starts it on
  the live console.

Desktop images stage assets into `/.temp_assets/` inside the chroot
(`stage-assets.sh`), consume them in later hooks, and remove the staging
directory in `cleanup-assets.sh`, so nothing temporary remains in the image.

## Tests

- `tests/test_config.py` — configuration validation, hook path resolution,
  mount/unmount failure handling, APT pinning of exclusions, kernel export,
  and boot entry generation. No root required.
- `tests/test_boot_image.py` — regression test for the BIOS boot image
  assembly (guards against the truncated CD loader bug).
- `tests/test_iso_integration.py` — optional smoke test (skipped unless
  `RUN_BOOT_SMOKE=1`) that assembles a GRUB fixture ISO and boots it in
  QEMU, BIOS and (with OVMF) UEFI.

## Outputs and temporary files

| Path | Contents | Lifetime |
|---|---|---|
| Work directory (`--workdir` or a temp dir) | `chroot/`, `iso/`, mount bookkeeping | Deleted after a successful build unless `--keep-workdir`; **retained after failure** for inspection |
| Output directory (`--outdir`, default `output/`) | The ISO and `.iso.sha256` | Permanent; existing ISO names are refused |
| `__pycache__/`, `*.log` | Python bytecode, logs | Ignored by Git; safe to delete |

Both `build/` and `output/` patterns are covered by `.gitignore`. Before
removing a failed work directory manually, make sure nothing under it is
still mounted (`mount | grep <workdir>`); the builder prints a warning when
it retains a work directory.

## CI architecture

`build.yml` runs a `validate` job (unit tests, all manifests `--validate`,
`bash -n` over every shell script) and then fans out to the reusable
`image.yml` workflow for each edition: Minimal and Extended on `ubuntu-latest`,
ARM64 on a native `ubuntu-24.04-arm` runner, and Server on `ubuntu-latest`.
Each `image.yml` job runs `docker run --privileged debian:trixie
bash scripts/ci-build.sh <manifest>` and uploads the log (always) and the
ISO + checksum (on success). `release.yml` does the same for every edition
when a GitHub release is published, and attaches the files to the release.
See [Releases](releases.md) for details.
