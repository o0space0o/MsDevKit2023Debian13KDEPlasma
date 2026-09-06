#!/usr/bin/env python3
"""Read-only source inventory, link, syntax and archive checks. No target access."""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAP = "config/project-map.json"
INDEX = "docs/FILE-INDEX.md"
IGNORED_ROOTS = {"build", ".git", "ISO"}
PUBLIC_DOCUMENTS = {"docs/DevKit2023CustomLinux-Guide.pdf"}
FORBIDDEN_SUFFIXES = {
    ".mbn", ".cat", ".inf", ".sys", ".reg", ".hiv", ".log", ".iso",
    ".deb", ".pdf", ".png", ".jpg", ".jpeg", ".heic", ".webp", ".pyc", ".pyo",
    ".zip", ".gz", ".qcow2", ".img",
}
PRIVATE_TEXT = re.compile(
    r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+"
)


def inventory(root: Path) -> tuple[dict, list[str]]:
    data = json.loads((root / MAP).read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise ValueError("unsupported project map schema")
    files: list[str] = []
    ids = set()
    for component in data["components"]:
        if component["id"] in ids:
            raise ValueError("duplicate component ID")
        ids.add(component["id"])
        if not component["purpose"] or not component["status"]:
            raise ValueError("component purpose/status required")
        for name in component["files"]:
            path = PurePosixPath(name)
            if (path.is_absolute() or ".." in path.parts or path.as_posix() != name
                    or not re.fullmatch(r"[A-Za-z0-9_.\-/]+", name)
                    or path.parts[0] in IGNORED_ROOTS):
                raise ValueError(f"unsafe inventory path: {name!r}")
            files.append(name)
    if len(files) != len(set(files)):
        raise ValueError("duplicate inventory file")
    for component in data["components"]:
        if not set(component.get("dependsOn", [])).issubset(ids):
            raise ValueError("unknown component dependency")
    return data, sorted(files)


def render_index(data: dict) -> str:
    lines = ["# File index", "", "Generated from `config/project-map.json`. Every active source file is listed.",
             "Update with `python3 -B scripts/check-source.py --render-index`; normal checks reject drift.", ""]
    for component in data["components"]:
        lines.extend(["## " + component["title"], "", component["purpose"], "",
                      "Status: " + component["status"] + ".", ""])
        for name in sorted(component["files"]):
            lines.append(f"- [{name}](../{name})")
        lines.append("")
    return "\n".join(lines)


def inspect_tree(root: Path, expected: list[str]) -> tuple[list[str], dict[str, str]]:
    errors: list[str] = []
    actual = set()
    texts: dict[str, str] = {}
    parents = {str(parent) for name in expected for parent in PurePosixPath(name).parents}
    for directory, dirs, names in os.walk(root, followlinks=False):
        folder = Path(directory)
        for child in list(dirs):
            path = folder / child
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                errors.append(f"symlinked directory: {relative}")
                dirs.remove(child)
            elif folder == root and child in IGNORED_ROOTS:
                dirs.remove(child)
            elif relative not in parents:
                errors.append(f"unregistered directory: {relative}")
                dirs.remove(child)
        for name in names:
            path = folder / name
            relative = path.relative_to(root).as_posix()
            actual.add(relative)
            if path.is_symlink() or not path.is_file():
                errors.append(f"non-regular source file: {relative}")
                continue
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                if relative in PUBLIC_DOCUMENTS:
                    if not path.read_bytes().startswith(b'%PDF-'):
                        errors.append(f"invalid public PDF: {relative}")
                    continue
                errors.append(f"private/generated payload type: {relative}")
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"non-UTF8 source payload: {relative}")
                continue
            texts[relative] = text
            if "\0" in text or PRIVATE_TEXT.search(text):
                errors.append(f"binary or fixed device/profile data: {relative}")
            if relative.endswith(".py") or text.startswith(("#!/usr/bin/env python3", "#!/usr/bin/python3")):
                try:
                    ast.parse(text, filename=relative)
                except SyntaxError as exc:
                    errors.append(f"Python syntax: {relative}:{exc.lineno}")
    errors.extend(f"unregistered file: {name}" for name in sorted(actual - set(expected)))
    errors.extend(f"missing file: {name}" for name in sorted(set(expected) - actual))
    return errors, texts


