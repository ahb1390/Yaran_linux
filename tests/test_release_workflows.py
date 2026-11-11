"""Configuration tests for the release workflows.

GitHub asset limits and release publishing rules cannot be exercised locally,
so these tests pin the workflow configuration itself: every edition must go
through the splitting step, no workflow may publish a raw oversized ISO, and
CI must run the split/join behaviour tests.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / '.github' / 'workflows'

GITHUB_ASSET_LIMIT = 2147483648
DEFAULT_PART_BYTES = 1887436800

RELEASE_CONFIGS = [
    'Yaran-2.0-amd64-minimal.json',
    'Yaran-2.0-amd64-extended.json',
    'Yaran-2.0-arm64.json',
    'Yaran-Server-2.0-amd64.json',
]


def read_workflow(name):
    return (WORKFLOWS / name).read_text(encoding='utf-8')


class ReleaseMatrixTest(unittest.TestCase):
    """release.yml must publish every edition through image.yml."""

    def setUp(self):
        self.text = read_workflow('release.yml')

    def test_release_workflow_runs_on_release_publish(self):
        self.assertIn('release:', self.text)
        self.assertIn('types: [published]', self.text)

    def test_release_matrix_covers_exactly_the_four_editions(self):
        configs = re.findall(r'^\s+- config:\s*(\S+)\s*$', self.text, re.M)
        self.assertEqual(configs, RELEASE_CONFIGS)

    def test_every_matrix_entry_passes_release_true(self):
        entries = re.split(r'(?m)^\s+- config:', self.text)[1:]
        self.assertEqual(len(entries), len(RELEASE_CONFIGS))
        for entry in entries:
            self.assertIn('runner:', entry)
            self.assertIn('artifact:', entry)
        # The shared `with:` block applies to every matrix instance.
        self.assertIn('release: true', self.text)
        self.assertEqual(self.text.count('release: true'), 1)
        self.assertLess(
            self.text.index('include:'),
            self.text.index('release: true'),
        )

    def test_release_workflow_reuses_the_shared_image_workflow(self):
        self.assertIn('uses: ./.github/workflows/image.yml', self.text)
        self.assertIn('release: true', self.text)

    def test_one_edition_failure_does_not_cancel_the_others(self):
        self.assertIn('fail-fast: false', self.text)


class ReleaseAssetGuardTest(unittest.TestCase):
    """image.yml must split, verify, and never upload a raw ISO."""

    def setUp(self):
        self.text = read_workflow('image.yml')

    def test_split_runs_before_verification_and_publishing(self):
        split = self.text.index('name: Split ISOs for GitHub Releases')
        verify = self.text.index('name: Verify release assets are within GitHub limits')
        publish = self.text.index('name: Publish release assets')
        self.assertLess(split, verify)
        self.assertLess(verify, publish)

    def test_split_verify_and_publish_are_release_only(self):
        for step in (
            'name: Split ISOs for GitHub Releases',
            'name: Verify release assets are within GitHub limits',
            'name: Publish release assets',
        ):
            index = self.text.index(step)
            following = self.text[index:index + 120]
            self.assertIn('if: inputs.release', following, step)

    def test_release_globs_never_match_the_unsplit_iso(self):
        publish = self.text.split('name: Publish release assets', 1)[1]
        files_block = publish.split('files:', 1)[1]
        patterns = [
            line.strip()
            for line in files_block.splitlines()
            if line.strip().startswith('output/')
        ]
        self.assertTrue(patterns, 'no release file patterns found')
        for pattern in patterns:
            self.assertNotEqual(pattern, 'output/*.iso')
            self.assertFalse(
                pattern.endswith('*.iso'),
                f'{pattern} would upload an unsplit ISO',
            )
        self.assertIn('output/*.iso.part[0-9]*', patterns)
        self.assertIn('output/*.sha256', patterns)
        # The split parts manifest must be uploaded exactly once.
        self.assertEqual(len(patterns), len(set(patterns)))
        self.assertNotIn('output/*.iso.part*', patterns)

    def test_fail_on_unmatched_files_is_enabled(self):
        self.assertIn('fail_on_unmatched_files: true', self.text)

    def test_guard_enforces_the_github_asset_limit(self):
        guard = self.text.split(
            'name: Verify release assets are within GitHub limits', 1
        )[1].split('name: Publish release assets', 1)[0]
        self.assertIn(f'limit={GITHUB_ASSET_LIMIT}', guard)
        self.assertIn('(( size >= limit ))', guard)
        # Rejects any file left in output/ whose name ends in .iso.
        self.assertIn('*.iso)', guard)
        # Requires parts and the parts manifest for every ISO checksum file.
        # Glob must match numbered parts only, never the manifest itself.
        self.assertIn('part"[0-9]*', guard)
        self.assertIn('.parts.sha256', guard)
        self.assertIn('exit 1', guard)

    def test_original_iso_is_still_archived_as_a_ci_artifact(self):
        artifact = self.text.split('name: Upload image and checksum', 1)[1].split(
            'name: Split ISOs', 1
        )[0]
        self.assertIn('output/*.iso', artifact)
        self.assertIn('if-no-files-found: error', artifact)

    def test_build_happens_before_the_split(self):
        build = self.text.index('name: Build and test')
        split = self.text.index('name: Split ISOs for GitHub Releases')
        artifact = self.text.index('name: Upload image and checksum')
        self.assertLess(build, artifact)
        self.assertLess(artifact, split)


class ReleasePublishingSurfaceTest(unittest.TestCase):
    """No workflow may publish a release asset without the split guard."""

    def test_only_image_workflow_publishes_release_assets(self):
        publishers = [
            path.name
            for path in sorted(WORKFLOWS.glob('*.yml'))
            if 'action-gh-release' in path.read_text(encoding='utf-8')
        ]
        self.assertEqual(publishers, ['image.yml'])

    def test_no_workflow_uploads_an_iso_as_a_release_asset(self):
        for path in sorted(WORKFLOWS.glob('*.yml')):
            text = path.read_text(encoding='utf-8')
            files_blocks = re.findall(r'(?ms)^\s+files:\s*\|(.*?)(?=^\s{0,8}\S|\Z)', text)
            for block in files_blocks:
                for line in block.splitlines():
                    pattern = line.strip()
                    if pattern.startswith('output/'):
                        self.assertNotEqual(
                            pattern, 'output/*.iso',
                            f'{path.name} would publish a raw ISO',
                        )

    def test_release_workflow_has_write_permissions(self):
        text = read_workflow('release.yml')
        self.assertIn('permissions:', text)
        self.assertIn('contents: write', text)


class ContinuousIntegrationTest(unittest.TestCase):
    """CI must run the split/join tests and syntax-check the scripts."""

    def test_build_workflow_runs_the_unit_tests(self):
        text = read_workflow('build.yml')
        self.assertIn('python3 -m unittest discover -s tests -v', text)

    def test_build_workflow_syntax_checks_shell_scripts(self):
        text = read_workflow('build.yml')
        self.assertIn('bash -n', text)
        self.assertIn('scripts', text)

    def test_container_build_runs_the_unit_tests(self):
        text = (ROOT / 'scripts' / 'ci-build.sh').read_text(encoding='utf-8')
        self.assertIn('unittest', text)

    def test_split_script_declares_the_safe_defaults(self):
        text = (ROOT / 'scripts' / 'split-release-isos.sh').read_text(encoding='utf-8')
        self.assertIn(f'DEFAULT_ASSET_LIMIT={GITHUB_ASSET_LIMIT}', text)
        self.assertIn(f'DEFAULT_PART_BYTES={DEFAULT_PART_BYTES}', text)
        self.assertIn('SPLIT_PART_BYTES < MAX_ASSET_BYTES', text)
        self.assertIn('reconstructed_hash', text)
        # The original ISO may only be removed after verification succeeded.
        remove_index = text.index('\n    rm -- "$iso"')
        verify_index = text.index('Verifying that the parts reconstruct')
        self.assertLess(verify_index, remove_index)

    def test_join_script_verifies_before_renaming_the_result(self):
        text = (ROOT / 'scripts' / 'join-iso-parts.sh').read_text(encoding='utf-8')
        self.assertIn('sha256sum --check', text)
        self.assertIn('refusing to overwrite', text)
        rename_index = text.index('mv -- "$join_tmp" "$iso"')
        verify_index = text.index('Verifying the reconstructed ISO')
        self.assertLess(verify_index, rename_index)


if __name__ == '__main__':
    unittest.main()