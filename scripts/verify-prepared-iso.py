#!/usr/bin/env python3
"""Verify a private prepared ISO by extracting its live filesystem and initramfs."""
import argparse
import hashlib
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
PROFILE = PROJECT / 'profiles/prepared/overlay'
API = runpy.run_path(str(PROFILE / 'usr/local/libexec/devkit2023customlinux-prepared'))
PREPARE = runpy.run_path(str(PROJECT / 'scripts/prepare-iso.py'))


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def verify_early_topology(root, init):
    relative = PREPARE['TOPOLOGY']
    source = root / relative
    matches = list(init.rglob(relative))
    if not source.is_file() or not source.resolve().is_relative_to(root.resolve()):
        raise ValueError('Root filesystem Blackrock topology is missing/unsafe')
    if len(matches) != 1 or not matches[0].is_file() or matches[0].is_symlink():
        raise ValueError('Early Blackrock topology is absent, ambiguous or a symlink')
    if not source.stat().st_size or matches[0].read_bytes() != source.read_bytes():
        raise ValueError('Early Blackrock topology differs from root filesystem')
    records = list(init.rglob('etc/devkit2023customlinux-prepared/firmware.sha256'))
    expected = hashlib.sha256(source.read_bytes()).hexdigest() + '  /' + relative
    if len(records) != 1 or expected not in records[0].read_text().splitlines():
        raise ValueError('Early topology integrity record is missing')


def verify(iso: Path, bundle: Path):
    parent = Path(os.environ.get('DEVKIT2023_WORK_ROOT', '/var/tmp'))
    work = Path(tempfile.mkdtemp(prefix='verify-', dir=parent))
    tree, root, init = work / 'iso', work / 'root', work / 'init'
    try:
        run('xorriso', '-osirrox', 'on', '-indev', iso, '-extract', '/live', tree / 'live',
            '-extract', '/boot/grub/grub.cfg', tree / 'grub.cfg', '-extract', '/EFI/BOOT/BOOTAA64.EFI', tree / 'BOOTAA64.EFI')
        run('grub-script-check', tree / 'grub.cfg')
        grub = (tree / 'grub.cfg').read_text()
        for required in ('clk_ignore_unused', 'pd_ignore_unused', 'Install DevKit2023CustomLinux', 'sc8280xp-microsoft-blackrock.dtb'):
            if required not in grub:
                raise ValueError('prepared GRUB missing ' + required)
        if 'efi=noruntime' in grub or grub.count('menuentry ') != 1:
            raise ValueError('unexpected prepared GRUB entries/options')
        run('grub-file', '--is-arm64-efi', tree / 'BOOTAA64.EFI')
        run('unsquashfs', '-no-progress', '-d', root, tree / 'live/filesystem.squashfs')
        if not (root / PREPARE['CANBERRA_BACKEND']).is_file():
            raise ValueError('KDE sound-test backend is missing')
        signer = root / 'usr/local/bin/osslsigncode'
        roots = root / 'usr/share/devkit2023customlinux/microsoft-driver-roots.pem'
        validator = PROJECT / 'overlay/usr/local/libexec/devkit2023customlinux-validate-windows-driver'
        original, selected = API['verify'](bundle, validator, roots, signer)
        embedded, packed = API['verify'](root / 'var/lib/devkit2023customlinux/prepared-bundle', validator, roots, signer)
        if original['binding'] != embedded['binding'] or original['bluetooth'] != embedded['bluetooth'] or len(embedded['files']) != 9:
            raise ValueError('prepared target data differs from explicit input')
        if [item[2] for item in selected] != [item[2] for item in packed]:
            raise ValueError('prepared firmware selection differs from authenticated input')
        PREPARE['require_current_base'](root)
        for source in PROFILE.rglob('*'):
            if source.is_file():
                actual = root / source.relative_to(PROFILE)
                if actual.read_bytes() != source.read_bytes():
                    raise ValueError('prepared overlay differs from source')
        for directory in (PROJECT / 'overlay', PROFILE):
            for source in directory.rglob('*'):
                if source.is_file() and source.read_bytes().startswith(b'#!'):
                    if (root / source.relative_to(directory)).stat().st_mode & 0o111 != 0o111:
                        raise ValueError('Executable permissions missing: ' + source.name)
        if (root / 'usr/share/applications/devkit2023customlinux-diagnostics.desktop').read_bytes() != (root / PREPARE['DIAGNOSTICS_DESKTOP']).read_bytes():
            raise ValueError('Diagnostics application-menu entry missing/stale')
        if not (root / 'usr/bin/kdialog').is_file() or not (root / 'usr/bin/qdbus6').is_file():
            raise ValueError('Diagnostics KDE UI dependencies missing')
        for path in (root / 'etc/systemd/system').rglob('*'):
            if path.is_file() and not path.is_symlink() and b'devkit2023customlinux-windows-firmware.service' in path.read_bytes():
                raise ValueError('legacy service dependency remains')
        run('unmkinitramfs', tree / 'live/initrd.img', init)
        verify_early_topology(root, init)
        early = list(init.rglob('scripts/init-premount/devkit2023customlinux-prepared'))
        if len(early) != 1 or early[0].read_bytes() != (PROFILE / 'etc/initramfs-tools/scripts/init-premount/devkit2023customlinux-prepared').read_bytes():
            raise ValueError('early prepared loader missing or stale')
        if list(init.rglob('scripts/live-bottom/devkit2023customlinux-firmware-cache')):
            raise ValueError('old USB cache loader remains in initramfs')
        bindings = list(init.rglob('etc/devkit2023customlinux-prepared/target-binding'))
        if len(bindings) != 1 or bindings[0].read_text().strip() != original['binding']['value']:
            raise ValueError('early target binding missing or wrong')
        for _rank, _source, record in selected:
            matches = list(init.rglob('usr/lib/firmware/qcom/sc8280xp/microsoft/blackrock/' + record['firmware']))
            if len(matches) != 1 or hashlib.sha256(matches[0].read_bytes()).hexdigest() != record['firmware_sha256']:
                raise ValueError('early firmware missing or different')
        if any(path.is_file() for path in (root / 'home').rglob('*')):
            raise ValueError('persisted home data in prepared image')
        print('Prepared ISO passed: target binding, signed firmware evidence, early firmware, clean services and ARM64 boot files.')
    finally:
        if work.parent == parent and work.name.startswith('verify-') and not work.is_symlink():
            shutil.rmtree(work)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    verify(args.iso, args.bundle)
