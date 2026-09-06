#!/usr/bin/env python3
"""Validate the one public preparation-base format, without accessing target disks."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
PREPARE = runpy.run_path(str(PROJECT / 'scripts/prepare-iso.py'))
FIRMWARE = ('qcadsp8280.mbn', 'qccdsp8280.mbn', 'qcdxkmsuc8280.mbn')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(*args):
    return subprocess.run([str(arg) for arg in args], check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300).stdout


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_logs(root):
    logs = root / 'var/log'
    require(logs.is_dir() and not logs.is_symlink(), 'Missing/linked base log directory')
    for path in logs.rglob('*'):
        if path.is_symlink():
            # Debian ships this documentation link; it is not a build log.
            # Inspect the link itself rather than following a chroot link on the host.
            require(path.relative_to(logs).as_posix() == 'README' and
                    path.readlink().as_posix() == '../../usr/share/doc/systemd/README.logs',
                    'Unexpected link in base logs')
        elif path.is_file():
            require(path.stat().st_size == 0, 'Build logs remain in base')


def verify_root(root):
    PREPARE['require_current_base'](root)
    for relative in ('tmp', 'run'):
        require(not any(not p.is_dir() or p.is_symlink() for p in (root / relative).rglob('*')),
                'Runtime/test leftovers in base: ' + relative)
    for directory in (PROJECT / 'overlay', PROJECT / 'profiles/prepared/overlay'):
        for source in directory.rglob('*'):
            if source.is_file() and source.read_bytes().startswith(b'#!'):
                require((root / source.relative_to(directory)).stat().st_mode & 0o111 == 0o111,
                        'Non-executable source helper: ' + source.name)
    for package in ('libcanberra-pulse', 'plasma-desktop', 'dolphin', 'kio-extras', 'konsole', 'kdialog', 'qdbus-qt6',
                    'pipewire-audio', 'wireplumber', 'bluez', 'firmware-atheros', 'firmware-qcom-soc', 'fdisk', 'e2fsprogs'):
        require(run('chroot', root, 'dpkg-query', '-W', '-f=${Status}', package) == 'install ok installed',
                'Required package missing: ' + package)
    require('osslsigncode 2.14' in run('chroot', root, '/usr/local/bin/osslsigncode', '--version'),
            'Reviewed catalog verifier missing')
    require(not (root / 'etc/devkit2023customlinux-prepared/target-binding').exists(), 'Private target binding in base')
    require(not (root / 'etc/devkit2023customlinux-prepared/firmware.sha256').exists(), 'Private firmware hashes in base')
    forbidden = ('opt/google/chrome', 'etc/apt/sources.list.d/google-chrome.list',
                 'etc/apt/keyrings/google-chrome.asc', 'var/lib/systemd/random-seed',
                 'var/lib/dbus/machine-id', 'root/.cache/calamares',
                 'etc/xdg/autostart/devkit2023customlinux-installer.desktop')
    for relative in forbidden:
        require(not (root / relative).exists() and not (root / relative).is_symlink(), 'Forbidden base content: ' + relative)
    for relative in ('home', 'var/lib/devkit2023customlinux', 'run/devkit2023customlinux',
                     'var/lib/bluetooth', 'var/lib/NetworkManager', 'etc/NetworkManager/system-connections',
                     'etc/ssl/private', 'etc/wireguard', 'root/.ssh'):
        require(not any(p.is_file() or p.is_symlink() for p in (root / relative).rglob('*')),
                'Private state in base: ' + relative)
    require(not (root / 'root/.bash_history').exists(), 'Builder shell history in base')
    require((root / 'etc/machine-id').read_bytes() == b'', 'Generated machine identity in base')
    verify_logs(root)
    require((root / 'etc/hostname').read_text().strip() == 'devkit2023', 'Builder hostname in base')
    for line in (root / 'etc/passwd').read_text().splitlines():
        require(not 1000 <= int(line.split(':')[2]) < 65534, 'Persistent user account in base')
    for path in root.rglob('*'):
        require(path.name not in FIRMWARE, 'Private Blackrock firmware in base')
        require(not (path.name.startswith('google-chrome') and path.suffix == '.deb'), 'Cached Chrome package')
        if path.is_file() and path.is_relative_to(root / 'etc/ssh'):
            require(not path.name.startswith('ssh_host_'), 'Generated SSH identity')
    private = re.compile(rb'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}|[A-Za-z]:[\\/]+Users[\\/]+|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
    for relative in ('usr/local', 'usr/share/devkit2023customlinux', 'etc/NetworkManager'):
        for path in (root / relative).rglob('*'):
            if path.is_file() and not path.is_symlink():
                data = path.read_bytes()
                if b'\0' not in data:
                    require(not private.search(data), 'Private identifier in ' + str(path.relative_to(root)))
    for path in (root / 'etc/systemd/system').rglob('*'):
        if path.is_file() and not path.is_symlink():
            require(b'devkit2023customlinux-windows-firmware.service' not in path.read_bytes(), 'Retired service dependency')
    allowed_local = {p.relative_to(base).as_posix() for base in (PROJECT / 'overlay', PROJECT / 'profiles/prepared/overlay')
                     for p in (base / 'usr/local').rglob('*') if p.is_file()}
    allowed_local.add('usr/local/bin/osslsigncode')
    for path in (root / 'usr/local').rglob('*'):
        if path.is_file():
            require(path.relative_to(root).as_posix() in allowed_local, 'Unowned local helper: ' + path.name)
    wanted = root / 'etc/systemd/system/multi-user.target.wants/devkit2023customlinux-prepared.service'
    require(wanted.is_symlink() and wanted.readlink().name == 'devkit2023customlinux-prepared.service', 'Prepared startup not enabled')
    preflight = root / 'usr/local/libexec/devkit2023customlinux-install-preflight'
    require(preflight.read_text().rstrip().endswith('devkit2023customlinux-install-storage capture'), 'Read-only installer preflight missing')
    installer = (root / 'etc/calamares/settings.conf').read_text()
    for forbidden_job in ('partition', 'bootloader', 'grubcfg'):
        require(('  - ' + forbidden_job + '\n') not in installer, 'Generic disk/boot job remains')
    require('  - devkitpartition\n' in installer and 'shellprocess@check-mount' in installer and
            'shellprocess@finish' in installer, 'Windows-preserving installer jobs missing')
    configs = list((root / 'boot').glob('config-*-devkit2023customlinux'))
    require(len(configs) == 1, 'Custom kernel missing/ambiguous')
    settings = configs[0].read_text().splitlines()
    for value in ('CONFIG_SQUASHFS_XATTR=y', 'CONFIG_DRM_MSM=m', 'CONFIG_QCOM_Q6V5_PAS=m', 'CONFIG_SND_SOC_SC8280XP=m'):
        require(value in settings, 'Required kernel setting missing: ' + value)
    topology = root / PREPARE['TOPOLOGY']
    require(topology.is_file() and topology.resolve().is_relative_to(root.resolve()) and topology.stat().st_size,
            'Blackrock AudioReach topology missing/unsafe')
    ucm = root / 'usr/share/alsa/ucm2/Qualcomm/sc8280xp/Blackrock-HiFi.conf'
    for port in range(3):
        require(f'SectionDevice."HDMI{port}"' in ucm.read_text(), 'Blackrock UCM route missing')


def verify_iso(iso, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    for key, value in {'distribution': 'DevKit2023CustomLinux', 'releaseProfile': 'public-base',
                       'architecture': 'arm64', 'containsDeviceIdentity': False, 'installationEnabled': False,
                       'windowsImportAtBoot': False, 'requiresWindowsPreparation': True}.items():
        require(manifest.get(key) == value, 'Incorrect manifest field: ' + key)
    require(sha(iso) == manifest['sha256'], 'Base ISO checksum mismatch')
    packages = manifest_path.parent / 'packages.tsv'
    require(packages.is_file() and sha(packages) == manifest['packageInventorySha256'], 'Package inventory missing/mismatched')
    require((iso.with_suffix('.iso.sha256')).read_text().split()[0] == manifest['sha256'], 'Checksum sidecar mismatch')
    # A KDE rootfs plus ISO can exceed a RAM-backed /tmp during parallel tests.
    with tempfile.TemporaryDirectory(prefix='devkit-base-verify-', dir=os.environ.get('DEVKIT2023_WORK_ROOT', '/var/tmp')) as directory:
        work = Path(directory)
        tree, root, init = work / 'iso', work / 'root', work / 'init'
        run('xorriso', '-osirrox', 'on', '-indev', iso, '-extract', '/', tree)
        run('unsquashfs', '-no-progress', '-d', root, tree / 'live/filesystem.squashfs')
        verify_root(root)
        # Parsing the config or starting a process is insufficient: an absent
        # branding key previously caused an immediate silent exit. Exercise the
        # real GUI initialization without exposing any host device or EFI state.
        run('python3', '-B', PROJECT / 'scripts/verify-installer-startup.py', root)
        grub = tree / 'boot/grub/grub.cfg'
        run('grub-script-check', grub)
        require(grub.read_bytes() == (PROJECT / 'config/grub/grub.cfg').read_bytes(), 'GRUB differs from source')
        for value in ('clk_ignore_unused', 'pd_ignore_unused', 'modprobe.blacklist=msm,qcom_q6v5_pas,snd_soc_sc8280xp'):
            require(value in grub.read_text(), 'Required boot option absent: ' + value)
        require('efi=noruntime' not in grub.read_text() and grub.read_text().count('menuentry ') == 1, 'Unexpected GRUB options')
        efi = tree / 'EFI/BOOT/BOOTAA64.EFI'
        run('grub-file', '--is-arm64-efi', efi)
        run('mcopy', '-i', tree / 'boot/grub/efi.img', '::/EFI/BOOT/BOOTAA64.EFI', work / 'esp.efi')
        require(efi.read_bytes() == (work / 'esp.efi').read_bytes(), 'EFI loader copies differ')
        run('grub-fstest', iso, 'cmp', '/boot/grub/grub.cfg', grub)
        require(sha(tree / 'live/vmlinuz') == manifest['kernelSha256'], 'Kernel hash mismatch')
        require(sha(root / 'boot' / ('config-' + manifest['kernelVersion'])) == manifest['kernelConfigSha256'], 'Kernel config hash mismatch')
        dtb = tree / 'boot/dtbs/sc8280xp-microsoft-blackrock.dtb'
        require(sha(dtb) == manifest['dtbSha256'], 'DTB hash mismatch')
        require('microsoft,blackrock' in run('fdtget', dtb, '/', 'compatible'), 'Wrong device tree')
        run('unmkinitramfs', tree / 'live/initrd.img', init)
        early = list(init.rglob('scripts/init-premount/devkit2023customlinux-prepared'))
        require(len(early) == 1 and early[0].read_bytes() == (PROJECT / 'profiles/prepared/overlay/etc/initramfs-tools/scripts/init-premount/devkit2023customlinux-prepared').read_bytes(), 'Early loader absent/stale')
        for path in init.rglob('*'):
            require(path.name not in (*FIRMWARE, 'target-binding', 'firmware.sha256'), 'Private state in base initramfs')
            require('firmware-cache' not in path.name, 'Retired cache loader in initramfs')
        # xorriso reports some formats on stderr.
        report_result = subprocess.run(['xorriso', '-indev', str(iso), '-report_system_area', 'plain',
                                        '-report_el_torito', 'plain'], capture_output=True, text=True, check=True, timeout=60)
        report = report_result.stdout + report_result.stderr
        require('GPT' in report and 'EFI boot partition' in report and 'UEFI' in report, 'Hybrid ARM64 EFI layout missing')
    manifest['staticVerification'] = 'passed'
    manifest['redistributionAudit'] = 'technical-privacy-check-passed; license-review-required'
    temporary = manifest_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    temporary.replace(manifest_path)
    print('Public base verified: target-free payload, prepared-only free-space installer, ARM64 boot layout.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--iso', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if args.root and not args.iso:
        verify_root(args.root)
    elif args.iso and args.manifest and not args.root:
        verify_iso(args.iso, args.manifest)
    else:
        parser.error('choose --root or --iso with --manifest')
