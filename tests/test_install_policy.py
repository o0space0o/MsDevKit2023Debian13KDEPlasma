"""Synthetic GPT snapshots; these tests never open host block devices."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('policy', ROOT / 'overlay/usr/lib/devkit2023customlinux/install_policy.py')
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


def fixture(sector=512):
    mib = 1024**2 // sector
    parts = []
    for number, start, size, kind in ((1, 1, 260, P.ESP), (2, 261, 16, P.MSR),
                                    (3, 277, 20000, P.WINDOWS), (4, 80000, 1024, P.RECOVERY)):
        parts.append({'node': f'/dev/nvme0n1p{number}', 'start': start * mib, 'size': size * mib,
                      'type': kind, 'uuid': f'00000000-0000-4000-8000-{number:012d}', 'name': f'original {number}'})
    parts[-1]['attrs'] = 'RequiredPartition GUID:63'
    return {'partitiontable': {'label': 'gpt', 'id': '11111111-1111-4111-8111-111111111111',
                              'device': '/dev/nvme0n1', 'unit': 'sectors', 'firstlba': 34,
                              'lastlba': 82000 * mib - 34, 'sectorsize': sector, 'partitions': parts}}


class InstallPolicyTests(unittest.TestCase):
    def test_only_unallocated_space_used(self):
        raw = fixture()
        value = P.plan(raw)
        root = value['root']
        self.assertEqual(root['start'], 20277 * 2048)
        self.assertEqual(root['size'], (80000 - 20277) * 2048)
        self.assertEqual(root['node'], '/dev/nvme0n1p5')
        self.assertEqual(raw, fixture())
        self.assertIn('WITHOUT formatting', P.describe(value))

    def test_4kn_sector_layout(self):
        value = P.plan(fixture(4096))
        self.assertEqual(value['root']['start'], 20277 * 256)
        self.assertEqual(value['root']['size'] * 4096, P.plan(fixture())['root']['size'] * 512)

    def test_after_retains_every_original_field(self):
        raw = fixture()
        value = P.plan(raw)
        after = copy.deepcopy(raw)
        after['partitiontable']['partitions'].append(value['root'])
        P.check_after(value, after)
        for field, change in (('start', 999), ('size', 888), ('name', 'changed'), ('attrs', '')):
            changed = copy.deepcopy(after)
            changed['partitiontable']['partitions'][3][field] = change
            with self.assertRaises(ValueError):
                P.check_after(value, changed)

    def test_stale_snapshot_rejected(self):
        raw = fixture()
        value = P.plan(raw)
        raw['partitiontable']['partitions'][0]['name'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'changed since'):
            P.check_before(value, raw)

    def test_tampered_plan_cannot_target_windows(self):
        value = P.plan(fixture())
        value['root'] = copy.deepcopy(value['before']['partitions'][2])
        with self.assertRaises(ValueError):
            P.validate_plan(value)

    def test_no_linux_reinstall_or_unknown_partition_type(self):
        for kind in (P.LINUX, '00000000-0000-4000-8000-000000000099'):
            raw = fixture()
            raw['partitiontable']['partitions'][3]['type'] = kind
            with self.assertRaisesRegex(ValueError, 'unknown partition'):
                P.plan(raw)

    def test_no_free_space(self):
        raw = fixture()
        raw['partitiontable']['partitions'][2]['size'] = (80000 - 277) * 2048
        with self.assertRaisesRegex(ValueError, 'No unallocated'):
            P.plan(raw)

    def test_missing_or_duplicate_esp(self):
        for kind in (P.WINDOWS, P.ESP):
            raw = fixture()
            raw['partitiontable']['partitions'][1]['type'] = kind
            with self.assertRaisesRegex(ValueError, 'EFI/MSR'):
                P.plan(raw)

    def test_missing_windows(self):
        raw = fixture()
        raw['partitiontable']['partitions'][2]['type'] = P.RECOVERY
        with self.assertRaises(ValueError):
            P.plan(raw)

    def test_small_esp_rejected(self):
        raw = fixture()
        raw['partitiontable']['partitions'][0]['size'] = 32 * 2048
        with self.assertRaisesRegex(ValueError, 'smaller'):
            P.plan(raw)

    def test_non_gpt_or_unsupported_sector(self):
        for field, change in (('label', 'dos'), ('unit', 'bytes'), ('sectorsize', 8192)):
            raw = fixture()
            raw['partitiontable'][field] = change
            with self.assertRaises(ValueError):
                P.plan(raw)

    def test_invalid_geometry(self):
        for change in (-1, 0, True, '123', 100000000000):
            raw = fixture()
            raw['partitiontable']['partitions'][0]['size'] = change
            with self.assertRaises(ValueError):
                P.plan(raw)

    def test_overlaps_rejected(self):
        raw = fixture()
        raw['partitiontable']['partitions'][1]['start'] = 2 * 2048
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            P.plan(raw)

    def test_holes_in_partition_numbers_rejected(self):
        raw = fixture()
        raw['partitiontable']['partitions'][3]['node'] = '/dev/nvme0n1p9'
        with self.assertRaisesRegex(ValueError, 'numbering'):
            P.plan(raw)

    def test_partition_guid_collision_rejected(self):
        raw = fixture()
        with self.assertRaisesRegex(ValueError, 'Duplicate new'):
            P.plan(raw, raw['partitiontable']['partitions'][0]['uuid'])

    def test_input_cannot_inject_sfdisk_fields(self):
        value = P.plan(fixture())
        value['root']['name'] = 'Linux\nsize=0'
        with self.assertRaises(ValueError):
            P.sfdisk_input(value)

    def test_native_partition_and_bootloader_jobs_removed(self):
        settings = (ROOT / 'overlay/etc/calamares/settings.conf').read_text()
        self.assertNotIn('  - partition\n', settings)
        self.assertNotIn('  - bootloader\n', settings)
        self.assertNotIn('  - grubcfg\n', settings)
        self.assertLess(settings.index('  - mount\n'), settings.index('  - shellprocess@check-mount'))
        self.assertLess(settings.index('  - shellprocess@check-mount'), settings.index('  - unpackfs\n'))
        self.assertLess(settings.index('  - initramfs\n'), settings.index('  - shellprocess@finish'))

    def test_no_force_format_no_windows_mount_no_efi_fallback(self):
        source = (ROOT / 'overlay/usr/local/libexec/devkit2023customlinux-install-storage').read_text()
        self.assertIn("'--wipe=never', '--wipe-partitions=never'", source)
        self.assertIn("'--no-nvram'", source)
        self.assertIn("'--create-only'", source)
        self.assertNotIn("'--removable'", source)
        self.assertNotIn("'--force'", source)
        self.assertNotIn("'mkfs.vfat'", source)
        self.assertNotIn("'ntfsresize'", source)
        self.assertNotIn('allow-qemu', source)

    def test_grub_library_allows_optional_unset_variables(self):
        source = (ROOT / 'overlay/etc/grub.d/09_devkit2023customlinux').read_text()
        self.assertNotIn('set -eu', source)
        self.assertIn('set -e\n', source)
        self.assertIn('clk_ignore_unused pd_ignore_unused', source)


if __name__ == '__main__':
    unittest.main()
