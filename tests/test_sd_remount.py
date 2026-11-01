#!/usr/bin/env python3
"""Actual preset wrappers/main remount against bundled FatFs on a RAM disk.
Uses the cleanup harness host-width/config adaptations. LXR_BASE_REV selects
baseline wrapper and main sources for a red/green differential test.
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
    source_text = (root/'Core/Src/Preset/presetManager.c').read_text()
    if os.getenv('LXR_BASE_REV'):
        source_text = subprocess.check_output(['git', '-C', str(root), 'show', os.environ['LXR_BASE_REV']+':Core/Src/Preset/presetManager.c'], text=True)
    helpers = source_text[source_text.index('static FRESULT preset_writeResult'):source_text.index('unsigned char preset_projectCleanupWarning;')]
    main = (root/'Core/Src/main.c').read_text()
    if os.getenv('LXR_BASE_REV'):
        main = subprocess.check_output(['git', '-C', str(root), 'show', os.environ['LXR_BASE_REV']+':Core/Src/main.c'], text=True)
    sequence = main[main.index('const uint8_t bg = soundengine_backgroundAudioBegin();', main.index('//check SD card')):main.index('soundengine_backgroundAudioEnd(bg);', main.index('//check SD card'))+len('soundengine_backgroundAudioEnd(bg);')]
    harness = (root/'tests/test_sd_remount.c').read_text()
    (d/'test.c').write_text(harness.replace('/* HELPERS */', helpers).replace('/* REMOUNT */', sequence))
    exe = d/'test'
    subprocess.run([os.getenv('CC','cc'), '-std=c11', '-g', '-fsanitize=address,undefined', '-Wno-deprecated-declarations', '-I'+str(d), str(d/'ff.c'), str(d/'test.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
