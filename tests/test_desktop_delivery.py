"""Current desktop delivery and fail-closed base compatibility, synthetic only."""
from pathlib import Path
import os
import runpy
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
API = runpy.run_path(str(ROOT / 'scripts/prepare-iso.py'))
BASE = runpy.run_path(str(ROOT / 'scripts/verify-base.py'))


class DesktopDeliveryTests(unittest.TestCase):
    def test_empty_base_logs_accepted(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            (target / 'var/log').mkdir(parents=True)
            (target / 'var/log/dpkg.log').touch()
            BASE['verify_logs'](target)

    def test_nonempty_build_log_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            (target / 'var/log').mkdir(parents=True)
            (target / 'var/log/dpkg.log').write_text('synthetic build log\n')
            with self.assertRaisesRegex(ValueError, 'Build logs remain'):
                BASE['verify_logs'](target)

    def test_packaged_log_documentation_link_accepted(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            (target / 'var/log').mkdir(parents=True)
            document = target / 'usr/share/doc/systemd/README.logs'
            document.parent.mkdir(parents=True)
            document.write_text('Packaged documentation, not build output.\n')
            (target / 'var/log/README').symlink_to('../../usr/share/doc/systemd/README.logs')
            BASE['verify_logs'](target)

    def test_arbitrary_log_link_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            (target / 'var/log').mkdir(parents=True)
            (target / 'var/log/README').symlink_to('/unrelated-host-path')
            with self.assertRaisesRegex(ValueError, 'Unexpected link'):
                BASE['verify_logs'](target)

    def test_fresh_build_installs_sound_test_backend(self):
        self.assertIn('libcanberra-pulse', (ROOT / 'scripts/build-rootfs.sh').read_text())

    def test_fresh_build_includes_file_search(self):
        self.assertIn('dolphin kio-extras', (ROOT / 'scripts/build-rootfs.sh').read_text())

    def test_missing_file_search_rejects_base(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            sound = target / API['CANBERRA_BACKEND']
            sound.parent.mkdir(parents=True)
            sound.write_bytes(b'synthetic backend')
            with self.assertRaisesRegex(ValueError, 'file-search backend'):
                API['require_current_base'](target)

    def test_missing_backend_rejects_old_base(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaisesRegex(ValueError, 'sound-test backend'):
                API['require_current_base'](Path(name))

    def test_current_overlay_required_and_drift_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            for source in (ROOT / 'overlay', ROOT / 'profiles/prepared/overlay'):
                shutil.copytree(source, target, dirs_exist_ok=True)
            backend = target / API['CANBERRA_BACKEND']
            backend.parent.mkdir(parents=True, exist_ok=True)
            backend.write_bytes(b'synthetic backend')
            search = target / API['FILESEARCH_BACKEND']
            search.parent.mkdir(parents=True, exist_ok=True)
            search.write_bytes(b'synthetic backend')
            API['require_current_base'](target)
            (target / 'usr/local/libexec/devkit2023customlinux-bluetooth-address').write_text('stale')
            with self.assertRaisesRegex(ValueError, 'source overlay differs'):
                API['require_current_base'](target)

    def test_chrome_uses_scoped_primary_key_and_arm64(self):
        source = (ROOT / 'overlay/usr/local/libexec/devkit2023customlinux-install-chrome').read_text()
        self.assertIn('google-chrome-stable:arm64', source)
        self.assertIn('signed-by=/etc/apt/keyrings/google-chrome.asc', source)
        self.assertIn('--export "$expected_fingerprint"', source)
        self.assertIn('--proto-redir', source)
        self.assertNotIn('apt-key', source)

    def test_live_chrome_consent_discloses_temporary_install(self):
        source = (ROOT / 'overlay/usr/local/bin/devkit2023customlinux-install-chrome').read_text()
        self.assertIn('--warningyesno', source)
        self.assertIn('disappears when you restart', source)
        self.assertIn('https://www.google.com/chrome/terms/', source)

    def test_installer_does_not_autostart(self):
        self.assertFalse((ROOT / 'overlay/etc/xdg/autostart/devkit2023customlinux-installer.desktop').exists())

    def test_public_and_prepared_use_same_runtime(self):
        source = (ROOT / 'scripts/build-rootfs.sh').read_text()
        self.assertIn('"$PROJECT_ROOT/profiles/prepared/overlay/"', source)
        self.assertNotIn('devkit2023customlinux-windows-firmware.service', source)
        self.assertFalse((ROOT / 'overlay/usr/local/libexec/devkit2023customlinux-bluetooth-address').exists())

    def hook_fixture(self, records):
        hook = ROOT / 'profiles/prepared/overlay/etc/initramfs-tools/hooks/devkit2023customlinux-prepared'
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            config = folder / 'input'
            config.mkdir()
            for record in records:
                (config / record).write_text('synthetic\n')
            helpers = folder / 'functions'
            helpers.write_text('copy_exec() { :; }\n')
            script = hook.read_text().replace('. /usr/share/initramfs-tools/hook-functions', '. "$1"')
            script = script.replace('/etc/devkit2023customlinux-prepared', str(config))
            env = {**os.environ, 'DESTDIR': str(folder / 'output')}
            result = subprocess.run(['sh', '-c', script, 'hook-test', str(helpers)], env=env, capture_output=True)
            copied = sorted(path.name for path in (folder / 'output').rglob('*') if path.is_file())
            return result.returncode, copied

    def test_unprepared_base_hook_does_not_require_private_records(self):
        self.assertEqual(self.hook_fixture([]), (0, []))

    def test_half_prepared_base_is_not_accepted(self):
        for record in ('target-binding', 'firmware.sha256'):
            self.assertNotEqual(self.hook_fixture([record])[0], 0)

    def test_prepared_hook_copies_both_records(self):
        self.assertEqual(self.hook_fixture(['target-binding', 'firmware.sha256']),
                         (0, ['firmware.sha256', 'target-binding']))


if __name__ == '__main__':
    unittest.main()
