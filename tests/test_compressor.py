#!/usr/bin/env python3
"""Actual production TUs and headers; host-only platform/intrinsic shims.
LXR_BASE_REV selects historical Compressor.c without modelling its conversion.
"""
from pathlib import Path
import os, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
 p = Path(tmp)
 def shim(name, text):
  f = p/name; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text)
 shim('Soundengine/globals.h', '#pragma once\n#include <stdint.h>\n#include <stddef.h>\n#include "main.h"\n')
 shim('Soundengine/config.h', '#pragma once\n#define REAL_FS 44140\n#define IN_ITCM_RAM\n#define INDTCMZ\n#define __fp16 _Float16\n')
 shim('stm32f7xx_hal.h', '#include <stdint.h>\n')
 shim('Soundengine/DSPAudio/BufferTools.h', '')
 shim('main.h', '''#pragma once
#include <stdint.h>
static inline int32_t sat16(int32_t x) { return x>32767?32767:x< -32768?-32768:x; }
#define __SSAT(x,n) sat16((int32_t)(x))
#define __PKHBT(a,b,n) (((uint32_t)(a)&65535u)|((uint32_t)(b)<<16))
static inline int32_t qadd16(int32_t a,int32_t b) {
 return __PKHBT(sat16((int16_t)a+(int16_t)b),
 sat16((int16_t)((uint32_t)a>>16)+(int16_t)((uint32_t)b>>16)),16);
}
#define __QADD16(a,b) qadd16(a,b)
''')
 source = root/'Core/Src/Soundengine/DSPAudio/FX/Compressor.c'
 if os.environ.get('LXR_BASE_REV'):
  source = p/'Compressor.c'
  source.write_bytes(subprocess.check_output(['git','-C',str(root),'show',os.environ['LXR_BASE_REV']+':Core/Src/Soundengine/DSPAudio/FX/Compressor.c']))
 for flags in (['-O1'], ['-O3','-ffast-math','-freciprocal-math']):
  print('compressor flags:', flags, flush=True)
  subprocess.run([os.environ.get('CC','cc'),'-std=gnu11',*flags,
   '-fsanitize=address,undefined,float-cast-overflow','-fno-sanitize-recover=all',
   '-I'+tmp,'-I'+str(root/'Core/Inc'), str(source),
   str(root/'Core/Src/Soundengine/FxBus.c'), str(root/'tests/test_compressor.c'),
   '-lm','-o',str(p/'test')],check=True)
  subprocess.run([str(p/'test')],check=True)
