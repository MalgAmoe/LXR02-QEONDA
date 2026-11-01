#!/usr/bin/env python3
"""Compile actual Decay.c; only HAL/section configuration is stubbed for host."""
from pathlib import Path
import os, subprocess, tempfile
root=Path(__file__).resolve().parents[1]
cc=os.environ.get('CC','cc')
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'Soundengine/DSPAudio').mkdir(parents=True)
 (p/'Soundengine/DSPAudio/Decay.h').write_bytes((root/'Core/Inc/Soundengine/DSPAudio/Decay.h').read_bytes())
 (p/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
 source=root/'Core/Src/Soundengine/DSPAudio/Decay.c'
 if os.environ.get('LXR_BASE_REV'):
  source=p/'Decay.c'
  source.write_bytes(subprocess.check_output(['git','-C',str(root),'show',os.environ['LXR_BASE_REV']+':Core/Src/Soundengine/DSPAudio/Decay.c']))
 for big in (0,1):
  (p/'Soundengine/config.h').write_text(f'#define IN_ITCM_RAM\n#define USE_BIG_SAMPLE_BUFFER {big}\n')
  for flags in (['-O2'],['-O3','-ffast-math','-freciprocal-math']):
   common=[cc,'-fsanitize=address,undefined','-I'+tmp]
   subprocess.run(common+flags+['-c',str(source),'-o',str(p/'decay.o')],check=True)
   subprocess.run(common+['-O2',str(p/'decay.o'),str(root/'tests/test_decay_endpoints.c'),'-lm','-o',str(p/'test')],check=True)
   print('buffer',big,'flags',flags,flush=True)
   subprocess.run([str(p/'test')],check=True)
