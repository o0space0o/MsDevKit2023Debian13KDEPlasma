#!/usr/bin/env python3
"""VM-only evidence harness. Never a build input or a distributable image."""
import argparse
import json
import platform
import os
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('rootfs', type=Path, help='Trusted current public rootfs (unchanged input)')
parser.add_argument('output', type=Path, help='New native Linux evidence directory outside source')
args = parser.parse_args()
BASE = args.rootfs.resolve()
WORK = args.output.resolve()
if os.geteuid() != 0 or platform.machine() != 'aarch64':
    parser.error('Native ARM64 Linux root is required')
if BASE == Path('/') or str(BASE).startswith('/mnt/') or not (BASE / 'usr/bin/calamares').is_file():
    parser.error('A trusted extracted public rootfs is required, never the host root')
if WORK.exists() or WORK.is_relative_to(SOURCE) or WORK.is_relative_to(BASE) or str(WORK).startswith('/mnt/'):
    parser.error('Choose a new native evidence directory outside source')
ROOT = WORK / 'rootfs'
WORK.mkdir(parents=True)
def run(*args):
    subprocess.run([str(v) for v in args], check=True)
def write(relative, content, mode=0o644):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(mode)

run(sys.executable, '-B', SOURCE / 'scripts/verify-base.py', '--root', BASE)
run('cp', '-a', '--one-file-system', '--reflink=auto', BASE, ROOT)
# Install virtual-display tooling ONLY in the disposable VM derivative.
(ROOT / 'etc/resolv.conf').unlink()
shutil.copyfile('/etc/resolv.conf', ROOT / 'etc/resolv.conf')
write('usr/sbin/policy-rc.d', '#!/bin/sh\nexit 101\n', 0o755)
os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
run('chroot', ROOT, 'apt-get', 'update', '-qq')
run('chroot', ROOT, 'apt-get', 'install', '-y', '--no-install-recommends', '--no-upgrade', 'xvfb', 'xdotool', 'x11-utils')
for name in ('sddm', 'live-config', 'devkit2023customlinux-prepared',
             'devkit2023customlinux-display-ready', 'devkit2023customlinux-audio',
             'devkit2023customlinux-bluetooth-address'):
    path = ROOT / ('etc/systemd/system/' + name + '.service')
    path.unlink(missing_ok=True)
    path.symlink_to('/dev/null')
