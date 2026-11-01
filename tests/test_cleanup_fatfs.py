#!/usr/bin/env python3
"""Real bundled FatFs, production config, RAM FAT32 disk; no physical media.
Only host integer widths and HAL-only header dependencies are adapted.
LXR_BASE_REV selects older cleanup for a differential operation-count run.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    for name in ('ff.c', 'ff.h', 'diskio.h', 'integer.h'):
        shutil.copyfile(root / 'Middlewares/Third_Party/FatFs/src' / name, d / name)
    p = d / 'integer.h'
    s = p.read_text().replace('typedef long\t\t\tLONG;', 'typedef int LONG;').replace('typedef unsigned long\tDWORD;', 'typedef unsigned int DWORD;')
    p.write_text(s)
    config = (root / 'FATFS/Target/ffconf.h').read_text()
    for h in ('main.h', 'stm32f7xx_hal.h', 'bsp_driver_sd.h'):
        config = config.replace(f'#include "{h}"', '')
    (d / 'ffconf.h').write_text(config)
    source = root / 'Core/Src/Preset/SafeStorage.c'
    if os.getenv('LXR_BASE_REV'):
        source = d / 'SafeStorage.c'
        source.write_bytes(subprocess.check_output(['git', '-C', str(root), 'show', os.environ['LXR_BASE_REV'] + ':Core/Src/Preset/SafeStorage.c']))
    exe = d / 'test'
    subprocess.run([os.getenv('CC', 'cc'), '-std=c11', '-g', '-fsanitize=address,undefined', '-Wno-deprecated-declarations', '-I'+str(d), '-I'+str(root/'Core/Inc'), str(d/'ff.c'), str(source), str(root/'tests/test_cleanup_fatfs.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
