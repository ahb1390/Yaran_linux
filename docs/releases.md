# Releases and CI artifacts

**English** ([releases.md](releases.md)) | فارسی ([releases.fa.md](releases.fa.md))

This document explains how Yaran Linux images are produced by CI, the
difference between a successful build, a CI artifact, and an official
release, and how to verify what you download. It reflects the workflows in
`.github/workflows/` as they exist today.

## The three levels of a build

| Level | What it is | Trust level |
|---|---|---|
| **Successful local build** | An ISO you built yourself from a specific commit | Highest — you controlled every step, but you must verify it yourself |
| **CI artifact** | An ISO + `.iso.sha256` uploaded by a successful workflow run | Tied to a exact commit; suitable for testing; not an official release |
| **GitHub release asset** | ISO + checksum attached to a published GitHub release by `release.yml` | The project's official distribution channel |

Only the third level should be presented to end users as an official Yaran
Linux image. CI artifacts expire (GitHub retains workflow artifacts for 90
days by default) and are meant for testing and review.

## How CI builds work

The [Build & Validate workflow](https://github.com/ahb1390/Yaran_linux/actions/workflows/build.yml)
runs on:

- pushes and pull requests touching manifests, `build.py`, hooks, scripts,
  tests, examples, assets, docs, or workflows (targeting the `main` branch),
- manual `workflow_dispatch` from the Actions tab (this is how the
  `rebrand/yaran-linux` branch builds are started).

It has two stages:

1. **`validate`** — unit tests, `--validate` on every manifest, and
   `bash -n` over every shell script. No image is built if this fails.
2. **Edition builds** — Minimal, Extended (both `ubuntu-latest`), ARM64
   (native `ubuntu-24.04-arm` runner), and Server, each in a privileged
   `debian:trixie` container running `scripts/ci-build.sh`.

Each edition job uploads:

- `<artifact>-log` — the full build log, **uploaded even when the build
  fails** (download this first when diagnosing);
- `<artifact>` — on success, `output/*.iso` and `output/*.sha256`
  (`compression-level: 0`, so the ISO is stored without re-compression).

Artifact names: `yaran-amd64-minimal`, `yaran-amd64-extended`,
`yaran-arm64`, `yaran-server-amd64` (each with a `-log` sibling).

## How releases work

The [Release Build workflow](https://github.com/ahb1390/Yaran_linux/actions/workflows/release.yml)
triggers when a GitHub release is **published**. It builds all four
editions with the same `image.yml` job and, because `release: true`, each
job attaches its `output/*.iso` and `output/*.sha256` to the release via
`softprops/action-gh-release` with `fail_on_unmatched_files: true` — if a
build produces no ISO, the release job fails instead of publishing a
partial release.

The release workflow builds from the commit the release tag points at, so
the ISOs correspond exactly to that tagged source.

## Cutting a release (maintainers)

1. Make sure the `rebrand/yaran-linux` (or target) branch is green: the
   latest Build workflow run must have succeeded for all four editions.
2. Decide the version string. The version in the manifests (`version`,
   `iso_filename`, `os_release`) should match the intended tag — update
   the manifests in a pull request first if they differ.
3. Create and **publish** a GitHub release with a tag such as `v2.0.1`.
   Draft releases do not trigger the workflow.
4. Wait for the Release Build run to finish, then verify all four
   ISO/checksum pairs are attached to the release.
5. Spot-verify a checksum (see below) and, ideally, boot one ISO in a VM
   before announcing the release.

## Downloading and verifying artifacts

**Release assets** are on the release page. **CI artifacts** require a
GitHub account and are downloaded from the workflow run page
(`Actions` → select the run → scroll to *Artifacts*).

Verify a downloaded ISO against its checksum file:

```bash
sha256sum -c Yaran-2.0-amd64-minimal.iso.sha256
```

The checksum file contains the SHA-256 and the ISO filename in
`sha256sum` format. To tie an artifact back to its source, compare the
workflow run's commit SHA (shown at the top of the run page) with
`git rev-parse HEAD` of your checkout, or build the same commit locally
and compare ISO checksums — noting that repository contents and timestamps
are not pinned, so two builds are not guaranteed to be byte-for-byte
identical even from the same commit.

## Status

All four editions currently build successfully in CI. No GitHub release
has been published yet; until one is, treat CI artifacts as the available
pre-release builds.
