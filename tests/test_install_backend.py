"""Installer failure paths with synthetic devices/EFI variables only."""
import base64
import copy
import json
import contextlib
import io
import os
import stat
import subprocess
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_install_policy import P, ROOT, fixture

with patch.dict(sys.modules, {'install_policy': P}):
    API = runpy.run_path(str(ROOT / 'overlay/usr/local/libexec/devkit2023customlinux-install-storage'))


class BackendTests(unittest.TestCase):
    def test_capture_returns_summary_over_pipe_with_private_record(self):
        """Exercise both capture branches with the launcher's restrictive umask."""
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as name:
                folder = Path(name)
                folder.chmod(0o755)
                record_file = folder / 'install-plan.json'
                planned = P.plan(fixture())
                record = {'plan': planned, 'phase': 'planned', 'efi_files': {}, 'boot_variables': {}}
                namespace = API['capture'].__globals__
                output = io.StringIO()
                original_read = Path.read_text
                def read(path, *args, **kwargs):
                    if path == Path('/proc/sys/kernel/random/boot_id'):
                        return 'synthetic-session'
                    return original_read(path, *args, **kwargs)
                with patch.dict(namespace, {'STATE': folder, 'RECORD': record_file,
                        'hardware': lambda: 'synthetic-binding', 'load': lambda: record,
                        'current': lambda r: '/dev/nvme0n1', 'snapshot': lambda d: fixture(),
                        'disk_identity': lambda d: {}, 'idle_disk': Mock(),
                        'efi_inventory': lambda e: {}, 'boot_variables': lambda: {},
                        'command': Mock(side_effect=AssertionError('No external device operations'))}), \
                        patch.object(Path, 'glob', return_value=[Path('nvme0n1')]), \
                        patch.object(Path, 'read_text', read):
                    if existing:
                        API['save'](record)
                    previous = os.umask(0o077)
                    try:
                        with contextlib.redirect_stdout(output):
                            API['capture']()
                    finally:
                        os.umask(previous)
                self.assertEqual(output.getvalue(), P.describe(planned) + '\n')
                self.assertEqual(stat.S_IMODE(record_file.stat().st_mode), 0o600)
                summary_file = folder / 'install-plan.txt'
                self.assertEqual(summary_file.read_text(), output.getvalue())
                self.assertEqual(stat.S_IMODE(summary_file.stat().st_mode), 0o600)
                if os.geteuid() == 0:
                    # Real privilege boundary: the desktop receives the pipe but
                    # still cannot open the authoritative root transaction.
                    code = ('import sys; from pathlib import Path\n'
                            'text = sys.stdin.read()\n'
                            'assert "WITHOUT formatting" in text\n'
                            'try: Path(sys.argv[1]).read_text()\n'
                            'except PermissionError: print("summary received; JSON remains private")\n'
                            'else: raise AssertionError("private plan readable")\n')
                    child = subprocess.run([sys.executable, '-B', '-c', code, str(record_file)],
                                           input=output.getvalue(), capture_output=True, text=True,
                                           user=65534, group=65534, extra_groups=[], cwd='/')
                    self.assertEqual(child.returncode, 0, child.stderr)
                    self.assertIn('JSON remains private', child.stdout)

    def test_private_summary_is_compatible_with_calamares_description(self):
        module_path = ROOT / 'overlay/usr/lib/calamares/modules/devkitpartition/main.py'
        with tempfile.TemporaryDirectory() as name, patch.dict(sys.modules, {'libcalamares': Mock()}):
            folder = Path(name)
            with patch.dict(API['present_plan'].__globals__, {'STATE': folder}), contextlib.redirect_stdout(io.StringIO()):
                API['present_plan'](P.plan(fixture()))
            module = runpy.run_path(str(module_path))
            with patch.dict(module['pretty_description'].__globals__, {'Path': lambda p: folder / 'install-plan.txt'}):
                self.assertIn('WITHOUT formatting', module['pretty_description']())

    def call_apply(self, phase='planned', stale=False, write_failure=False, corrupt_after=False):
        planned = P.plan(fixture())
        record = {'plan': planned, 'phase': phase, 'efi_files': {}, 'boot_variables': {}}
        before = fixture()
        after = fixture()
        after['partitiontable']['partitions'].append(planned['root'])
        if stale:
            before['partitiontable']['partitions'][2]['name'] = 'Changed'
        if corrupt_after:
            after['partitiontable']['partitions'][2]['size'] -= 1
        writes = []
        def command(*args, **kwargs):
            writes.append(args)
            if args[0] == 'sfdisk' and write_failure:
                raise ValueError('fixture write failed')
            if args[:4] == ('blkid', '-s', 'UUID', '-o'):
                return '01234567-89ab-4def-8123-456789abcdef' if args[-1] == planned['root']['node'] else '1234-ABCD'
            return ''
        namespace = API['apply'].__globals__
        with patch.dict(namespace, {'load': lambda: record, 'current': lambda r: '/dev/nvme0n1',
                'snapshot': Mock(side_effect=[before, before, after]), 'efi_inventory': lambda e: {},
                'boot_variables': lambda: {}, 'idle_disk': Mock(), 'save': Mock(),
                'verify_partition_node': Mock(), 'command': command}):
            if phase != 'planned' or stale or write_failure or corrupt_after:
                with self.assertRaises(ValueError):
                    API['apply']()
            else:
                API['apply']()
        return writes, record

    def test_happy_path_formats_only_new_node(self):
        writes, record = self.call_apply()
        formats = [cmd for cmd in writes if cmd[0].startswith('mkfs')]
        self.assertEqual(len(formats), 1)
        self.assertEqual(formats[0][-1], '/dev/nvme0n1p5')
        self.assertEqual(record['phase'], 'formatted')

    def test_no_second_format(self):
        for phase in ('formatted', 'partition-write-started', 'complete'):
            writes, _ = self.call_apply(phase=phase)
            self.assertEqual(writes, [])

    def test_stale_plan_cannot_start_writes(self):
        writes, _ = self.call_apply(stale=True)
        self.assertEqual(writes, [])

    def test_partition_write_failure_never_formats(self):
        writes, record = self.call_apply(write_failure=True)
        self.assertFalse(any(cmd[0].startswith('mkfs') for cmd in writes))
        self.assertEqual(record['phase'], 'partition-write-started')

    def test_unexpected_table_after_write_never_formats(self):
        writes, _ = self.call_apply(corrupt_after=True)
        self.assertFalse(any(cmd[0].startswith('mkfs') for cmd in writes))

    def boot_fixture(self, failure=None):
        suffix = '-8be4df61-93ca-11d2-aa0d-00e098032b8c'
        attributes = b'\x07\0\0\0'
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            originals = {'Boot0000' + suffix: attributes + b'Synthetic Windows entry',
                         'Boot000A' + suffix: attributes + b'Synthetic recovery entry',
                         'BootOrder' + suffix: attributes + b'\0\0\x0a\0'}
            for key, value in originals.items():
                (folder / key).write_bytes(value)
            record = {'plan': P.plan(fixture()), 'identity': {'device': '/dev/nvme0n1'},
                      'boot_variables': {key: base64.b64encode(value).decode() for key, value in originals.items()}}
            calls = []
            def command(*args):
                calls.append(args)
                if args == ('efibootmgr', '-v'):
                    return 'Windows Boot Manager'
                if '--create-only' in args:
                    (folder / ('Boot000B' + suffix)).write_bytes(attributes + b'Synthetic Linux entry')
                    if failure == 'modified-original':
                        (folder / ('Boot0000' + suffix)).write_bytes(b'changed')
                    if failure == 'extra-entry':
                        (folder / ('Boot000C' + suffix)).write_bytes(b'extra')
                if '--bootorder' in args and failure != 'order-not-written':
                    order = b''.join(int(item, 16).to_bytes(2, 'little') for item in args[-1].split(','))
                    (folder / ('BootOrder' + suffix)).write_bytes(attributes + order)
                return ''
            namespace = API['register_boot_entry'].__globals__
            with patch.dict(namespace, {'EFI_VARS': folder, 'command': command}):
                if failure:
                    with self.assertRaises(ValueError):
                        API['register_boot_entry'](record)
                else:
                    API['register_boot_entry'](record)
                    for key, value in originals.items():
                        if not key.startswith('BootOrder'):
                            self.assertEqual((folder / key).read_bytes(), value)
                    self.assertEqual((folder / ('BootOrder' + suffix)).read_bytes()[4:], b'\x0b\0\0\0\x0a\0')
            return calls

    def test_boot_add_keeps_windows_recovery_entries_and_order(self):
        calls = self.boot_fixture()
        self.assertFalse(any('--delete-bootnum' in args or '--delete-bootorder' in args for args in calls))
        self.assertTrue(any('--create-only' in args for args in calls))

    def test_original_boot_change_stops_before_order_change(self):
        calls = self.boot_fixture('modified-original')
        self.assertFalse(any('--bootorder' in args for args in calls))

    def test_ambiguous_new_entry_stops_before_order_change(self):
        calls = self.boot_fixture('extra-entry')
        self.assertFalse(any('--bootorder' in args for args in calls))

    def test_ignored_boot_order_write_is_reported(self):
        self.boot_fixture('order-not-written')

    def test_source_retains_target_and_firmware_guards(self):
        source = (ROOT / 'overlay/usr/local/libexec/devkit2023customlinux-install-storage').read_text()
        for guard in ("api['verify']", "api['require_target']", "'--check-ready'", "'efi=noruntime'",
                      "policy.check_after", "verify_partition_node", "'--is-arm64-efi'"):
            self.assertIn(guard, source)


if __name__ == '__main__':
    unittest.main()