run('chroot', ROOT, 'useradd', '--create-home', '--uid', '1000', '--shell', '/bin/bash', 'devkit')
write('etc/fstab', '/dev/vda / ext4 defaults 0 1\n')
write('etc/hostname', 'synthetic-vm\n')
write('etc/polkit-1/rules.d/00-handoff-test.rules', '''polkit.addRule(function(action, subject) {
  if (subject.user == "devkit" &&
      (action.id == "com.github.calamares.calamares.pkexec.run" ||
       (action.id == "org.freedesktop.policykit.exec" &&
        action.lookup("program") == "/usr/local/libexec/devkit2023customlinux-install-preflight"))) {
    return polkit.Result.YES;
  }
});
''')
sys.path.insert(0, str(SOURCE / 'tests'))
from test_install_policy import P, fixture
write('opt/handoff-test/plan.json', json.dumps(P.plan(fixture())), 0o600)
# Actual storage capture + JSON protection, synthetic hardware/GPT inputs only.
# This replacement exists ONLY in the VM copy, never the ISO source/rootfs.
write('usr/local/libexec/devkit2023customlinux-install-preflight', '''#!/usr/bin/python3
import os, json, runpy
from pathlib import Path
from unittest.mock import patch
assert os.geteuid() == 0
assert os.umask(0o022) == 0o022, 'Private log umask leaked into privileged installation'
api = runpy.run_path('/usr/local/libexec/devkit2023customlinux-install-storage')
state = Path('/run/devkit2023customlinux')
state.mkdir(mode=0o755, exist_ok=True)
state.chmod(0o755)
plan = json.loads(Path('/opt/handoff-test/plan.json').read_text())
record = {'plan': plan, 'phase': 'planned', 'efi_files': {}, 'boot_variables': {}}
api['save'](record)
snapshot = {'partitiontable': plan['before']}
def forbidden(*args, **kwargs):
    raise AssertionError('VM fixture cannot access device commands')
with patch.dict(api['capture'].__globals__, {'hardware': lambda: 'fixture',
        'current': lambda r: '/dev/nvme0n1', 'snapshot': lambda d: snapshot,
        'efi_inventory': lambda e: {}, 'boot_variables': lambda: {},
        'command': forbidden}):
    api['capture']()
''', 0o755)
write('opt/handoff-test/runner.py', '''#!/usr/bin/python3
import os, subprocess, time, stat, traceback
from pathlib import Path
def run(*args, **kw):
    return subprocess.run(args, text=True, capture_output=True, timeout=45, **kw)
def wait_window(title, timeout=180):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        r = run('xdotool', 'search', '--onlyvisible', '--name', title)
        if r.returncode == 0:
            return r.stdout.splitlines()[0]
        time.sleep(1)
    raise AssertionError('Window timeout: ' + title)
try:
    print('HANDOFF_VM: exact release kernel ' + os.uname().release, flush=True)
    os.environ['DISPLAY'] = ':77'
    runtime = Path('/run/user/1000')
    runtime.mkdir(parents=True, exist_ok=True)
    runtime.chmod(0o700)
    os.chown(runtime, 1000, 1000)
    display = subprocess.Popen(['Xvfb', ':77', '-screen', '0', '1280x800x24', '-nolisten', 'tcp', '-ac'])
    for _ in range(100):
        if Path('/tmp/.X11-unix/X77').exists(): break
        time.sleep(.2)
    env = ['HOME=/home/devkit', 'DISPLAY=:77', 'XDG_RUNTIME_DIR=/run/user/1000',
           'LC_ALL=C.UTF-8', 'QT_QPA_PLATFORM=xcb']
    logfile = open('/opt/handoff-test/user-launch.log', 'w')
    launch = subprocess.Popen(['runuser', '-u', 'devkit', '--', 'env', *env,
        'dbus-run-session', '--', '/usr/local/bin/devkit2023customlinux-installer'],
        stdout=logfile, stderr=subprocess.STDOUT)
    warning = wait_window('^Install DevKit2023CustomLinux$')
    plan = Path('/run/devkit2023customlinux/install-plan.json')
    assert plan.stat().st_uid == 0 and stat.S_IMODE(plan.stat().st_mode) == 0o600
    summary = plan.with_suffix('.txt')
    assert summary.stat().st_uid == 0 and stat.S_IMODE(summary.stat().st_mode) == 0o600
    assert 'WITHOUT formatting' in summary.read_text()
    denied = run('runuser', '-u', 'devkit', '--', 'cat', str(plan))
    assert denied.returncode != 0 and 'Permission denied' in denied.stderr
    print('HANDOFF_VM: normal-user launcher + real pkexec + root-only JSON passed', flush=True)
    run('xdotool', 'windowfocus', '--sync', warning)
    run('xdotool', 'key', '--window', warning, 'Return')
    main = wait_window('^DevKit2023CustomLinux Installer$')
    info = run('xwininfo', '-id', main).stdout
    assert 'IsViewable' in info
    print('HANDOFF_VM: continued warning into actual Calamares main window', flush=True)
    roots = run('pgrep', '-u', '0', '-x', 'calamares')
    assert roots.returncode == 0
    searchfile = Path('/home/devkit/handoff-search-needle.txt')
    searchfile.write_text('synthetic search fixture')
    os.chown(searchfile, 1000, 1000)
    # DBus-activated workers can inherit output descriptors. A regular log
    # avoids waiting on those descendants after the client itself has exited.
    searchlog = Path('/opt/handoff-test/search.log')
    with searchlog.open('w') as stream:
        result = subprocess.run(['runuser', '-u', 'devkit', '--', 'env', *env,
            'QT_NO_XDG_DESKTOP_PORTAL=1', 'dbus-run-session', '--', 'kioclient',
            'ls', 'filenamesearch:?search=handoff-search-needle&url=file:///home/devkit'],
            stdout=stream, stderr=subprocess.STDOUT, timeout=120)
    searchtext = searchlog.read_text()
    print('HANDOFF_VM: file search status ' + str(result.returncode), flush=True)
    print(searchtext[-3000:], flush=True)
    assert result.returncode == 0 and 'handoff-search-needle' in searchtext
    print('HANDOFF_VM_PASS: user handoff, real installer window and filename search. No Install click.', flush=True)
except BaseException:
    traceback.print_exc()
    for log in Path('/home/devkit/.local/state/devkit2023customlinux').glob('installer-*.log'):
        print(log.read_text()[-5000:], flush=True)
    print('HANDOFF_VM_FAIL', flush=True)
finally:
    subprocess.run(['systemctl', 'poweroff'])
''', 0o755)
write('etc/systemd/system/handoff-test.service', '''[Unit]
Description=VM-only installer user handoff test
After=dbus.service systemd-user-sessions.service polkit.service
Wants=dbus.service polkit.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -B /opt/handoff-test/runner.py
TimeoutStartSec=500
StandardOutput=journal+console
StandardError=journal+console
[Install]
WantedBy=multi-user.target
''')
run('chroot', ROOT, 'systemctl', 'enable', 'handoff-test.service')
image = WORK / 'rootfs.ext4'
run('truncate', '-s', '8G', image)
run('mkfs.ext4', '-q', '-F', '-d', ROOT, image)
kernel = next((SOURCE / 'build/rootfs/boot').glob('vmlinuz-*-devkit2023customlinux'))
print('VM-only fixture built; original release rootfs and kernel not changed.', flush=True)
with (WORK / 'serial.log').open('w') as log:
    result = subprocess.run(['timeout', '--signal=TERM', '--kill-after=10s', '600',
        'qemu-system-aarch64', '-machine', 'virt,gic-version=3', '-cpu', 'max',
        '-accel', 'tcg,thread=multi', '-smp', '2', '-m', '4096',
        '-kernel', str(kernel), '-append',
        'root=/dev/vda rw boot=live console=ttyAMA0 loglevel=4 systemd.unit=multi-user.target',
        '-drive', f'file={image},format=raw,if=none,id=vmroot',
        '-device', 'virtio-blk-pci,drive=vmroot', '-device', 'virtio-rng-pci', '-nic', 'none',
        '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-no-reboot'],
        stdout=log, stderr=subprocess.STDOUT)
output = (WORK / 'serial.log').read_text(errors='replace')
print(output[-8000:])
assert result.returncode == 0 and 'HANDOFF_VM_PASS:' in output and 'HANDOFF_VM_FAIL' not in output
