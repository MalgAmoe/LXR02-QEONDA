#!/usr/bin/env python3
"""Inspect the integrated float experiment ELF, not cycles or hardware behaviour."""
import argparse
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('build', type=Path)
args = parser.parse_args()
cache = (args.build / 'CMakeCache.txt').read_text()
assert re.search(r'^LXR_AUDIO_FLOAT32:BOOL=ON$', cache, re.M)
objdump = re.search(r'^CMAKE_OBJDUMP:FILEPATH=(.+)$', cache, re.M)[1]
elf = args.build / 'LXR_V2_STM32F765.elf'
for name in ('mixer_calcNextSampleBlock', 'FxBus_process', 'Distortion_process',
             'Ringmod_process', 'Compressor_process', 'Delay_process',
             'Delay_processPingPong', 'calcWavetableOscBlock'):
    text = subprocess.check_output([objdump, '-d', '--disassemble='+name, str(elf)], text=True)
    assert '<'+name+'>:' in text, name
    assert not re.search(r'\b(?:qadd16|qsub16|ssat)\b', text), text
    assert not re.search(r'\bv(?:add|sub|mul|div|fma|fms)\.f64\b', text), text
    assert re.search(r'\bv(?:add|sub|mul|div|fma|fms)\.f32\b', text), text
    if re.search(r'^LXR_FLOAT_MIX_CLIP:BOOL=ON$', cache, re.M) and name != 'calcWavetableOscBlock':
        assert 'vminnm.f32' in text and 'vmaxnm.f32' in text, name
    if name == 'calcWavetableOscBlock':
        assert 'ldrsh' in text and 'vfma.f32' in text, text
    print(name+': float32 arithmetic, no packed integer saturation or float64 arithmetic')
# The FM-specific checker separately distinguishes phase conversion from PWM's
# deliberate waveform clip. Original float64 distortion tables may still load
# and convert to float32: this check does not require regenerating any table.
