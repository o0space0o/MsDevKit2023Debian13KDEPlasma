#!/usr/bin/python3
"""Exercise installed fstab/initramfs/GRUB on a disposable loop disk.

Argument: a trusted target-free built rootfs (read-only input). All test target
records/firmware are synthetic. No hardware authentication is claimed. EFI
variable writes are mocked; real GRUB installation uses --no-nvram. Real host
Windows partitions and boot entries are never read or written.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('install_policy', PROJECT / 'overlay/usr/lib/devkit2023customlinux/install_policy.py')
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def run(*args):
    result = subprocess.run([str(a) for a in args], text=True, capture_output=True, timeout=600)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed: {result.stdout}\n{result.stderr}')
    return result.stdout


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit('Root required; supply a trusted target-free rootfs directory, never a disk')
    source = Path(sys.argv[1]).resolve()
    if not (source / 'etc/devkit2023customlinux-release').is_file() or (source / 'var/lib/devkit2023customlinux/prepared-bundle').exists():
        raise SystemExit('Expected a public target-free rootfs input')
    with tempfile.TemporaryDirectory(prefix='devkit-chroot-fixture-', dir='/var/tmp') as directory, tempfile.TemporaryDirectory(prefix='calamares-root-') as mountname:
        work, target = Path(directory), Path(mountname)
        disk = work / 'synthetic.raw'
        with disk.open('xb') as stream:
            stream.truncate(42 * 1024**3)
        loop = run('losetup', '--find', '--show', '--partscan', disk).strip()
        mounts = []
        try:
            def ensure_backing():
                device = json.loads(run('losetup', '--json', '--output', 'BACK-FILE', loop))['loopdevices']
                assert len(device) == 1 and Path(device[0]['back-file']).resolve() == disk
                assert loop.startswith('/dev/loop') and disk.parent == work
                return loop
            ensure_backing()
            table = ('label: gpt\n'
                     f'start=2048,size=532480,type={POLICY.ESP}\n'
                     f'size=32768,type={POLICY.MSR}\n'
                     f'size=65536,type={POLICY.WINDOWS}\n')
            subprocess.run(['sfdisk', loop], input=table, text=True, check=True, stdout=subprocess.DEVNULL)
            run('udevadm', 'settle')
            before = json.loads(run('sfdisk', '--json', loop))
            planned = POLICY.plan(before)
            subprocess.run(['sfdisk', '--append', '--lock=yes', '--wipe=never', '--wipe-partitions=never', loop],
                           input=POLICY.sfdisk_input(planned), text=True, check=True, stdout=subprocess.DEVNULL)
            run('udevadm', 'settle')
            POLICY.check_after(planned, json.loads(run('sfdisk', '--json', loop)))
            rootnode, efinode = planned['root']['node'], planned['efi']['node']
            run('mkfs.ext4', '-q', rootnode)
            # Only this fixture creates an ESP; production NEVER formats an ESP.
            run('mkfs.vfat', '-F', '32', efinode)
            run('mount', rootnode, target)
            mounts.append(target)
            run('rsync', '-aHAX', '--numeric-ids', str(source) + '/', str(target) + '/')
            (target / 'boot/efi').mkdir(parents=True, exist_ok=True)
            run('mount', efinode, target / 'boot/efi')
            mounts.append(target / 'boot/efi')
            for relative, args in (('dev', ('--rbind', '/dev')), ('proc', ('-t', 'proc', 'proc')),
                                   ('sys', ('-t', 'sysfs', '-o', 'ro', 'sysfs')), ('run', ('-t', 'tmpfs', 'tmpfs'))):
                run('mount', *args, target / relative)
                if relative == 'dev':
                    run('mount', '--make-rslave', target / relative)
                mounts.append(target / relative)
            # There is intentionally NO efivarfs mount inside the target.
            assert not (target / 'sys/firmware/efi/efivars/BootOrder-8be4df61-93ca-11d2-aa0d-00e098032b8c').exists()
            efi = target / 'boot/efi'
            (efi / 'EFI/Microsoft/Boot').mkdir(parents=True)
            (efi / 'EFI/BOOT').mkdir(parents=True)
            (efi / 'EFI/Microsoft/Boot/bootmgfw.efi').write_bytes(b'SYNTHETIC WINDOWS SENTINEL; NOT BOOTABLE')
            (efi / 'EFI/BOOT/BOOTAA64.EFI').write_bytes(b'SYNTHETIC FALLBACK SENTINEL')
            live_records = work / 'live-records'
            live_records.mkdir()
            records = target / 'etc/devkit2023customlinux-prepared'
            records.mkdir()
            (records / 'target-binding').write_text('synthetic test binding\n')
            firmware = target / 'usr/lib/firmware/qcom/sc8280xp/microsoft/blackrock'
            hashes = []
            provenance = []
            validator = runpy.run_path(str(PROJECT / 'overlay/usr/local/libexec/devkit2023customlinux-validate-windows-driver'))
            for name, rule in validator['RULES'].items():
                payload = bytearray(rule['minimum'])
                payload[:4] = b'\x7fELF'
                payload[18:20] = b'\xa4\0'
                marker = b'SYNTHETIC NONBOOTABLE FIXTURE!!'
                payload[20:20 + len(marker)] = marker
                (firmware / name).write_bytes(payload)
                digest = hashlib.sha256(payload).hexdigest()
                hashes.append(digest + '  /usr/lib/firmware/qcom/sc8280xp/microsoft/blackrock/' + name)
                item = {key: rule[key] for key in ('catalog', 'class', 'class_guid', 'extension_id', 'hardware_id', 'inf')}
                item.update({'firmware': name, 'format': 1, 'source': 'target-windows-driverstore',
                    'verification': 'authenticode-catalog-members:inf,firmware', 'verification_tool': 'osslsigncode-2.14',
                    'package': rule['inf'] + '_arm64_' + '1' * 16, 'catalog_sha256': '1' * 64,
                    'firmware_sha256': digest, 'inf_sha256': '2' * 64, 'trust_bundle_sha256': '3' * 64,
                    'firmware_size': len(payload), 'driver_date': '2026-01-01', 'driver_version': '1.0.0.0'})
                provenance.append(json.dumps(item, sort_keys=True))
            (records / 'firmware.sha256').write_text('\n'.join(hashes) + '\n')
            shutil.copytree(records, live_records, dirs_exist_ok=True)
            (target / 'var/lib/devkit2023customlinux/prepared-bundle').mkdir(parents=True)
            (target / 'var/lib/devkit2023customlinux/windows-firmware-provenance.jsonl').write_text('\n'.join(provenance) + '\n')
            fs_uuid = run('blkid', '-s', 'UUID', '-o', 'value', rootnode).strip()
            efi_uuid = run('blkid', '-s', 'UUID', '-o', 'value', efinode).strip()
            gs = {'rootMountPoint': str(target), 'partitions': [
                {'device': rootnode, 'fs': 'ext4', 'mountPoint': '/', 'uuid': fs_uuid},
                {'device': efinode, 'fs': 'fat32', 'mountPoint': '/boot/efi', 'uuid': efi_uuid}],
                'partitionChoices': {'swap': 'file'}, 'mountOptionsList': [
                    {'mountpoint': '/', 'option_string': 'defaults,noatime'},
                    {'mountpoint': '/boot/efi', 'option_string': 'defaults,umask=0077'}]}
            utility = SimpleNamespace(gettext_path=lambda: '/usr/share/locale', gettext_languages=lambda: ['en'],
                                      debug=lambda *a: None, warning=lambda *a: None,
                                      host_env_process_output=lambda args: run(*args))
            cala = SimpleNamespace(globalstorage=SimpleNamespace(value=lambda key: gs.get(key)), utils=utility,
                                   job=SimpleNamespace(configuration={}, setprogress=lambda p: None))
            with patch.dict(sys.modules, {'libcalamares': cala}):
                fstab = runpy.run_path(str(source / 'usr/lib/aarch64-linux-gnu/calamares/modules/fstab/main.py'))
                assert fstab['run']() is None
            text = (target / 'etc/fstab').read_text()
            assert fs_uuid in text and efi_uuid in text and '/swapfile' in text
            assert planned['before']['partitions'][2]['uuid'] not in text
            # Simulate removal of the live-only packages before the installed initramfs.
            run('chroot', target, 'apt-get', '-y', 'remove', 'live-boot', 'live-boot-initramfs-tools',
                'live-config', 'live-config-systemd', 'user-setup', 'squashfs-tools', 'calamares-settings-debian', 'calamares')
            run('chroot', target, 'update-initramfs', '-k', 'all', '-c', '-t')
            with patch.dict(sys.modules, {'install_policy': POLICY}):
                backend = runpy.run_path(str(PROJECT / 'overlay/usr/local/libexec/devkit2023customlinux-install-storage'))
            record = {'plan': planned, 'phase': 'formatted', 'identity': {'device': loop},
                      'efi_files': backend['tree_hash'](efi), 'boot_variables': {},
                      'root_fs_uuid': fs_uuid, 'efi_fs_uuid': efi_uuid}
            original_read = Path.read_bytes
            def read_bytes(path):
                if str(path).startswith('/boot/vmlinuz-'):
                    return original_read(source / str(path).lstrip('/'))
                if str(path).startswith('/etc/devkit2023customlinux-prepared/'):
                    return original_read(live_records / path.name)
                return original_read(path)
            api_fixture = {'verify': lambda path: ({'synthetic': True}, []),
                           'require_target': lambda data: data['synthetic'] or None}
            # Only this test replaces physical target/signature and EFI-variable checks.
            # Installed firmware packing, mount checks, grub-mkconfig, grub-install
            # --no-nvram, script/ARM64-loader verification and preservation are real.
            namespace = backend['finish'].__globals__
            with patch.dict(namespace, {'load': lambda: record, 'save': lambda r: None,
                    'current': lambda r, mounted=False: ensure_backing(), 'boot_variables': lambda: {},
                    'register_boot_entry': lambda r: None}), patch.object(Path, 'read_bytes', read_bytes), \
                    patch('runpy.run_path', return_value=api_fixture):
                backend['finish'](str(target))
            assert record['phase'] == 'complete'
            assert (efi / 'EFI/DevKit2023CustomLinux/grubaa64.efi').is_file()
            assert (efi / 'EFI/Microsoft/Boot/bootmgfw.efi').read_bytes() == b'SYNTHETIC WINDOWS SENTINEL; NOT BOOTABLE'
            assert (efi / 'EFI/BOOT/BOOTAA64.EFI').read_bytes() == b'SYNTHETIC FALLBACK SENTINEL'
            print('PASS: real Calamares fstab + installed initramfs + ARM64 GRUB --no-nvram on disposable disk; original EFI files preserved. Hardware/signature/UEFI-variable checks mocked here; no Windows/installed boot claim.')
        finally:
            for path in reversed(mounts):
                run('umount', '-R', path)
            run('losetup', '--detach', loop)


if __name__ == '__main__':
    main()
