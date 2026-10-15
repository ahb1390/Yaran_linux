# Manifest reference

**English** ([manifest.md](manifest.md)) | فارسی ([manifest.fa.md](manifest.fa.md))

Every Yaran Linux image is described by one JSON manifest consumed by
`build.py`. This document lists every accepted field, its default, and its
validation rules, exactly as implemented in the builder. Unknown keys are
rejected, so a misspelled setting fails validation instead of silently
disappearing.

Validate a manifest without root or network access:

```sh
python3 build.py path/to/manifest.json --validate
```

## Minimal example

```json
{
  "distro_name": "Yaran",
  "version": "2.0",
  "architecture": "amd64",
  "suite": "trixie",
  "apt_mirror": "http://deb.debian.org/debian",
  "apt_components": ["main", "contrib", "non-free", "non-free-firmware"],
  "apt_sources": [
    "deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware",
    "deb http://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware",
    "deb http://security.debian.org/debian-security trixie-security main contrib non-free non-free-firmware"
  ],
  "hostname": "yaran",
  "live_username": "admin",
  "live_user_password": "yaranlinux",
  "root_password": null,
  "packages": ["kde-plasma-desktop", "firefox-esr"],
  "pre_chroot_scripts": [],
  "post_install_scripts": [],
  "iso_filename": "Yaran-example.iso",
  "iso_volume_id": "YARAN_EXAMPLE"
}
```

## Required fields

| Key | Type | Rules |
|---|---|---|
| `distro_name` | string | Nonempty, single line; no `"` `\` `` ` `` `$` `;` `{` `}` characters (they would end up in boot configuration) |
| `version` | string | Same rules as `distro_name` |
| `suite` | string | Upstream debootstrap release, e.g. `trixie` or `noble` |
| `apt_mirror` | string | Bootstrap mirror URL |
| `packages` | list | Package names (`[a-z0-9][a-z0-9+.:_-]*`); may be empty |

## Identity and architecture

| Key | Default | Notes |
|---|---|---|
| `architecture` | `amd64` | One of `amd64`, `arm64`, `armhf`. Must match the build host's `dpkg --print-architecture` |
| `hostname` | slug of `distro_name` | A single valid DNS label, ≤ 63 chars |
| `kernel_package` | Debian metapackage per architecture (`linux-image-amd64`, `linux-image-arm64`, `linux-image-armmp`) | Override for derivatives |
| `iso_filename` | `<slug>-<version>-<arch>.iso` | Must be a plain `.iso` filename: `[A-Za-z0-9][A-Za-z0-9_.-]*\.iso`. An existing file with that name is refused at build time |
| `iso_volume_id` | uppercased `distro_name` | 1–32 letters, digits or underscores; becomes the ISO volume label and the primary GRUB search key |

Legacy aliases `arch` (for `architecture`) and `debian_distro` (for `suite`)
remain supported; conflicting alias + new key pairs are rejected.

## APT configuration

| Key | Default | Notes |
|---|---|---|
| `apt_components` | `["main"]` | Also passed to debootstrap; must be nonempty |
| `apt_sources` | one `deb` line built from mirror/suite/components | Full source lines. **No implicit security/updates repositories** — list every repository you want, including updates, security, backports, and third-party ones |
| `install_recommends` | `false` | Applies to both APT's simulation and the actual installation |
| `vendor_repositories` | `false` | Explicit opt-in allowing hooks to add **non-Debian** APT repositories to `/etc/apt/sources.list.d/`. Without it, any `pre_chroot_scripts` hook that ships a vendor package (Google Chrome, VirtualBox, …) fails validation, and `hooks/common/verify-image.sh` fails the build if it finds a vendor source that the manifest did not opt into. Forwarded to hooks as `YARAN_VENDOR_REPOSITORIES=1` |
| `exclude_packages` | `[]` | Installed as negative APT pins that prevent selection; must not overlap explicitly requested packages |
| `debootstrap_variant` | omitted | Normally `minbase` or `buildd` |
| `debootstrap_script`, `debootstrap_keyring` | omitted | Existing host file paths (relative to the manifest or absolute) selecting a custom suite script or signing keyring |

Because a derivative does not inherit Debian's repositories automatically,
`apt_sources` must be complete: for example, an Ubuntu-based manifest needs
its own updates line if it wants updates.

## Live system

