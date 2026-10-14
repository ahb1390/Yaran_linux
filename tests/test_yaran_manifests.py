"""Policy tests for the Yaran manifests, hooks and Calamares configuration.

These encode the lessons from testing Yaran 2.0 on real hardware so the
regressions they catch cannot silently return:
  * background APT jobs must never take the package locks (APT lock issue);
  * only signed, justified repositories may ship in the image;
  * the screen-sharing stack (xdg-desktop-portal + KDE backend) is mandatory;
  * Persian/CJK/emoji fonts ship and fontconfig prefers them;
  * the Calamares finished page offers a restart;
  * the installed system gets a GRUB theme and a Plymouth splash;
  * KWallet stays disabled and ~/Projects comes from /etc/skel;
  * Hiddify's runtime dependency and launcher are handled by the hook.
"""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DESKTOP_MANIFESTS = [
    ROOT / 'Yaran-2.0-amd64.json',
    ROOT / 'Yaran-2.0-amd64-minimal.json',
    ROOT / 'Yaran-2.0-amd64-extended.json',
    ROOT / 'Yaran-2.0-arm64.json',
]

REQUIRED_PACKAGES = {
    # Screen sharing in Chrome/Meet (Wayland and X11) needs the full portal
    # chain, not just PipeWire.
    'xdg-desktop-portal',
    'xdg-desktop-portal-kde',
    'pipewire',
    'pipewire-audio',
    'wireplumber',
    # Sound control (volume keys, applet, pavucontrol path).
    'plasma-pa',
    # Laptop power management: powerdevil drives brightness keys, the
    # battery applet, lid-close and suspend policies.
    'powerdevil',
    'upower',
    'power-profiles-daemon',
    # KDE shell tools.
    'bluedevil',
    'plasma-nm',
    'kinfocenter',
    # Firmware updates through Discover/fwupd.
    'fwupd',
    'plasma-discover-backend-fwupd',
    # Font coverage.
    'fonts-vazirmatn',
    'fonts-vazirmatn-variable',
    'fonts-noto-core',
    'fonts-noto-cjk',
    'fonts-noto-mono',
    'fonts-noto-ui-core',
    'fonts-noto-color-emoji',
    # Firmware for common laptop hardware.
    'firmware-misc-nonfree',
    'bluez-firmware',
    # Audio quality: rtkit grants PipeWire realtime priority (its absence
    # shows up as "RTKit error: ServiceUnknown" on every session start);
    # alsa-ucm-conf provides codec UCM profiles for correct speaker/
    # headphone/mic path handling; zram-tools adds compressed RAM swap
    # because Calamares installs without a swap partition by default.
    'rtkit',
    'alsa-ucm-conf',
    'zram-tools',
    # Boot branding.
    'plymouth',
}

# AMD64-only additions: Intel thermal management (thermald exits cleanly on
# non-Intel hardware but there is no reason to ship it on ARM).
AMD64_REQUIRED_PACKAGES = {'thermald'}

# Diagnostic tools only the Extended image carries.
EXTENDED_DIAGNOSTIC_PACKAGES = {
    'v4l-utils', 'vainfo', 'pciutils', 'usbutils', 'lshw', 'lm-sensors',
}

# Applications that must never appear in a Yaran desktop image; TLP would
# additionally fight power-profiles-daemon over power management.
FORBIDDEN_PACKAGES = {
    'nautilus', 'gnome-terminal', 'file-roller', 'evince', 'eog',
    'totem', 'rhythmbox', 'tlp', 'tlp-rdw',
    # Zenity was shipped but used by no Yaran script; it only pulled the
    # GNOME toolkit (libadwaita + adwaita-icon-theme) into the image.
    'zenity',
}

# Extra font families only the Extended image carries (large download).
EXTENDED_FONT_PACKAGES = {'fonts-noto-cjk-extra', 'fonts-noto-ui-extra', 'fonts-noto-extra'}

DISABLED_UNITS = {'apt-daily.timer', 'apt-daily-upgrade.timer', 'unattended-upgrades.service'}


def load(path):
    return json.loads(path.read_text())


