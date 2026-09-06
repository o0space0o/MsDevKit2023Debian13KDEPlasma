#!/usr/bin/env python3
"""Repack a verified public ISO with explicitly supplied private target material."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
PROFILE = PROJECT / 'profiles/prepared/overlay'
HELPER = PROFILE / 'usr/local/libexec/devkit2023customlinux-prepared'
VALIDATOR = PROJECT / 'overlay/usr/local/libexec/devkit2023customlinux-validate-windows-driver'
PRODUCT = 'DevKit2023CustomLinux'
ISO_NAME = PRODUCT + '-1.0.0-arm64.iso'
TOPOLOGY = 'usr/lib/firmware/qcom/sc8280xp/SC8280XP-MICROSOFT-BLACKROCK-tplg.bin'
DIAGNOSTICS_DESKTOP = 'etc/skel/Desktop/DevKit2023Diagnostics.desktop'
CANBERRA_BACKEND = 'usr/lib/aarch64-linux-gnu/libcanberra-0.30/libcanberra-pulse.so'
FILESEARCH_BACKEND = 'usr/lib/aarch64-linux-gnu/qt6/plugins/kf6/kio/kio_filenamesearch.so'


def require_current_base(root):
    """No legacy base upgrades or boot-time firmware imports are supported."""
    if not (root / CANBERRA_BACKEND).is_file():
        raise ValueError('Rebuild the public base: KDE sound-test backend is missing')
    if not (root / FILESEARCH_BACKEND).is_file():
        raise ValueError('Rebuild the public base: Dolphin file-search backend is missing')
    for directory in (PROJECT / 'overlay', PROFILE):
        for source in directory.rglob('*'):
            if source.is_file():
                actual = root / source.relative_to(directory)
                if not actual.is_file() or actual.read_bytes() != source.read_bytes():
                    raise ValueError('Rebuild the public base: source overlay differs at ' +
                                     source.relative_to(directory).as_posix())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run(*args, **kwargs):
    print('[prepare] ' + str(args[0]), flush=True)
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    path.chmod(mode)


def create_root(bundle, root, api):
    require_current_base(root)
    signer = root / 'usr/local/bin/osslsigncode'
    roots = root / 'usr/share/devkit2023customlinux/microsoft-driver-roots.pem'
    data, selected = api['verify'](bundle, VALIDATOR, roots, signer)
    state = root / 'var/lib/devkit2023customlinux'
    state.mkdir(parents=True, exist_ok=True)
    state.chmod(0o700)
    installed_bundle = state / 'prepared-bundle'
    installed_bundle.mkdir(mode=0o700)
    normalized = {**data, 'files': {}}
    provenance = []
    hashes = []
    for _rank, payload, record in selected:
        directory = installed_bundle / 'packages' / payload.parent.name
        directory.mkdir(parents=True)
        for name in (record['firmware'], record['inf'], record['catalog']):
            source = payload.parent / name
            destination = directory / name
            shutil.copyfile(source, destination)
            destination.chmod(0o600)
            normalized['files'][destination.relative_to(installed_bundle).as_posix()] = sha(destination)
        destination = root / 'usr/lib/firmware/qcom/sc8280xp/microsoft/blackrock' / record['firmware']
        write(destination, payload.read_bytes())
        hashes.append(record['firmware_sha256'] + '  /' + destination.relative_to(root).as_posix())
        provenance.append(json.dumps(record, sort_keys=True))
    write(installed_bundle / 'manifest.json', json.dumps(normalized, sort_keys=True) + '\n', 0o600)
    write(state / 'windows-firmware-provenance.jsonl', '\n'.join(provenance) + '\n', 0o600)
    write(root / 'etc/devkit2023customlinux-prepared/target-binding', data['binding']['value'] + '\n', 0o600)
    topology = root / TOPOLOGY
    if not topology.is_file() or not topology.resolve().is_relative_to(root.resolve()) or topology.stat().st_size == 0:
        raise ValueError('Base lacks the required Blackrock topology at the kernel request path')
    hashes.append(sha(topology) + '  /' + TOPOLOGY)
    write(root / 'etc/devkit2023customlinux-prepared/firmware.sha256', '\n'.join(hashes) + '\n', 0o600)
    api['verify'](installed_bundle, VALIDATOR, roots, signer)
    return normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--base-sha256', required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work-parent', type=Path, default=Path('/var/tmp'))
    args = parser.parse_args()
    if os.geteuid() != 0 or os.uname().machine not in ('aarch64', 'arm64'):
        raise ValueError('native ARM64 Linux as root is required')
    os.umask(0o077)
    base, bundle, output = args.base.resolve(), args.bundle.resolve(), args.output.resolve()
    if not re.fullmatch(r'[0-9a-f]{64}', args.base_sha256) or sha(base) != args.base_sha256:
        raise ValueError('base ISO checksum mismatch')
    if output.exists() or output == PROJECT or output.is_relative_to(PROJECT) or output.is_relative_to(bundle):
        raise ValueError('new private output outside source and input bundle is required')
    run('python3', '-B', PROJECT / 'scripts/check-source.py', '--shell')
    source_api = runpy.run_path(str(PROJECT / 'scripts/check-source.py'))
    _map, source_names = source_api['inventory'](PROJECT)
    source_digest = hashlib.sha256()
    for name in source_names:
        source_digest.update(name.encode('utf-8') + b'\0' + hashlib.sha256((PROJECT / name).read_bytes()).digest())
    work_parent = args.work_parent.resolve(strict=True)
    if str(work_parent).startswith('/mnt/') or work_parent == PROJECT or work_parent.is_relative_to(PROJECT):
        raise ValueError('preparation scratch must be on native Linux outside source')
    work = Path(tempfile.mkdtemp(prefix='DevKit2023CustomLinux-prepare-', dir=work_parent))
    iso_tree, root = work / 'iso', work / 'root'
    print('Private preparation workspace: ' + str(work), flush=True)
    proc_mounted = False
    try:
        run('xorriso', '-osirrox', 'on', '-indev', base, '-extract', '/', iso_tree)
        run('unsquashfs', '-no-progress', '-d', root, iso_tree / 'live/filesystem.squashfs')
        # Do not execute an arbitrary foreign root filesystem: the selected base
        # must match this project's firmware validator and branded kernel tree.
        if (root / 'usr/local/libexec/devkit2023customlinux-validate-windows-driver').read_bytes() != VALIDATOR.read_bytes():
            raise ValueError('base validator does not match reviewed source')
        kernels = list((root / 'boot').glob('vmlinuz-*-devkit2023customlinux'))
        if len(kernels) != 1:
            raise ValueError('base kernel is missing or ambiguous')
        kernel = kernels[0].name.removeprefix('vmlinuz-')
        api = runpy.run_path(str(HELPER))
        normalized = create_root(bundle, root, api)
        # Required tools are executed from the user's explicitly trusted base.
        # Only a private proc mount is supplied, never host disks or EFI variables.
        (root / 'proc').mkdir(exist_ok=True)
        run('mount', '-t', 'proc', 'proc', root / 'proc')
        proc_mounted = True
        run('chroot', root, 'update-initramfs', '-u', '-k', kernel)
        run('umount', root / 'proc')
        proc_mounted = False
        shutil.copyfile(root / 'boot' / ('initrd.img-' + kernel), iso_tree / 'live/initrd.img')
        (iso_tree / 'live/filesystem.squashfs').unlink()
        run('mksquashfs', root, iso_tree / 'live/filesystem.squashfs', '-comp', 'zstd', '-Xcompression-level', '15', '-noappend', '-no-progress')
        size = sum(path.stat().st_size for path in root.rglob('*') if path.is_file() and not path.is_symlink())
        write(iso_tree / 'live/filesystem.size', str(size) + '\n')
        result = work / ISO_NAME
        run('xorriso', '-as', 'mkisofs', '-iso-level', '3', '-full-iso9660-filenames', '-volid', PRODUCT,
            '-eltorito-alt-boot', '-e', 'boot/grub/efi.img', '-no-emul-boot', '-efi-boot-part', '--efi-boot-image', '-o', result, iso_tree)
        run('python3', '-B', PROJECT / 'scripts/verify-prepared-iso.py', '--iso', result, '--bundle', bundle)
        output.mkdir(parents=True, mode=0o700)
        # Publish ISO first; manifest is the final completion marker.
        partial = output / (ISO_NAME + '.partial')
        shutil.copyfile(result, partial)
        digest = sha(result)
        if sha(partial) != digest:
            raise ValueError('prepared ISO copy checksum mismatch')
        partial.rename(output / ISO_NAME)
        write(output / (ISO_NAME + '.sha256'), digest + '  ' + ISO_NAME + '\n')
        manifest = {'distribution': PRODUCT, 'version': '1.0.0', 'releaseProfile': 'private-prepared',
                    'baseSha256': args.base_sha256, 'sha256': digest, 'containsDeviceIdentity': True,
                    'targetBinding': normalized['binding'], 'firmwareSource': 'explicit-target-windows-export',
                    'windowsImportAtBoot': False, 'staticVerification': 'passed', 'hardwareValidation': 'required',
                    'installationEnabled': True, 'installerPolicy': 'windows-free-space-v1',
                    'candidateRevision': 'prepared-workflow-v1',
                    'diagnosticsIncluded': True, 'earlyAudioTopology': True}
        manifest['preparationSourceSha256'] = source_digest.hexdigest()
        write(output / 'build-manifest.json', json.dumps(manifest, indent=2) + '\n', 0o600)
        write(output / 'INSTALLATION-README.txt', 'Private prepared installation candidate: only for the exported Dev Kit. Back up Windows and free unallocated space in Windows Disk Management (64 GiB recommended, 32 GiB minimum). Boot the USB and open Install DevKit2023CustomLinux. The installer creates one new Linux partition; it never resizes or formats Windows or the existing EFI partition. Read SETUP.md. Installed hardware boot and Windows reboot must still be confirmed before a production release. Do not distribute this private ISO.\n', 0o600)
        print('Prepared ISO verified and published: ' + str(output / ISO_NAME), flush=True)
    finally:
        if proc_mounted:
            subprocess.run(['umount', str(root / 'proc')], check=True)
        # Discard only this invocation's scratch tree, on success and ordinary errors.
        if work.parent == work_parent and work.name.startswith('DevKit2023CustomLinux-prepare-') and not work.is_symlink():
            shutil.rmtree(work)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('ISO preparation failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
