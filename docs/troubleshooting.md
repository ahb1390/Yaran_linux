# Troubleshooting

**English** ([troubleshooting.md](troubleshooting.md)) | فارسی ([troubleshooting.fa.md](troubleshooting.fa.md))

This guide covers failures you can hit while building or booting Yaran Linux
images. Each entry follows the same structure: the error symptom, where the
relevant log is, the likely causes, diagnosis steps, and a safe fix. Every
error message quoted here is produced by the actual `build.py` code or the
CI scripts. Build steps print banners (`Running debootstrap`, `Installing
packages`, `Building squashfs`, `Building ISO image`, …), so the failing
phase is always visible in the output.

A build log in CI is uploaded as the `<artifact>-log` artifact of each job,
even when the job fails. Locally, capture the output with `tee`:

```sh
sudo python3 build.py Yaran-2.0-amd64-minimal.json \
  --workdir build --outdir output 2>&1 | tee build.log
```

## Manifest and configuration errors

**Symptom:** `✗ Build failed: Unknown configuration keys: ...`,
`Missing required keys: ...`, or another `BuildError` before any step banner
appears.

**Log:** the validation message on stderr; nothing else was executed.

**Causes:** a misspelled key (unknown keys are deliberately rejected), a
missing required field, conflicting legacy aliases (`arch` vs
`architecture`), an invalid hostname/locale/timezone, an `iso_volume_id`
longer than 32 characters, hook paths that do not exist, or a
`grub_background` path that is absolute or points to an unsupported file.

**Diagnosis:** run validation, which performs the same checks without root
or network:

```sh
python3 build.py Yaran-2.0-amd64-minimal.json --validate
```

**Fix:** correct the manifest against the [manifest reference](manifest.md).
Do not work around validation by renaming fields to guesses — every
accepted key is listed there.

## Required tool missing

**Symptom:** `✗ Build failed: Required tool not found: <name>` or
`This script must be run as root.`

**Log:** stderr, before the first step banner.

**Causes:** missing host packages, or `/usr/sbin` not in root's PATH
(needed for `chroot` and related tools).

**Diagnosis:** check the tool and your packages:

```sh
command -v debootstrap mksquashfs xorriso mmd mcopy grub-mkimage mkfs.vfat
dpkg -l debootstrap squashfs-tools xorriso mtools dosfstools grub2-common
```

