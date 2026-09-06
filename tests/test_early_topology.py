"""Synthetic early-audio packaging regression checks; no host drivers or firmware."""
import hashlib
from pathlib import Path
import re
import runpy
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
API = runpy.run_path(str(ROOT / 'scripts/verify-prepared-iso.py'))
RELATIVE = API['PREPARE']['TOPOLOGY']


class EarlyTopologyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root, self.init = self.folder / 'root', self.folder / 'init'
        self.payload = b'synthetic topology, not real firmware'
        self.source = self.root / RELATIVE
        self.early = self.init / 'main' / RELATIVE
        for path in (self.source, self.early):
            path.parent.mkdir(parents=True)
            path.write_bytes(self.payload)
        record = self.init / 'main/etc/devkit2023customlinux-prepared/firmware.sha256'
        record.parent.mkdir(parents=True)
        record.write_text(hashlib.sha256(self.payload).hexdigest() + '  /' + RELATIVE + '\n')
        self.record = record

    def test_matching_topology_and_integrity_record(self):
        API['verify_early_topology'](self.root, self.init)

    def test_missing_topology_reproduces_old_image_failure(self):
        self.early.unlink()
        with self.assertRaisesRegex(ValueError, 'absent'):
            API['verify_early_topology'](self.root, self.init)

    def test_stale_topology_rejected(self):
        self.early.write_bytes(b'stale')
        with self.assertRaisesRegex(ValueError, 'differs'):
            API['verify_early_topology'](self.root, self.init)

    def test_missing_hash_rejected(self):
        self.record.write_text('')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            API['verify_early_topology'](self.root, self.init)

    def test_hook_copies_resolved_symlink_before_firmware_early_exit(self):
        text = (ROOT / 'overlay/etc/initramfs-tools/hooks/devkit2023customlinux-firmware').read_text()
        function = re.search(r'copy_blackrock_topology\(\) \{\n.*?\n\}', text, re.S).group(0)
        self.assertLess(text.index('\ncopy_blackrock_topology\n'), text.index('payload_present=no'))
        target = self.folder / 'real-source'
        target.write_bytes(self.payload)
        link = self.folder / 'source-link'
        link.symlink_to(target)
        # Execute the exact production function, with only its input/destination variables replaced.
        script = 'set -eu\ntopology="$1"\nDESTDIR="$2"\n' + function + '\ncopy_blackrock_topology\n'
        destination = self.folder / 'destination'
        subprocess.run(['sh', '-c', script, 'fixture', str(link), str(destination)], check=True)
        copied = destination / str(link).lstrip('/')
        self.assertFalse(copied.is_symlink())
        self.assertEqual(copied.read_bytes(), self.payload)


if __name__ == '__main__': unittest.main()
