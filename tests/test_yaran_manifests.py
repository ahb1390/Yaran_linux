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
import os
import re
import subprocess
import sys
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

    def test_grub_theme_uses_only_grub_2_12_properties(self):
        """GRUB 2.12 (Debian trixie, grub2 2.12-9+deb13u2 on every platform)
        registers no `terminal-color` theme property — its gfxmenu modules
        expose only terminal-border/box/font/height/left/top/width — and the
        parser aborts every boot with
        `theme.txt:17:26 unknown property 'terminal-color'` plus a
        "Press any key to continue" when the theme uses it."""
        theme = ROOT / 'assets/grub-theme/yaran/theme.txt'
        code = '\n'.join(line for line in theme.read_text().splitlines()
                         if not line.lstrip().startswith('#'))
        self.assertNotIn('terminal-color', code)
        # desktop-color keeps the menu readable if the background image
        # fails to load; it IS a registered GRUB 2.12 property.
        self.assertIn('desktop-color:', code)

    def test_grub_background_path_has_no_whitespace(self):
        """update-grub's 05_debian_theme emits `background_image <path>`
        for GRUB_BACKGROUND WITHOUT quoting it, so a whitespace-containing
        path is truncated at the first space by GRUB and every boot of the
        installed system fails with `bitmap file "/usr/share/wallpapers/Yaran"
        is of unsupported format`."""
        hook = (ROOT / 'hooks/desktop/login-branding.sh').read_text()
        match = re.search(r'^GRUB_BACKGROUND="([^"]*)"', hook, re.M)
        self.assertIsNotNone(match, 'login-branding must set GRUB_BACKGROUND')
        background = match.group(1)
        self.assertNotRegex(background, r'\s',
                            'GRUB_BACKGROUND must not contain whitespace')
        self.assertRegex(background, r'\.(png|jpg|jpeg|tga)$',
                         'GRUB_BACKGROUND must be a GRUB-supported image')
        self.assertEqual(background, '/usr/share/grub/themes/yaran/background.png',
                         'fallback must be the space-free theme copy that '
                         'grub-theme.sh installs')

    def test_theme_txt_references_only_fonts_the_hook_generates(self):
        """grub-theme.sh generates DejaVuSans.pf2 and DejaVuSansMono.pf2 (or
        rewrites the theme to Unifont/regular-face fallbacks); every font
        family theme.txt mentions must be one of those."""
        theme = (ROOT / 'assets/grub-theme/yaran/theme.txt').read_text()
        for family in re.findall(r'font\s*[:=]\s*"([^"]+)"', theme):
            with self.subTest(family=family):
                self.assertRegex(family, r'^(DejaVu Sans( Mono)?|Unifont) Regular \d+$')

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


