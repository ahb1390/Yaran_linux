# Yaran Linux

[English](README.md) | **فارسی** ([README.fa.md](README.fa.md))

[![Build](https://github.com/ahb1390/Yaran_linux/actions/workflows/build.yml/badge.svg)](https://github.com/ahb1390/Yaran_linux/actions/workflows/build.yml)
![Debian](https://img.shields.io/badge/base-Debian%2013-A81D33?logo=debian&logoColor=white)
![Architectures](https://img.shields.io/badge/architectures-amd64%20%7C%20arm64-4B6CB7)

Yaran Linux is a Debian 13-based operating system built as reproducible live
ISO images. It ships a polished KDE Plasma desktop in two AMD64 editions plus
an ARM64 desktop image, and a headless server edition with a guided
command-line installer. Every image is defined by a JSON manifest and built by
a single, distribution-agnostic Python builder.

## Project status

Yaran Linux 2.0 is pinned to Debian 13 (Trixie) and enables the matching
security, updates, and backports repositories. The following legend is used
throughout the documentation:

| Symbol | Meaning |
|---|---|
| ✅ | Implemented and verified (successful CI builds or tests) |
| 🟡 | Implemented but not yet exercised end-to-end |
| 📋 | Planned or proposed; not implemented |

Current status of the editions:

| Edition | Manifest | Status |
|---|---|---|
| Desktop Minimal (AMD64) | `Yaran-2.0-amd64-minimal.json` | ✅ Built and tested in CI |
| Desktop Extended (AMD64) | `Yaran-2.0-amd64-extended.json` | ✅ Built and tested in CI |
| Desktop (ARM64) | `Yaran-2.0-arm64.json` | ✅ Built in CI on a native ARM64 runner |
| Server (AMD64) | `Yaran-Server-2.0-amd64.json` | ✅ Built and tested in CI |
| Legacy desktop (AMD64) | `Yaran-2.0-amd64.json` | ✅ Built and tested in CI (not published in releases) |

Secure Boot signing, cross-architecture bootstrap, and architectures other
than amd64/arm64/armhf are **not implemented** (📋).

## Design goals

- **Stable:** Yaran Linux 2.0 tracks Debian 13 (Trixie) with the matching
  security and stable-updates repositories.
- **User-friendly:** The live desktop session provides Plasma on both Wayland
  and X11, modern web browsing, common file formats, screenshots,
  networking, audio, Bluetooth, power and firmware management, disk-health
  monitoring, and a branded graphical installer.
- **Lean:** Packages install without automatic recommendations. Each image
  carries a deliberately small application set instead of multiple programs
  for the same task.

Package additions should solve a common desktop need, hardware requirement,
security issue, or accessibility problem. Optional specialist applications
belong in the repositories rather than the base image.

## Editions and applications

Both AMD64 desktop editions share the same Plasma desktop, branding, and
live experience. All desktop images ship Fastfetch (shown when an interactive
Bash terminal opens), the Flathub Flatpak remote, and the Calamares graphical
installer.

**Base application set (Minimal and Extended):** Firefox ESR, LibreOffice
(Writer, Calc, Impress, Draw, Base, Math), VLC, Telegram Desktop, Google
Chrome (from Google's signed APT repository), Hiddify and v2rayN (pinned
official `.deb` releases with SHA-256 verification), Dolphin, Kate, Konsole,
Gwenview, Okular, Ark, Spectacle, KCalc, Partition Manager, Plasma Discover
with Flatpak backend, Print Manager, timeshift, plus firmware, Mesa/Vulkan
graphics, PipeWire audio, Bluetooth, AppArmor, nftables, the
xdg-desktop-portal screen-sharing stack, full Persian/CJK/emoji fonts, and
the `unattended-upgrades` tooling (disabled by default — updates are
user-initiated via `yaran-update`, see the
[update policy](docs/updates-policy.md)).

**Extended adds** on top of the base set: GIMP, VirtualBox 7.2 (from
Oracle's signed APT repository), VSCodium and Obsidian (pinned official
`.deb` releases with SHA-256 verification), and a development toolchain
(`build-essential`, `git`, `dkms`, `linux-headers-amd64`, Node.js 26 with
`npm`/`npx` from the pinned official tarball under `/usr/local` (Debian
trixie only packages Node.js 20.x, and adding an external APT repository
violates the repository policy), `python3`, `python3-pip`, `python3-venv`,
`lazygit`).

The ARM64 image omits the AMD64-only components (Google Chrome, Telegram,
VirtualBox, the vendor `.deb` downloads, and some VA/VDPAU and ALSA
packages) because those do not publish ARM64 builds.

The server image ships administration, diagnostics, storage, networking,
security, container (Podman), and virtualization (QEMU guest agent) tools
with SSH installed but disabled until the administrator enables it.

## Building an ISO

The builder supports configurable Debian-family live images. See the
[builder guide](docs/builder.md) for host dependencies, architecture
requirements, and every build option. Full builds require root;
configuration validation does not.

```bash
python3 build.py Yaran-2.0-amd64-minimal.json --validate
sudo python3 build.py Yaran-2.0-amd64-minimal.json --workdir build --outdir output
```

Use `Yaran-2.0-amd64-extended.json` for the full edition,
`Yaran-2.0-arm64.json` for the ARM64 image (requires a native ARM64 host),
and `Yaran-Server-2.0-amd64.json` for the headless server. Generated files
are written to `output/`; temporary build state is kept in the work
directory and ignored by Git.

More guides:

- [Architecture](docs/architecture.md) — how the builder, manifests, and
  hooks fit together
- [Manifest reference](docs/manifest.md) — every manifest field and how to
  add packages safely
- [Troubleshooting](docs/troubleshooting.md) — symptoms, logs, and verified
  fixes for common build and boot failures
- [Releases](docs/releases.md) — how CI artifacts and GitHub releases work
- [Theme guide](docs/theme.md) — the visual identity and where it lives
- [Contributing](CONTRIBUTING.md) — branches, tests, and pull requests

## Testing

Run the unit tests (no root required):

```bash
python3 -m unittest discover -s tests -v
```

CI additionally runs a BIOS **and** UEFI boot smoke test on AMD64
(`RUN_BOOT_SMOKE=1 REQUIRE_UEFI_SMOKE=1`): a GRUB fixture ISO is assembled
and booted in QEMU. The fixture contains no operating system; a full-image
boot test in a VM should still be done before distributing an ISO. See the
[builder guide](docs/builder.md#verification) for details.

### Test in QEMU

For an AMD64 desktop ISO, run from the project directory:

```bash
qemu-system-x86_64 -m 4096 -smp 2 -boot d \
  -cdrom output/Yaran-2.0-amd64-minimal.iso
```

The GRUB menu appears, then the live session starts automatically. Select
the `live, debug` entry to see boot messages, or `live, nomodeset` when
troubleshooting a blank graphical display. Use QEMU's graphical window; the
default boot entries do not configure a serial console. ARM64 images require
an ARM64 virtual machine and matching UEFI firmware.

If an older AMD64 image stalls at `Booting from DVD/CD...` before GRUB
appears, rebuild it with the current builder. Earlier builds truncated
GRUB's CD loader to 512 bytes, producing an ISO that built successfully but
could not boot via BIOS.

## Getting the images

- **CI artifacts:** every successful run of the
  [Build workflow](https://github.com/ahb1390/Yaran_linux/actions/workflows/build.yml)
  uploads each ISO together with its `.iso.sha256` checksum and the build
  log as downloadable artifacts. See [Releases](docs/releases.md) for how to
  download and verify them.
- **Releases:** publishing a GitHub release triggers
  [the release workflow](https://github.com/ahb1390/Yaran_linux/actions/workflows/release.yml),
  which rebuilds all four images and attaches the ISOs and checksums to the
  release. No release has been published yet (🟡).

Verify any downloaded image before use:

```bash
sha256sum -c Yaran-2.0-amd64-minimal.iso.sha256
```

## Trying and installing

**Desktop:** boot the ISO, and the live session logs in automatically as
`admin` (live password: `yaranlinux`). The installer is available as
`Install Yaran Linux.desktop` on the desktop; run it to install to disk.

**Server:** boot the live media as `admin` (live password: `yaranlinux`).
The text-interface installer starts automatically on the first console; it
lists unused disks with capacity and model, asks for an installed hostname,
time zone, and a new admin password, and requires explicit confirmation
before erasing the selected disk. You can also run `sudo install-yaran`
from a local console. SSH is installed but intentionally disabled on live
media until the administrator changes the live password and enables the
service.

Never use the published live passwords on a production installed system.

## Project layout

- `build.py` — configurable Debian-family live ISO builder
- `Yaran-2.0-*.json` — desktop image manifests
- `Yaran-Server-2.0-amd64.json` — headless AMD64 server manifest
- `hooks/` — image customization scripts (`common/`, `desktop/`, `server/`)
- `scripts/ci-build.sh` — the shared Debian build script used by CI
- `examples/` — minimal Debian and Ubuntu starting-point manifests
- `assets/` — Plasma, SDDM, Calamares, Fastfetch, and wallpaper branding
- `tests/` — unit tests and the QEMU boot smoke test
- `.github/workflows/` — pull request, branch, and release builds
- `docs/` — [documentation index](docs/)

## Contributing

Bug reports, fixes, and documentation improvements are welcome. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for the branch layout, required tests,
and pull request process, and [troubleshooting](docs/troubleshooting.md)
before filing build failures. Use the
[issue tracker](https://github.com/ahb1390/Yaran_linux/issues) for bug
reports and feature proposals.

## License

Yaran Linux is distributed under the terms of the [LICENSE](LICENSE) file
in this repository.