class ManifestPolicyTests(unittest.TestCase):
    def setUp(self):
        self.configs = {p.name: load(p) for p in DESKTOP_MANIFESTS}

    def test_every_desktop_variant_ships_required_packages(self):
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                packages = set(cfg['packages'])
                missing = REQUIRED_PACKAGES - packages
                self.assertFalse(missing, f'{name} is missing: {sorted(missing)}')

    def test_amd64_variants_ship_thermald_and_enable_it(self):
        for name, cfg in self.configs.items():
            if 'amd64' not in name:
                continue
            with self.subTest(manifest=name):
                self.assertTrue(AMD64_REQUIRED_PACKAGES <= set(cfg['packages']),
                                f'{name} is missing {sorted(AMD64_REQUIRED_PACKAGES)}')
                self.assertIn('thermald', cfg['services'].get('enable', []))
        for name, cfg in self.configs.items():
            if 'amd64' in name:
                continue
            with self.subTest(manifest=name):
                self.assertFalse(AMD64_REQUIRED_PACKAGES & set(cfg['packages']),
                                 f'{name} must not ship x86-only packages')

    def test_diagnostic_tools_only_ship_in_extended(self):
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                present = EXTENDED_DIAGNOSTIC_PACKAGES & set(cfg['packages'])
                if name.endswith('extended.json'):
                    self.assertFalse(EXTENDED_DIAGNOSTIC_PACKAGES - present,
                                     f'extended missing {sorted(EXTENDED_DIAGNOSTIC_PACKAGES - present)}')
                else:
                    self.assertFalse(present,
                                     f'{name} should not carry Extended-only tools: {sorted(present)}')

    def test_no_package_lists_are_duplicated(self):
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                packages = cfg['packages']
                self.assertEqual(len(packages), len(set(packages)),
                                 f'{name} contains duplicate package names')

    def test_no_unwanted_gnome_apps_or_conflicting_power_managers(self):
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                packages = set(cfg['packages'])
                present = FORBIDDEN_PACKAGES & packages
                self.assertFalse(present, f'{name} ships unwanted packages: {sorted(present)}')
                # Excluding them keeps future dependency changes from
                # silently reintroducing them.
                self.assertTrue(FORBIDDEN_PACKAGES <= set(cfg['exclude_packages']),
                                f'{name} must exclude {sorted(FORBIDDEN_PACKAGES - set(cfg["exclude_packages"]))}')

    def test_extended_ships_the_extra_font_families(self):
        extended = self.configs['Yaran-2.0-amd64-extended.json']
        missing = EXTENDED_FONT_PACKAGES - set(extended['packages'])
        self.assertFalse(missing, f'extended is missing large font sets: {sorted(missing)}')

    def test_dolphin_is_the_default_file_manager(self):
        mimeapps = (ROOT / 'assets/yaran-plasma-theme/etc/xdg/mimeapps.list').read_text()
        self.assertIn('inode/directory=org.kde.dolphin.desktop', mimeapps)
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                self.assertIn('dolphin', cfg['packages'])
                # Everything needed to open common file types in KDE apps.
                for pkg in ('gwenview', 'okular', 'ark'):
                    self.assertIn(pkg, cfg['packages'])

    def test_verify_image_covers_script_and_power_policy(self):
        hook = (ROOT / 'hooks/common/verify-image.sh').read_text()
        self.assertIn('powerdevil', hook)
        self.assertIn('nautilus', hook)
        self.assertIn('inode/directory=org.kde.dolphin.desktop', hook)
        # One fc-list probe per major script must exist.
        for lang in ('fa', 'ar', 'he', 'hi', 'th', 'bo', 'hy', 'ka', 'am',
                     'zh-cn', 'zh-tw', 'ja', 'ko'):
            self.assertIn(f'{lang}|', hook)

    def test_apt_sources_are_signed_and_have_no_backports_by_default(self):
        for name, cfg in self.configs.items():
            for source in cfg['apt_sources']:
                with self.subTest(manifest=name, source=source):
                    self.assertNotIn('trusted=yes', source)
                    self.assertNotIn('[', source, 'no inline apt options allowed')
            # trixie-backports may only ship when a package genuinely needs it
            # (telegram-desktop is only packaged in trixie-backports).
            backports = [s for s in cfg['apt_sources'] if 'backports' in s]
            if backports:
                self.assertIn('telegram-desktop', cfg['packages'],
                              f'{name} enables backports without a pinned package')

    def test_background_apt_jobs_are_disabled(self):
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                self.assertNotIn('unattended-upgrades', cfg['services'].get('enable', []))
                self.assertTrue(DISABLED_UNITS <= set(cfg['services'].get('disable', [])),
                                f'{name} must disable {sorted(DISABLED_UNITS)}')

    def test_update_policy_hook_disables_periodic_apt(self):
        hook = (ROOT / 'hooks/desktop/automatic-updates.sh').read_text()
        self.assertIn('APT::Periodic::Update-Package-Lists "0"', hook)
        self.assertIn('APT::Periodic::Unattended-Upgrade "0"', hook)
        self.assertIn('yaran-update', hook)
        # The hook must never delete locks or force-kill package managers.
        for forbidden in ('rm -f /var/lib/dpkg', 'kill -9', 'rm -f /var/lib/apt'):
            self.assertNotIn(forbidden, hook)

    def test_last_chroot_hook_validates_the_image(self):
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                scripts = cfg['post_install_scripts']
                self.assertIn('hooks/common/verify-image.sh', scripts)
                self.assertEqual(scripts[-1], 'hooks/common/verify-image.sh',
                                 f'{name}: verify-image.sh must run last')

    def test_boot_branding_hooks_run_after_plasma_assets(self):
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                scripts = cfg['post_install_scripts']
                self.assertIn('hooks/desktop/grub-theme.sh', scripts)
                self.assertIn('hooks/desktop/plymouth-theme.sh', scripts)
                self.assertLess(scripts.index('hooks/desktop/plasma-assets.sh'),
                                scripts.index('hooks/desktop/grub-theme.sh'),
                                'wallpapers must be installed before the GRUB theme')
                self.assertLess(scripts.index('hooks/desktop/plasma-assets.sh'),
                                scripts.index('hooks/desktop/plymouth-theme.sh'),
                                'wallpapers must be installed before the Plymouth theme')

    def test_boot_append_keeps_quiet_splash(self):
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                self.assertIn('splash', cfg['boot_append'].split())


