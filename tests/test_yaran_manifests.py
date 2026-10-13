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
    # Font coverage.
    'fonts-vazirmatn',
    'fonts-vazirmatn-variable',
    'fonts-noto-core',
    'fonts-noto-cjk',
    'fonts-noto-color-emoji',
    # Boot branding.
    'plymouth',
}

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

    def test_no_package_lists_are_duplicated(self):
        for name, cfg in self.configs.items():
            with self.subTest(manifest=name):
                packages = cfg['packages']
                self.assertEqual(len(packages), len(set(packages)),
                                 f'{name} contains duplicate package names')

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


if __name__ == '__main__':
    unittest.main()