class VendorRepositoryPolicyTests(unittest.TestCase):
    """Nothing in this project may add a non-Debian source to
    /etc/apt/sources.list.d without an explicit per-manifest opt-in
    ("vendor_repositories": true). These tests keep the opt-in gate, the
    consent record and the final in-image check from being weakened."""

    VENDOR_PACKAGES = ('google-chrome-stable', 'virtualbox')

    def vendor_hook(self, name):
        return (ROOT / 'hooks/desktop' / name).read_text()

    def test_manifests_opt_in_only_when_they_ship_vendor_packages(self):
        for path in DESKTOP_MANIFESTS + [ROOT / 'Yaran-Server-2.0-amd64.json']:
            cfg = load(path)
            with self.subTest(manifest=path.name):
                ships_vendor = any(
                    pkg in self.VENDOR_PACKAGES or pkg.startswith('virtualbox')
                    for pkg in cfg['packages'])
                opted_in = cfg.get('vendor_repositories', False)
                self.assertEqual(
                    opted_in, ships_vendor,
                    f'{path.name}: vendor_repositories must be true exactly '
                    'when the manifest ships vendor-repository packages')

    def test_vendor_hooks_gate_on_the_manifest_opt_in(self):
        for name in ('vendor-repos.sh', 'vendor-repos-extended.sh'):
            with self.subTest(hook=name):
                hook = self.vendor_hook(name)
                self.assertIn('YARAN_VENDOR_REPOSITORIES', hook)
                self.assertRegex(
                    hook, r'\[ "\$\{YARAN_VENDOR_REPOSITORIES:-0\}" != "1" \]',
                    f'{name} must skip everything without the opt-in')
                # Every written .list file must be recorded so
                # verify-image.sh can prove the consent existed.
                self.assertIn('/etc/apt/yaran-vendor-repos', hook)

    def test_vendor_hooks_never_use_insecure_shortcuts(self):
        for name in ('vendor-repos.sh', 'vendor-repos-extended.sh'):
            with self.subTest(hook=name):
                code = '\n'.join(line for line in self.vendor_hook(name).splitlines()
                                 if not line.lstrip().startswith('#'))
                for forbidden in ('trusted=yes', 'allow-insecure', 'apt-key',
                                  'add-apt-repository', 'check-valid-until=no'):
                    self.assertNotIn(forbidden, code)

    def test_builder_requires_the_opt_in_for_vendor_packages(self):
        build = (ROOT / 'build.py').read_text()
        self.assertIn('VENDOR_REPOSITORY_PACKAGES', build)
        self.assertIn('YARAN_VENDOR_REPOSITORIES', build)

    def test_verify_image_fails_on_a_repo_without_opt_in(self):
        hook = (ROOT / 'hooks/common/verify-image.sh').read_text()
        self.assertIn('/etc/apt/yaran-vendor-repos', hook)
        self.assertIn('has no vendor_repositories opt-in', hook)

    def test_verify_image_covers_both_list_and_deb822_sources(self):
        """A vendor source must not dodge the policy by switching from the
        one-line (.list) to the deb822 (.sources) syntax."""
        hook = (ROOT / 'hooks/common/verify-image.sh').read_text()
        self.assertIn("'*.sources'", hook, 'the consent scan must read .sources')
        self.assertIn('URIs:', hook, 'deb822 origins come from URIs:')
        self.assertIn('Signed-By:', hook, 'deb822 key pinning is Signed-By:')
        # Both find expressions must include the deb822 glob.
        self.assertRegex(hook, r"-name '\*\.list' -o -name '\*\.sources'")

    def test_only_vendor_hooks_touch_sources_list_d(self):
        """No other hook or script may create .list/.sources files or call
        add-apt-repository; the only allowed writer besides the vendor hooks
        is the builder itself (build.py writes /etc/apt/sources.list)."""
        offenders = []
        for script in sorted((ROOT / 'hooks').rglob('*.sh')):
            if script.name.startswith('vendor-repos'):
                continue
            code = '\n'.join(line for line in script.read_text().splitlines()
                             if not line.lstrip().startswith('#'))
            for pattern in ('add-apt-repository', 'apt-key add',
                            'sources.list.d/'):
                if pattern in code:
                    offenders.append(f'{script.relative_to(ROOT)}: {pattern}')
        self.assertEqual(offenders, [],
                         'hooks outside vendor-repos*.sh must not add APT sources')


class NodeJs26Tests(unittest.TestCase):
    """The project must ship Node.js 26.x, obtained repeatably and
    verifiably, without adding an external APT repository."""

    HOOK = ROOT / 'hooks/desktop/install-nodejs26.sh'

    def test_hook_installs_a_pinned_v26_release_with_hashes(self):
        hook = self.HOOK.read_text()
        match = re.search(r'^NODE_VERSION="(v(\d+)\.\d+\.\d+)"', hook, re.M)
        self.assertIsNotNone(match, 'install-nodejs26.sh must pin NODE_VERSION')
        self.assertEqual(match.group(2), '26',
                         f'Node.js must come from the 26 release line, got {match.group(1)}')
        for arch in ('x64', 'arm64'):
            pinned = re.search(rf'^NODE_SHA256_{arch}="([0-9a-f]{{64}})"', hook, re.M)
            self.assertIsNotNone(pinned, f'missing pinned SHA-256 for {arch}')
        # The download must be verified before extraction, and cross-checked
        # against the upstream manifest next to the tarball.
        self.assertIn('sha256sum', hook)
        self.assertIn('SHASUMS256.txt', hook)
        # No APT repository may be involved.
        code = '\n'.join(line for line in hook.splitlines()
                         if not line.lstrip().startswith('#'))
        for forbidden in ('add-apt-repository', 'sources.list.d', 'apt-key',
                          'nodesource', 'deb http', 'deb https'):
            self.assertNotIn(forbidden, code)

    def test_hook_extracts_into_the_platform_suffixed_directory(self):
        """The upstream tarball extracts to node-<version>-linux-<arch>/;
        pointing at node-<version>/ silently produces a broken /usr/local/bin
        (the hook then fails its own bin/node existence check)."""
        hook = self.HOOK.read_text()
        self.assertIn('node-$NODE_VERSION-linux-$node_arch', hook)

    def test_extended_ships_the_hook_and_drops_debian_nodejs(self):
        cfg = load(ROOT / 'Yaran-2.0-amd64-extended.json')
        self.assertIn('hooks/desktop/install-nodejs26.sh',
                      cfg['pre_chroot_scripts'])
        for path in DESKTOP_MANIFESTS + [ROOT / 'Yaran-Server-2.0-amd64.json']:
            with self.subTest(manifest=path.name):
                self.assertNotIn('nodejs', load(path)['packages'],
                                 'Debian trixie only packages Node.js 20.x')
                self.assertNotIn('npm', load(path)['packages'])

    def test_only_extended_ships_nodejs(self):
        for path in DESKTOP_MANIFESTS:
            if path.name.endswith('extended.json'):
                continue
            with self.subTest(manifest=path.name):
                self.assertNotIn('hooks/desktop/install-nodejs26.sh',
                                 load(path)['pre_chroot_scripts'])

    def test_verify_image_asserts_the_v26_toolchain(self):
        hook = (ROOT / 'hooks/common/verify-image.sh').read_text()
        self.assertIn('v26.*', hook)
        self.assertIn('npm', hook)


