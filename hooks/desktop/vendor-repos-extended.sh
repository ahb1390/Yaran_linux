#!/bin/bash
# Extended-only: add the signed Oracle VirtualBox APT repository — but ONLY
# when the manifest explicitly opted in with "vendor_repositories": true
# (forwarded by build.py as YARAN_VENDOR_REPOSITORIES=1). VirtualBox is not
# packaged in Debian trixie; Oracle publishes its own signed repository and
# the repository policy requires that adding it is always a conscious,
# per-manifest decision, never automatic. amd64 hosts only — VirtualBox has
# no official ARM host support. The origin host is recorded in
# /etc/apt/yaran-vendor-repos so verify-image.sh can prove it had consent.
set -euo pipefail

: "${ROOTFS:?ROOTFS must point at the bootstrap rootfs}"

arch=$(dpkg --print-architecture)
if [ "$arch" != "amd64" ]; then
    echo "vendor-repos-extended: skipping (VirtualBox is amd64-only; host is $arch)"
    exit 0
fi

if [ "${YARAN_VENDOR_REPOSITORIES:-0}" != "1" ]; then
    echo 'vendor-repos-extended: skipping VirtualBox repository (no opt-in)'
    echo 'vendor-repos-extended: set "vendor_repositories": true in the manifest to allow it'
    exit 0
fi

keyring_dir="$ROOTFS/usr/share/keyrings"
sources_dir="$ROOTFS/etc/apt/sources.list.d"
mkdir -p "$keyring_dir" "$sources_dir"

fetch_key() {
    local url="$1" dest="$2"
    python3 - "$url" "$dest" <<'PY'
import sys, urllib.request
url, dest = sys.argv[1], sys.argv[2]
with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as out:
    out.write(resp.read())
PY
    local size
    size=$(stat -c%s "$dest")
    if [ "$size" -lt 500 ] || [ "$size" -gt 20000 ]; then
        echo "vendor-repos-extended: refusing implausible key size ($size bytes) for $url" >&2
        exit 1
    fi
}

echo "vendor-repos-extended: installing Oracle VirtualBox repository (manifest opted in)"
fetch_key "https://www.virtualbox.org/download/oracle_vbox_2016.asc" \
    "$keyring_dir/oracle-virtualbox.asc"
cat > "$sources_dir/yaran-virtualbox.list" <<'EOF'
deb [arch=amd64 signed-by=/usr/share/keyrings/oracle-virtualbox.asc] https://download.virtualbox.org/virtualbox/debian trixie contrib
EOF
echo "download.virtualbox.org" >> "$ROOTFS/etc/apt/yaran-vendor-repos"

echo "vendor-repos-extended: done"
