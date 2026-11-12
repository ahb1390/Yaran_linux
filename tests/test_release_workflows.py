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

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / '.github' / 'workflows'

GITHUB_ASSET_LIMIT = 2147483648
DEFAULT_PART_BYTES = 1887436800

LEGACY_CONFIG = 'Yaran-2.0-amd64.json'

RELEASE_CONFIGS = [
    'Yaran-2.0-amd64-minimal.json',
    'Yaran-2.0-amd64-extended.json',
    'Yaran-2.0-arm64.json',
    'Yaran-Server-2.0-amd64.json',
]

# Every manifest that a push to main must build: the four released editions
# plus the legacy desktop edition that is built but never released.
BUILD_CONFIGS = [LEGACY_CONFIG] + RELEASE_CONFIGS


def read_workflow(name):
    return (WORKFLOWS / name).read_text(encoding='utf-8')


def parse_workflow(name):
    return yaml.safe_load(read_workflow(name))


def parse_events(name):
    """Return the `on:` mapping; PyYAML reads the bare key `on` as True."""
    data = parse_workflow(name)
    return data.get(True, data.get('on'))


def matrix_entries(name, job):
    return parse_workflow(name)['jobs'][job]['strategy']['matrix']['include']


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

    def test_release_output_ownership_is_fixed_before_splitting(self):
        ownership = self.text.index(
            'name: Make build output writable for release packaging'
        )
        split = self.text.index('name: Split ISOs for GitHub Releases')
        self.assertLess(ownership, split)
        ownership_step = self.text[ownership:split]
        self.assertIn('if: inputs.release', ownership_step)
        self.assertIn('sudo chown -R "$(id -u):$(id -g)" -- output', ownership_step)

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


class EditionMatrixConsistencyTest(unittest.TestCase):
    """build.yml builds five editions, release.yml publishes four.

    `Yaran-2.0-amd64.json` is a legacy manifest that is built and tested by
    every push but is intentionally never attached to a release, matching
    the assets of every published Yaran Linux release so far.  Anything
    else that differs between the two matrices is drift and must fail here
    before it fails in a release run.
    """

    def build_entries(self):
        entries = [dict(entry) for entry in matrix_entries('build.yml', 'build-desktop')]
        server = parse_workflow('build.yml')['jobs']['build-server']['with']
        entries.append({
            'config': server['config'],
            'runner': server['runner'],
            'artifact': server['artifact'],
        })
        return entries

    def test_build_matrix_covers_every_manifest(self):
        configs = [entry['config'] for entry in self.build_entries()]
        self.assertEqual(configs, BUILD_CONFIGS)
        self.assertEqual(sorted(configs), sorted(set(configs)))

    def test_release_matrix_is_the_build_matrix_without_the_legacy_edition(self):
        build = [entry['config'] for entry in self.build_entries()]
        release = [entry['config'] for entry in matrix_entries('release.yml', 'build')]
        self.assertEqual(release, RELEASE_CONFIGS)
        self.assertEqual(
            [config for config in build if config != LEGACY_CONFIG],
            release,
        )

    def test_only_the_legacy_edition_is_excluded_from_releases(self):
        build = {entry['config'] for entry in self.build_entries()}
        release = {entry['config'] for entry in matrix_entries('release.yml', 'build')}
        self.assertEqual(build - release, {LEGACY_CONFIG})
        self.assertEqual(release - build, set())

    def test_runners_and_artifact_names_agree_across_matrices(self):
        build = {
            entry['config']: (entry['runner'], entry['artifact'])
            for entry in self.build_entries()
        }
        for entry in matrix_entries('release.yml', 'build'):
            self.assertEqual(
                build[entry['config']],
                (entry['runner'], entry['artifact']),
                entry['config'],
            )

    def test_release_workflow_triggers_only_on_a_published_release(self):
        events = parse_events('release.yml')
        self.assertEqual(list(events), ['release'])
        self.assertEqual(events['release'], {'types': ['published']})

    def test_push_builds_never_ask_image_workflow_to_publish(self):
        build_text = read_workflow('build.yml')
        self.assertNotIn('release:', build_text)
        self.assertNotIn('release: true', build_text)
        events = parse_events('build.yml')
        self.assertEqual(set(events), {'push', 'pull_request', 'workflow_dispatch'})
        # A push run can therefore never attach assets to a release.
        release_call = parse_workflow('release.yml')['jobs']['build']
        self.assertIs(release_call['with']['release'], True)
        build_jobs = parse_workflow('build.yml')['jobs']
        for job in ('build-desktop', 'build-server'):
            self.assertNotIn('release', build_jobs[job]['with'], job)

    def test_release_only_steps_stay_gated_in_the_shared_workflow(self):
        text = read_workflow('image.yml')
        self.assertEqual(text.count('if: inputs.release'), 4)
        self.assertIn('default: false', text)


class ReleaseMatrixDocumentationTest(unittest.TestCase):
    """The documented matrix must match the workflows and never contradict CI."""

    def test_legacy_edition_exclusion_is_documented(self):
        text = (ROOT / 'docs' / 'releases.md').read_text(encoding='utf-8')
        self.assertIn(LEGACY_CONFIG, text)
        self.assertRegex(text, r'(?i)intentionally')

    def test_no_document_still_claims_ci_skips_the_legacy_edition(self):
        for path in sorted((ROOT / 'docs').glob('*.md')):
            text = path.read_text(encoding='utf-8')
            self.assertNotIn(
                'not built by CI',
                text,
                f'{path.name} still contradicts the build matrix',
            )


if __name__ == '__main__':
    unittest.main()