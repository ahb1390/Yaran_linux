"""Tests for release ISO splitting and reconstruction.

These tests drive the real shell scripts against small ISO-like files so the
split/join round trip, the GitHub per-asset size limit and the failure paths
are all exercised without needing a multi-gigabyte image.
"""

from __future__ import annotations

import hashlib
import os
import random
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPLIT_SCRIPT = ROOT / 'scripts' / 'split-release-isos.sh'
JOIN_SCRIPT = ROOT / 'scripts' / 'join-iso-parts.sh'

# GitHub rejects a ReleaseAsset whose size is not strictly below this value.
GITHUB_ASSET_LIMIT = 2147483648
# Default part size used by scripts/split-release-isos.sh (1800 MiB).
DEFAULT_PART_BYTES = 1887436800

PART_NAME = re.compile(r'^(?P<iso>.+)\.part(?P<index>[0-9]+)$')


def run_script(script, *args, cwd=None, env=None):
    """Run a shell script and return the completed process."""
    environment = dict(os.environ)
    environment.update(env or {})
    return subprocess.run(
        ['bash', str(script), *[str(arg) for arg in args]],
        cwd=str(cwd) if cwd is not None else None,
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
    )


def write_iso(directory, name, size, seed=1, with_checksum=True):
    """Create a small deterministic ISO-like file plus its sha256 file."""
    payload = random.Random(seed).randbytes(size)
    iso = Path(directory) / name
    iso.write_bytes(payload)
    if with_checksum:
        Path(directory, name + '.sha256').write_text(
            f'{hashlib.sha256(payload).hexdigest()}  {name}\n'
        )
    return payload


def read_manifest(directory, name):
    """Return the part file names listed in the parts manifest, in order."""
    manifest = Path(directory, name + '.parts.sha256')
    names = []
    for line in manifest.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, filename = line.partition('  ')
        names.append(filename.lstrip('*'))
    return names


class SplitAndJoinRoundTripTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.out = self.work / 'output'
        self.out.mkdir()

    def split(self, env=None):
        return run_script(SPLIT_SCRIPT, self.out, env=env)

    def join(self, iso_path, cwd=None, env=None):
        return run_script(JOIN_SCRIPT, iso_path, cwd=cwd or self.out, env=env)

    # -- splitting ---------------------------------------------------------

    def test_default_part_bytes_stay_below_the_github_limit(self):
        self.assertLess(DEFAULT_PART_BYTES, GITHUB_ASSET_LIMIT)
        self.assertEqual(GITHUB_ASSET_LIMIT, 2147483648)
        self.assertEqual(DEFAULT_PART_BYTES, 1800 * 1024 * 1024)

    def test_split_creates_numbered_parts_below_the_limit(self):
        payload = write_iso(self.out, 'Yaran-test.iso', 5 * 1024 * 1024 + 7)

        result = self.split(env={'SPLIT_PART_BYTES': str(2 * 1024 * 1024)})

        self.assertEqual(result.returncode, 0, result.stderr)
        parts = sorted(self.out.glob('Yaran-test.iso.part[0-9]*'))
        self.assertEqual(
            [p.name for p in parts],
            ['Yaran-test.iso.part001',
             'Yaran-test.iso.part002',
             'Yaran-test.iso.part003'],
        )
        for part in parts:
            size = part.stat().st_size
            self.assertGreater(size, 0)
            self.assertLess(size, GITHUB_ASSET_LIMIT)
        self.assertEqual(
            sum(p.stat().st_size for p in parts), len(payload)
        )
        # The original ISO is gone, its checksum is preserved.
        self.assertFalse((self.out / 'Yaran-test.iso').exists())
        self.assertTrue((self.out / 'Yaran-test.iso.sha256').exists())

    def test_manifest_lists_only_the_numbered_parts(self):
        write_iso(self.out, 'Yaran-test.iso', 300 * 1024)

        result = self.split(env={'SPLIT_PART_BYTES': str(64 * 1024)})

        self.assertEqual(result.returncode, 0, result.stderr)
        names = read_manifest(self.out, 'Yaran-test.iso')
        self.assertGreater(len(names), 1)
        for name in names:
            match = PART_NAME.match(name)
            self.assertIsNotNone(match, name)
            self.assertEqual(match.group('iso'), 'Yaran-test.iso')
        self.assertNotIn('Yaran-test.iso.parts.sha256', names)
        # Every part listed on disk exists and verifies.
        checked = subprocess.run(
            ['sha256sum', '--check', 'Yaran-test.iso.parts.sha256'],
            cwd=self.out, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(checked.stdout.count(': OK'), len(names))

    def test_part_suffix_width_covers_more_than_999_parts(self):
        # A fixed --suffix-length=3 makes GNU split abort with
        # "output file suffixes exhausted" once the 1000th part is needed.
        write_iso(self.out, 'Yaran-test.iso', 400_000)

        result = self.split(env={'SPLIT_PART_BYTES': '256'})

        self.assertEqual(result.returncode, 0, result.stderr)
        parts = sorted(self.out.glob('Yaran-test.iso.part[0-9]*'))
        self.assertEqual(len(parts), 1563)
        self.assertEqual(parts[0].name, 'Yaran-test.iso.part0001')
        self.assertEqual(parts[-1].name, 'Yaran-test.iso.part1563')

    def test_no_unsplit_iso_remains_after_splitting(self):
        write_iso(self.out, 'Yaran-test.iso', 200 * 1024)

        result = self.split(env={'SPLIT_PART_BYTES': str(64 * 1024)})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.out.glob('*.iso')), [])
        for path in self.out.iterdir():
            if path.is_file():
                self.assertLess(path.stat().st_size, GITHUB_ASSET_LIMIT)

    def test_split_cleans_stale_parts_from_an_earlier_run(self):
        write_iso(self.out, 'Yaran-test.iso', 200 * 1024)
        stale = self.out / 'Yaran-test.iso.part009'
        stale.write_bytes(b'stale')

        result = self.split(env={'SPLIT_PART_BYTES': str(64 * 1024)})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(stale.exists())
        checked = subprocess.run(
            ['sha256sum', '--check', 'Yaran-test.iso.parts.sha256'],
            cwd=self.out, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_split_fails_when_the_iso_directory_is_missing(self):
        result = run_script(SPLIT_SCRIPT, self.work / 'does-not-exist')
        self.assertNotEqual(result.returncode, 0)

    def test_split_fails_when_there_is_no_iso(self):
        result = self.split()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no ISO files', result.stderr)

    # -- guards that protect the original ISO ------------------------------

    def test_split_keeps_the_iso_when_the_original_checksum_is_wrong(self):
        write_iso(self.out, 'Yaran-test.iso', 100 * 1024)
        (self.out / 'Yaran-test.iso.sha256').write_text(
            f'{"0" * 64}  Yaran-test.iso\n'
        )

        result = self.split(env={'SPLIT_PART_BYTES': str(32 * 1024)})

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.out / 'Yaran-test.iso').exists())
        self.assertEqual(list(self.out.glob('Yaran-test.iso.part[0-9]*')), [])
        self.assertFalse((self.out / 'Yaran-test.iso.parts.sha256').exists())

    def test_split_fails_when_the_original_checksum_file_is_missing(self):
        write_iso(self.out, 'Yaran-test.iso', 100 * 1024, with_checksum=False)

        result = self.split(env={'SPLIT_PART_BYTES': str(32 * 1024)})

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.out / 'Yaran-test.iso').exists())
        self.assertEqual(list(self.out.glob('Yaran-test.iso.part[0-9]*')), [])

    def test_split_rejects_parts_that_reach_the_asset_limit(self):
        write_iso(self.out, 'Yaran-test.iso', 4096)

        result = self.split(
            env={'SPLIT_PART_BYTES': '4000', 'MAX_ASSET_BYTES': '1000'}
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('MAX_ASSET_BYTES', result.stderr)
        self.assertTrue((self.out / 'Yaran-test.iso').exists())

    def test_split_rejects_a_non_numeric_part_size(self):
        write_iso(self.out, 'Yaran-test.iso', 4096)

        result = self.split(env={'SPLIT_PART_BYTES': 'lots'})

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.out / 'Yaran-test.iso').exists())

    # -- reconstruction ----------------------------------------------------

    def test_round_trip_from_another_working_directory(self):
        payload = write_iso(self.out, 'Yaran-test.iso', 400 * 1024)
        split_result = self.split(env={'SPLIT_PART_BYTES': str(96 * 1024)})
        self.assertEqual(split_result.returncode, 0, split_result.stderr)

        # Run from the parent directory with a path that contains a
        # directory component: the manifest stores bare file names.
        result = self.join(Path('output') / 'Yaran-test.iso', cwd=self.work)

        self.assertEqual(result.returncode, 0, result.stderr)
        rebuilt = (self.out / 'Yaran-test.iso').read_bytes()
        self.assertEqual(rebuilt, payload)
        checked = subprocess.run(
            ['sha256sum', '--check', 'Yaran-test.iso.sha256'],
            cwd=self.out, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_round_trip_rebuilds_only_the_parts_never_the_manifest(self):
        payload = write_iso(self.out, 'Yaran-test.iso', 150 * 1024)
        split_result = self.split(env={'SPLIT_PART_BYTES': str(50 * 1024)})
        self.assertEqual(split_result.returncode, 0, split_result.stderr)
        manifest = (self.out / 'Yaran-test.iso.parts.sha256').stat().st_size
        self.assertGreater(manifest, 0)

        result = self.join('Yaran-test.iso')

        self.assertEqual(result.returncode, 0, result.stderr)
        rebuilt = self.out / 'Yaran-test.iso'
        self.assertEqual(rebuilt.stat().st_size, len(payload))
        self.assertNotEqual(rebuilt.stat().st_size, len(payload) + manifest)
        self.assertEqual(rebuilt.read_bytes(), payload)

    def test_join_detects_a_corrupted_part_and_writes_no_iso(self):
        write_iso(self.out, 'Yaran-test.iso', 150 * 1024)
        split_result = self.split(env={'SPLIT_PART_BYTES': str(50 * 1024)})
        self.assertEqual(split_result.returncode, 0, split_result.stderr)
        part = self.out / 'Yaran-test.iso.part002'
        data = bytearray(part.read_bytes())
        data[10] ^= 0xFF
        part.write_bytes(bytes(data))

        result = self.join('Yaran-test.iso')

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.out / 'Yaran-test.iso').exists())
        # No temporary reconstruction file is left behind.
        self.assertEqual(list(self.out.glob('.*Yaran-test.iso.join.*')), [])

    def test_join_refuses_to_overwrite_an_existing_iso(self):
        write_iso(self.out, 'Yaran-test.iso', 150 * 1024)
        split_result = self.split(env={'SPLIT_PART_BYTES': str(50 * 1024)})
        self.assertEqual(split_result.returncode, 0, split_result.stderr)
        existing = self.out / 'Yaran-test.iso'
        existing.write_bytes(b'do not clobber me')

        result = self.join('Yaran-test.iso')

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(existing.read_bytes(), b'do not clobber me')

    def test_join_requires_the_parts_manifest(self):
        write_iso(self.out, 'Yaran-test.iso', 150 * 1024)
        split_result = self.split(env={'SPLIT_PART_BYTES': str(50 * 1024)})
        self.assertEqual(split_result.returncode, 0, split_result.stderr)
        (self.out / 'Yaran-test.iso.parts.sha256').unlink()

        result = self.join('Yaran-test.iso')

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.out / 'Yaran-test.iso').exists())

    def test_join_rejects_a_manifest_entry_that_is_not_a_numbered_part(self):
        # Regression: a manifest line pointing at the manifest itself must
        # never be concatenated into the reconstructed ISO.
        write_iso(self.out, 'Yaran-test.iso', 150 * 1024)
        split_result = self.split(env={'SPLIT_PART_BYTES': str(50 * 1024)})
        self.assertEqual(split_result.returncode, 0, split_result.stderr)
        manifest = self.out / 'Yaran-test.iso.parts.sha256'
        with manifest.open('a') as handle:
            handle.write(f'{"0" * 64}  Yaran-test.iso.parts.sha256\n')

        result = self.join('Yaran-test.iso')

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not a numbered part', result.stderr)
        self.assertFalse((self.out / 'Yaran-test.iso').exists())

    def test_join_ignores_parts_that_are_not_listed_in_the_manifest(self):
        write_iso(self.out, 'Yaran-test.iso', 150 * 1024)
        split_result = self.split(env={'SPLIT_PART_BYTES': str(50 * 1024)})
        self.assertEqual(split_result.returncode, 0, split_result.stderr)
        (self.out / 'Yaran-test.iso.part999').write_bytes(b'leftover')

        result = self.join('Yaran-test.iso')

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.out / 'Yaran-test.iso').exists())

    def test_join_fails_without_an_existing_manifest(self):
        write_iso(self.out, 'Yaran-test.iso', 1024)
        result = self.join('Yaran-test.iso')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('manifest', result.stderr)

    def test_join_rejects_a_filename_without_the_iso_suffix(self):
        result = self.join('Yaran-test.img')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must end in .iso', result.stderr)

    def test_join_refuses_a_corrupted_reconstructed_iso(self):
        # Tamper with the preserved original checksum after splitting, so the
        # final ISO verification must fail and nothing must be published.
        write_iso(self.out, 'Yaran-test.iso', 150 * 1024)
        split_result = self.split(env={'SPLIT_PART_BYTES': str(50 * 1024)})
        self.assertEqual(split_result.returncode, 0, split_result.stderr)
        (self.out / 'Yaran-test.iso.sha256').write_text(
            f'{"0" * 64}  Yaran-test.iso\n'
        )

        result = self.join('Yaran-test.iso')

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not match', result.stderr)
        self.assertFalse((self.out / 'Yaran-test.iso').exists())
        self.assertEqual(list(self.out.glob('.*Yaran-test.iso.join.*')), [])


if __name__ == '__main__':
    unittest.main()