| Key | Default | Notes |
|---|---|---|
| `live_username` | `user` | Valid non-root account name, or `null` to skip live user creation |
| `live_user_password`, `root_password` | `null` | `null` locks password authentication; empty string deletes the account; any other string sets that password |
| `user_groups` | `sudo`, `audio`, `video`, `plugdev`, `netdev` | Groups for the live user |
| `live_packages` | `live-boot`, `live-config`, `live-config-systemd`, `live-boot-initramfs-tools`, `initramfs-tools`, `tzdata`, `systemd-sysv`, `sudo`, `locales` | Providing this key **replaces the whole default list** |
| `locale`, `timezone` | `en_US.UTF-8`, `UTC` | Timezone is relative to the zoneinfo directory (e.g. `Asia/Tehran`) |
| `boot_append` | `quiet` | Kernel arguments for the live entries; same character restrictions as `distro_name`. Add `noautologin` to disable live session autologin |
| `squashfs_compression` | `xz` | Also `zstd`, `gzip`, `lzo`, `lz4` when supported by the host tools and the target kernel |
| `services` | `{"enable": [], "disable": [], "mask": []}` | systemd units; any failure stops the build |
| `os_release` | `{}` | Upper-case field overrides merged into `/usr/lib/os-release`; unspecified upstream fields remain intact |

Null passwords lock password authentication; they do not disable live
session autologin or sudo configuration. Yaran Linux manifests retain their
published live passwords (`admin` / `yaranlinux`). Never use these defaults
for a production installed system.

The old unused `splash` key should be replaced by `boot_append`; the legacy
`security_mirror` key should be replaced by explicit `apt_sources`.

## Hooks

| Key | Default | Notes |
|---|---|---|
| `pre_chroot_scripts` | `[]` | Host hooks run after bootstrap and before the first APT update; `$ROOTFS` points at the chroot |
| `post_install_scripts` | `[]` | Chroot hooks run after packages, users, and system configuration |

Entries may be paths (relative to the manifest) or inline scripts. Hooks run
with Bash and `-eu` as root and are trusted code. Prefer `services` and
`os_release` for common configuration; use hooks for distribution-specific
files and applications. See [Architecture](architecture.md#hooks-pre-chroot-versus-post-install)
for the exact execution order.

## Boot menu

| Key | Default | Notes |
|---|---|---|
| `grub_menu` | generated defaults | Object that may contain `timeout`, `default`, `background`, and/or `entries` |
| `grub_background` | omitted | Legacy top-level background path; prefer `grub_menu.background` |

- `background` is a PNG/JPG/TGA path **relative to the manifest directory**.
  Configuring it enables GRUB's graphical terminal and embeds the required
  image modules.
- `entries` is a list of menu entries with `title`, `linux`, `initrd`, and
  optional `parameters`; the kernel/initrd paths are **relative to the ISO
  root** (e.g. `/live/vmlinuz`). Omitting `entries` keeps the generated
  `live`, `live, nomodeset`, and `live, debug` entries.

## Yaran Linux manifests

| Manifest | Edition | Notes |
|---|---|---|
| `Yaran-2.0-amd64-minimal.json` | Desktop Minimal | Base KDE Plasma desktop + Calamares |
| `Yaran-2.0-amd64-extended.json` | Desktop Extended | Adds GIMP, VirtualBox, VSCodium, Obsidian, dev toolchain |
| `Yaran-2.0-arm64.json` | Desktop ARM64 | Omits AMD64-only applications |
| `Yaran-Server-2.0-amd64.json` | Server | Headless; CLI installer; SSH disabled on live media |
| `Yaran-2.0-amd64.json` | Legacy desktop | Kept for compatibility; not built by CI |

## Adding packages safely

1. **Prefer Debian packages.** Everything in `packages` must exist in the
   suite and components you configured. Validate, then check with a real
   build — validation does not query remote repositories.
2. **Third-party APT repositories** belong in a `pre_chroot_scripts` hook
   that writes a **signed** source: fetch the vendor's signing key over
   HTTPS, store it under `/usr/share/keyrings/` (or the staged
   equivalent), and reference it with `signed-by=` in the source line —
   exactly as `hooks/desktop/vendor-repos.sh` does for Google Chrome. Do
   not disable signature verification; the builder provides no bypass.
3. **Third-party `.deb` files without a repository** should follow the
   pattern in `hooks/desktop/install-external-apps.sh`: pin the exact
   official release URL and verify the download against a recorded
   SHA-256 before installing it with `apt-get install ./file.deb`, so APT
   resolves dependencies from your configured repositories.
4. **Architecture-specific additions** must be guarded. Vendor hooks in
   this repository check `dpkg --print-architecture` and skip cleanly on
   other architectures, which is what keeps the ARM64 image buildable.
   Never add an amd64-only package to a shared list without such a guard.
5. **Keep the set lean.** Package additions should solve a common need,
   hardware requirement, security issue, or accessibility problem.
