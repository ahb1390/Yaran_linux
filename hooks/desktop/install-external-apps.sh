#!/bin/bash
# Install the official third-party .deb applications that have no APT repository.
# Runs inside the chroot after the package set is installed, so APT can resolve
# each application's runtime dependencies from the configured Debian repositories.
# Every download is pinned to a specific official release and verified against a
# SHA-256 recorded from that same artifact.
set -euo pipefail

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

install_deb() {
    local label="$1" url="$2" sha="$3" file="$work/pkg.deb"
    echo "external-apps: installing $label"
    curl -fsSL --retry 3 --retry-delay 2 -o "$file" "$url"
    echo "$sha  $file" | sha256sum -c --status - || {
        echo "external-apps: SHA-256 mismatch for $label" >&2
        exit 1
    }
    apt-get install -y "$file"
}

# Hiddify — official release (amd64 only; no ARM64 .deb is published).
install_deb "Hiddify 4.1.1" \
    "https://github.com/hiddify/hiddify-app/releases/download/v4.1.1/Hiddify-Debian-x64.deb" \
    "e622abd15f7d4410c5655f3fdcd0fa9300944666fa40ac22761f06f93020f10e"

# v2rayN — official self-contained .NET release (amd64).
install_deb "v2rayN 7.25.4" \
    "https://github.com/2dust/v2rayN/releases/download/7.25.4/v2rayN-linux-64.deb" \
    "440eb32f5eeb21e1ea899b6782ef8585422c511d841d86492c53c2bf979d899d"

echo "external-apps: done"
