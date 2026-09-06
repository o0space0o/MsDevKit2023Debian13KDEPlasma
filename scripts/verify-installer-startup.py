#!/usr/bin/env python3
"""Launch the real installer window in a disposable, device-free native chroot.

No install clicks, private bundle, physical disks, EFI, or host display are used.
The input must be a trusted public rootfs. An overlay keeps that rootfs unchanged.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import tempfile
import time

READY = ('STARTUP: loadModules for all modules done',
         'STARTUP: Window now visible and ProgressTreeView populated',
         'All requirements have been checked.')
FAILURE = re.compile(r'ERROR: FATAL|key not found:|Failed to load module|'
                     r'Could not load (?:module|the Qt platform plugin)|Segmentation fault', re.I)


def check_log(output, returncode, timed_out):
    if not timed_out or returncode != -signal.SIGTERM:
        raise ValueError(f'Installer exited before the startup test ended: {returncode}\n{output[-4000:]}')
    if FAILURE.search(output) or not all(marker in output for marker in READY):
        raise ValueError('Installer window/module initialization failed:\n' + output[-6000:])


def isolated(root, x11=False):
    subprocess.run(['mount', '--make-rprivate', '/'], check=True)
    with tempfile.TemporaryDirectory(prefix='devkit-installer-startup-', dir=os.environ.get('DEVKIT2023_WORK_ROOT', '/var/tmp')) as directory:
        work = Path(directory)
        for name in ('upper', 'work', 'root'):
            (work / name).mkdir()
        target = work / 'root'
        mounts = []
        display = None
        process = None
        mapped = False
        try:
            options = f'lowerdir={root},upperdir={work / "upper"},workdir={work / "work"}'
            subprocess.run(['mount', '-t', 'overlay', 'overlay', '-o', options, str(target)], check=True)
            mounts.append(target)
            # Hide every input/host runtime entry, especially block devices,
            # system DBus, EFI variables and real display sockets.
            for name in ('dev', 'proc', 'sys', 'run', 'tmp', 'root'):
                path = target / name
                path.mkdir(exist_ok=True)
                subprocess.run(['mount', '-t', 'tmpfs', '-o', 'mode=0755,nosuid', 'tmpfs', str(path)], check=True)
                mounts.append(path)
            for name, minor in (('null', 3), ('zero', 5), ('random', 8), ('urandom', 9)):
                subprocess.run(['mknod', '-m', '666', str(target / 'dev' / name), 'c', '1', str(minor)], check=True)
            runtime = target / 'run/installer-smoke'
            runtime.mkdir(mode=0o700)
            env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root', 'LC_ALL': 'C.UTF-8',
                   'QT_QPA_PLATFORM': 'offscreen', 'XDG_RUNTIME_DIR': '/run/installer-smoke'}
            if x11:
                # This private mount/network namespace gets its own /tmp and
                # display, never WSLg or a user's real desktop. Xvfb is test-only.
                subprocess.run(['mount', '-t', 'tmpfs', '-o', 'mode=1777', 'tmpfs', '/tmp'], check=True)
                mounts.append(Path('/tmp'))
                display = subprocess.Popen(['Xvfb', ':77', '-screen', '0', '1024x768x24', '-nolisten', 'tcp'],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for _ in range(50):
                    if Path('/tmp/.X11-unix/X77').exists():
                        break
                    if display.poll() is not None:
                        raise ValueError('Isolated Xvfb failed to start')
                    time.sleep(0.1)
                sockets = target / 'tmp/.X11-unix'
                sockets.mkdir()
                subprocess.run(['mount', '--bind', '/tmp/.X11-unix', str(sockets)], check=True)
                mounts.append(sockets)
                env.update(QT_QPA_PLATFORM='xcb', DISPLAY=':77')
            process = subprocess.Popen(['chroot', str(target), '/usr/bin/calamares', '-d'],
                                       env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, errors='replace', start_new_session=True)
            timed_out = False
            try:
                output, _ = process.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                timed_out = True
                window_tree = ''
                if x11:
                    window_tree = subprocess.run(['xwininfo', '-display', ':77', '-root', '-tree'],
                                                 capture_output=True, text=True, timeout=4).stdout
                    window = re.search(r'(0x[0-9a-f]+) "DevKit2023CustomLinux Installer": '
                                       r'\("calamares" "calamares"\)\s+(\d+)x(\d+)', window_tree)
                    if window and int(window[2]) >= 800 and int(window[3]) >= 520:
                        info = subprocess.run(['xwininfo', '-display', ':77', '-id', window[1]],
                                              capture_output=True, text=True, timeout=4).stdout
                        mapped = 'Map State: IsViewable' in info
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    output, _ = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    output, _ = process.communicate()
            check_log(output, process.returncode, timed_out)
            if x11 and not mapped:
                raise ValueError('Installer has no mapped X11 main window:\n' + window_tree)
            print('Installer startup passed: real Calamares window and all view modules initialized; '
                  'no disks, EFI or install actions exposed. Physical desktop/installation still needs testing.')
            if x11:
                print('X11/XCB check passed: actual Calamares main window exists on the isolated virtual display.')
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            if display is not None and display.poll() is None:
                display.terminate()
                display.wait(timeout=5)
            for path in reversed(mounts):
                subprocess.run(['umount', str(path)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rootfs', type=Path)
    parser.add_argument('--x11', action='store_true', help='also require an actual XCB window (test host needs Xvfb and xwininfo)')
    parser.add_argument('--isolated', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.rootfs.resolve()
    if os.geteuid() != 0 or platform.machine() != 'aarch64':
        parser.error('native ARM64 Linux root is required')
    if root == Path('/') or str(root).startswith('/mnt/') or re.search(r'[,\\:\s]', str(root)):
        parser.error('use a trusted native Linux rootfs directory, not the running system')
    if not (root / 'usr/bin/calamares').is_file():
        parser.error('Calamares is missing from rootfs')
    if args.isolated:
        isolated(root, args.x11)
    else:
        subprocess.run(['unshare', '--mount', '--net', '--fork', sys.executable, '-B',
                        str(Path(__file__).resolve()), str(root), '--isolated',
                        *(['--x11'] if args.x11 else [])], check=True)


if __name__ == '__main__':
    main()