class DesktopFontIconTests(unittest.TestCase):
    """The desktop must ship a complete, readable font and icon set."""

    ICON_PACKAGES = {'breeze-icon-theme', 'hicolor-icon-theme'}
    GRUB_FONT_SOURCE = {'fonts-dejavu-core'}

    def test_every_desktop_manifest_ships_icons_and_grub_fonts(self):
        for path in DESKTOP_MANIFESTS:
            cfg = load(path)
            with self.subTest(manifest=path.name):
                packages = set(cfg['packages'])
                missing = (self.ICON_PACKAGES | self.GRUB_FONT_SOURCE) - packages
                self.assertFalse(missing,
                                 f'{path.name} is missing: {sorted(missing)}')

    def test_core_text_fonts_cover_ui_mono_persian_and_arabic(self):
        # Noto Sans (UI), Noto Sans Mono (terminal), Vazirmatn (Persian) and
        # the Noto Arabic families (shipped inside fonts-noto-core) must all
        # be present; Amiri is the extra Arabic fallback.
        for path in DESKTOP_MANIFESTS:
            cfg = load(path)
            with self.subTest(manifest=path.name):
                packages = set(cfg['packages'])
                for pkg in ('fonts-noto-core', 'fonts-noto-mono',
                            'fonts-vazirmatn', 'fonts-hosny-amiri'):
                    self.assertIn(pkg, packages,
                                  f'{path.name} is missing {pkg}')

    def test_kdeglobals_selects_breeze_icons(self):
        globals_ = (ROOT / 'assets/yaran-plasma-theme/etc/xdg/kdeglobals').read_text()
        self.assertIn('IconTheme=breeze', globals_)
        self.assertIn('breeze', load(DESKTOP_MANIFESTS[0])['packages'],
                      'the selected icon theme must be installed')


