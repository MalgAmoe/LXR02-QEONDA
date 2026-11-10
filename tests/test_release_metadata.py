#!/usr/bin/env python3
"""Release metadata and exact-image validation; no ARM tools required."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('verify_release', Path(__file__).resolve().parents[1] / 'cmake/tools/verify_release.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ReleaseMetadata(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.info = dict(version='0.2', image='LXR_QEONDA_V0.2.img', payload='LXR_V2_STM32F765.bin')
        self.write_metadata()
        payload = b'\x01\x02\x03\x04'
        (self.root / self.info['payload']).write_bytes(payload)
        (self.root / self.info['image']).write_bytes(struct.pack('<8sIB3x', b'LXRV2IMG', 4, 255-sum(payload)) + payload)
        (self.root / 'compile_commands.json').write_text('[{"command":"cc normal.c"}]')

    def write_metadata(self):
        (self.root / 'release-metadata.json').write_text(json.dumps(self.info))

    def test_exact_image_ignores_stale_neighbor(self):
        (self.root / 'LXR_QEONDA_V0.1.img').write_bytes(b'stale')
        self.assertEqual(validator.verify(self.root), self.info)
        self.assertIn(self.info['image'], (self.root / 'SHA256SUMS').read_text())

    def test_missing_and_malformed_metadata(self):
        path = self.root / 'release-metadata.json'
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            validator.verify(self.root)
        for text in ('{', '[]', '{}', '{"version":null}'):
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    validator.verify(self.root)

    def test_ci_outputs(self):
        output = self.root / 'outputs'
        subprocess.run([sys.executable, str(spec.origin), str(self.root), str(output)], check=True)
        self.assertEqual(output.read_text(), 'version=0.2\nimage=LXR_QEONDA_V0.2.img\n')

    def test_missing_payload(self):
        (self.root / self.info['payload']).unlink()
        with self.assertRaises(ValueError):
            validator.verify(self.root)

    def test_wrong_paths_and_version(self):
        for key, value in [('payload', '../LXR_V2_STM32F765.bin'), ('payload', '/tmp/payload.bin'),
                           ('payload', 'wrong.bin'), ('image', '../LXR_QEONDA_V0.2.img'),
                           ('version', '0.1'), ('version', 2)]:
            with self.subTest(key=key, value=value):
                old = self.info[key]
                self.info[key] = value
                self.write_metadata()
                with self.assertRaises(ValueError):
                    validator.verify(self.root)
                self.info[key] = old

    def test_stale_image_is_not_fallback(self):
        (self.root / self.info['image']).rename(self.root / 'LXR_QEONDA_V0.1.img')
        with self.assertRaises(ValueError):
            validator.verify(self.root)

    def test_wrong_payload_and_truncated_image(self):
        (self.root / self.info['payload']).write_bytes(b'bad!')
        with self.assertRaises(ValueError):
            validator.verify(self.root)
        (self.root / self.info['image']).write_bytes(b'short')
        with self.assertRaises(ValueError):
            validator.verify(self.root)

    def test_symlink_payload_rejected(self):
        path = self.root / self.info['payload']
        path.rename(self.root / 'other.bin')
        path.symlink_to('other.bin')
        with self.assertRaises(ValueError):
            validator.verify(self.root)


if __name__ == '__main__':
    unittest.main()
