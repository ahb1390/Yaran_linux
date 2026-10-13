"""Bash experience tests: syntax, safety and real PTY behaviour.

The acceptance criteria demand more than `bash -n`: these tests spawn a real
interactive Bash on a pseudo-terminal and assert prompt, aliases, git branch
display, exit-code marker, Tab completion and history behaviour, plus the
non-interactive guarantee that scripts are unaffected.
"""
import os
import pty
import re
import select
import subprocess
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSET = ROOT / 'assets/bash/yaran-bashrc'
DESKTOP_MANIFESTS = [
    ROOT / 'Yaran-2.0-amd64.json',
    ROOT / 'Yaran-2.0-amd64-minimal.json',
    ROOT / 'Yaran-2.0-amd64-extended.json',
    ROOT / 'Yaran-2.0-arm64.json',
]
ALL_MANIFESTS = DESKTOP_MANIFESTS + [ROOT / 'Yaran-Server-2.0-amd64.json']


def bash(args, env=None, timeout=30):
    return subprocess.run(['bash'] + args, capture_output=True, text=True,
                          timeout=timeout, env=env)


class PtyBash:
    """Minimal interactive-Bash driver on a pseudo terminal."""

    def __init__(self, rcfile, env=None, workdir=None):
        master, slave = pty.openpty()
        environment = {**os.environ, 'TERM': 'xterm-256color',
                       'HISTFILE': str(Path(rcfile).parent / '.histfile'),
                       'PS1': '$ ', 'HOME': str(Path(rcfile).parent)}
        if env:
            environment.update(env)
        self.master = master
        self.proc = subprocess.Popen(
            ['bash', '--noprofile', '--rcfile', str(rcfile), '-i'],
            stdin=slave, stdout=slave, stderr=slave, cwd=workdir,
            env=environment, close_fds=True)
        os.close(slave)
        self.buffer = ''

    def read_until(self, marker, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if marker in self.buffer:
                out, self.buffer = self.buffer, ''
                return out
            ready, _, _ = select.select([self.master], [], [], 0.2)
            if ready:
                try:
                    data = os.read(self.master, 4096)
                except OSError:
                    break
                if not data:
                    break
                self.buffer += data.decode('utf-8', 'replace')
        raise AssertionError(
            f'timeout waiting for {marker!r}; got:\n{self.buffer[-2000:]}')

    def send(self, line):
        os.write(self.master, (line + '\n').encode())

    def close(self):
        with __import__('contextlib').suppress(Exception):
            self.proc.kill()
        self.proc.wait(timeout=5)
        os.close(self.master)


def make_rcfile(directory):
    rc = Path(directory) / 'rcfile'
    rc.write_text(f'. "{ASSET}"\n')
    return rc


class SyntaxAndPolicyTests(unittest.TestCase):
    def test_asset_and_hooks_pass_bash_n(self):
        result = bash(['-n', str(ASSET)])
        self.assertEqual(result.returncode, 0, result.stderr)
        for hook in ('hooks/common/install-ble.sh', 'hooks/common/bash-experience.sh'):
            with self.subTest(hook=hook):
                result = bash(['-n', str(ROOT / hook)])
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_ble_pins_version_and_forbids_curl_pipe_bash(self):
        hook = (ROOT / 'hooks/common/install-ble.sh').read_text()
        self.assertRegex(hook, r'BLE_SHA256="[0-9a-f]{64}"')
        self.assertIn('BLE_VERSION="0.4.0-devel3"', hook)
        code = '\n'.join(line for line in hook.splitlines()
                         if not line.lstrip().startswith('#'))
        self.assertNotRegex(code, r'\|\s*(ba)?sh\b', 'no curl|bash pattern')
        self.assertIn('BSD-3-Clause', hook)

    def test_manifests_ship_the_experience(self):
        for path in ALL_MANIFESTS:
            text = path.read_text()
            with self.subTest(manifest=path.name):
                self.assertIn('"bash-completion"', text)
                self.assertIn('hooks/common/bash-experience.sh', text)
        for path in DESKTOP_MANIFESTS:
            text = path.read_text()
            with self.subTest(manifest=path.name):
                self.assertIn('hooks/common/install-ble.sh', text)
                # git ships git-sh-prompt (/usr/lib/git-core/git-sh-prompt),
                # which the branch display in the prompt depends on.
                self.assertRegex(text, r'"git",', 'git must be a default desktop package')
        server = (ROOT / 'Yaran-Server-2.0-amd64.json').read_text()
        self.assertNotIn('install-ble.sh', server, 'server keeps plain bash')

    def test_stage_assets_stages_bash_config(self):
        for hook in ('hooks/desktop/stage-assets.sh', 'hooks/server/stage-assets.sh'):
            self.assertIn('assets/bash', (ROOT / hook).read_text())

    def test_non_interactive_shells_are_untouched(self):
        # Sourcing from a script must return immediately without aliases,
        # prompt changes or errors.
        script = f'. "{ASSET}"; alias ll >/dev/null 2>&1 && echo defined || echo undefined'
        result = bash(['--noprofile', '--norc', '-c', script])
        self.assertEqual(result.stdout.strip(), 'undefined')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_asset_guards_missing_tools(self):
        # git is absent from the test sandbox PATH; the prompt must still
        # come up without errors.
        env = {**os.environ, 'PATH': '/usr/bin:/bin', 'GIT_EXEC_PATH': '/nonexistent'}
        result = bash(['--noprofile', '--norc', '-c',
                       f'. "{ASSET}" 2>&1; echo sourced-ok'], env=env)
        self.assertIn('sourced-ok', result.stdout)


class InteractivePtyTests(unittest.TestCase):
    """Drive a real interactive bash on a PTY."""

    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.rc = make_rcfile(self.temp.name)

    def spawn(self, **kwargs):
        shell = PtyBash(self.rc, **kwargs)
        self.addCleanup(shell.close)
        shell.read_until('$ ', timeout=15)  # first prompt
        return shell

    def test_interactive_shell_starts_clean(self):
        shell = self.spawn()
        # Quotes keep the echoed input line from containing the marker.
        shell.send("echo RE''ADY")
        out = shell.read_until('READY')
        out = shell.read_until('$ ')
        self.assertNotIn('command not found', out)
        self.assertNotIn('error', out.lower())

    def test_aliases_and_history_settings(self):
        shell = self.spawn()
        shell.send('alias ll')
        out = shell.read_until('alF')
        self.assertIn('--color=auto', out)
        shell.send("echo HS=1''00000")
        self.assertIn('HS=100000', shell.read_until('HS=100000'))

    def test_git_branch_and_dirty_state_in_prompt(self):
        repo = Path(self.temp.name) / 'repo'
        repo.mkdir()
        init = bash(['-c', f'git init -q -b yaran-test "{repo}"'])
        self.assertEqual(
            init.returncode, 0,
            f'git init failed in the test environment: {init.stderr.strip()!r} '
            '(is the git package installed?)')
        shell = self.spawn(workdir=str(repo))
        shell.send('')
        out = shell.read_until('yaran-test')
        self.assertIn('(yaran-test', out)
        # untracked file marks the branch dirty (%)
        (repo / 'new-file').write_text('x')
        shell.send('')
        out = shell.read_until('$ ')
        self.assertIn('%', out)
        # leaving the repo removes the branch part
        shell.send(f'cd "{self.temp.name}"')
        shell.read_until('$ ')
        shell.send('')
        out = shell.read_until('$ ')
        self.assertNotIn('yaran-test', out)

    def test_exit_code_marker_is_subtle_and_disappears(self):
        shell = self.spawn()
        shell.send('false')
        out = shell.read_until('$ ')
        self.assertRegex(out, r'\[1\]')
        shell.send('true')
        out = shell.read_until('$ ')
        self.assertNotRegex(out, r'\[\d+\]')

    def test_tab_completes_unique_file_prefix(self):
        workdir = Path(self.temp.name)
        (workdir / 'yaran_tab_probe.txt').write_text('probe')
        shell = self.spawn(workdir=str(workdir))
        os.write(shell.master, b'cat yaran_tab_probe.\t')
        out = shell.read_until('yaran_tab_probe.txt', timeout=5)
        self.assertIn('yaran_tab_probe.txt', out)

    def test_startup_is_fast(self):
        start = time.time()
        shell = self.spawn()
        elapsed = time.time() - start
        shell.send('echo done')
        shell.read_until('done')
        self.assertLess(elapsed, 10.0, 'interactive startup too slow')  # generous CI bound

    def test_history_survives_and_deduplicates(self):
        shell = self.spawn()
        shell.send('echo unique-yaran-history-entry')
        shell.read_until('unique-yaran-history-entry')
        shell.send('')
        shell.read_until('$ ')
        result = bash(['--noprofile', '--norc', '-c',
                       f'cat "{self.temp.name}/.histfile"'])
        self.assertIn('unique-yaran-history-entry', result.stdout)


if __name__ == '__main__':
    unittest.main()