class HookContentTests(unittest.TestCase):
    def test_external_apps_hook_installs_hiddify_runtime_and_launcher(self):
        hook = (ROOT / 'hooks/desktop/install-external-apps.sh').read_text()
        self.assertIn('libayatana-appindicator3-1', hook,
                      'Hiddify links against libayatana-appindicator3 at runtime')
        self.assertIn('/usr/bin/hiddify', hook,
                      'the upstream .deb ships no launcher on PATH')
        self.assertIn('ldd', hook)

    def test_external_apps_hook_pins_verified_hashes(self):
        hook = (ROOT / 'hooks/desktop/install-external-apps.sh').read_text()
        hashes = re.findall(r'"([0-9a-f]{64})"', hook)
        self.assertGreaterEqual(len(hashes), 2, 'every .deb needs a pinned SHA-256')

    def test_verify_image_checks_lock_policy_and_portals(self):
        hook = (ROOT / 'hooks/common/verify-image.sh').read_text()
        self.assertIn('trusted=yes', hook)
        self.assertIn('xdg-desktop-portal-kde', hook)
        self.assertIn('apt-daily.timer', hook)

    def test_fontconfig_prefers_persian_and_cjk(self):
        hook = (ROOT / 'hooks/desktop/desktop-defaults.sh').read_text()
        self.assertIn('Vazirmatn', hook)
        self.assertIn('Noto Sans CJK SC', hook)
        self.assertIn('/etc/skel/Projects', hook)
        self.assertIn('fc-cache', hook)

    def test_grub_branding_config_uses_theme(self):
        hook = (ROOT / 'hooks/desktop/login-branding.sh').read_text()
        self.assertIn('GRUB_THEME="/usr/share/grub/themes/yaran/theme.txt"', hook)
        self.assertIn('GRUB_BACKGROUND', hook, 'background stays as a fallback')

    def test_no_hook_deletes_apt_locks(self):
        for script in (ROOT / 'hooks').rglob('*.sh'):
            with self.subTest(script=script.name):
                # Comments may discuss lock paths (documentation); only real
                # commands must avoid them.
                code = '\n'.join(line for line in script.read_text().splitlines()
                                 if not line.lstrip().startswith('#'))
                self.assertNotIn('/var/lib/dpkg/lock', code)
                self.assertNotIn('/var/lib/apt/lists/lock', code)
                self.assertNotIn('kill -9', code)