class CIFailureRegressionTests(unittest.TestCase):
    """Regressions for the three real failures of CI run 38727935250
    (commit 6dfcdfa, "Build & Validate Yaran Linux" run #8):

      1. AMD64+ARM64: verify-image reported
         "the installed GRUB theme uses terminal-color" — a FALSE POSITIVE:
         the theme.txt '#' comment that documents the GRUB 2.12 history
         mentions the literal string, and the old check matched it.
      2. Minimal: verify-image reported
         "vendor repository host dl.google.com in
         /etc/apt/sources.list.d/google-chrome.sources has no
         vendor_repositories opt-in" — google-chrome-stable's OWN postinst
         writes that deb822 file on a fresh install; consent was tracked
         per FILENAME, so the package's file had no matching entry.
      3. Extended: install-nodejs26.sh failed with
         "tar (child): xz: Cannot exec" — the pre_chroot hook extracts the
         .tar.xz on the BUILD HOST, where the minimal CI container ships
         no xz binary.

    Each test runs the REAL check code extracted from the hooks against
    fixtures that model the built image, so the checks cannot silently
    drift back to the broken behaviour."""

    VERIFY = ROOT / 'hooks/common/verify-image.sh'

    @staticmethod
    def extract_block(text, start_prefix, end_predicate):
        """Return the real hook lines from the one starting with
        start_prefix through the first line satisfying end_predicate."""
        lines = text.splitlines()
        start = next(i for i, line in enumerate(lines)
                     if line.startswith(start_prefix))
        end = next(i for i in range(start, len(lines))
                   if end_predicate(lines[i]))
        return '\n'.join(lines[start:end + 1])

    @staticmethod
    def run_with_definitions(block, tmp_path, extra=''):
        harness = (
            'fail=0\n'
            'problem() { echo "PROBLEM: $*" >&2; fail=1; }\n'
            'ok() { echo "OK: $*"; }\n'
            f'{extra}\n'
            f'{block}\n'
            'echo "FAILCOUNT=$fail"\n'
        )
        return subprocess.run(['bash', '-c', harness], cwd=tmp_path,
                              capture_output=True, text=True)

    # --- failure 1: theme.txt comment false positive ------------------------

    def test_theme_check_ignores_documenting_comments(self):
        hook = self.VERIFY.read_text()
        block = self.extract_block(
            hook, '    theme_content=$(grep -Ev',
            lambda line: line.strip() == 'esac')
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / 'theme.txt'
            # The REAL repository theme: mentions terminal-color only in
            # '#' comments (the documentation of this very CI failure).
            theme.write_text((ROOT / 'assets/grub-theme/yaran/theme.txt').read_text())
            result = self.run_with_definitions(
                block.replace('/usr/share/grub/themes/yaran/theme.txt',
                              str(theme)), tmp)
            self.assertNotIn('PROBLEM', result.stdout + result.stderr,
                             'the documenting comment must not trip the check')
            self.assertIn('FAILCOUNT=0', result.stdout)
            # A theme that really uses the property must still fail.
            theme.write_text('title-text: "Yaran Linux"\n'
                             'terminal-color: "#E7F5EC"\n')
            result = self.run_with_definitions(
                block.replace('/usr/share/grub/themes/yaran/theme.txt',
                              str(theme)), tmp)
            self.assertIn('FAILCOUNT=1', result.stdout)
            self.assertIn('terminal-color', result.stderr)

    def test_theme_check_filters_comments_exactly_like_grub(self):
        hook = self.VERIFY.read_text()
        self.assertIn("grep -Ev '^[[:space:]]*#'", hook,
                      'GRUB ignores "#" comment lines; the check must too')

    # --- failure 2: Chrome postinst's own google-chrome.sources -------------

    # Byte-for-byte content that google-chrome-stable's postinst
    # (gen_sources_content, v155.0.8059.79-1) writes to
    # /etc/apt/sources.list.d/google-chrome.sources on a fresh install.
    CHROME_POSTINST_SOURCES = (
        '### THIS FILE IS AUTOMATICALLY CONFIGURED ###\n'
        '# Changes to this file will not be preserved.\n'
        '# This file will not be recreated if removed.\n'
        'X-Repolib-Name: Google Chrome\n'
        'Types: deb\n'
        'URIs: https://dl.google.com/linux/chrome-stable/deb/\n'
        'Suites: stable\n'
        'Components: main\n'
        'Architectures: amd64\n'
        'Signed-By: /usr/share/keyrings/google-chrome.gpg\n'
    )

    def consent_block(self):
        return self.extract_block(
            self.VERIFY.read_text(), 'consent=$(tr',
            lambda line: line.startswith("[ \"$fail\" -eq 0 ] && ok 'no vendor"))

    def prepare_apt_sandbox(self, tmp, consent):
        etc = Path(tmp) / 'etc'
        (etc / 'sources.list.d').mkdir(parents=True)
        (etc / 'sources.list').write_text(
            'deb http://deb.debian.org/debian trixie main\n'
            'deb http://deb.debian.org/debian trixie-backports main\n')
        # The hook's own file (as vendor-repos.sh writes it)...
        (etc / 'sources.list.d/yaran-google-chrome.list').write_text(
            'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.asc] '
            'https://dl.google.com/linux/chrome/deb/ stable main\n')
        # ...plus the file google-chrome-stable's postinst adds itself.
        (etc / 'sources.list.d/google-chrome.sources').write_text(
            self.CHROME_POSTINST_SOURCES)
        if consent is not None:
            (etc / 'yaran-vendor-repos').write_text(consent)
        return self.consent_block().replace('/etc/apt', f'{etc}')

    def test_chrome_postinst_sources_pass_when_the_origin_is_consented(self):
        """The Minimal manifest opts in with "vendor_repositories": true and
        vendor-repos.sh records the dl.google.com origin; the SECOND file
        that Chrome's own postinst writes for the SAME origin must then be
        accepted — the policy checks the origin, not the filename."""
        with tempfile.TemporaryDirectory() as tmp:
            block = self.prepare_apt_sandbox(tmp, 'dl.google.com\n')
            result = self.run_with_definitions(block, tmp)
            self.assertNotIn('PROBLEM', result.stdout + result.stderr,
                             result.stdout + result.stderr)
            self.assertIn('FAILCOUNT=0', result.stdout)

    def test_vendor_source_without_consent_still_fails_the_build(self):
        """Removing the opt-in must bring the failure back — the check may
        not be weakened by the false-positive fix."""
        with tempfile.TemporaryDirectory() as tmp:
            block = self.prepare_apt_sandbox(tmp, None)
            result = self.run_with_definitions(block, tmp)
            self.assertIn('FAILCOUNT=1', result.stdout)
            self.assertIn('dl.google.com', result.stderr)
            self.assertIn('has no vendor_repositories opt-in', result.stderr)

    def test_rogue_origin_without_consent_still_fails_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            block = self.prepare_apt_sandbox(tmp, 'dl.google.com\n')
            rogue = Path(tmp) / 'etc/sources.list.d/rogue.sources'
            rogue.write_text('Types: deb\nURIs: https://evil.example/repo\n'
                             'Suites: stable\nComponents: main\n')
            result = self.run_with_definitions(block, tmp)
            self.assertIn('FAILCOUNT=1', result.stdout)
            self.assertIn('evil.example', result.stderr)

    def test_vendor_hooks_record_origin_hosts_not_filenames(self):
        chrome = (ROOT / 'hooks/desktop/vendor-repos.sh').read_text()
        self.assertIn('echo "dl.google.com" >> "$ROOTFS/etc/apt/yaran-vendor-repos"',
                      chrome)
        vbox = (ROOT / 'hooks/desktop/vendor-repos-extended.sh').read_text()
        self.assertIn('echo "download.virtualbox.org" >> '
                      '"$ROOTFS/etc/apt/yaran-vendor-repos"', vbox)

    # --- failure 3: xz missing on the build host ---------------------------

    def test_nodejs_extraction_needs_no_external_xz_binary(self):
        hook = (ROOT / 'hooks/desktop/install-nodejs26.sh').read_text()
        # Comments may discuss the old `tar -xJf` failure mode; only real
        # code counts.
        code = '\n'.join(line for line in hook.splitlines()
                         if not line.lstrip().startswith('#'))
        self.assertNotIn('tar -xJf', code,
                         'tar -xJf shells out to the xz binary, absent in '
                         'the CI build container')
        self.assertIn('r:xz', hook, 'Python stdlib lzma must do the extraction')
        # The CI build environment still ships xz-utils for other tooling.
        ci = (ROOT / 'scripts/ci-build.sh').read_text()
        self.assertIn('xz-utils', ci)

    def test_nodejs_extraction_runs_without_xz_on_path(self):
        """Execute the hook's real extraction snippet with a PATH that has
        ONLY python3 — no xz anywhere — and prove the archive extracts."""
        hook = (ROOT / 'hooks/desktop/install-nodejs26.sh').read_text()
        snippet = self.extract_block(hook, 'python3 - "$work/$tarball"',
                                     lambda line: line == 'PY')
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            payload = tmp / 'payload.txt'
            payload.write_text('node fixture payload')
            import tarfile as _tarfile
            with _tarfile.open(tmp / 'fixture.tar.xz', 'w:xz') as archive:
                archive.add(payload, arcname='node-fixture-linux-x64/payload.txt')
            bin_dir = tmp / 'bin'
            bin_dir.mkdir()
            os.symlink(sys.executable, bin_dir / 'python3')
            rootfs = tmp / 'rootfs'
            (rootfs / 'usr/local/lib/nodejs').mkdir(parents=True)
            script = (f'work={tmp}\ntarball=fixture.tar.xz\n'
                      f'ROOTFS={rootfs}\n' + snippet + '\n')
            result = subprocess.run(
                ['/bin/bash', '-c', script], env={'PATH': str(bin_dir)},
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            extracted = (rootfs / 'usr/local/lib/nodejs'
                         / 'node-fixture-linux-x64/payload.txt')
            self.assertEqual(extracted.read_text(), 'node fixture payload')


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
