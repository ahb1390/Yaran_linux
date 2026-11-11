# Releases and CI artifacts

**English** ([releases.md](releases.md)) | فارسی ([releases.fa.md](releases.fa.md))

This document explains how Yaran Linux images are produced by CI, the
difference between a successful build, a CI artifact, and an official
release, and how to verify what you download.

## The three levels of a build

| Level | What it is | Trust level |
|---|---|---|
| **Successful local build** | An ISO you built yourself from a specific commit | Highest — you controlled every step, but you must verify it yourself |
| **CI artifact** | An ISO + `.iso.sha256` uploaded by a successful workflow run | Tied to an exact commit; suitable for testing; not an official release |
| **GitHub release asset** | Numbered ISO parts + checksums attached to a published GitHub release | The project's official distribution channel |

Only the third level should be presented to end users as an official Yaran
Linux image. CI artifacts expire (GitHub retains workflow artifacts for 90
days by default) and are meant for testing and review.

## How CI builds work

The [Build & Validate workflow](https://github.com/ahb1390/Yaran_linux/actions/workflows/build.yml)
validates the source and builds the editions defined in the workflow matrix.
Each edition job uploads its build log and, on success, the original ISO and
its checksum as a CI artifact. CI artifacts are intended for testing and
are not the permanent public download channel.

## How releases work

The [Release Build workflow](https://github.com/ahb1390/Yaran_linux/actions/workflows/release.yml)
triggers when a GitHub release is **published**. It builds every edition in
the release matrix from the commit referenced by the release tag.

Before publishing release assets, the workflow splits every generated ISO
into numbered parts of at most 1800 MiB. This keeps every individual asset
below GitHub's per-file release limit (2147483648 bytes). The original ISO
is not attached as a single large file, and it is only deleted after the
parts have been verified to reproduce its checksum. Each edition publishes:

- `NAME.iso.part001`, `NAME.iso.part002`, and any following parts;
- `NAME.iso.sha256` — checksum of the reconstructed original ISO;
- `NAME.iso.parts.sha256` — checksums of all downloaded parts.

All editions are attached to the same GitHub release. The workflow fails if
a build does not produce the expected ISO, if any release asset is not
below GitHub's per-file limit, if an unsplit ISO is still present, or if
release assets cannot be prepared.

## Edition matrices: what CI builds vs what is released

| Image config | Build & Validate (push) | Release Build (release) |
|---|---|---|
| `Yaran-2.0-amd64-minimal.json` | ✅ | ✅ |
| `Yaran-2.0-amd64-extended.json` | ✅ | ✅ |
| `Yaran-2.0-arm64.json` | ✅ | ✅ |
| `Yaran-Server-2.0-amd64.json` | ✅ | ✅ |
| `Yaran-2.0-amd64.json` (legacy desktop) | ✅ | ❌ excluded intentionally |

The two workflows share every runner and artifact name; the release matrix
is exactly the build matrix minus the legacy `Yaran-2.0-amd64.json` entry.
That manifest is kept for compatibility, is built and tested on every push
to `main`, and is intentionally **not published**: none of the published
releases (`v2.0`, `v2.1`) ever contained a `Yaran-2.0-amd64.iso`, so
publishing it would silently change the released edition set.

`tests/test_release_workflows.py` enforces this contract. It fails if an
edition is added to one workflow but not the other, if a runner or artifact
label drifts between the matrices, if a push build ever passes
`release: true` to the shared image workflow, or if the release workflow
gains any trigger besides a published release. Only the four editions in
the table above are split, verified, and attached to a release.

## Cutting a release (maintainers)

1. Make sure the target branch is green and all edition builds pass.
2. Confirm that the version in the manifests matches the intended tag.
3. Create and **publish** a GitHub release with a tag such as `v2.0.1`.
   Draft releases do not trigger the workflow.
4. Wait for the Release Build run to finish, then verify that every edition's
   numbered parts and both checksum files are attached to the release.
5. Reassemble and verify at least one ISO before announcing the release.

## Downloading, reassembling, and verifying

Download **all** numbered parts for the edition you want, along with both
checksum files, into the same directory. Do not rename the files.

From the repository checkout, run:

```bash
bash scripts/join-iso-parts.sh Yaran-2.0-amd64-minimal.iso
```

Alternatively, if the parts and checksum files are already in the current
directory, the equivalent manual commands are:

```bash
sha256sum -c Yaran-2.0-amd64-minimal.iso.parts.sha256
cat Yaran-2.0-amd64-minimal.iso.part[0-9]* > Yaran-2.0-amd64-minimal.iso
sha256sum -c Yaran-2.0-amd64-minimal.iso.sha256
```

The `part[0-9]*` pattern matches only the numbered parts — never the
`Yaran-2.0-amd64-minimal.iso.parts.sha256` manifest — and the parts are
zero-padded, so glob order is the same as part order. The first checksum
verifies every downloaded part. The final checksum verifies that the
reconstructed ISO is byte-for-byte identical to the original build. If
either check fails, download the missing or damaged part again before
using the ISO.

`scripts/join-iso-parts.sh` performs these same steps: it reads the part
list from the manifest, verifies every part, reconstructs the ISO into a
temporary file, compares it with `NAME.iso.sha256`, and only then renames
it into place. It refuses to overwrite an existing `NAME.iso`.

CI artifacts require a GitHub account and are downloaded from the workflow
run page (`Actions` → select the run → *Artifacts*). Release assets are
available from the public release page.
