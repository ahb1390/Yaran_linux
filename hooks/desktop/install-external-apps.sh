#!/bin/bash
# Install the official third-party .deb applications that have no APT repository.
# Runs inside the chroot after the package set is installed, so APT can resolve
# each application's runtime dependencies from the configured Debian repositories.
# Every download is pinned to a specific official release and verified against a
# SHA-256 recorded from that same artifact.
#
# NOTE on Hiddify: the upstream .deb declares NO dependencies and ships no
# /usr/bin/hiddify launcher, even though its desktop entry runs "Exec=hiddify".
# Without the explicit steps below the app appears installed but fails at
# launch with
#   error while loading shared libraries: libayatana-appindicator3.so.1
# and the menu entry does nothing. Both are fixed here, and the result is
# verified before the build is allowed to continue.
set -euo pipefail

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

install_deb() {
    local label="$1" url="$2" sha="$3" file="$work/pkg.deb"
    echo "external-apps: installing $label"
    if ! curl -fsSL --retry 3 --retry-delay 2 -o "$file" "$url"; then
        echo "external-apps: download FAILED for $label from $url" >&2
        exit 1
    fi
    if ! echo "$sha  $file" | sha256sum -c --status -; then
        echo "external-apps: SHA-256 mismatch for $label" >&2
        echo "  expected: $sha" >&2
        echo "  actual  : $(sha256sum "$file" | cut -d' ' -f1)" >&2
        exit 1
    fi
    if ! apt-get install -y "$file"; then
        echo "external-apps: apt failed to install $label (dependency resolution)" >&2
        exit 1
    fi
}

# Runtime libraries the Hiddify .deb needs but does not declare. Installing
# them through APT (instead of copying .so files) keeps them tracked and
# updated by the package manager; libayatana-appindicator3-1 pulls in
# libayatana-indicator3, libayatana-ido3 and libdbusmenu-glib.
echo "external-apps: installing Hiddify runtime dependencies"
apt-get install -y libayatana-appindicator3-1

# Hiddify — official release (amd64 only; no ARM64 .deb is published).
install_deb "Hiddify 4.1.1" \
    "https://github.com/hiddify/hiddify-app/releases/download/v4.1.1/Hiddify-Debian-x64.deb" \
    "e622abd15f7d4410c5655f3fdcd0fa9300944666fa40ac22761f06f93020f10e"

# v2rayN — official self-contained .NET release (amd64).
install_deb "v2rayN 7.25.4" \
    "https://github.com/2dust/v2rayN/releases/download/7.25.4/v2rayN-linux-64.deb" \
    "440eb32f5eeb21e1ea899b6782ef8585422c511d841d86492c53c2bf979d899d"

# --- Verification -----------------------------------------------------------
# The menu entry runs "hiddify", so a launcher must exist on the default PATH.
verify_command() {
    local cmd="$1" label="$2"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "external-apps: $label provides no '$cmd' on PATH" >&2
        exit 1
    fi
}

if [ "$(dpkg --print-architecture)" = amd64 ]; then
    if [ ! -e /usr/bin/hiddify ]; then
        echo "external-apps: upstream .deb ships no launcher; creating /usr/bin/hiddify"
        if [ -x /usr/share/hiddify/hiddify ]; then
            ln -s /usr/share/hiddify/hiddify /usr/bin/hiddify
        else
            echo "external-apps: /usr/share/hiddify/hiddify is missing; cannot create launcher" >&2
            exit 1
        fi
    fi
    verify_command hiddify Hiddify
    verify_command v2rayn v2rayN
    # Catch missing shared libraries now instead of at the user's first click.
    # Capture the ldd output instead of piping into grep -q: with pipefail a
    # short-circuiting grep can kill ldd with SIGPIPE and report a false
    # failure (or mask a real one) on large outputs.
    hiddify_libs=$(ldd /usr/share/hiddify/hiddify 2>/dev/null || true)
    case "$hiddify_libs" in
        *'not found'*)
            echo "external-apps: Hiddify has unresolved shared libraries:" >&2
            printf '%s\n' "$hiddify_libs" | grep 'not found' >&2 || true
            exit 1
            ;;
    esac
    test -f /usr/share/applications/hiddify.desktop || {
        echo "external-apps: hiddify.desktop is missing" >&2
        exit 1
    }
fi

echo "external-apps: done"
