"""Synthetic portable diagnostics tests. Never query host devices or journals."""
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / 'overlay/etc/skel/Desktop'
API = runpy.run_path(str(ROOT / 'overlay/usr/local/libexec/devkit2023customlinux-diagnostics'))
API = API['main'].__globals__
PACK = runpy.run_path(str(ROOT / 'scripts/package-diagnostics.py'))


class LiveTesterTests(unittest.TestCase):
    def test_installer_error_collection_excludes_account_and_plan_details(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'session.log'
            log.write_text('username: synthetic-person\npassword: private-value\n'
                           'partition plan: private-disk-data\n'
                           'ERROR: FATAL in "/etc/calamares/branding/product/branding.desc"\n'
                           'key not found: slideshow\n'
                           'cat: /private/synthetic-person/plan: Permission denied\n'
                           'Installer startup failure: The installation summary was empty. No disk changes were started.\n')
            report = API['Collector']()
            API['installer_failures'](report, log)
            text = report.output()
            self.assertIn('key not found: slideshow', text)
            self.assertIn('Permission denied', text)
            self.assertIn('The installation summary was empty', text)
            for value in ('synthetic-person', 'private-value', 'private-disk-data'):
                self.assertNotIn(value, text)

    def test_archive_contains_only_generic_tester(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = PACK['package'](Path(directory) / 'new')
            self.assertEqual(archive.name, 'DevKit2023CustomLinux-Diagnostics-' + API['VERSION'] + '.zip')
            with zipfile.ZipFile(archive) as stream:
                names = stream.namelist()
                self.assertEqual(len(names), 3)
                self.assertTrue(all(name.startswith('DevKit2023CustomLinux-Diagnostics/') for name in names))
                self.assertTrue(any(name.endswith('/.support/devkit2023customlinux-diagnostics') for name in names))
            with self.assertRaises(ValueError):
                PACK['package'](archive.parent)

    def test_archive_cannot_be_created_inside_source(self):
        with self.assertRaises(ValueError):
            PACK['package'](ROOT / 'forbidden-artifact')

    def test_complete_cli_writes_redacted_report_beside_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / 'DevKit2023Diagnostics.desktop'
            with patch('sys.argv', ['tester', '--launcher', str(launcher)]), \
                    patch('subprocess.run', side_effect=AssertionError('No real process in synthetic CLI test')), \
                    patch.dict(API, {'collect_user': Mock(return_value='Alias: secret\n'),
                                     'elevated_snapshot': Mock(return_value='fixture system log\n')}):
                self.assertEqual(API['main'](), 0)
            reports = list(Path(directory).glob('*.txt'))
            self.assertEqual(len(reports), 1)
            text = reports[0].read_text()
            self.assertNotIn('secret', text)
            self.assertIn('fixture system log', text)
            self.assertTrue(text.endswith('END OF REPORT\n'))

    def test_common_identifiers_redacted(self):
        values = [':'.join(['12', '34', '56', '78', '90', 'ab']),
                  '-'.join(['12', '34', '56', '78', '90', 'ab']),
                  '12345678-' + '1234-5678-abcd-1234567890ab',
                  'enx' + '1234567890ab', '192.0.2.47', '2001:db8::47',
                  '/home/synthetic/Documents/file', 'a' * 64]
        for value in values:
            with self.subTest(value=value):
                self.assertNotIn(value, API['redact'](value))

    def test_friendly_names_and_hostnames_redacted(self):
        output = API['redact']('Name: synthetic-phone\nAlias: private alias\nHost Name: test-host\n'
                               'monitor_name private monitor\nhostname=my-host\n')
        for word in ('synthetic-phone', 'private alias', 'test-host', 'my-host', 'private monitor'):
            self.assertNotIn(word, output)

    def test_password_free_sudo_never_prompts(self):
        with patch('os.geteuid', return_value=1000), patch.object(Path, 'is_file', return_value=True), \
                patch('subprocess.run', return_value=Mock(returncode=0, stdout='fixture', stderr='')) as run:
            self.assertEqual(API['elevated_snapshot'](), 'fixture')
        self.assertEqual(run.call_args.args[0][:2], ['/usr/bin/sudo', '-n'])
        self.assertEqual(run.call_count, 1)

    def test_authorization_cancel_still_returns_partial_text(self):
        denied = Mock(returncode=1, stdout='', stderr='authorization required')
        cancelled = Mock(returncode=126, stdout='', stderr='cancelled')
        with patch('os.geteuid', return_value=1000), patch.object(Path, 'is_file', return_value=True), \
                patch('subprocess.run', side_effect=[denied, cancelled]) as run:
            self.assertIn('cancelled', API['elevated_snapshot']())
        self.assertEqual(run.call_args.args[0][0], '/usr/bin/pkexec')

    def test_useful_driver_evidence_preserved(self):
        value = 'qca/hpnv21g.bin error -2\nhci0: missing options: public-address\nDP2 Jack: off\n'
        self.assertEqual(API['redact'](value), value)

    def test_empty_fields_do_not_consume_following_lines(self):
        value = 'monitor_name\t\neld_valid\t1\nshort name \nmissing options:\n'
        output = API['redact'](value)
        self.assertIn('eld_valid\t1', output)
        self.assertIn('missing options:', output)

    def test_live_rootfs_path_and_board_longname(self):
        value = '/run/live/rootfs/filesystem.squashfs\nMicrosoftCorporation-WindowsDevKit2023-SYNTHETICTARGET123\n'
        output = API['redact'](value)
        self.assertIn('/run/live/rootfs/filesystem.squashfs', output)
        self.assertNotIn('SYNTHETICTARGET123', output)

    def test_mixer_eld_bytes_omitted_but_routes_preserved(self):
        text = ("numid=1,iface=PCM,name='ELD',device=2\n  : values=0x12,0x34\n"
                "numid=2,iface=MIXER,name='DP2 Jack'\n  : values=on\n")
        output = API['omit_eld_bytes'](text)
        self.assertNotIn('0x12', output)
        self.assertIn('DP2 Jack', output)
        self.assertIn('values=on', output)

    def test_no_overwrite_and_report_beside_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'Desktop with spaces'
            folder.mkdir()
            first = API['save_report'](folder, 'first')
            second = API['save_report'](folder, 'second')
            self.assertEqual(first.parent, folder)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(), 'first')
            self.assertEqual(second.read_text(), 'second')
            if os.name == 'posix':
                self.assertEqual(first.stat().st_mode & 0o777, 0o600)

    def test_nonwritable_or_missing_directory_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OSError):
                API['save_report'](Path(directory) / 'absent', 'report')

    def test_missing_command(self):
        report = API['Collector']()
        with patch('shutil.which', return_value=None), patch('subprocess.run') as run:
            report.command('fixture', 'synthetic-tool')
        run.assert_not_called()
        self.assertIn('NOT AVAILABLE', report.output())

    def test_command_timeout_is_reported(self):
        report = API['Collector']()
        with patch('shutil.which', return_value='/synthetic/tool'), patch('subprocess.run',
                side_effect=subprocess.TimeoutExpired('fixture', 1)):
            report.command('fixture', 'synthetic-tool')
        self.assertIn('TIMED OUT', report.output())

    def test_timeout_retains_filtered_redacted_partial_reply(self):
        report = API['Collector']()
        error = subprocess.TimeoutExpired('fixture', 1, output=b'Alias: private\nuseful evidence\n')
        with patch('shutil.which', return_value='/synthetic/tool'), patch('subprocess.run', side_effect=error):
            report.command('fixture', 'synthetic-tool')
        self.assertIn('useful evidence', report.output())
        self.assertNotIn('private', report.output())

    def test_command_exit_and_output_redacted(self):
        report = API['Collector']()
        with patch('shutil.which', return_value='/synthetic/tool'), patch('subprocess.run',
                return_value=Mock(returncode=1, stdout='Alias: private\n', stderr='error')) as run:
            report.command('fixture', 'synthetic-tool', 'read')
        self.assertEqual(run.call_args.args[0], ['/synthetic/tool', 'read'])
        self.assertNotIn('shell', run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs['input'], '')
        self.assertNotIn('stdin', run.call_args.kwargs)
        self.assertIn('Exit: 1', report.output())
        self.assertNotIn('private', report.output())

    def test_command_budget(self):
        report = API['Collector'](seconds=-1)
        with patch('subprocess.run') as run:
            report.command('fixture', 'uname', '-r')
        run.assert_not_called()
        self.assertIn('time budget exhausted', report.output())

    def test_query_inventory_is_read_only(self):
        collected = []
        def command(self, title, *args, **kwargs):
            collected.append(args)
        with patch.object(API['Collector'], 'command', command), patch.object(API['Collector'], 'read'), \
                patch.object(Path, 'glob', return_value=[]), patch.dict(API, {'device_state': Mock()}), \
                patch('os.geteuid', return_value=0):
            API['collect_user']()
            API['collect_privileged']()
        allowed = {'uname', 'lspci', 'lsusb', 'ip', 'lsblk', 'dpkg-query',
                   'systemctl', 'journalctl', 'pactl', 'wpctl', 'aplay', 'alsaucm',
                   'btmgmt', 'bluetoothctl', 'rfkill'}
        self.assertTrue(all(args[0] in allowed for args in collected))
        forbidden = {'power', 'on', 'off', 'public-addr', 'scan', 'pair', 'connect',
                     'unblock', 'block', 'restart', 'start', 'stop', 'set', 'sset',
                     'set-default-sink', 'set-sink-volume', 'modprobe', 'mount'}
        self.assertFalse(forbidden.intersection(arg for args in collected for arg in args))
        self.assertIn(('btmgmt', 'info'), collected)
        self.assertIn(('btmgmt', 'config'), collected)

    def test_launcher_resolves_local_and_uri_paths(self):
        text = PACK['portable_launcher']().decode()
        line = next(line[5:] for line in text.splitlines() if line.startswith('Exec='))
        argv = shlex.split(line)
        code = argv[argv.index('-c') + 1]
        self.assertEqual(argv[-1], '%k')
        self.assertEqual(argv[:3], ['python3', '-B', '-c'])
        for name in ('/tmp/Desktop with spaces/DevKit2023Diagnostics.desktop',
                     'file:///tmp/Desktop%20with%20spaces/DevKit2023Diagnostics.desktop'):
            with patch('sys.argv', ['bootstrap', name]), patch('runpy.run_path') as run:
                exec(code, {})
            self.assertEqual(run.call_args.args[0], '/tmp/Desktop with spaces/.support/devkit2023customlinux-diagnostics')

    def test_production_desktop_has_only_requested_launchers(self):
        self.assertEqual(sorted(p.name for p in DESKTOP.iterdir()),
                         ['DevKit2023Diagnostics.desktop', 'InstallDevKit2023CustomLinux.desktop', 'InstallGoogleChrome.desktop'])
        for launcher in DESKTOP.iterdir():
            self.assertTrue(launcher.read_bytes().startswith(b'#!'))

    def test_gui_cancel_creates_no_report(self):
        ui = Mock()
        ui.begin.return_value = False
        with patch('sys.argv', ['diagnostics', '--gui']), patch.object(Path, 'is_file', return_value=True), \
                patch.dict(API, {'DesktopUI': Mock(return_value=ui), 'save_report': Mock()}):
            self.assertEqual(API['main'](), 0)
            API['save_report'].assert_not_called()

    def test_report_folder_local_uri_and_network_rejection(self):
        self.assertEqual(API['report_folder']('file:///tmp/Desktop%20space/launcher.desktop'), Path('/tmp/Desktop space'))
        with self.assertRaises(ValueError): API['report_folder']('https://example.invalid/launcher.desktop')

    def test_gui_finish_uses_native_report_viewer(self):
        ui = API['DesktopUI']()
        with patch.object(ui, 'dialog', return_value=Mock(returncode=0)) as dialog:
            ui.finished(Path('/synthetic/report.txt'), False)
        self.assertEqual(dialog.call_args.args[:2], ('--textbox', '/synthetic/report.txt'))


if __name__ == '__main__':
    unittest.main()
