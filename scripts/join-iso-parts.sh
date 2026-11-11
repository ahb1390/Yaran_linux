#!/usr/bin/env bash
# Reassemble a release ISO from its numbered parts and verify the result.
#
# The parts manifest is the source of truth for the part list, the part
# order and the part checksums, so the manifest itself can never be
# concatenated into the ISO.  The reconstructed file is written to a
# temporary file and only renamed to its final name after it matches the
# original ISO checksum.
#
# Usage: scripts/join-iso-parts.sh FILE.iso
set -euo pipefail
shopt -s nullglob

die() {
    echo "join-iso-parts: $*" >&2
    exit 1
}

iso=${1:-}
[[ -n $iso ]] || die "Usage: scripts/join-iso-parts.sh FILE.iso"
case "$iso" in
    *.iso) ;;
    *) die "the output filename must end in .iso: $iso" ;;
esac

iso_dir=$(dirname -- "$iso")
iso_name=$(basename -- "$iso")
[[ -d $iso_dir ]] || die "directory not found: $iso_dir"
cd -- "$iso_dir"
iso=$iso_name

manifest=${iso}.parts.sha256
[[ -f $manifest ]] || die "missing parts checksum manifest: $manifest"

if [[ -e $iso ]]; then
    die "refusing to overwrite existing file: $iso"
fi

declare -a part_names=()
declare -A seen=()
lineno=0
while IFS= read -r line || [[ -n $line ]]; do
    lineno=$((lineno + 1))
    [[ -n $line ]] || continue
    if [[ $line =~ ^([0-9a-f]{64})[[:space:]]{1,2}(\*.+|[[:graph:]]+)$ ]]; then
        hash=${BASH_REMATCH[1]}
        name=${BASH_REMATCH[2]}
    else
        die "malformed line $lineno in $manifest: $line"
    fi
    name=${name#\*}
    [[ $name != */* ]] || die "unsafe part name in $manifest: $name"
    case "$name" in
        "${iso}.part"*) ;;
        *) die "manifest entry does not belong to $iso: $name" ;;
    esac
    suffix=${name#"${iso}.part"}
    [[ $suffix =~ ^[0-9]+$ ]] ||
        die "manifest entry is not a numbered part: $name"
    [[ -z ${seen[$name]+x} ]] || die "duplicate manifest entry: $name"
    seen[$name]=$hash
    part_names+=("$name")
done < "$manifest"

(( ${#part_names[@]} > 0 )) || die "no parts are listed in $manifest"

# Every part on disk must be listed, and every listed part must be on disk.
on_disk=( "${iso}.part"[0-9]* )
for file in "${on_disk[@]}"; do
    [[ -n ${seen[$file]+x} ]] ||
        die "part on disk is missing from the manifest: $file"
done
(( ${#on_disk[@]} == ${#part_names[@]} )) ||
    die "manifest lists ${#part_names[@]} part(s) but ${#on_disk[@]} are present"

echo "==> Verifying the downloaded parts against $manifest"
sha256sum --check -- "$manifest" ||
    die "a downloaded part does not match $manifest; re-download it"

join_tmp=$(mktemp -- ".${iso}.join.XXXXXX")
cleanup() {
    rm -f -- "$join_tmp"
}
trap cleanup EXIT

echo "==> Reassembling $iso from ${#part_names[@]} part(s)"
for name in "${part_names[@]}"; do
    cat -- "$name" >> "$join_tmp"
done
chmod 0644 -- "$join_tmp"

if [[ -f ${iso}.sha256 ]]; then
    echo "==> Verifying the reconstructed ISO against ${iso}.sha256"
    expected_hash=$(awk 'NR == 1 { print $1 }' "${iso}.sha256")
    [[ $expected_hash =~ ^[0-9a-f]{64}$ ]] ||
        die "could not read a SHA-256 digest from ${iso}.sha256"
    actual_hash=$(sha256sum -- "$join_tmp" | awk '{print $1}')
    [[ $actual_hash == "$expected_hash" ]] ||
        die "reconstructed ISO checksum $actual_hash does not match $expected_hash"
else
    echo "join-iso-parts: warning: ${iso}.sha256 not found, full ISO verification skipped" >&2
fi

mv -- "$join_tmp" "$iso"
trap - EXIT
echo "    wrote $iso ($(stat -c%s -- "$iso") bytes)"
echo "==> Done"