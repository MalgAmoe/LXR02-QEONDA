#!/usr/bin/env python3
"""Inspect a built production ELF; not a host model or hardware timing test.
Usage: python3 tests/check_fm_arm_codegen.py build/release [--baseline ELF]
Rebuild release first; this script does not establish ELF freshness.
"""
import argparse
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('build', type=Path)
parser.add_argument('--baseline', type=Path)
args = parser.parse_args()
cache = (args.build / 'CMakeCache.txt').read_text()
objdump = re.search(r'^CMAKE_OBJDUMP:FILEPATH=(.+)$', cache, re.M)[1]
elf = args.build / 'LXR_V2_STM32F765.elf'
for name in ('calcFmSineBlock', 'calcFmBlock', 'calcPwmFmBlock'):
    text = subprocess.check_output([objdump, '-d', '--disassemble='+name, str(elf)], text=True)
    assert '<'+name+'>:' in text, name
    conversions = 2 if name == 'calcPwmFmBlock' else 1  # PWM offset plus FM
    assert len(re.findall(r'\bvcvt\.u32\.f32\b', text)) == conversions, text
    assert re.search(r'vmul\.f32[^\n]*\n[^\n]*vcvt\.u32\.f32', text), text
    float_pwm = name == 'calcPwmFmBlock'
    if float_pwm:
        # Original QSUB16 PWM waveform saturation becomes float min/max.
        # It must follow the FM conversion, never guard its negative input.
        last_conversion = list(re.finditer(r'\bvcvt\.u32\.f32\b', text))[-1].end()
        assert not re.search(r'\bvmax(?:nm)?\.f32\b', text[:last_conversion]), text
        assert len(re.findall(r'\bvmaxnm\.f32\b', text)) == 1, text
        assert len(re.findall(r'\bvminnm\.f32\b', text)) == 1, text
    else:
        assert not re.search(r'\bvmax(?:nm)?\.f32\b', text), text
    print(f'{name}: {conversions} vcvt.u32.f32; direct FM multiply/conversion; '
          + ('one downstream PWM waveform bound' if float_pwm else 'no vmax/vmaxnm.f32'))
    if args.baseline:
        old = subprocess.check_output([objdump, '-d', '--disassemble='+name, str(args.baseline)], text=True)
        assert len(re.findall(r'\bvmaxnm\.f32\b', old)) == 1, old
        assert len(re.findall(r'\bvcvt\.u32\.f32\b', old)) == conversions, old
        print(f'  baseline: one vmaxnm.f32 and {conversions} vcvt.u32.f32')
    print(text)
