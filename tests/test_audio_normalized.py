#!/usr/bin/env python3
"""Compile a deterministic production probe; compare frozen 20e6e6b observations.
Optional --source ROOT --scale 1 --record FILE captures an independently supplied
baseline tree. Ordinary tests need neither Git history nor baseline build files.
Host observations are not target audio/timing certification. Negative FM is
covered by test_wavetable_wrap's labeled ARM model, not this nonnegative probe.
"""
import argparse
import gzip
from collections import defaultdict
from pathlib import Path
import os
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, default=HERE.parent)
p.add_argument('--scale', default='32768.f')
p.add_argument('--record', type=Path)
a = p.parse_args()
root = a.source.resolve()
cmake = (root/'tests/CMakeLists.txt').read_text()
block = cmake.split('add_executable(test_audio_float32 ', 1)[1].split('\n)', 1)[0]
sources = re.findall(r'\$\{LXR_SOURCE_DIR\}/([^\s]+)', block)
engine = (root/'Core/Src/Soundengine/Soundengine.c').read_text()
renderer = engine.split('uint8_t soundengine_calcNextSampleBlock()', 1)[1].split('void soundengine_init()', 1)[0]
fixture = HERE/'fixtures/audio_baseline_20e6e6b.txt.gz'
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    (tmp/'float_renderer.h').write_text('uint8_t soundengine_calcNextSampleBlock()'+renderer)
    (tmp/'probe.c').write_bytes((HERE/'audio_normalized_probe.c').read_bytes())
    observations = []
    for flags in (['-O1'], ['-O3', '-ffast-math', '-freciprocal-math']):
        cmd = [os.getenv('CC', 'clang'), '-std=gnu11', '-DLXR_HOST_TEST',
               '-DAUDIO_PROBE_SCALE='+a.scale, *flags, '-ffunction-sections', '-fdata-sections',
               '-fsanitize=address,undefined,float-cast-overflow', '-fno-sanitize-recover=all',
               '-Wno-deprecated-non-prototype', '-I'+str(tmp), '-I'+str(root/'tests'),
               '-I'+str(root/'tests/shim'), '-I'+str(root/'Core/Inc'),
               str(tmp/'probe.c'), *[str(root/s) for s in sources], '-lm', '-o', str(tmp/'probe')]
        cmd += ['-Wl,-dead_strip'] if os.uname().sysname == 'Darwin' else ['-Wl,--gc-sections']
        subprocess.run(cmd, check=True)
        observations.append(subprocess.check_output([str(tmp/'probe')], text=True))
    if a.record:
        a.record.write_bytes(gzip.compress(('# Baseline 20e6e6b; AppleClang 17; O1 then O3 fast-math; normalized observations\n'+'# O3\n'.join(observations)).encode(), mtime=0))
    else:
        old = gzip.decompress(fixture.read_bytes()).decode().split('\n', 1)[1].split('# O3\n')
        assert len(old) == len(observations) == 2
        for mode, before, after in zip(('O1', 'O3-fast'), old, observations):
            b, n = before.splitlines(), after.splitlines()
            assert len(b) == len(n)
            errors = defaultdict(list)
            for x, y in zip(b, n):
                k, v = x.split(); j, w = y.split(); assert j == k
                errors[k].append(abs(float(v)-float(w)))
            for category, diffs in errors.items():
                # 0.02 old units: explicit regression ceiling, not equivalence.
                assert max(diffs)*32768 < 0.02, (mode, category, max(diffs)*32768)
                print(f'{mode} {category}: n={len(diffs)} changed={sum(d != 0 for d in diffs)} '
                      f'max-old-units={max(diffs)*32768:.9g} rms-old-units='
                      f'{(sum(d*d for d in diffs)/len(diffs))**0.5*32768:.9g}')
