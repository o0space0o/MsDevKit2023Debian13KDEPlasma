#!/usr/bin/python3
"""Destructive tests ONLY inside fresh disposable file-backed loop disks.

Must run as root on native Linux. Refuses any supplied disk/path argument.
Uses temporary sparse files, validates each loop's exact backing file, and
never mounts or reads real Windows partitions or UEFI variables.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('policy', ROOT / 'overlay/usr/lib/devkit2023customlinux/install_policy.py')
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


def run(*args, input=None):
    result = subprocess.run(args, input=input, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed: {result.stdout}')
    return result.stdout


def test():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        raise SystemExit('Root required; no disk/path arguments accepted')
    with tempfile.TemporaryDirectory(prefix='devkit-install-fixture-', dir='/var/tmp') as name:
        directory = Path(name).resolve()
        disk = directory / 'synthetic-windows.raw'
        with disk.open('xb') as stream:
            stream.truncate(42 * 1024**3)
        loop = run('losetup', '--find', '--show', '--partscan', str(disk)).strip()
        try:
            backing = json.loads(run('losetup', '--json', '--output', 'NAME,BACK-FILE', loop))['loopdevices']
            assert len(backing) == 1 and Path(backing[0]['back-file']).resolve() == disk
            assert loop.startswith('/dev/loop') and disk.parent == directory
            table = ('label: gpt\n'
                     f'start=2048,size=532480,type={P.ESP},name="Fixture ESP"\n'
                     f'size=32768,type={P.MSR},name="Fixture MSR"\n'
                     f'size=2097152,type={P.WINDOWS},name="Fixture Windows"\n'
                     f'start=83886080,size=2097152,type={P.RECOVERY},name="Fixture Recovery",attrs="RequiredPartition"\n')
            run('sfdisk', loop, input=table)
            run('udevadm', 'settle')
            before = json.loads(run('sfdisk', '--json', loop))
            original = before['partitiontable']['partitions']
            # Place sentinels at both ends of EVERY original partition.
            with disk.open('r+b', buffering=0) as stream:
                for i, part in enumerate(original):
                    for offset in (part['start'] * 512, (part['start'] + part['size']) * 512 - 4096):
                        stream.seek(offset)
                        stream.write(bytes([i + 1]) * 4096)
            def sentinels():
                hashes = []
                with disk.open('rb', buffering=0) as stream:
                    for part in original:
                        # Full original-partition hashing (~2.3 GiB), not just endpoints.
                        stream.seek(part['start'] * 512)
                        remain = part['size'] * 512
                        digest = hashlib.sha256()
                        while remain:
                            chunk = stream.read(min(remain, 4 * 1024**2))
                            assert chunk
                            digest.update(chunk)
                            remain -= len(chunk)
                        hashes.append(digest.hexdigest())
                return hashes
            expected = sentinels()
            planned = P.plan(before)
            P.check_before(planned, json.loads(run('sfdisk', '--json', loop)))
            # Same append invocation as the production backend.
            run('sfdisk', '--append', '--lock=yes', '--wipe=never', '--wipe-partitions=never',
                loop, input=P.sfdisk_input(planned))
            run('udevadm', 'settle')
            written = json.loads(run('sfdisk', '--json', loop))
            try:
                P.check_after(planned, written)
            except ValueError:
                print('Expected new partition:', planned['root'])
                print('Written new partition:', written['partitiontable']['partitions'][-1])
                raise
            run('mkfs.ext4', '-q', '-L', 'DevKit2023Custom', planned['root']['node'])
            run('sync')
            assert sentinels() == expected, 'An original partition was modified'
            P.check_after(planned, json.loads(run('sfdisk', '--json', loop)))
            try:
                P.check_before(planned, json.loads(run('sfdisk', '--json', loop)))
            except ValueError:
                pass
            else:
                raise AssertionError('A used plan was accepted again')
            print('PASS: real GPT append + ext4 format on disposable loop disk; all original partition bytes and GPT fields unchanged; stale plan rejected')
        finally:
            run('losetup', '--detach', loop)


if __name__ == '__main__':
    test()
