#!/usr/bin/env python3
"""Package the portable diagnostics launcher, hidden helper and directions."""
import argparse
import ast
import hashlib
from pathlib import Path
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
DESKTOP = PROJECT / 'overlay/etc/skel/Desktop'
HELPER = PROJECT / 'overlay/usr/local/libexec/devkit2023customlinux-diagnostics'


def portable_launcher():
    text = (DESKTOP / 'DevKit2023Diagnostics.desktop').read_text()
    original = next(line for line in text.splitlines() if line.startswith('Exec='))
    replacement = ('Exec=python3 -B -c "import pathlib,runpy,sys; from urllib.parse import unquote,urlsplit; '
        "p=pathlib.Path(unquote(urlsplit(sys.argv[1]).path)); h=p.parent/'.support/devkit2023customlinux-diagnostics'; "
        "sys.argv=[str(h),'--gui','--launcher',str(p)]; runpy.run_path(str(h),run_name='__main__')\" %k")
    return text.replace(original, replacement).encode()


def package(output):
    output = output.resolve()
    if output.exists() or output.is_relative_to(PROJECT) or output.parent == output:
        raise ValueError('Use a new output directory outside the source tree')
    output.mkdir(parents=True)
    version = next(ast.literal_eval(node.value) for node in ast.parse(HELPER.read_text()).body
                   if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'VERSION'
                                                            for t in node.targets))
    if not isinstance(version, str) or not version.replace('.', '').isdecimal():
        raise ValueError('Invalid diagnostics version')
    archive = output / ('DevKit2023CustomLinux-Diagnostics-' + version + '.zip')
    files = [(portable_launcher(), 'DevKit2023Diagnostics.desktop', 0o755),
             (HELPER.read_bytes(), '.support/devkit2023customlinux-diagnostics', 0o755),
             ((PROJECT / 'docs/TESTER.md').read_bytes(), 'README.md', 0o644)]
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as stream:
        for content, name, mode in files:
            info = zipfile.ZipInfo('DevKit2023CustomLinux-Diagnostics/' + name, (2026, 9, 5, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            stream.writestr(info, content)
    with zipfile.ZipFile(archive) as stream:
        if stream.testzip() is not None or len(stream.infolist()) != 3:
            raise ValueError('Archive verification failed')
        for content, name, mode in files:
            entry = 'DevKit2023CustomLinux-Diagnostics/' + name
            if stream.read(entry) != content:
                raise ValueError('Archive differs from source')
            if stream.getinfo(entry).external_attr >> 16 & 0o777 != mode:
                raise ValueError('Archive executable permissions differ')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(package(args.output))
