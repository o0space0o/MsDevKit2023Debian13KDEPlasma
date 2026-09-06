"""Windows-preserving GPT policy. Pure functions; never opens or writes a disk."""
from __future__ import annotations
import copy
import re
import uuid

ESP = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
MSR = 'e3c9e316-0b5c-4db8-817d-f92df00215ae'
WINDOWS = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
RECOVERY = 'de94bba4-06d1-4d40-a16a-bfd50179d6ac'
LINUX = '0fc63daf-8483-4772-8e79-3d69d8477de4'
MIN_ROOT = 32 * 1024**3
POLICY = 'windows-free-space-v1'


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('Invalid sector value')
    return value


def guid(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value.lower():
        raise ValueError('Invalid GPT identifier')
    if uuid.UUID(value).int == 0:
        raise ValueError('Empty GPT identifier')
    return value.lower()


def normalize(raw):
    """Validate a complete sfdisk JSON snapshot, retaining ALL partition fields."""
    table = copy.deepcopy(raw['partitiontable'])
    if table['label'] != 'gpt' or table['unit'] != 'sectors':
        raise ValueError('Only an existing Windows GPT disk is supported')
    table['id'] = guid(table['id'])
    sector = integer(table['sectorsize'])
    if sector not in (512, 4096):
        raise ValueError('Unsupported sector size')
    first, last = integer(table['firstlba']), integer(table['lastlba'])
    if first < 2 or last <= first:
        raise ValueError('Invalid GPT usable range')
    parts = table['partitions']
    if not isinstance(parts, list) or not 3 <= len(parts) < 128:
        raise ValueError('Unsupported partition layout')
    nodes, identifiers, numbers = set(), set(), []
    for part in parts:
        start, size = integer(part['start']), integer(part['size'])
        if size == 0 or start < first or start + size - 1 > last:
            raise ValueError('Partition outside GPT usable range')
        part['type'] = guid(part['type'])
        identifier = part['uuid'] = guid(part['uuid'])
        # Linux exposes NVMe/loop partition names with pN; no shell evaluation.
        match = re.fullmatch(re.escape(table['device']) + r'p([1-9][0-9]*)', part['node'])
        if not match or part['node'] in nodes or identifier in identifiers:
            raise ValueError('Ambiguous partition identity')
        nodes.add(part['node'])
        identifiers.add(identifier)
        numbers.append(int(match[1]))
    if sorted(numbers) != list(range(1, len(parts) + 1)):
        raise ValueError('Non-contiguous partition numbering is not supported')
    ordered = sorted(parts, key=lambda part: part['start'])
    if any(a['start'] + a['size'] > b['start'] for a, b in zip(ordered, ordered[1:])):
        raise ValueError('Overlapping GPT partitions')
    return table


def plan(raw, root_guid=None):
    table = normalize(raw)
    parts = table['partitions']
    types = [p['type'].lower() for p in parts]
    if types.count(ESP) != 1 or types.count(MSR) != 1 or WINDOWS not in types:
        raise ValueError('One Windows EFI/MSR layout is required')
    if any(t not in (ESP, MSR, WINDOWS, RECOVERY) for t in types):
        raise ValueError('An existing Linux or unknown partition is present; reinstall is not supported')
    efi = next(p for p in parts if p['type'].lower() == ESP)
    if efi['size'] * table['sectorsize'] < 100 * 1024**2:
        raise ValueError('EFI partition is smaller than 100 MiB')
    alignment = 1024**2 // table['sectorsize']
    gaps = []
    cursor = table['firstlba']
    for part in sorted(parts, key=lambda p: p['start']) + [{'start': table['lastlba'] + 1, 'size': 0}]:
        start = ((cursor + alignment - 1) // alignment) * alignment
        end = (part['start'] // alignment) * alignment
        if end - start >= MIN_ROOT // table['sectorsize']:
            gaps.append((end - start, start))
        cursor = part['start'] + part['size']
    if not gaps:
        raise ValueError('No unallocated space of at least 32 GiB. Free space in Windows Disk Management first; 64 GiB is recommended')
    size, start = max(gaps)
    root = {'node': table['device'] + 'p' + str(len(parts) + 1),
            'start': start, 'size': size, 'type': LINUX,
            'uuid': guid(root_guid or str(uuid.uuid4())), 'name': 'DevKit2023CustomLinux'}
    if root['uuid'] in {p['uuid'].lower() for p in parts}:
        raise ValueError('Duplicate new partition identity')
    return {'policy': POLICY, 'before': table, 'root': root, 'efi': copy.deepcopy(efi)}


def validate_plan(value):
    expected = plan({'partitiontable': value['before']}, value['root']['uuid'])
    if value != expected:
        raise ValueError('Installation plan was changed or is unsupported')


def check_before(value, raw):
    validate_plan(value)
    if normalize(raw) != value['before']:
        raise ValueError('Disk layout changed since confirmation; no formatting is allowed')


def check_after(value, raw):
    validate_plan(value)
    table = normalize(raw)
    before = copy.deepcopy(value['before'])
    actual = table.pop('partitions')
    original = before.pop('partitions')
    if table != before or len(actual) != len(original) + 1:
        raise ValueError('Unexpected GPT modification')
    by_node = {p['node']: p for p in actual}
    if any(by_node.get(p['node']) != p for p in original):
        raise ValueError('An original Windows/EFI/MSR/Recovery partition changed')
    if by_node.get(value['root']['node']) != value['root']:
        raise ValueError('New Linux partition does not match the confirmed plan')


def sfdisk_input(value):
    validate_plan(value)
    root = value['root']
    return (f'start={root["start"]}, size={root["size"]}, type={LINUX}, '
            f'uuid={root["uuid"]}, name="DevKit2023CustomLinux"\n')


def describe(value):
    validate_plan(value)
    size = value['root']['size'] * value['before']['sectorsize'] / 1024**3
    return (f'Install DevKit2023CustomLinux alongside Windows on {value["before"]["device"]}.\n\n'
            f'Create ONE new ext4 Linux partition: {size:.1f} GiB of existing unallocated space.\n'
            f'Reuse {value["efi"]["node"]} for Linux boot files WITHOUT formatting it.\n'
            'Do not resize, format or remove any existing partition.\n'
            'Keep Windows Boot Manager and add DevKit2023CustomLinux to the boot menu.\n\n'
            'Back up important files and keep Windows recovery media before continuing. '
            'This first-install route does not support reinstalling over an existing Linux system. '
            'The final Install confirmation in the next window starts disk changes.')
