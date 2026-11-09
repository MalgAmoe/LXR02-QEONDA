#!/usr/bin/env python3
"""Real lifecycle bodies + actual compressor/filter TUs, not setter stubs.
Reuses perf-reload's bounded storage/MIDI/engine seams. No audio scheduling,
physical UI dispatch, disk loading, or hardware timing claim.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ns = {'__file__': str(ROOT / 'tests/test_perf_reload.py')}
fixture = (ROOT / 'tests/test_perf_reload.py').read_text()
exec(fixture.split("p=clean(src(")[0], ns)
clean, fn, src = ns['clean'], ns['fn'], ns['src']
p = clean(src('Core/Src/Preset/presetManager.c'))
s = clean(src('Core/Src/Soundengine/Sequencer/sequencer.c'))
b = clean(src('Core/Src/buttonHandler.c'))
b = b[b.index('case SEQ_RELOAD:'):]
b = b[b.index('{'):b.index('case SEQ_CONFIG:')]
b = b[:b.rfind('break;')]
order = clean(src('Core/Src/Parameters.c'))
order = order[order.index('uint8_t parameterOrder'):]
order = order[:order.index('};') + 2]
stubs = ns['stubs']
old_reset = 'static void menu_resetPerformanceFilter(void){activeParameters[PAR_PERF_HP]=0;activeParameters[PAR_PERF_LP]=127;activeParameters[PAR_PERF_RESONANCE]=0;}'
assert old_reset in stubs
stubs = stubs.replace(old_reset, '')
c = ns['pre'] + '''
#include "Parameters.h"
#include "Soundengine/DSPAudio/MainCompressor.h"
#include "Soundengine/DSPAudio/MainDjFilter.h"
static uint16_t buttonHandler_originalParameter[2];
static uint8_t buttonHandler_originalValue[2],buttonHandler_resetLock1,buttonHandler_resetLock2;
'''
c += stubs + fn(clean(src('Core/Src/menu/menu.c')), 'menu_resetPerformanceFilter') + order
c += ''.join(fn(p, n) for n in ('interpolate', 'preset_morph', 'preset_morph_tick',
    'preset_sendDrumsetParameters', 'preset_sendDrumsetParametersImmediate', 'preset_loadDrumsetRam'))
c += ''.join(fn(s, n) for n in ('seq_patternIsUsed','seq_copyPatternToBackupBuffer', 'seq_copyBackupBufferToPattern',
    'seq_setPendingPatternActive', 'seq_setNextPattern'))
c += 'static void press_reload(void) ' + b
# Whole production DSP TUs: private render/cache/target state is observable here.
c += '\n#include "' + str(ROOT / 'Core/Src/Soundengine/DSPAudio/MainCompressor.c') + '"\n'
c += '#include "' + str(ROOT / 'Core/Src/Soundengine/DSPAudio/MainDjFilter.c') + '"\n'
c += ns['main'].split('int main(void){')[0]
c += r'''
static uint8_t expected[4];
static unsigned char renderBefore[sizeof comp];
static void seed(int run,int md,int busy,int linked,int perf) {
 setup(run,md,busy,linked);menu_activePage=perf?PERF_PAGE:0;
 for(unsigned i=0;i<4;i++) {
  expected[i]=(uint8_t[]){7,13,9,31}[i];
  activeParameters[MASTER_COMP_THRESHOLD+i]=expected[i];
  MainCompressor_setParameter(MASTER_COMP_THRESHOLD+i,expected[i]);
 }
 assert(MainCompressor_beginBlock());
 for(unsigned i=0;i<2048;i++){float pair[2]={28000,-19000};MainCompressor_processPair(pair);}
 assert(comp.envelope>0 && comp.gain<1 && comp.makeup>1);
 memcpy(renderBefore,&comp,sizeof comp);
 activeParameters[PAR_PERF_HP]=100;activeParameters[PAR_PERF_LP]=20;activeParameters[PAR_PERF_RESONANCE]=99;
 MainDjFilter_setTargets(100,20,99);
}
static void preserved(void) {
 for(unsigned i=0;i<4;i++)assert(activeParameters[MASTER_COMP_THRESHOLD+i]==expected[i]);
 /* beginBlock reads real targets; detects silent reset/retarget as well as
    active-parameter damage. No sample processing is scheduled by this seam. */
 assert(MainCompressor_beginBlock());
 assert(!memcmp(renderBefore,&comp,sizeof comp));
}
static void filters(int reset) {
 assert(activeParameters[PAR_PERF_HP]==(reset?0:100));
 assert(activeParameters[PAR_PERF_LP]==(reset?127:20));
 assert(activeParameters[PAR_PERF_RESONANCE]==(reset?0:99));
 assert(targetHp==(reset?0:100) && targetLp==(reset?127:20) && targetResonance==(reset?0:99));
}
int main(void) {
 unsigned cases=0;
 for(int immediate=0;immediate<2;immediate++)for(int kit=0;kit<2;kit++) {
  seed(0,0,0,0,0);activeParameters[PAR_MORPH]=0;
  preset_loadDrumsetRam(kit,0,immediate);drain();preserved();filters(0);cases++;
 }
 for(int amount=0;amount<=255;amount++) {
  seed(0,0,0,0,0);preset_morph(amount);drain();preserved();filters(0);cases++;
 }
 for(int run=0;run<2;run++)for(int md=0;md<3;md++)for(int linked=0;linked<2;linked++) {
  seed(run,md,0,linked,0);activeParameters[PAR_MORPH]=0;seq_patternSet.kitNr[1]=linked;
  seq_setNextPattern(1);if(seq_loadPendigFlag)seq_setPendingPatternActive();drain();
  assert(seq_activePattern==1);preserved();filters(0);cases++;
 }
 for(int run=0;run<2;run++)for(int md=0;md<3;md++)for(int busy=0;busy<4;busy++)
 for(int linked=0;linked<2;linked++)for(int perf=0;perf<2;perf++) {
  seed(run,md,busy,linked,perf);inject=0;
  press_reload();preserved();filters(1);
  assert(activeParameters[PAR_MORPH]==0);
  if(seq_loadPendigFlag)seq_setPendingPatternActive();drain();preserved();filters(1);cases++;
 }
 printf("PASS %u real-state compressor lifecycle cases: kit, morph, pattern, ordinary RAM reload, ShiftReload; accepted filter reset retained\n",cases);
}
'''
with tempfile.TemporaryDirectory(prefix='lxr-comp-lifecycle-') as d:
    path = Path(d)
    (path / 'stm32f7xx_hal.h').write_text('#pragma once\n#include <stdint.h>\n')
    (path / 'test.c').write_text(c)
    for flags in (['-O1'], ['-O3', '-ffast-math', '-freciprocal-math']):
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-DLXR_HOST_TEST',
            *flags, '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
            '-I' + d, '-I' + str(ROOT / 'Core/Inc'), str(path / 'test.c'),
            '-lm', '-o', str(path / 'test')], check=True)
        subprocess.run([str(path / 'test')], check=True)
