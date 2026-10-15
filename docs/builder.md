# Building Debian-family live images

**English** ([builder.md](builder.md)) | فارسی ([builder.fa.md](builder.fa.md))

`build.py` consumes a JSON manifest and assembles a live ISO. Yaran Linux branding,
packages and hooks live in its manifests and `hooks/`, not in the builder.
Python 3.9 or newer is required; no third-party Python modules are needed.

## Start with another distribution

Copy `examples/debian-minimal.json` or `examples/ubuntu-minimal.json`. Set the
upstream suite, bootstrap mirror, APT components and sources, kernel package,
and your additional packages. The Ubuntu example uses Debian's `live-boot`
implementation available in Ubuntu's universe repository, not Casper.
The examples are starting points, not fully tested distribution releases.

```sh
python3 build.py examples/debian-minimal.json --validate
sudo python3 build.py examples/debian-minimal.json --workdir build-debian --outdir output-debian
```

Validation does not require root, build tools, or network access. It checks
configuration types, names, paths and contradictions; it does not check remote
package availability. Actual builds run APT's dependency simulation before
installing packages. Repository and package errors include the failing phase.

## Host requirements

The host must be Linux with working mounts and chroots, running as root. Use a
native amd64, arm64 or armhf host/container matching the manifest; the builder
refuses to start when `dpkg --print-architecture` differs from the manifest's
`architecture`. amd64 images include BIOS and UEFI; ARM images target machines
supporting GRUB UEFI and the selected kernel, not board-specific boot firmware.
Cross-architecture bootstrap and Secure Boot signing are not implemented. Other
architectures need additional kernel and GRUB mappings and boot assembly support.

The builder also requires these tools on the host PATH: `dpkg`, `debootstrap`,
`mksquashfs`, `xorriso`, `mmd`, `mcopy`, `mount`, `umount`, `chroot`,
`grub-mkimage`, and `mkfs.vfat`.

On a Debian amd64 host, install:

```sh
sudo apt-get install debootstrap debian-archive-keyring ca-certificates \
  squashfs-tools grub2-common grub-pc-bin grub-efi-amd64-bin grub-efi-ia32-bin \
  xorriso mtools dosfstools python3 xz-utils
```

`xz-utils` keeps `tar -xJf` usable for `.tar.xz` release artifacts on the
build host; the Node.js install hook additionally falls back to Python's
stdlib `lzma` module, so it still works on hosts without the `xz` binary.

For ARM use the matching `grub-efi-arm64-bin` or `grub-efi-arm-bin` package instead
of the amd64/BIOS GRUB packages. Include `/usr/sbin` in root's PATH. A derivative
needs a debootstrap suite script and archive signing key available on the host;
for Ubuntu use a suitable Ubuntu build host or install its archive keyring.
`debootstrap_script` and `debootstrap_keyring` can explicitly select these files.
No signature verification bypass is provided.

This builds systems using the Debian live-boot/initramfs-tools layout. A derivative
with another init system can replace `live_packages` and leave `services` empty,
then configure its init system in hooks. Changing a distribution name alone does
not make an incompatible bootstrap suite, kernel or live boot stack compatible.

> **Security note:** a full build runs `debootstrap`, your hooks, and package
> maintainer scripts as root, and mounts pseudo-filesystems under the work
> directory. Run builds only on machines you control, with a dedicated work
> directory, and review third-party hooks before including them — hooks are
> arbitrary root code.

## Command-line interface

```text
python3 build.py CONFIG [--workdir DIR] [--outdir DIR] [--keep-workdir] [--validate]
```

| Option | Default | Meaning |
|---|---|---|
| `CONFIG` | — | Path to the JSON manifest |
| `--workdir` | temporary directory | Working directory for the chroot and ISO tree |
| `--outdir` | `./output` | Where the ISO and its checksum are published |
| `--keep-workdir` | off | Keep working files after a successful build |
| `--validate` | off | Validate the manifest; no root or build tools needed |

## Building an ISO

Always validate first, then build into separate work and output directories:

```sh
python3 build.py Yaran-2.0-amd64-minimal.json --validate
sudo python3 build.py Yaran-2.0-amd64-minimal.json \
  --workdir build-minimal --outdir output-minimal
```

