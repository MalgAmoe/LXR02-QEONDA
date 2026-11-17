"""Validate the normal QEONDA image before release; emit its SHA-256 manifest."""
import hashlib
import json
import re
from pathlib import Path
import struct
import sys


def metadata(directory):
    value = json.loads((directory / 'release-metadata.json').read_text())
    if (not isinstance(value, dict) or set(value) != {'version', 'image', 'payload'} or
            not isinstance(value['version'], str) or
            not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?', value['version']) or
            value['image'] != f"LXR_QEONDA_V{value['version']}.img" or
            value['payload'] != 'LXR_V2_STM32F765.bin'):
        raise ValueError('Invalid release metadata')
    # Only exact, local filenames are accepted; never discover images by glob.
    for key in ('image', 'payload'):
        path = directory / value[key]
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing or non-local {key}')
    return value


def verify(directory):
    info = metadata(directory)
    image = directory / info['image']
    data = image.read_bytes()
    binary = (directory / info['payload']).read_bytes()
    if len(data) < 16:
        raise ValueError('Truncated image header')
    magic, size, checksum = struct.unpack('<8sIB3x', data[:16])
    if (magic != b'LXRV2IMG' or not size or size % 4 or
            size != len(binary) or data[16:] != binary or
            (sum(binary) + checksum) & 255 != 255):
        raise ValueError('Invalid image header, payload or checksum')
    commands = json.loads((directory / 'compile_commands.json').read_text())
    if not commands or any('LXR_MEASUREMENT' in entry.get('command', ' '.join(entry.get('arguments', [])))
                           for entry in commands):
        raise ValueError('Missing build commands or measurement definition present')
    digest = hashlib.sha256(data).hexdigest()
    (directory / 'SHA256SUMS').write_text(f'{digest}  {image.name}\n')
    print(f'Validated {image.name}: {size} payload bytes, SHA256 {digest}')
    return info


if __name__ == '__main__':
    info = verify(Path(sys.argv[1]))
    if len(sys.argv) == 3:
        with open(sys.argv[2], 'a') as output:
            output.write(f"version={info['version']}\nimage={info['image']}\n")
