#!/usr/bin/env python3
"""Production occupancy, edits/generator, file/tmp codecs and activation bodies.
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
#define STEPS_PER_PATTERN 64
#undef USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
#define USE_INTERRUPT_ONLY_DURING_SAVE_PROJ 0
#include "Soundengine/MIDI/MidiMessages.h"
#define FR_OK 0
#define FR_INT_ERR 2
#define FR_INVALID_PARAMETER 3
#define FA_OPEN_EXISTING 0
#define FA_READ 1
#define FA_CREATE_ALWAYS 2
#define FA_WRITE 4
#define SAVE_TYPE_PATTERN 0
#define SEQ_CC 0
#define SEQ_SET_SHOWN_PATTERN 0
typedef int FRESULT; typedef int FIL; typedef unsigned UINT;
PatternSet seq_patternSet;
PatternBackupBuffer patternBackupBuffer;
uint8_t seq_activePattern, seq_pendingPattern;
static uint8_t menu_playedPattern,menu_shownPattern,menu_selectedPresetNr[1];
static FIL SDFile;
#define PATTERN_NAMES 0
#define FEXT_PAT 0
static char savefileNames[64][1][9];
static uint8_t preset_projectWriteActive,preset_fileCleanupWarning;
static FRESULT preset_writeResult;
static unsigned char disk[10000];
static unsigned pos,size;
static int readError;
static FRESULT preset_openFile(FIL*f,const char*n,int flags){(void)f;(void)n;pos=0;if(flags&FA_WRITE)size=0;return 0;}
static FRESULT preset_closeFile(FIL*f){(void)f;return 0;}
static FRESULT preset_initTmpFolder(void){return 0;}
static FRESULT preset_writeFile(FIL*f,const void*v,UINT n,UINT*w){(void)f;assert(pos+n<=sizeof disk);memcpy(disk+pos,v,n);pos+=n;size=pos;*w=n;return 0;}
static FRESULT f_read(FIL*f,void*v,UINT n,UINT*r){(void)f;if(readError){*r=0;return 1;}*r=n<size-pos?n:size-pos;memcpy(v,disk+pos,*r);pos+=*r;return 0;}
static unsigned f_tell(FIL*f){(void)f;return pos;}
static FRESULT f_lseek(FIL*f,unsigned offset){(void)f;assert(offset<=size);pos=offset;return 0;}
static void preset_makeFileNameSave(char*n,uint8_t p,int ext,const char*name){(void)p;(void)ext;(void)name;strcpy(n,"00-test.pat");}
static FRESULT preset_makeFileNameLoad(char*n,uint8_t p,int ext){(void)p;(void)ext;strcpy(n,"00-test.pat");return preset_openFile(&SDFile,n,FA_READ);}
static void preset_makeFileNameOld(char*n,uint8_t p,int ext){(void)p;(void)ext;strcpy(n,"old.pat");}
static FRESULT storage_removeOtherSlotFiles(const char*d,const char*n){(void)d;(void)n;return 0;}
static void menu_repaintAll(void){}
static void frontPanel_sendData(int a,int b,int d){(void)a;(void)b;(void)d;}
void seq_slipStepWritten(uint8_t p,uint8_t v,uint8_t s){(void)p;(void)v;(void)s;}
'''
c += ''.join(fn(s,n) for n in ('seq_patternIsUsed','seq_copyPatternToBackupBuffer','seq_copyBackupBufferToPattern','seq_resetNote','seq_clearTrack','seq_clearPattern','seq_copyTrack','seq_copyPattern','seq_toggleMainStep','seq_setMainStep'))
c += ''.join(fn(p,n) for n in ('preset_writePatternOccupancy','preset_readPatternOccupancy','preset_writePatternData','preset_readPatternData','preset_LoadTmpPat','preset_saveTmpPat','preset_savePatternSD','preset_loadPatternSD'))
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
  size=pos=0;preset_writePatternData(0);unsigned full=size;
  seq_clearPattern(0);pos=0;assert(preset_readPatternData(0,4));
  assert(seq_patternIsUsed(0)==(used||hits)&&seq_patternSet.kitNr[0]==13);
  for(int staged=0;staged<2;staged++){
   preset_projectWriteActive=staged;assert(preset_savePatternSD(0)==0);
   assert(!memcmp(disk+8,"PatV04",6));
   memset(&seq_patternSet,0,sizeof seq_patternSet);assert(preset_loadPatternSD(0)==0);
   assert(seq_patternIsUsed(0)==(used||hits)&&seq_patternSet.kitNr[0]==13);
  }
  // Restart from a completely reset RAM image through the real tmp path.
  menu_playedPattern=0;assert(preset_saveTmpPat()==0);unsigned tmpSize=size;
  memset(&seq_patternSet,0,sizeof seq_patternSet);assert(preset_LoadTmpPat()==0);
  assert(seq_patternIsUsed(0)==(used||hits)&&seq_patternSet.kitNr[0]==13);
  // Old unversioned tmp has no trailing byte: scan hits, not stale history.
  size=tmpSize-1;seq_patternSet.used[0]=1;assert(preset_LoadTmpPat()==0);
  assert(seq_patternIsUsed(0)==hits);
  size=pos=0;preset_writePatternData(0);size=full-1;pos=0;
  seq_patternSet.used[0]=1;assert(preset_readPatternData(0,3));assert(seq_patternIsUsed(0)==hits);
  pos=0;assert(!preset_readPatternData(0,4)); // required byte absent
  size=full;disk[full-1]=0x42;pos=0;assert(!preset_readPatternData(0,4));
 }
 // An empty tag with actual hits is promoted, never loses notes to kit inheritance.
 size=pos=0;seq_clearPattern(0);seq_setMainStep(0,0,0,1);preset_writePatternData(0);
 disk[size-1]=0xe0;seq_patternSet.used[0]=0;pos=0;
 assert(preset_readPatternData(0,4)&&seq_patternSet.used[0]);
 readError=1;assert(!preset_readPatternOccupancy(0,0));
 return 0;
}
'''
# Actual activation + RAM-kit load bodies; deliberately empty slots below.
a = ns['pre'] + '#include "Parameters.h"\n' + ns['stubs'].replace('assert(activeParameters[PAR_MORPH]==0);', '')
order=clean(src('Core/Src/Parameters.c')); order=order[order.index('uint8_t parameterOrder'):];order=order[:order.index('};')+2]
a += order
for n in ('interpolate','preset_morph','preset_morph_tick','preset_sendDrumsetParameters','preset_sendDrumsetParametersImmediate','preset_loadDrumsetRam'):
    body = fn(p,n)
    if n == "preset_loadDrumsetRam": body = body.replace("{", "{loads++;", 1)
    a += body
for n in ('seq_patternIsUsed','seq_copyPatternToBackupBuffer','seq_setPendingPatternActive','seq_setNextPattern'):
    a += fn(s,n)
a += ns['main'].split('int main(void){')[0]
a += r'''
int main(void){
 for(int run=0;run<2;run++)for(int md=0;md<3;md++){
  setup(run,md,0,0);seq_patternSet.used[1]=0;seq_patternSet.kitNr[1]=1;
  uint8_t before[NUM_PARAMS];memcpy(before,activeParameters,sizeof before);
  int oldLoads=loads;seq_setNextPattern(1);if(run)seq_setPendingPatternActive();
  assert(seq_activePattern==1 && !seq_patternSet.used[1]);
  assert(seq_patternSet.kitNr[1]==0 && patternBackupBuffer.kitNr==0 && !patternBackupBuffer.used);
  assert(loads==oldLoads); // no reload, no morph reset or unsaved sound overwrite
  for(int i=0;i<NUM_PARAMS;i++)if(i!=PAR_PATTERN_MODE && i!=PAR_SHUFFLE)assert(before[i]==activeParameters[i]);
  assert(activeParameters[PAR_PATTERN_MODE]==(md==2?1:md));
  // A silent but used destination must still perform ordinary kit behavior.
  seq_patternSet.used[0]=1;seq_patternSet.kitNr[0]=1;
  seq_setNextPattern(0);if(run)seq_setPendingPatternActive();drain();
  assert(loads==oldLoads+(md!=0));assert(menu_loadedPresetNr[0]==(md?1:0));
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
print('Production empty-pattern edits, generator, codecs/tmp restart and sound-retaining activation passed.')
