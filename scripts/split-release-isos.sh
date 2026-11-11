#!/usr/bin/env bash
# Split every built ISO into GitHub-release-safe numbered parts.
#
# GitHub rejects any ReleaseAsset whose size is not strictly less than
# 2147483648 bytes (2 GiB), so each uploaded file must stay below that
# limit.  The original ISO is only removed after every part has been
# written, checksummed and verified to reproduce the original checksum.
#
# Usage: scripts/split-release-isos.sh [OUTPUT_DIR]
#
# Environment:
#   SPLIT_PART_BYTES  bytes per part, must be below MAX_ASSET_BYTES
#                     (default 1887436800 = 1800 MiB)
#   MAX_ASSET_BYTES   per-file limit enforced on every produced file
#                     (default 2147483648 = GitHub's release asset limit)
set -euo pipefail
shopt -s nullglob

readonly DEFAULT_ASSET_LIMIT=2147483648
readonly DEFAULT_PART_BYTES=1887436800

MAX_ASSET_BYTES=${MAX_ASSET_BYTES:-$DEFAULT_ASSET_LIMIT}
SPLIT_PART_BYTES=${SPLIT_PART_BYTES:-$DEFAULT_PART_BYTES}

die() {
    echo "split-release-isos: $*" >&2
    exit 1
}

is_positive_integer() {
    [[ $1 =~ ^[1-9][0-9]*$ ]]
}

is_positive_integer "$MAX_ASSET_BYTES" ||
    die "MAX_ASSET_BYTES must be a positive integer, got: $MAX_ASSET_BYTES"
is_positive_integer "$SPLIT_PART_BYTES" ||
    die "SPLIT_PART_BYTES must be a positive integer, got: $SPLIT_PART_BYTES"
(( SPLIT_PART_BYTES < MAX_ASSET_BYTES )) ||
    die "SPLIT_PART_BYTES ($SPLIT_PART_BYTES) must be strictly below MAX_ASSET_BYTES ($MAX_ASSET_BYTES)"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
out_dir=${1:-${OUTPUT_DIR:-"$script_dir/../output"}}
[[ -d $out_dir ]] || die "output directory not found: $out_dir"
cd -- "$out_dir"

isos=( *.iso )
(( ${#isos[@]} > 0 )) || die "no ISO files found in $out_dir"

for iso in "${isos[@]}"; do
    checksum_file=${iso}.sha256
    manifest_file=${iso}.parts.sha256

    [[ -f $checksum_file ]] ||
        die "missing original ISO checksum file: $checksum_file"
    echo "==> Verifying the original checksum of $iso"
    sha256sum --check -- "$checksum_file" ||
        die "original ISO checksum mismatch, refusing to touch $iso"
    original_hash=$(awk 'NR == 1 { print $1 }' "$checksum_file")
    [[ $original_hash =~ ^[0-9a-f]{64}$ ]] ||
        die "could not read a SHA-256 digest from $checksum_file"

    size=$(stat -c%s -- "$iso")
    (( size > 0 )) || die "refusing to split an empty file: $iso"

    parts_needed=$(( (size + SPLIT_PART_BYTES - 1) / SPLIT_PART_BYTES ))
    suffix_length=${#parts_needed}
    if (( suffix_length < 3 )); then
        suffix_length=3
    fi

    # Drop leftovers from an earlier run so no stale part is published.
    stale=( "${iso}.part"[0-9]* "$manifest_file" )
    if (( ${#stale[@]} > 0 )); then
        rm -f -- "${stale[@]}"
    fi

    echo "==> Splitting $iso ($size bytes) into $parts_needed part(s) of at most $SPLIT_PART_BYTES bytes"
    split --bytes="$SPLIT_PART_BYTES" --numeric-suffixes=1 \
        --suffix-length="$suffix_length" -- "$iso" "${iso}.part"

    parts=( "${iso}.part"[0-9]* )
    (( ${#parts[@]} == parts_needed )) ||
        die "expected $parts_needed parts for $iso, found ${#parts[@]}"

    total=0
    for part in "${parts[@]}"; do
        part_size=$(stat -c%s -- "$part")
        (( part_size > 0 )) || die "part is empty: $part"
        (( part_size <= SPLIT_PART_BYTES )) ||
            die "part is larger than the requested size: $part"
        (( part_size < MAX_ASSET_BYTES )) ||
            die "part is not below GitHub's asset limit: $part"
        total=$(( total + part_size ))
    done
    (( total == size )) ||
        die "parts add up to $total bytes but $iso is $size bytes"

    echo "==> Writing checksums for ${#parts[@]} part(s)"
    manifest_tmp=$(mktemp -- ".${iso}.parts.sha256.XXXXXX")
    sha256sum -- "${parts[@]}" > "$manifest_tmp"
    chmod 0644 -- "$manifest_tmp"
    mv -- "$manifest_tmp" "$manifest_file"

    # Prove that concatenating the parts reproduces the original ISO
    # before the original ISO is removed.
    echo "==> Verifying that the parts reconstruct $iso"
    reconstructed_hash=$(cat -- "${parts[@]}" | sha256sum | awk '{print $1}')
    [[ $reconstructed_hash == "$original_hash" ]] ||
        die "reconstructed checksum $reconstructed_hash does not match $original_hash"

    rm -- "$iso"
    echo "    removed $iso after successful verification; $checksum_file is kept"
done

echo "==> Checking that no release file exceeds $MAX_ASSET_BYTES bytes"
for file in *; do
    [[ -f $file ]] || continue
    file_size=$(stat -c%s -- "$file")
    (( file_size < MAX_ASSET_BYTES )) ||
        die "$file is $file_size bytes, which is not below $MAX_ASSET_BYTES"
done

remaining_isos=( *.iso )
(( ${#remaining_isos[@]} == 0 )) ||
    die "unsplit ISO files are still present: ${remaining_isos[*]}"

for checksum_file in *.iso.sha256; do
    name=${checksum_file%.sha256}
    published_parts=( "${name}.part"[0-9]* )
    (( ${#published_parts[@]} > 0 )) ||
        die "no numbered parts were produced for $name"
    [[ -f ${name}.parts.sha256 ]] ||
        die "missing parts manifest for $name"
done

echo "==> Release assets are ready in $out_dir"
for file in *.iso.part[0-9]* *.sha256; do
    printf '      %-40s %s bytes\n' "$file" "$(stat -c%s -- "$file")"
done