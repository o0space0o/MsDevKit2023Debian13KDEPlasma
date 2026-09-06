"""Synthetic private-bundle validation; no real firmware, UUID or radio address."""
import hashlib
import json
from pathlib import Path
import runpy
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
API = runpy.run_path(str(ROOT / 'profiles/prepared/overlay/usr/local/libexec/devkit2023customlinux-prepared'))
RULES = runpy.run_path(str(ROOT / 'overlay/usr/local/libexec/devkit2023customlinux-validate-windows-driver'))['RULES']


class PreparedBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bundle = Path(self.tmp.name)
        self.address = ':'.join(['10','20','30','40','50','60'])
        self.data = {'format': 1, 'model': 'Windows Dev Kit 2023',
                     'binding': {'kind': 'smbios-uuid-sha256-v1', 'value': 'a' * 64},
                     'bluetooth': {'source': 'windows-device-address-cache', 'address': self.address}, 'files': {}}
        for firmware, rule in RULES.items():
            package = rule['inf'] + '_arm64_' + 'a' * 16
            for name in (firmware, rule['inf'], rule['catalog']):
                relative = 'packages/' + package + '/' + name
                path = self.bundle / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'synthetic-not-firmware')
                self.data['files'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save()

    def save(self):
        (self.bundle / 'manifest.json').write_text(json.dumps(self.data))

    def inspect(self):
        return API['inspect_bundle'](self.bundle, RULES)

    def test_valid_structure_is_not_signature_authentication(self):
        self.assertEqual(self.inspect(), self.data)

    def test_modified_firmware_rejected(self):
        path = self.bundle / next(iter(self.data['files']))
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.inspect()

    def test_extra_file_rejected(self):
        (self.bundle / 'extra').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.inspect()

    def test_missing_file_rejected(self):
        (self.bundle / next(iter(self.data['files']))).unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.inspect()

    def test_unknown_manifest_fields_rejected(self):
        self.data['raw_uuid'] = 'must-not-be-kept'
        self.save()
        with self.assertRaises(ValueError): self.inspect()

    def test_duplicate_manifest_fields_rejected(self):
        (self.bundle / 'manifest.json').write_text('{"format":1,"format":1}')
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.inspect()

    def test_symlink_rejected(self):
        path = self.bundle / next(iter(self.data['files']))
        path.unlink()
        try: path.symlink_to(self.bundle / 'manifest.json')
        except OSError: self.skipTest('symlinks unavailable')
        with self.assertRaisesRegex(ValueError, 'symbolic'): self.inspect()

    def test_binding_algorithm_cannot_change(self):
        self.data['binding']['kind'] = 'first-available-hardware-id'
        self.save()
        with self.assertRaisesRegex(ValueError, 'binding'): self.inspect()

    def test_uuid_token_case_is_canonical(self):
        value = '12345678-' + '9abc-def0-1234-56789abcdef0'
        self.assertEqual(API['target_token'](value), API['target_token'](value.upper()))
        expected = hashlib.sha256(('DevKit2023CustomLinux target v1\nsmbios-uuid\n' + value + '\n').encode()).hexdigest()
        self.assertEqual(API['target_token'](value), expected)

    def test_missing_uuid_has_no_fallback(self):
        for value in ('0' * 32, 'f' * 32, 'unknown'):
            with self.assertRaises(ValueError): API['target_token'](value)

    def test_address_rejects_random_or_multicast(self):
        for first in ('11', '12', '13'):
            with self.assertRaises(ValueError): API['address'](first + self.address[2:])

    def test_address_does_not_strip_invalid_characters(self):
        with self.assertRaises(ValueError): API['address']('radio=' + self.address)


if __name__ == '__main__': unittest.main()
