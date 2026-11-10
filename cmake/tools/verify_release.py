"""Validate the normal QEONDA image before release; emit its SHA-256 manifest."""
import hashlib
import json
from pathlib import Path
import struct
import sys


def verify(directory):
    image = directory / 'LXR_QEONDA_V0.2.img'
    data = image.read_bytes()
    binary = (directory / 'LXR_V2_STM32F765.bin').read_bytes()
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


if __name__ == '__main__':
    verify(Path(sys.argv[1]))