A successful build writes the ISO and a matching `.iso.sha256` file to the
output directory. The ISO is assembled into a temporary `.partial` file and
published atomically only after `xorriso` succeeds, so a failed assembly never
leaves a partial ISO under the final name. An existing ISO with the same name
is refused — choose a different output directory or remove the old file first.

### Building in Docker (as CI does)

CI builds every image inside a privileged Debian container. You can reproduce
this locally on any Linux host with Docker; the container needs
`--privileged` because the build performs mounts and chroots:

```sh
docker run --rm --privileged \
  -v "$PWD:/work" -w /work \
  debian:trixie bash scripts/ci-build.sh Yaran-2.0-amd64-minimal.json
```

The script installs the build dependencies for the container's architecture,
runs the unit tests and manifest validation, and then performs the full build.
For amd64 containers it also enables the QEMU boot smoke tests
(`RUN_BOOT_SMOKE=1 REQUIRE_UEFI_SMOKE=1`), which additionally require QEMU and
OVMF inside the container (installed by the script). Outputs land in
`output/`; the container image and any network access follow your Docker
configuration.

## Workspaces, output and failures

Use an empty dedicated work directory, separate from the output directory. A
nonempty work directory or overlapping paths are rejected. Failed builds retain
the workspace for inspection; there is no automatic resume. Unmount any remaining
mounts before manually removing a failed workspace, and use a fresh work directory
for the next attempt. Unmount failures stop image creation and cleanup; a mount
that reports busy is retried with backoff and finally detached lazily before the
build gives up.

Successful builds remove working files unless `--keep-workdir` is set, including
when the builder chose a temporary work directory. The final output is an ISO
and an `.iso.sha256` checksum. Repository contents and timestamps are not pinned,
so builds are not guaranteed byte-for-byte reproducible.

## CI builds and artifacts

CI uses native architecture runners and the shared Debian build script
`scripts/ci-build.sh`. Unit tests and manifest validation run first; the four
edition builds only start after the validate job succeeds. Every job uploads
its build log as an artifact even when the build fails; successful jobs upload
`output/*.iso` and `output/*.sha256`. Publishing a GitHub release additionally
attaches those files to the release. See [Releases](releases.md) for download
and verification steps.

## Verification

```sh
python3 -m unittest discover -s tests -v
for config in Yaran*.json examples/*.json; do
  python3 build.py "$config" --validate
done
find hooks scripts -name '*.sh' -exec bash -n {} \;
```

A full build and BIOS/UEFI VM boot should be checked before distributing an image.
Set `RUN_BOOT_SMOKE=1` to also assemble and boot a GRUB fixture in QEMU. This
requires the amd64 GRUB modules, QEMU and ISO tools; OVMF enables the UEFI check
(`REQUIRE_UEFI_SMOKE=1` makes a missing OVMF a failure instead of a skip).
CI requires both BIOS and UEFI checks for amd64. This fixture contains no OS.

Unit tests validate configuration and assembly behavior, not the availability
of all packages or desktop functionality. The minimal examples lock passwords;
choose a temporary test password or an appropriate autologin setup for VM testing.

## Common failures

| Symptom | Likely cause | Where to look |
|---|---|---|
| `Working directory must be empty` | Reused work directory from a failed build | Start with a fresh directory; unmount leftovers first |
| `Use a native <arch> host/container` | Cross-architecture build attempt | Use a matching host or container |
| `Unknown configuration keys` | Misspelled manifest key | See the [manifest reference](manifest.md) |
| `Package ... has no installation candidate` | Package missing from the configured repositories | The failing phase is printed; check `apt_sources` and the suite |
| debootstrap or key fetch fails | Network, mirror, or TLS/certificate problem | The build log names the failing step; `ca-certificates` is installed at bootstrap |
| GRUB/xorriso errors at the end | Missing GRUB packages or modules for the target architecture | Install the GRUB packages listed under [Host requirements](#host-requirements) |

For symptoms that persist, see [Troubleshooting](troubleshooting.md).

## Next steps

- [Architecture](architecture.md) — the build pipeline step by step
- [Manifest reference](manifest.md) — every field explained
- [Troubleshooting](troubleshooting.md) — detailed diagnosis guides
