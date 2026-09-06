"""The sole partition-writing Calamares job: one confirmed free-space plan."""
import json
from pathlib import Path
import subprocess
import libcalamares


def pretty_name():
    return 'Install alongside Windows in unallocated space'


def pretty_description():
    import html
    return '<p>' + html.escape(Path('/run/devkit2023customlinux/install-plan.txt').read_text()).replace('\n', '<br/>') + '</p>'


def run():
    result = subprocess.run(['/usr/local/libexec/devkit2023customlinux-install-storage', 'apply'],
                            capture_output=True, text=True, timeout=600)
    if result.returncode:
        return ('Installation stopped safely', result.stderr)
    data = json.loads(result.stdout)
    libcalamares.globalstorage.insert('partitions', data['partitions'])
    libcalamares.globalstorage.insert('firmwareType', 'efi')
    libcalamares.globalstorage.insert('efiSystemPartition', '/boot/efi')
    libcalamares.globalstorage.insert('partitionChoices', {'swap': 'file'})
