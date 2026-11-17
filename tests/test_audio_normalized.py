#!/usr/bin/env python3
"""Same-toolchain original/normalized DSP comparison (not hardware certification).
--source ROOT --scale VALUE --record FILE captures observations with build metadata;
it never replaces the frozen original source or historical observations.
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
MODES = (['-O1'], ['-O3', '-ffast-math', '-freciprocal-math'])
COMMON = ['-std=gnu11', '-DLXR_HOST_TEST', '-ffunction-sections', '-fdata-sections',
          '-fsanitize=address,undefined,float-cast-overflow', '-fno-sanitize-recover=all',
          '-Wno-deprecated-non-prototype']
CC = os.getenv('CC', 'clang')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, sources, scale, tmp):
    engine = (root/'Core/Src/Soundengine/Soundengine.c').read_text()
    renderer = engine.split('uint8_t soundengine_calcNextSampleBlock()', 1)[1].split('void soundengine_init()', 1)[0]
    (tmp/'float_renderer.h').write_text('uint8_t soundengine_calcNextSampleBlock()'+renderer)
    # Resolve textual production includes against the selected tree, not HERE.
    (tmp/'test_audio_float32.c').write_text((HERE/'test_audio_float32.c').read_text().replace('../Core/', str(root/'Core')+'/'))
    (tmp/'probe.c').write_bytes((HERE/'audio_normalized_probe.c').read_bytes())
    observations, commands = [], []
    for flags in MODES:
        cmd = [CC, *COMMON, '-DAUDIO_PROBE_SCALE='+scale, *flags,
               '-I'+str(tmp), '-I'+str(HERE), '-I'+str(HERE/'shim'),
               '-I'+str(root/'Core/Inc'), str(tmp/'probe.c'),
               *[str(root/s) for s in sources], '-lm', '-o', str(tmp/'probe')]
        cmd += ['-Wl,-dead_strip'] if platform.system() == 'Darwin' else ['-Wl,--gc-sections']
        subprocess.run(cmd, check=True)
        observations.append(subprocess.check_output([str(tmp/'probe')], text=True))
        commands.append(cmd)
    return observations, commands


def compare(old, new):
    failures = []
    if len(old) != 2 or len(new) != 2:
        return ["Expected both optimization modes"]
    for mode, before, after in zip(('O1', 'O3-fast'), old, new):
        b, n = before.splitlines(), after.splitlines()
        if not b or not n:
            failures.append(f'{mode}: empty observations')
        if len(b) != len(n):
            failures.append(f'{mode}: row count {len(b)} != {len(n)}')
        errors = defaultdict(list)
        for index, (x, y) in enumerate(zip(b, n)):
            try:
                k, v = x.split(); j, w = y.split()
                v, w = float(v), float(w)
                if k != j or not math.isfinite(v) or not math.isfinite(w):
                    raise ValueError('category mismatch or nonfinite sample')
                errors[k].append(abs(v-w)*32768)
            except ValueError as exc:
                failures.append(f'{mode} row {index}: {exc}: {x!r}, {y!r}')
        for category, diffs in errors.items():
            maximum = max(diffs)
            if not maximum < 0.02:
                failures.append(f'{mode} {category}: max-old-units={maximum:.9g} >= 0.02')
            print(f'{mode} {category}: n={len(diffs)} changed={sum(d != 0 for d in diffs)} '
                  f'max-old-units={maximum:.9g} rms-old-units={math.sqrt(sum(d*d for d in diffs)/len(diffs)):.9g}')
    return failures


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=HERE.parent)
    p.add_argument('--scale', default='32768.f')
    p.add_argument('--record', type=Path)
    a = p.parse_args()
    root = a.source.resolve()
    block = (root/'tests/CMakeLists.txt').read_text().split('add_executable(test_audio_float32 ', 1)[1].split('\n)', 1)[0]
    sources = re.findall(r'\$\{LXR_SOURCE_DIR\}/([^\s]+)', block)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        current, commands = run(root, sources, a.scale, tmp)
        if a.record:
            # Content hashes identify dirty trees too; do not label captures as 20e6e6b.
            identity = {str(f.relative_to(root)): digest(f) for folder in ('Core', 'tests')
                        for f in sorted((root/folder).rglob('*')) if f.is_file() and f.suffix in ('.c', '.h', '.txt', '.py')}
            metadata = {'compiler': subprocess.check_output([CC, '--version'], text=True),
                        'target': subprocess.check_output([CC, '-dumpmachine'], text=True).strip(),
                        'host': platform.platform(), 'host_machine': platform.machine(),
                        'source_root': str(root), 'source_sha256': identity,
                        'shared_test_sha256': {str(f.relative_to(HERE)): digest(f)
                                               for f in sorted(HERE.rglob('*'))
                                               if f.is_file() and f.suffix in ('.c', '.h', '.py')},
                        'commands': commands, 'scale': a.scale}
            a.record.write_bytes(gzip.compress(('# '+json.dumps(metadata, sort_keys=True)+'\n'+'# O3\n'.join(current)).encode(), mtime=0))
            return 0
        manifest = json.loads((HERE/'fixtures/audio_source_20e6e6b.json').read_text())
        original = tmp/'original'
        original.mkdir()
        with tarfile.open(HERE/'fixtures/audio_source_20e6e6b.tar.gz', 'r:gz') as archive:
            for member in archive:
                if member.name not in manifest['sha256'] or not member.isfile():
                    raise ValueError('unexpected archive member: '+member.name)
                data = archive.extractfile(member).read()
                if hashlib.sha256(data).hexdigest() != manifest['sha256'][member.name]:
                    raise ValueError('original source hash mismatch: '+member.name)
                dest = original/member.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
        for name, expected in manifest['sha256'].items():
            if digest(original/name) != expected:
                raise ValueError('original source hash mismatch: '+name)
        baseline, _ = run(original, manifest['sources'], '1.f', tmp)
        failures = compare(baseline, current)
        if failures:
            print('FAILURES:\n'+'\n'.join(failures))
        return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