class BootBrandingTests(unittest.TestCase):
    def test_grub_theme_assets_exist(self):
        theme = ROOT / 'assets/grub-theme/yaran/theme.txt'
        self.assertTrue(theme.is_file())
        content = theme.read_text()
        self.assertIn('desktop-image: "background.png"', content)
        self.assertIn('boot_menu', content)

    def test_plymouth_theme_assets_exist(self):
        for filename in ('yaran.plymouth', 'yaran.script'):
            self.assertTrue((ROOT / 'assets/plymouth/yaran' / filename).is_file())
        descriptor = (ROOT / 'assets/plymouth/yaran/yaran.plymouth').read_text()
        self.assertIn('ModuleName=script', descriptor)
        self.assertIn('ImageDir=/usr/share/plymouth/themes/yaran', descriptor)


class CalamaresTests(unittest.TestCase):
    def setUp(self):
        self.settings = (ROOT / 'assets/calamares/settings.conf').read_text()

    def test_finished_page_is_shown(self):
        self.assertIn('- finished', self.settings)

    def test_finished_module_offers_restart(self):
        finished = (ROOT / 'assets/calamares/modules/finished.conf').read_text()
        self.assertIn('restartNowEnabled: true', finished)
        self.assertIn('restartNowCommand:', finished)
        # Restart must go through the official Calamares mechanism only.
        self.assertNotIn('shutdown', finished)

    def test_cleanup_removes_live_only_config(self):
        cleanup = (ROOT / 'assets/calamares/modules/shellprocess-cleanup.conf').read_text()
        self.assertIn('zz-yaran-live-autologin.conf', cleanup)


class WalletPolicyTests(unittest.TestCase):
    def test_kdeglobals_disables_wallet(self):
        globals_ = (ROOT / 'assets/yaran-plasma-theme/etc/xdg/kdeglobals').read_text()
        match = re.search(r'\[Wallet\](.*?)\n\[', globals_ + '\n[', re.S)
        self.assertIsNotNone(match, 'a [Wallet] section must exist')
        self.assertIn('Enabled=false', match.group(1))

    def test_wallet_helpers_are_excluded(self):
        for path in DESKTOP_MANIFESTS:
            cfg = load(path)
            with self.subTest(manifest=path.name):
                self.assertIn('kwalletmanager', cfg['exclude_packages'])
                self.assertIn('kwallet-pam', cfg['exclude_packages'])


