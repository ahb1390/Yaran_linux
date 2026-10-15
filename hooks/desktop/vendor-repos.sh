#!/bin/bash
# Prepare the APT configuration this image needs beyond the plain Debian
# archives: pin Telegram Desktop to the official trixie-backports repository
# (a Debian repository, so no consent gate applies) and — only when the
# manifest explicitly opted in with "vendor_repositories": true — add the
# signed Google Chrome repository. Runs on the build host with network
# access, writing straight into the bootstrap rootfs ($ROOTFS). The
# builder's configure_apt step runs afterwards and refreshes these sources.
#
# Repository policy: nothing in this project may add a non-Debian source to
# /etc/apt/sources.list.d without that explicit opt-in. build.py forwards
# the manifest flag as YARAN_VENDOR_REPOSITORIES=1; every vendor ORIGIN HOST
# enabled here is recorded in /etc/apt/yaran-vendor-repos so
# verify-image.sh can prove the origin had consent. Consent is tracked per
# host (not per filename) because google-chrome-stable's own postinst
# writes its deb822 google-chrome.sources for the same origin, and the
# manifest opted in to that origin.
set -euo pipefail

: "${ROOTFS:?ROOTFS must point at the bootstrap rootfs}"

arch=$(dpkg --print-architecture)
if [ "$arch" != "amd64" ]; then
    echo "vendor-repos: skipping vendor part (amd64-only repositories; host is $arch)"
    exit 0
fi

keyring_dir="$ROOTFS/usr/share/keyrings"
sources_dir="$ROOTFS/etc/apt/sources.list.d"
prefs_dir="$ROOTFS/etc/apt/preferences.d"
mkdir -p "$keyring_dir" "$sources_dir" "$prefs_dir"

# Telegram Desktop is not packaged in trixie itself; it ships in the official
# Debian backports repository. Pin it there so the plain package name resolves.
echo "vendor-repos: pinning telegram-desktop to trixie-backports"
cat > "$prefs_dir/90-telegram-backports" <<'EOF'
Package: telegram-desktop
Pin: release n=trixie-backports
Pin-Priority: 990
EOF

if [ "${YARAN_VENDOR_REPOSITORIES:-0}" != "1" ]; then
    echo 'vendor-repos: skipping Google Chrome repository (no opt-in)'
    echo 'vendor-repos: set "vendor_repositories": true in the manifest to allow it'
    echo "vendor-repos: done"
    exit 0
fi

# Fetch a signing key with the host Python (always present); avoids depending on
# curl/wget in the build container. Keys are stored ASCII-armored, which apt's
# signed-by accepts directly.
fetch_key() {
    local url="$1" dest="$2"
    python3 - "$url" "$dest" <<'PY'
import sys, urllib.request
url, dest = sys.argv[1], sys.argv[2]
with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as out:
    out.write(resp.read())
PY
    # A signing key is a few KB at most; refuse anything that looks wrong.
    local size
    size=$(stat -c%s "$dest")
    if [ "$size" -lt 500 ] || [ "$size" -gt 20000 ]; then
        echo "vendor-repos: refusing implausible key size ($size bytes) for $url" >&2
        exit 1
    fi
}

echo "vendor-repos: installing Google Chrome repository (manifest opted in)"
fetch_key "https://dl.google.com/linux/linux_signing_key.pub" \
    "$keyring_dir/google-chrome.asc"
cat > "$sources_dir/yaran-google-chrome.list" <<'EOF'
deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.asc] https://dl.google.com/linux/chrome/deb/ stable main
EOF
echo "dl.google.com" >> "$ROOTFS/etc/apt/yaran-vendor-repos"

echo "vendor-repos: done"
