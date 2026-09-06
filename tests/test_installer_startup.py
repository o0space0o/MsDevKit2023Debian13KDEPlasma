"""Synthetic launcher control-flow tests; never call a real privileged tool."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import runpy
import signal

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'overlay/usr/local/bin/devkit2023customlinux-installer'
SMOKE = runpy.run_path(str(ROOT / 'scripts/verify-installer-startup.py'))


class InstallerStartupTests(unittest.TestCase):
    def test_smoke_requires_window_modules_and_non_early_exit(self):
        good = '\n'.join(SMOKE['READY'])
        SMOKE['check_log'](good, -signal.SIGTERM, True)
        for text, code, timeout in ((good, 0, False), (good, 1, False),
                                    ('Using Calamares settings', -signal.SIGTERM, True),
                                    (good + '\nERROR: FATAL', -signal.SIGTERM, True)):
            with self.assertRaises(ValueError):
                SMOKE['check_log'](text, code, timeout)

    def run_launcher(self, *, preflight=0, cancel=False, display=0, installer=0, summary=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = root / 'bin'
            commands.mkdir()
            (root / 'runtime').mkdir()
            (root / 'cmdline').write_text('boot=live')
            calls = root / 'calls'
            fake = ('#!/bin/sh\n'
                    'name="${0##*/}"\n'
                    'printf "%s %s\\n" "$name" "$*" >> "$CALLS"\n'
                    'case "$name" in\n'
                    'kdialog) case "$*" in *--warningcontinuecancel*) exit "$CANCEL";; esac;;\n'
                    'xhost) case "$1" in +*) exit "$DISPLAY_EXIT";; esac;;\n'
                    'pkexec) case "$1" in *install-preflight)\n'
                    ' printf "privileged-mask %s\\n" "$(umask)" >> "$CALLS"\n'
                    ' [ "$SUMMARY" = 1 ] && printf "Synthetic read-only proposed disk/size\\n"\n'
                    ' exit "$PREFLIGHT";;\n'
                    ' /usr/bin/calamares) echo "synthetic Calamares result"; exit "$INSTALLER";;\n'
                    ' *) exit 99;; esac;;\n'
                    'esac\nexit 0\n')
            for name in ('pkexec', 'xhost', 'kdialog'):
                path = commands / name
                path.write_text(fake)
                path.chmod(0o755)
            # Fixture substitution in this test only; shipped code has no bypass.
            source = LAUNCHER.read_text().replace('/proc/cmdline', str(root / 'cmdline'))
            source = source.replace('/run/user/$(id -u)', str(root / 'runtime'))
            source = source.replace('/run/devkit2023customlinux', str(root))
            env = {**os.environ, 'PATH': str(commands) + ':' + os.environ['PATH'],
                   'HOME': str(root), 'DISPLAY': ':fixture', 'CALLS': str(calls),
                   'CANCEL': str(int(cancel)), 'PREFLIGHT': str(preflight),
                   'DISPLAY_EXIT': str(display), 'INSTALLER': str(installer), 'SUMMARY': str(int(summary))}
            result = subprocess.run(['sh', '-c', source], env=env, capture_output=True, text=True)
            logfiles = list((root / '.local/state/devkit2023customlinux').glob('installer-*.log'))
            self.assertEqual(logfiles[0].stat().st_mode & 0o777, 0o600)
            return result, calls.read_text(), [p.read_text() for p in logfiles]

    def test_branding_uses_required_image_list_not_missing_or_scalar_qml(self):
        brand = ROOT / 'overlay/etc/calamares/branding/devkit2023customlinux/branding.desc'
        self.assertIn('slideshow: [ "devkit2023customlinux-logo.svg" ]', brand.read_text())
        self.assertTrue((brand.parent / 'devkit2023customlinux-logo.svg').is_file())

    def test_launches_exact_policy_executable_and_releases_display(self):
        result, calls, logs = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('pkexec /usr/bin/calamares -platform xcb', calls)
        self.assertRegex(calls, r'privileged-mask 0*22\b')
        self.assertIn('xhost -si:localuser:root', calls)
        self.assertNotIn('--yesno', calls)
        self.assertIn('Synthetic read-only proposed disk/size', calls)
        self.assertNotIn('Synthetic read-only proposed disk/size', logs[0])
        self.assertIn('synthetic Calamares result', logs[0])

    def test_calamare_failure_is_visible_not_hidden_by_cleanup(self):
        for status in (1, 126, 127, 134, 139):
            result, calls, logs = self.run_launcher(installer=status)
            self.assertEqual(result.returncode, 1)
            self.assertIn(f'exit {status}', calls)
            self.assertIn('--yesno', calls)
            self.assertIn('--textbox', calls)
            self.assertIn('xhost -si:localuser:root', calls)
            self.assertIn('synthetic Calamares result', logs[0])

    def test_warning_cancel_never_launches_or_grants_display_access(self):
        result, calls, _ = self.run_launcher(cancel=True)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('/usr/bin/calamares', calls)
        self.assertNotIn('xhost ', calls)

    def test_preflight_failure_never_launches(self):
        result, calls, _ = self.run_launcher(preflight=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn('--yesno', calls)
        self.assertNotIn('/usr/bin/calamares', calls)

    def test_display_failure_never_launches(self):
        result, calls, _ = self.run_launcher(display=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn('--yesno', calls)
        self.assertNotIn('/usr/bin/calamares', calls)

    def test_empty_summary_stops_before_window_and_offers_log(self):
        result, calls, logs = self.run_launcher(summary=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn('summary was empty', calls)
        self.assertIn('--textbox', calls)
        self.assertIn('Installer startup failure:', logs[0])
        self.assertNotIn('/usr/bin/calamares', calls)

    def test_summary_has_no_shared_file_dependency(self):
        self.assertNotIn('install-plan.txt', LAUNCHER.read_text())


if __name__ == '__main__':
    unittest.main()
