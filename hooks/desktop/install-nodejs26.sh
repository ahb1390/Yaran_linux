#!/bin/bash
# Install the official Node.js 26 toolchain into the image WITHOUT adding any
# APT repository: the pinned release tarball from nodejs.org (which bundles
# npm and npx) is extracted under /usr/local/lib/nodejs and linked onto
# PATH. Debian trixie only packages Node.js 20.x, and every external APT
# repository that ships newer Node (e.g. NodeSource) is forbidden by the
# Yaran repository policy — a tarball with pinned hashes is the compatible
# alternative. Runs on the build host with network access, writing straight
# into the bootstrap rootfs ($ROOTFS).
set -euo pipefail

: "${ROOTFS:?ROOTFS must point at the bootstrap rootfs}"

# Pinned upstream release. Update procedure: pick the newest v26.x listed in
# https://nodejs.org/dist/index.json, copy the linux-x64 and linux-arm64
# tarball hashes from that release's SHASUMS256.txt into the pins below, and
# keep the major-version check in hooks/common/verify-image.sh in sync.
NODE_VERSION="v26.12.0"
NODE_SHA256_x64="fd47865ecd6391ebb431fc815e01b9135bf83ded5cf373247e9331e196b7aded"
NODE_SHA256_arm64="fd6cc729fa4448c2ac27c3fca5606019ced63c65a15c152c8df03e0cbce7f4c5"

arch=$(dpkg --print-architecture)
case "$arch" in
    amd64) node_arch=x64; pinned=$NODE_SHA256_x64 ;;
    arm64) node_arch=arm64; pinned=$NODE_SHA256_arm64 ;;
    *)
        echo "nodejs: no official Node.js build for architecture '$arch'" >&2
        echo 'nodejs: remove install-nodejs26.sh from this manifest or add a pinned release for it' >&2
        exit 1
        ;;
esac

tarball="node-$NODE_VERSION-linux-$node_arch.tar.xz"
base_url="https://nodejs.org/dist/$NODE_VERSION"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Fetch with the host Python (always present); avoids depending on curl or
# wget in the build container. Three attempts so a transient network error
# does not fail the whole image build.
echo "nodejs: fetching $tarball"
python3 - "$base_url/$tarball" "$work/$tarball" <<'PY'
import sys, urllib.request
url, dest = sys.argv[1], sys.argv[2]
for attempt in range(3):
    try:
        with urllib.request.urlopen(url, timeout=300) as resp, open(dest, "wb") as out:
            out.write(resp.read())
        break
    except OSError:
        if attempt == 2:
            raise
PY

echo "nodejs: verifying the download against the pinned SHA-256"
actual=$(sha256sum "$work/$tarball" | cut -d' ' -f1)
if [ "$actual" != "$pinned" ]; then
    echo "nodejs: SHA-256 mismatch for $tarball" >&2
    echo "  expected: $pinned" >&2
    echo "  actual  : $actual" >&2
    exit 1
fi

# The release manifest published next to the tarball must list the same
# hash, so a swapped upstream artifact fails the build even before the
# pinned value is bumped.
echo "nodejs: cross-checking the upstream SHASUMS256.txt"
python3 - "$base_url/SHASUMS256.txt" "$tarball" "$pinned" <<'PY'
import sys, urllib.request
manifest_url, name, pinned = sys.argv[1:4]
for attempt in range(3):
    try:
        with urllib.request.urlopen(manifest_url, timeout=60) as resp:
            manifest = resp.read().decode()
        break
    except OSError:
        if attempt == 2:
            raise
recorded = None
for line in manifest.splitlines():
    parts = line.split(None, 1)
    if len(parts) == 2 and parts[1].strip() == name:
        recorded = parts[0]
        break
if recorded is None:
    sys.exit(f"nodejs: {name} is missing from the upstream SHASUMS256.txt")
if recorded != pinned:
    sys.exit(
        "nodejs: upstream SHASUMS256.txt no longer matches the pinned hash\n"
        f"  pinned   : {pinned}\n"
        f"  upstream : {recorded}"
    )
PY

install -d -m 0755 "$ROOTFS/usr/local/lib/nodejs"
# Extract with Python's stdlib tarfile instead of `tar -xJf`: the pre_chroot
# hook runs on the BUILD HOST, where the external `xz` binary is not part of
# the minimal CI toolchain (`tar (child): xz: Cannot exec` broke the Extended
# build). python3 is already required by this hook for the downloads and the
# SHA-256/SHASUMS256.txt checks, and its stdlib lzma module decompresses
# .tar.xz without any external binary. The archive's integrity was already
# established above, before extraction.
python3 - "$work/$tarball" "$ROOTFS/usr/local/lib/nodejs" <<'PY'
import sys, tarfile
with tarfile.open(sys.argv[1], "r:xz") as archive:
    try:
        archive.extractall(sys.argv[2], filter="data")
    except TypeError:  # Python without the extraction-filter argument
        archive.extractall(sys.argv[2])
PY
# The upstream tarball extracts to node-<version>-linux-<arch>/ (the platform
# suffix is part of the directory name), NOT node-<version>/.
install_dir="$ROOTFS/usr/local/lib/nodejs/node-$NODE_VERSION-linux-$node_arch"
if [ ! -x "$install_dir/bin/node" ] || [ ! -x "$install_dir/bin/npm" ]; then
    echo "nodejs: extracted tree is missing bin/node or bin/npm" >&2
    exit 1
fi
install -d -m 0755 "$ROOTFS/usr/local/bin"
for tool in node npm npx; do
    ln -sfn "../lib/nodejs/node-$NODE_VERSION-linux-$node_arch/bin/$tool" "$ROOTFS/usr/local/bin/$tool"
done

echo "nodejs: Node.js $NODE_VERSION (+ npm) installed under /usr/local in the image"
