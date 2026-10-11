#!/bin/bash
# Extended-only: add the signed Oracle VirtualBox APT repository. VirtualBox is
# not packaged in Debian trixie; Oracle publishes its own signed repository.
# amd64 hosts only — VirtualBox has no official ARM host support.
set -euo pipefail

: "${ROOTFS:?ROOTFS must point at the bootstrap rootfs}"

arch=$(dpkg --print-architecture)
if [ "$arch" != "amd64" ]; then
    echo "vendor-repos-extended: skipping (VirtualBox is amd64-only; host is $arch)"
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

echo "vendor-repos-extended: installing Oracle VirtualBox repository"
fetch_key "https://www.virtualbox.org/download/oracle_vbox_2016.asc" \
    "$keyring_dir/oracle-virtualbox.asc"
cat > "$sources_dir/yaran-virtualbox.list" <<'EOF'
deb [arch=amd64 signed-by=/usr/share/keyrings/oracle-virtualbox.asc] https://download.virtualbox.org/virtualbox/debian trixie contrib
EOF

echo "vendor-repos-extended: done"
