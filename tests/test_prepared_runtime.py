"""Read-only synthetic target and Bluetooth checks; never use host radio/disks."""
from pathlib import Path
import json
import runpy
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'profiles/prepared/overlay'
API = runpy.run_path(str(PROFILE / 'usr/local/libexec/devkit2023customlinux-prepared'))
with patch('runpy.run_path', return_value=API):
    # Execute the Bluetooth source without looking up installed target helpers.
    RADIO = {'__name__': 'prepared_radio_test'}
    exec(compile((PROFILE / 'usr/local/libexec/devkit2023customlinux-bluetooth-address').read_text(), 'prepared-radio', 'exec'), RADIO)


class PreparedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.identity = '12345678-' + '9abc-def0-1234-56789abcdef0'
        self.data = {'binding': {'value': API['target_token'](self.identity)}}
        self.address = ':'.join(['10', '20', '30', '40', '50', '60'])

    def test_matching_target(self):
        with patch.object(Path, 'read_bytes', return_value=b'microsoft,blackrock\0qcom,sc8280xp\0'), patch.object(Path, 'read_text', return_value=self.identity.upper()):
            API['require_target'](self.data)

    def test_wrong_target(self):
        with patch.object(Path, 'read_bytes', return_value=b'microsoft,blackrock\0'), patch.object(Path, 'read_text', return_value='87654321-' + self.identity[9:]):
            with self.assertRaisesRegex(ValueError, 'different target'):
                API['require_target'](self.data)

    def test_wrong_board(self):
        with patch.object(Path, 'read_bytes', return_value=b'linux,dummy-virt\0'):
            with self.assertRaisesRegex(ValueError, 'requires Windows Dev Kit'):
                API['require_target'](self.data)

    def test_missing_dmi_does_not_fallback(self):
        with patch.object(Path, 'read_bytes', return_value=b'microsoft,blackrock\0'), patch.object(Path, 'read_text', side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError): API['require_target'](self.data)

    def info(self, actual=None, index='0'):
        return ('hci' + index + ':\tPrimary controller\n\taddr ' + (actual or self.address) +
                ' version 12 manufacturer 29 class 0x000000\n'
                '\tsupported settings: powered configuration\n\tcurrent settings: bondable\n'
                '\tname synthetic\n\tshort name \n' + 'hci' + index + ':\tConfiguration options\n'
                '\tsupported options: public-address\n\tmissing options: \n')

    def configured(self, output, config='Unconfigured index list with 0 items\n'):
        with patch.dict(RADIO, {'command': Mock(side_effect=[config, output])}), \
                patch.object(Path, 'read_text', side_effect=AssertionError('HCI has no address file')):
            return RADIO['configured'](Path('/synthetic/hci0'), self.address)

    def test_empty_options_with_following_line(self):
        self.assertTrue(self.configured(self.info() + 'other detail\n'))

    def test_crlf_options(self):
        self.assertTrue(self.configured(self.info().replace('\n', '\r\n')))

    def test_missing_public_address(self):
        config = ('Unconfigured index list with 1 item\nhci0:\tUnconfigured controller\n'
                  '\tmanufacturer 29\n\tsupported options: public-address\n'
                  '\tmissing options: public-address\n')
        self.assertFalse(self.configured('', config))

    def test_ambiguous_options(self):
        with self.assertRaises(ValueError):
            self.configured(self.info() + 'missing options:\n')

    def test_configured_other_address_is_not_replaced(self):
        with self.assertRaises(RADIO['ControllerMismatch']):
            self.configured(self.info('20' + self.address[2:]))

    def test_wrong_or_multiple_indices_rejected(self):
        for value in (self.info(index='1'), self.info() + self.info()):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.configured(value)

    def test_incomplete_read_or_missing_followup_rejected(self):
        for value in ('Reading hci0 info failed with status 0x11', 'Too small info reply',
                      self.info().split('hci0:\tConfiguration options')[0],
                      self.info().replace('version 12', 'version unknown')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.configured(value)

    def test_config_list_error_cannot_trigger_address_write(self):
        for value in ('', 'Unconfigured index list with 1 item\n',
                      'Unconfigured index list with 0 items\nUnconfigured index list with 0 items\n'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.configured(self.info(), value)

    def test_other_unconfigured_radio_not_selected(self):
        config = ('Unconfigured index list with 1 item\nhci5:\tUnconfigured controller\n'
                  '\tsupported options: public-address\n\tmissing options: public-address\n')
        self.assertTrue(self.configured(self.info(), config))

    def test_exit_zero_error_is_rejected(self):
        with patch('subprocess.run', return_value=Mock(returncode=0, stdout='Too small info reply (4 bytes)', stderr='')):
            with self.assertRaises(ValueError): RADIO['command']('btmgmt', 'info')

    def test_management_command_has_pollable_stdin(self):
        with patch('subprocess.run', return_value=Mock(returncode=0,
                stdout='Unconfigured index list with 0 items\n', stderr='')) as run:
            RADIO['command']('btmgmt', 'config')
        self.assertEqual(run.call_args.kwargs['input'], '')
        self.assertNotIn('stdin', run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs['timeout'], 8)

    def test_no_power_command_on_unconfigured_controller(self):
        source = (PROFILE / 'usr/local/libexec/devkit2023customlinux-bluetooth-address').read_text()
        self.assertNotIn("'power', 'off'", source)
        self.assertNotIn("path / 'address'", source)

    def provision(self, statuses, target_error=False):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state / 'prepared-bundle').mkdir()
            (state / 'prepared-bundle/manifest.json').write_text(json.dumps({
                'binding': {'value': 'synthetic'}, 'bluetooth': {'address': self.address}}))
            command, write = Mock(), Mock()
            require = Mock(side_effect=ValueError('wrong target') if target_error else None)
            controller = Mock(side_effect=[Path('/synthetic/hci0'), Path('/synthetic/hci2')])
            api = {**API, 'require_target': require, 'write_file': write}
            with patch.dict(RADIO, {'STATE': state, 'READY': state / 'ready', 'API': api,
                    'command': command, 'builtin_controller': controller,
                    'configured': Mock(side_effect=statuses), 'unblock_controller': Mock()}), \
                    patch('os.geteuid', return_value=0), patch('sys.argv', ['helper']), \
                    patch.object(Path, 'is_file', return_value=True), patch('time.sleep'):
                if target_error:
                    with self.assertRaisesRegex(ValueError, 'wrong target'): RADIO['main']()
                else:
                    RADIO['main']()
            return command, write, controller

    def test_provision_rediscovers_changed_controller_index(self):
        command, write, controller = self.provision([False, True])
        command.assert_called_once_with('btmgmt', '--index', '0', 'public-addr', self.address)
        self.assertEqual(controller.call_count, 2)
        self.assertIn(b'controller=hci2\n', write.call_args.args[1])

    def test_matching_configured_controller_never_reprogrammed(self):
        command, write, controller = self.provision([True])
        command.assert_not_called()
        self.assertEqual(controller.call_count, 1)

    def test_wrong_target_cannot_touch_controller(self):
        command, write, controller = self.provision([], target_error=True)
        command.assert_not_called()
        write.assert_not_called()
        controller.assert_not_called()

    def test_rfkill_scoped_to_builtin(self):
        command = Mock()
        with patch.dict(RADIO, {'command': command}), patch.object(Path, 'glob', return_value=iter([Path('/synthetic/hci0/rfkill7')])):
            RADIO['unblock_controller'](Path('/synthetic/hci0'))
        command.assert_called_once_with('rfkill', 'unblock', '7')

    def test_ambiguous_rfkill_rejected(self):
        with patch.object(Path, 'glob', return_value=iter([])):
            with self.assertRaises(ValueError): RADIO['unblock_controller'](Path('/synthetic/hci0'))

    def test_installer_preflight_delegates_only_read_only_capture(self):
        text = (PROFILE / 'usr/local/libexec/devkit2023customlinux-install-preflight').read_text()
        self.assertTrue(text.rstrip().endswith('devkit2023customlinux-install-storage capture'))
        for forbidden in ('calamares-install-debian', 'mkfs', 'sfdisk', 'parted', 'windows-firmware.service', ' apply'):
            self.assertNotIn(forbidden, text)


if __name__ == '__main__': unittest.main()