def inspect_links(root: Path, texts: dict[str, str]) -> list[str]:
    errors = []
    for name, text in texts.items():
        if not name.endswith(".md"):
            continue
        for target in re.findall(r"\[[^\]\n]*\]\(([^)\s]+)\)", text):
            parts = urlsplit(target)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            linked = ((root / name).parent / unquote(parts.path)).resolve()
            if not linked.is_relative_to(root.resolve()) or not linked.exists():
                errors.append(f"broken/outside local link in {name}: {target}")
    return errors


def inspect_services(root: Path, texts: dict[str, str]) -> list[str]:
    errors = []
    overlays = (root / 'overlay', root / 'profiles/prepared/overlay')
    for name, text in texts.items():
        if not any(name.startswith(prefix + '/etc/systemd/system/') for prefix in ('overlay', 'profiles/prepared/overlay')):
            continue
        for command in re.findall(r"^Exec(?:Start|StartPre|StartPost|Stop|StopPost)=[-+!:@]*([^\s]+)", text, re.M):
            if command.startswith("/usr/local/") and not any((overlay / command.lstrip('/')).is_file() for overlay in overlays):
                errors.append(f"missing local service executable: {name} -> {command}")
    return errors


def inspect_archive(root: Path, archive: Path, expected: list[str]) -> list[str]:
    errors = []
    with tarfile.open(archive, "r:gz") as stream:
        members = stream.getmembers()
        names = [member.name for member in members]
        if sorted(names) != expected or len(set(names)) != len(names):
            errors.append("archive file inventory differs from source")
        for member in members:
            if member.name not in expected or not member.isfile() or member.mode != 0o644:
                errors.append("unexpected archive entry/type/mode")
                continue
            content = stream.extractfile(member)
            if content is None or content.read() != (root / member.name).read_bytes():
                errors.append(f"archive content mismatch: {member.name}")
            if member.uid != 0 or member.gid != 0 or member.mtime != 0:
                errors.append(f"non-normalized archive metadata: {member.name}")
    return errors


def check(root: Path, shell: bool = False) -> list[str]:
    data, expected = inventory(root)
    errors, texts = inspect_tree(root, expected)
    errors.extend(inspect_links(root, texts))
    errors.extend(inspect_services(root, texts))
    if texts.get(INDEX, "").rstrip() != render_index(data).rstrip():
        errors.append("file index is stale; review --render-index output")
    if shell:
        for name, text in texts.items():
            line = text.partition("\n")[0]
            if line in {"#!/bin/sh", "#!/bin/bash", "#!/usr/bin/env bash"}:
                interpreter = "sh" if line == "#!/bin/sh" else "bash"
                result = subprocess.run([interpreter, "-n", str(root / name)], capture_output=True, text=True)
                if result.returncode:
                    errors.append(f"shell syntax: {name}: {result.stderr.strip()}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", action="store_true", help="also parse shell scripts without running them")
    parser.add_argument("--render-index", action="store_true", help="print the generated Markdown index")
    parser.add_argument("--list-files", action="store_true", help="print validated source paths for packaging")
    parser.add_argument("--archive", type=Path, help="verify source archive inventory, bytes and metadata")
    args = parser.parse_args()
    try:
        data, expected = inventory(ROOT)
        if args.render_index:
            print(render_index(data), end="")
            return 0
        errors = check(ROOT, shell=args.shell)
        if args.archive:
            errors.extend(inspect_archive(ROOT, args.archive, expected))
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        if args.list_files:
            print("\n".join(expected))
        else:
            print(f"Source checks passed: {len(expected)} files, {len(data['components'])} components.")
        return 0
    except (ValueError, KeyError, OSError, tarfile.TarError) as exc:
        print(f"Source check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