**Fix:** install the packages listed in the
[builder guide](builder.md#host-requirements), and export
`PATH=$PATH:/usr/sbin` for root if `chroot` is not found.

## Wrong architecture host

**Symptom:** `Use a native <arch> host/container; detected <arch>`

**Log:** stderr, before the first step banner.

**Causes:** building the ARM64 manifest on an AMD64 machine (or vice
versa). The builder refuses cross-architecture builds; this is by design —
cross-architecture bootstrap is not implemented.

**Fix:** use a native host or container of the target architecture. CI uses
a native `ubuntu-24.04-arm` runner for the ARM64 image; locally, an ARM64
machine or a properly configured ARM64 container with emulation can be used.

## Work directory problems

**Symptom:** `Working directory must be empty: ...` or
`Work and output directories must not overlap`.

**Log:** the `Preparing directories` step banner precedes the error.

**Causes:** reusing a work directory from a previous failed build, or
pointing `--workdir` and `--outdir` at the same or nested paths.

**Diagnosis:** list leftover mounts from a previous failure:

```sh
mount | grep "$(realpath build)"
```

**Fix:** unmount anything still mounted (the builder retries busy mounts
and finally detaches lazily, but a manual check is safer), then remove the
directory and use a fresh one. There is no automatic resume of failed
builds.

## Bootstrap failures (debootstrap, network, certificates)

**Symptom:** the `Running debootstrap` step fails; messages mention
`E:` package retrieval, `Failed to fetch`, `SSL certificate problem`, or
keyring errors.

**Log:** debootstrap writes its detailed log inside the work directory
(`chroot/var/log/bootstrap.log` after a failure).

**Causes:** no network access from the build machine or container, a
mirror that does not carry the requested suite, a proxy that intercepts
HTTPS, missing `debian-archive-keyring` on the host, or a derivative suite
without a debootstrap script/keyring on the host.

**Diagnosis:** test the mirror directly and check DNS/time (wrong system
time breaks TLS):

```sh
curl -I http://deb.debian.org/debian/dists/trixie/Release
date -u
```

**Fix:** restore connectivity, fix the mirror URL in `apt_sources` /
`apt_mirror`, install `debian-archive-keyring` and `ca-certificates`, or
set `debootstrap_script` / `debootstrap_keyring` for a derivative. There is
no signature-verification bypass; do not add one.

## APT and package failures

**Symptom:** the `Installing packages` or `Configuring APT` step fails with
`E: Package '...' has no installation candidate`, `Unable to locate
package`, or `E: Unmet dependencies`.

**Log:** APT's full output is in the step's log section; the builder runs
APT's dependency simulation first, so resolution errors appear before
anything is installed.

**Causes:** a package name that does not exist in the configured
suite/components, a third-party repository that was never added (or added
in the wrong hook stage), `exclude_packages` overlapping an explicitly
requested package, or a repository that requires a key that failed to
install.

**Diagnosis:** check that the package exists in the configured sources,
and that any vendor repository hook ran in `pre_chroot_scripts` (so it is
on disk before the APT update):

```sh
apt-cache policy <package>
grep -r . chroot/etc/apt/sources.list.d/
```

**Fix:** correct the package name or add the missing repository via a
signed-source hook as described in
[the manifest guide](manifest.md#adding-packages-safely).

## Hook failures

**Symptom:** a `pre_chroot_scripts` or `post_install_scripts` step fails
with `Step '<name>' failed: ...`.

**Log:** the hook's own output immediately precedes the error; hooks run
with `bash -eu`, so the failing command and line number appear.

**Causes:** a hook running in the wrong environment — a chroot hook using
`$ROOTFS` (only pre-chroot hooks get it), or a pre-chroot hook assuming
packages are already installed (they are not yet). Also common: a network
fetch inside a hook without error handling.

**Diagnosis:** identify the environment: pre-chroot hooks run on the host
with `$ROOTFS` set; post-install hooks run inside the chroot. Re-run the
failing command manually in the right environment if the build retained
the work directory.

**Fix:** move the operation to the correct hook list, or make the hook
idempotent and network-tolerant. Chroot hook temporary files are removed
even on failure, so inspect them before cleanup or add `set -x` debugging.

## SquashFS build failure

**Symptom:** the `Building squashfs` step fails.

**Log:** `mksquashfs` output in that step's section.

**Causes:** insufficient disk space for the compressed image, an
unsupported compression for the host's `squashfs-tools`, or a corrupted
chroot (e.g. leftover mounts pointing into it — though the builder
unmounts and verifies before this step).

**Diagnosis:** check free space and tool support:

```sh
df -h .
mksquashfs -help 2>&1 | grep -iE 'zstd|lz4|lzo|xz'
```

**Fix:** free space (the image needs room for both the chroot and the
squashfs), or change `squashfs_compression` to a supported algorithm.

## GRUB and ISO assembly failures

**Symptom:** the `Writing GRUB configuration` or `Building ISO image` step
fails; messages may mention missing GRUB modules, `grub-mkimage`, or
`xorriso`.

**Log:** the respective step section; GRUB module errors name the missing
modules.

**Causes:** missing GRUB packages for the target architecture
(`grub-pc-bin`/`grub-efi-amd64-bin`/`grub-efi-ia32-bin` for amd64,
`grub-efi-arm64-bin` for arm64), a corrupted GRUB installation, or an ISO
volume label / filename problem (already validated, but a read-only output
directory also surfaces here).

**Diagnosis:**

```sh
command -v grub-mkimage xorriso
ls /usr/lib/grub/
```

**Fix:** install the GRUB packages from the
[builder guide](builder.md#host-requirements) and ensure the output
directory is writable. Note: an ISO that builds but hangs at
`Booting from DVD/CD...` indicates an old builder that truncated GRUB's
CD loader — rebuild with the current code.

## CI failures and missing artifacts

**Symptom:** a workflow run is red, or a run succeeded but an expected
artifact is missing.

**Log:** always check the `<artifact>-log` artifact first — it is uploaded
even on failure.

**Causes:** the `validate` job failed (unit tests, manifest validation, or
`bash -n` over shell scripts), a build step failed inside the Docker
container, the job timed out (the image job has a 120-minute limit), or a
successful build produced no ISO (the upload step is configured with
`if-no-files-found: error`, so an upload problem fails the job rather
than passing silently).

**Diagnosis:** open the failing job, download its log artifact, and search
for `✗ Build failed` or the failing step banner. Note that `build.yml`
triggers on pushes and pull requests targeting `main` and on manual
`workflow_dispatch`; pushes to other branches do not start it automatically.

**Fix:** fix the underlying build problem locally first (the Docker recipe
in the [builder guide](builder.md#building-in-docker-as-ci-does) reproduces
CI exactly), then push.

## Live boot problems

**Symptom:** the ISO boots to a GRUB menu but the session does not start,
the display stays black, or networking/audio is missing in the live session.

**Log:** select the `live, debug` GRUB entry to see boot messages.

**Causes:** a GPU that needs `nomodeset` (try the `live, nomodeset` entry),
insufficient VM resources, or an image built from a manifest with a broken
hook.

**Diagnosis:** boot `live, debug`; for VMs use at least 4 GB of RAM for the
desktop image. On real hardware, check that firmware for the device is
present in the image.

**Fix:** use the debug entry to identify the failing component. Desktop
autologin is configured by `hooks/desktop/live-autologin.sh`; the server
image deliberately boots to a text console with the installer service.

## Installation problems (server CLI installer)

**Symptom:** the `install-yaran` installer does not start on the live
console, or installation fails partway.

**Log:** the installer writes a log to `/tmp/yaran-installer.*` inside the
live session.

**Causes:** the installer service is enabled by
`hooks/server/install-cli-installer.sh`; an image built without that hook
has no installer. The installer only offers unused disks and requires
explicit confirmation before erasing one.

**Diagnosis:** run it manually from a local console:

```sh
sudo install-yaran
```

**Fix:** ensure the manifest includes the server hooks, and re-run the
installer. SSH is intentionally disabled on live media; enable it only
after changing the live password.

## Getting help

Before filing an issue, include: the manifest name, the exact command, the
failing step banner, the surrounding log excerpt, the host distribution and
architecture, and the output of `python3 --version` and
`dpkg --print-architecture`. Report problems on the
[issue tracker](https://github.com/ahb1390/Yaran_linux/issues).