class SpacePathRegressionTests(unittest.TestCase):
    """Quoting bugs are semantic: `bash -n` accepts them and only a real
    build inside the image fails. Assigning
        background=/usr/share/wallpapers/Yaran Emblem/...
    unquoted broke all three desktop CI builds; these tests keep the
    mistake from ever coming back."""

    HOOKS = sorted((ROOT / 'hooks').rglob('*.sh')) + [ROOT / 'assets/bash/yaran-bashrc']

    def test_no_unquoted_assignment_contains_a_space(self):
        for hook in self.HOOKS:
            heredoc = None
            for number, line in enumerate(hook.read_text().splitlines(), 1):
                stripped = line.strip()
                if heredoc:
                    if stripped == heredoc:
                        heredoc = None
                    continue
                if '<<' in stripped:
                    match = re.search(r"<<-?\s*['\"]?(\w+)['\"]?\s*$", stripped)
                    heredoc = match.group(1) if match else None
                if stripped.startswith('#'):
                    continue
                assignment = re.match(r"([A-Za-z_]\w*)=([^'\"$].*\s.*)$", stripped)
                if assignment:
                    self.fail(f'{hook}:{number}: unquoted assignment containing '
                              f'a space: {stripped!r}')

    def test_space_containing_path_survives_the_hooks_quoting_pattern(self):
        # Execute the quoting pattern the theme hooks use against a fake
        # tree whose path contains a space, and prove the unquoted variant
        # really fails — documenting why the quotes must stay.
        with tempfile.TemporaryDirectory() as tmp:
            image_dir = Path(tmp) / 'usr/share/wallpapers/Yaran Emblem/contents/images'
            image_dir.mkdir(parents=True)
            (image_dir / '1585x992.png').write_bytes(b'\x89PNG-fixture')
            quoted = (
                f'background="{image_dir}/1585x992.png"\n'
                '[ -f "$background" ] || { echo "quoted form lost the path" >&2; exit 1; }\n'
                'cp "$background" "$1/background.png"\n'
            )
            result = subprocess.run(['bash', '-euo', 'pipefail', '-c', quoted, '_', tmp],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((Path(tmp) / 'background.png').read_bytes(), b'\x89PNG-fixture')
            unquoted = (
                f'background={image_dir}/1585x992.png\n'
                '[ -f "$background" ]\n'
            )
            result = subprocess.run(['bash', '-c', unquoted], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0,
                                'the unquoted variant unexpectedly succeeded; '
                                'the test fixture no longer models the bug')

    def test_theme_hooks_quote_the_real_asset_path(self):
        image = ROOT / 'assets/wallpapers/Yaran Emblem/contents/images/1585x992.png'
        self.assertTrue(image.is_file(), 'the GRUB/Plymouth background asset is missing')
        expected = 'background="/usr/share/wallpapers/Yaran Emblem/contents/images/1585x992.png"'
        for hook in ('hooks/desktop/grub-theme.sh', 'hooks/desktop/plymouth-theme.sh'):
            with self.subTest(hook=hook):
                self.assertIn(expected, (ROOT / hook).read_text())


class PipefailGrepRegressionTests(unittest.TestCase):
    """`set -o pipefail` + `grep -q` is a trap: the grep exits on the first
    match while the upstream producer is still writing, the producer dies
    with SIGPIPE (exit 141) and the whole pipeline reports failure even
    though the match existed. On the Extended image the fc-list output is
    large enough (fonts-noto-extra/cjk-extra) to hit this every time —
    this is what failed in CI run 38573661931."""

    HOOKS = sorted((ROOT / 'hooks').rglob('*.sh'))

    def test_no_hook_pipes_into_a_short_circuiting_grep(self):
        for hook in self.HOOKS:
            with self.subTest(hook=hook.name):
                # Comments may discuss the pattern; only real code counts.
                code = '\n'.join(line for line in hook.read_text().splitlines()
                                 if not line.lstrip().startswith('#'))
                self.assertNotRegex(
                    code, r'\|\s*grep\s+-[A-Za-z]*q',
                    f'{hook.name} pipes into grep -q; capture the output '
                    'into a variable and match against it instead')

    def test_grep_q_pipeline_really_breaks_on_large_streams(self):
        # Reproduce the CI failure mode deterministically: an early match
        # kills the producer with SIGPIPE under pipefail.
        trap = subprocess.run(
            ['bash', '-euo', 'pipefail', '-c', 'seq 1 200000 | grep -q 1'],
            capture_output=True)
        self.assertNotEqual(trap.returncode, 0,
                            'expected the grep -q pipeline to fail under '
                            'pipefail with a large stream')
        # ...and prove the capture-then-match pattern used by the hooks
        # survives the same volume.
        capture = subprocess.run(
            ['bash', '-euo', 'pipefail', '-c',
             'big=$(seq 1 200000)\n'
             'case "$big" in *199999*) : ;; *) exit 1 ;; esac\n'
             'printf "%s\\n" "$big" | wc -l >/dev/null\n'
             'echo survived'],
            capture_output=True, text=True)
        self.assertEqual(capture.returncode, 0, capture.stderr)
        self.assertIn('survived', capture.stdout)

    def test_font_coverage_checks_still_require_real_families(self):
        # The pipefail fix must not weaken the coverage criteria: the hook
        # still demands a registered family per script and the Noto
        # families by name.
        hook = (ROOT / 'hooks/common/verify-image.sh').read_text()
        for lang in ('fa', 'ar', 'he', 'hi', 'th', 'bo', 'hy', 'ka', 'am',
                     'zh-cn', 'zh-tw', 'ja', 'ko'):
            self.assertIn(f'{lang}|', hook)
        self.assertIn("case \"$zh_fonts\" in", hook)
        self.assertIn("'Noto Sans CJK'", hook)
        self.assertIn('Vazirmatn', hook)


if __name__ == '__main__':
    unittest.main()
