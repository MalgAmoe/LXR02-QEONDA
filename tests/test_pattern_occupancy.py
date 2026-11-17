#!/usr/bin/env python3
"""Production occupancy, edits/generator, backup and activation bodies.
Memory-backed FatFs and engine/UI seams: not SD fault or hardware timing tests.
"""
from pathlib import Path
import os, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[1]
ns = {'__file__': str(ROOT / 'tests/test_perf_reload.py')}
exec((ROOT / 'tests/test_perf_reload.py').read_text().split('p=clean(src(')[0], ns)
fn, clean, src = ns['fn'], ns['clean'], ns['src']
s = clean(src('Core/Src/Soundengine/Sequencer/sequencer.c'))
p = clean(src('Core/Src/Preset/presetManager.c'))
c = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include "Soundengine/Sequencer/sequencer.h"
#include "Soundengine/Sequencer/EuklidGenerator.h"
#include "Soundengine/MIDI/MidiMessages.h"
#define SAVE_TYPE_PATTERN 0
#define SEQ_CC 0
#define SEQ_SET_SHOWN_PATTERN 0
PatternSet seq_patternSet;
PatternBackupBuffer patternBackupBuffer;
uint8_t seq_activePattern, seq_pendingPattern;
static uint8_t menu_playedPattern,menu_shownPattern,menu_selectedPresetNr[1];
static void menu_repaintAll(void){}
static void frontPanel_sendData(int a,int b,int d){(void)a;(void)b;(void)d;}
void seq_slipStepWritten(uint8_t p,uint8_t v,uint8_t s){(void)p;(void)v;(void)s;}
'''
c += ''.join(fn(s,n) for n in ('seq_patternIsUsed','seq_copyPatternToBackupBuffer','seq_copyBackupBufferToPattern','seq_resetNote','seq_clearTrack','seq_clearPattern','seq_copyTrack','seq_copyPattern','seq_toggleMainStep','seq_setMainStep'))
c += r'''
int main(void){
 for(int i=0;i<NUM_PATTERN;i++){seq_clearPattern(i);assert(!seq_patternIsUsed(i));}
 seq_patternSet.seq_subStepPattern[0][0][0].param1Nr=10;
 seq_patternSet.seq_subStepPattern[0][0][0].volume=255;
 assert(!seq_patternIsUsed(0)); // automation/substep data alone is not a main hit
 // All 28 positions, including disabled bars/tracks, count as enabled hits.
 for(int b=0;b<4;b++)for(int t=0;t<7;t++){
  seq_clearPattern(0);seq_patternSet.seq_mainSteps[b][0][t]=0x8000;
  assert(seq_patternIsUsed(0));seq_clearTrack(t,0);assert(seq_patternIsUsed(0));
 }
 seq_clearPattern(0);seq_toggleMainStep(0,63,0);assert(seq_patternSet.used[0]);
 seq_toggleMainStep(0,63,0);assert(seq_patternIsUsed(0));
 seq_clearPattern(0);seq_setMainStep(0,6,0,1);seq_setMainStep(0,6,0,0);assert(seq_patternIsUsed(0));
 // Observe before destructive replacement, even for imported raw hits.
 seq_clearPattern(0);seq_patternSet.seq_mainSteps[0][0][1]=1;
 seq_copyTrack(0,1,0);assert(seq_patternIsUsed(0));
 seq_clearPattern(0);seq_patternSet.seq_mainSteps[0][0][0]=1;
 seq_copyTrack(0,1,0);assert(seq_patternIsUsed(0));
 seq_clearPattern(0);euklid_init();euklid_setLength(0,16);euklid_setSteps(0,4,0);
 assert(seq_patternSet.used[0]);euklid_setSteps(0,0,0);assert(seq_patternIsUsed(0));
 seq_clearPattern(0);seq_patternSet.seq_mainSteps[0][0][0]=1;
 euklid_init();euklid_transferPattern(0,0);assert(seq_patternIsUsed(0));
 for(int b=0;b<4;b++)assert(!seq_patternSet.seq_mainSteps[b][0][0]);
 // Whole copies carry history, even used-but-silent; empty source resets it.
 seq_copyPattern(0,1);assert(seq_patternSet.used[1]);
 seq_clearPattern(0);seq_copyPattern(0,1);assert(!seq_patternIsUsed(1));
 for(int used=0;used<2;used++)for(int hits=0;hits<2;hits++){
  seq_clearPattern(0);seq_patternSet.used[0]=used;seq_patternSet.kitNr[0]=13;
  seq_patternSet.seq_mainSteps[3][0][6]=hits?0x8000:0;
  seq_copyPatternToBackupBuffer(0);seq_clearPattern(0);seq_copyBackupBufferToPattern(0);
  assert(seq_patternIsUsed(0)==(used||hits));
 }
 // Storage round-trips, including silent-used, now live in test_project_codec
 // and the actual project-wrapper integration suite, not removed tmp codecs.
 return 0;
}
'''
# Actual activation, copy/save-as and RAM-kit load bodies.
a = ns['pre'] + '#include "Parameters.h"\n' + ns['stubs'].replace('assert(activeParameters[PAR_MORPH]==0);', '')
order=clean(src('Core/Src/Parameters.c')); order=order[order.index('uint8_t parameterOrder'):];order=order[:order.index('};')+2]
a += order
for n in ('interpolate','preset_morph','preset_morph_tick','preset_sendDrumsetParameters','preset_sendDrumsetParametersImmediate','preset_loadDrumsetRam'):
    body = fn(p,n)
    if n == "preset_loadDrumsetRam": body = body.replace("{", "{loads++;", 1)
    a += body
for n in ('seq_patternIsUsed','seq_copyPatternToBackupBuffer','seq_setPendingPatternActive','seq_setNextPattern','seq_copyPattern'):
    a += fn(s,n)
a += fn(p,'preset_savePatternRAM')
a += ns['main'].split('int main(void){')[0]
a += r'''
int main(void){
 // Empty, silent-used and imported-hit destinations use identical activation policy.
 for(int run=0;run<2;run++)for(int md=0;md<3;md++)
 for(int state=0;state<3;state++)for(int same=0;same<2;same++){
  setup(run,md,0,0);int dest=same?0:1;
  seq_patternSet.used[dest]=state==1;
  seq_patternSet.seq_mainSteps[3][dest][6]=state==2?0x8000:0;
  seq_patternSet.kitNr[dest]=2; // differs from both loaded kit and destination slot
  seq_patternSet.kitNr[1-dest]=0;
  uint8_t before[NUM_PARAMS];memcpy(before,activeParameters,sizeof before);
  seq_setNextPattern(dest);
  if(run){assert(seq_activePattern==0 && seq_loadPendigFlag && loads==0);seq_setPendingPatternActive();}
  drain();
  assert(seq_activePattern==dest && !seq_loadPendigFlag);
  assert(seq_patternSet.used[dest]==(state!=0));
  assert(seq_patternSet.kitNr[dest]==2 && patternBackupBuffer.kitNr==2);
  assert(patternBackupBuffer.used==(state!=0));
  assert(seq_patternSet.kitNr[1-dest]==0);
  assert(loads==(md==1));
  assert(menu_loadedPresetNr[0]==(md==1?2:0));
  assert(menu_selectedPresetNr[0]==(md==1?2:0));
  assert(activeParameters[PAR_PATTERN_MODE]==(md==2?1:md));
  if(md!=1){for(int i=0;i<NUM_PARAMS;i++)if(i!=PAR_PATTERN_MODE && i!=PAR_SHUFFLE)assert(before[i]==activeParameters[i]);}
  // Skip applies only once; manual remains off, auto and consumed skip now load.
  seq_setNextPattern(dest);if(run)seq_setPendingPatternActive();drain();
  assert(loads==(md==0?0:md==1?2:1));
  assert(seq_patternSet.kitNr[dest]==2 && seq_patternSet.used[dest]==(state!=0));
 }
 // Whole copy and save-as preserve source association even for empty sources.
 for(int run=0;run<2;run++)for(int md=0;md<3;md++)for(int used=0;used<2;used++){
  setup(run,md,0,0);seq_patternSet.used[0]=used;seq_patternSet.kitNr[0]=2;
  seq_copyPattern(0,1);
  assert(seq_patternSet.kitNr[0]==2 && seq_patternSet.kitNr[1]==2 && seq_patternSet.used[1]==used);
  seq_patternSet.kitNr[1]=0;seq_patternSet.used[1]=!used;
  assert(preset_savePatternRAM(1)==FR_OK);if(run)seq_setPendingPatternActive();drain();
  assert(seq_activePattern==1 && seq_patternSet.kitNr[0]==2 && seq_patternSet.kitNr[1]==2);
  assert(seq_patternSet.used[0]==used && seq_patternSet.used[1]==used);
  assert(patternBackupBuffer.kitNr==2 && patternBackupBuffer.used==used);
 }
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='lxr-occupancy-') as d:
    for name,code in (('codec',c),('activation',a)):
        path=Path(d)/f'{name}.c';exe=Path(d)/name;path.write_text(code)
        cmd=[os.environ.get('CC','clang'),'-std=c11','-DLXR_HOST_TEST','-g','-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'tests/shim'),'-I'+str(ROOT/'Core/Inc'),str(path)]
        if name=='codec': cmd += [str(ROOT/'Core/Src/Soundengine/Sequencer/EuklidGenerator.c')]
        subprocess.run(cmd+['-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
print('Production empty-pattern edits, generator, backup and occupancy-independent kit activation/copy/save-as passed.')
