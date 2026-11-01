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
    assert not re.search(r'\bvmax(?:nm)?\.f32\b', text), text
    print(f'{name}: {conversions} vcvt.u32.f32; FM multiply directly followed by conversion; no vmax/vmaxnm.f32')
    if args.baseline:
        old = subprocess.check_output([objdump, '-d', '--disassemble='+name, str(args.baseline)], text=True)
        assert len(re.findall(r'\bvmaxnm\.f32\b', old)) == 1, old
        assert len(re.findall(r'\bvcvt\.u32\.f32\b', old)) == conversions, old
        print(f'  baseline: one vmaxnm.f32 and {conversions} vcvt.u32.f32')
    print(text)
