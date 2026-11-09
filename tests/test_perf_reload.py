#!/usr/bin/env python3
"""Actual reload case and seq/preset bodies; adapted from perf-reload interactions.
MIDI/DSP/LCD/engine endpoints and Step layout are stubs, not hardware/audio tests.
"""
from pathlib import Path
import re, subprocess, os, tempfile
ROOT=Path(__file__).resolve().parents[1]
def src(p): return (ROOT/p).read_text()
def clean(s): return re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
def fn(s,n):
 m=re.search(r'^(?:IN_ITCM_RAM )?(?:static )?(?:void|uint8_t|FRESULT) '+n+r'\([^;\n]*\)\s*\{',s,re.M); assert m,n
 p=s.index('{',m.start());d=1;p+=1
 while d: d+=(s[p]=='{')-(s[p]=='}');p+=1
 return s[m.start():p]+'\n'
pre=r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdlib.h>
#define PERF_PAGE 42
#define FRESULT int
#define FR_OK 0
#define IN_ITCM_RAM
#define MAX_PATTERN 2
#define NUM_TRACKS 7
#define NUM_STEPS 64
#define NUM_BARS 4
#define SKIP_NEXT_KIT_AUTOLOAD 2
#define SEQ_CC 9
#define SEQ_CHANGE_PAT 11
#define PRESET_KIT_TIMER 0
#define SAVE_TYPE_KIT 0
#define CURRENT_KIT 0
#define MIDI_CC 1
#define CC_2 2
#define CC_VELO_TARGET 3
#define CC_LFO_TARGET 4
#define FX_OFF 0
#define PATTERN_LOAD_PAGE 20
#define SONG_MODE_PAGE 23
#define SELECT_MODE_PATTERN 2
#define SELECT_MODE_PATTERN_LIVE 12
#define SELECT_MODE_SONG 3
#define pgm_read_word(p) (*(p))
'''
stubs=r'''
static unsigned slipCancels;
static void seq_slipClear(void) {slipCancels++;}
static void seq_slipSync(void) {}
typedef struct {uint8_t status,data1,data2;} MidiMsg;
typedef struct {uint8_t note,param1Nr,param1Val,param2Nr,param2Val,prob,volume;} Step; /* named copy fields; not real Step layout */
static struct {Step seq_subStepPattern[2][7][64]; uint8_t seq_stepTiming[2][7][64]; uint16_t seq_mainSteps[4][2][7]; uint8_t length[2][7],shuffle[2],kitNr[2],used[2];} seq_patternSet;
static struct {Step seq_subStepPattern[7][64]; uint8_t seq_stepTiming[7][64]; uint16_t seq_mainSteps[4][7]; uint8_t length[7],shuffle,kitNr,used;} patternBackupBuffer;
static uint8_t activeParameters[NUM_PARAMS],mainParameters[3][END_OF_SOUND_PARAMETERS],*morphParameters;
static uint8_t morph_state,morph_index,seq_activePattern,seq_pendingPattern,seq_loadPendigFlag,seq_running;
static uint8_t menu_selectedPresetNr[1],menu_loadedPresetNr[1],menu_activePage,menu_playedPattern,menu_shownPattern,menu_songMenuPosition,seq_songPositionPointer,midi_process_block;
static struct {int fxType;} fxBus;
static struct {uint16_t param;} modTargets[256];
static int engineValues[NUM_PARAMS];
static int engineSrt,engineProbe,displaySrt,displayMrp,calls,inject,depth,loads,lastKit,notes,repaints,mode,placement,nonzeroTicks,oldSourceTicks;
static void preset_morph_tick(void);
static void preset_loadDrumsetRam(uint8_t,uint8_t,uint8_t);
static void seq_setNextPattern(uint8_t);
static void seq_setPendingPatternActive(void);
static uint8_t menu_getActivePage(void){return menu_activePage;}
static void menu_repaint(void){displayMrp=activeParameters[PAR_MORPH];displaySrt=activeParameters[PAR_VOICE_DECIMATION_ALL];repaints++;}
static void menu_repaintAll(void){menu_repaint();}
static void preset_touchTimer(int t){(void)t;}
static void menu_resetPerformanceFilter(void){activeParameters[PAR_PERF_HP]=0;activeParameters[PAR_PERF_LP]=127;activeParameters[PAR_PERF_RESONANCE]=0;}
static unsigned position,positionResets;
static void seq_setStepIndexToStart(void){position=0;positionResets++;}
static void seq_setShuffle(float x){(void)x;}
static int led_idx2StepLed(int x){return x;}
static void led_setBlinkLed(int a,int b){(void)a;(void)b;}
static void led_clearSequencerLeds(void){}
static void led_clearSelectLeds(void){}
static void led_clearAllBlinkLeds(void){}
static void led_initPatternSelectLeds(void){}
static void led_updateSeqLeds(void){}
static void menu_setShownPattern(int p){menu_shownPattern=p;}
static int menu_getActiveVoice(void){return 0;}
static int seq_getTrackLength(int t){return seq_patternSet.length[seq_activePattern][t];}
static int buttonHandler_getMode(void){return 0;}
static void seq_sendProgChg(int p){(void)p;}
static void voiceControl_noteOff(int v){(void)v;notes++;}
static void frontPanel_sendData(uint8_t a,uint8_t b,uint8_t c){assert(activeParameters[PAR_MORPH]==0);if(a==SEQ_CC&&b==SEQ_CHANGE_PAT)seq_setNextPattern(c);}
static void midiParser_ccHandler(MidiMsg m,int a,int b,float f){
 (void)a;(void)b;(void)f;int p=m.status==MIDI_CC?((m.data1+127)&127):m.data1+128;
 if(p<NUM_PARAMS)engineValues[p]=m.data2;
 if(p==PAR_VOICE_DECIMATION_ALL)engineSrt=m.data2;
 if(p==0)engineProbe=m.data2;
}
/* seq_tick seam: inject activation BEFORE morph tick as Soundengine.c:94-123 does.
 One-shot injection bounds recursive activation; other engine work is not simulated. */
static void soundengine_process(void){
 calls++; if(!depth && inject==calls){depth++;seq_setPendingPatternActive();depth--;}
 if(morph_state){if(activeParameters[PAR_MORPH])nonzeroTicks++;if(activeParameters[PAR_VOICE_DECIMATION_ALL]==10)oldSourceTicks++;}
 preset_morph_tick();
}
'''
main=r'''
static void drain(void){int n=0;while(morph_state){preset_morph_tick();assert(++n<512);}}
static void setup(int run,int md,int busy,int linked){
 memset(activeParameters,0,sizeof activeParameters);memset(mainParameters,0,sizeof mainParameters);
 memset(&seq_patternSet,0,sizeof seq_patternSet);memset(&patternBackupBuffer,0,sizeof patternBackupBuffer);
 mainParameters[0][PAR_VOICE_DECIMATION_ALL]=127;mainParameters[1][PAR_VOICE_DECIMATION_ALL]=63;mainParameters[2][PAR_VOICE_DECIMATION_ALL]=31;
 mainParameters[0][0]=100;mainParameters[1][0]=60;mainParameters[2][0]=20;
 morphParameters=mainParameters[2];memcpy(activeParameters,mainParameters[0],END_OF_SOUND_PARAMETERS);
 activeParameters[PAR_VOICE_DECIMATION_ALL]=10;activeParameters[PAR_MORPH]=128;activeParameters[PAR_PATTERN_MODE]=md;
 seq_running=run;seq_activePattern=seq_pendingPattern=seq_loadPendigFlag=0;
 seq_patternSet.used[0]=seq_patternSet.used[1]=1; /* existing used-slot regressions */
 seq_patternSet.kitNr[0]=0;patternBackupBuffer.kitNr=linked; /* stale snapshot must not restore association */
 menu_selectedPresetNr[0]=0;menu_loadedPresetNr[0]=0;menu_activePage=0;
 calls=depth=notes=repaints=loads=nonzeroTicks=oldSourceTicks=0;engineSrt=engineProbe=-1;
 preset_morph(128);drain();menu_repaint();if(busy){preset_morph(128);morph_index=busy==1?PAR_VOICE_DECIMATION_ALL:busy==2?0:END_OF_SOUND_PARAMETERS-1;}
}
static void show(const char*s){printf("%s MRP=%d source=%d engine=%d probe=%d display=%d/%d selected=%d linked=%d mode=%d pending=%d sweep=%d/%d notes=%d calls=%d nonzeroTicks=%d oldSourceTicks=%d loads=%d lastKit=%d\n",s,activeParameters[PAR_MORPH],activeParameters[PAR_VOICE_DECIMATION_ALL],engineSrt,engineProbe,displayMrp,displaySrt,menu_selectedPresetNr[0],seq_patternSet.kitNr[0],activeParameters[PAR_PATTERN_MODE],seq_loadPendigFlag,morph_state,morph_index,notes,calls,nonzeroTicks,oldSourceTicks,loads,lastKit);}
int main(void){
 setup(1,0,0,0);unsigned cancels=slipCancels;
 seq_setNextPattern(1);assert(slipCancels==cancels); /* queue is not activation */
 seq_setPendingPatternActive();assert(slipCancels==cancels+1);
 seq_setPendingPatternActive();assert(slipCancels==cancels+1); /* unchanged epoch */
 seq_setNextPattern(1);assert(slipCancels==cancels+1);
 seq_setPendingPatternActive();assert(slipCancels==cancels+2); /* same-slot reload */
 setup(1,0,0,0);cancels=slipCancels;press_reload();assert(slipCancels==cancels+1);
 for(int run=0;run<2;run++){
  setup(run,2,0,0);position=29;unsigned resets=positionResets;
  press_reload();
  assert(position==29 && positionResets==resets);
  assert(seq_activePattern==0 && seq_pendingPattern==0 && !seq_loadPendigFlag);
  assert(activeParameters[PAR_PATTERN_MODE]==2); /* no activation consumes skip */
 }
 /* Actual ordinary RAM-load body must retain all session controls. */
 for(int immediate=0;immediate<2;immediate++){
  setup(0,0,0,0);activeParameters[PAR_MORPH]=0;
  activeParameters[PAR_PERF_HP]=100;activeParameters[PAR_PERF_LP]=20;activeParameters[PAR_PERF_RESONANCE]=99;
  preset_loadDrumsetRam(0,0,immediate);drain();
  assert(activeParameters[PAR_PERF_HP]==100 && activeParameters[PAR_PERF_LP]==20 && activeParameters[PAR_PERF_RESONANCE]==99);
 }
 for(int run=0;run<2;run++)for(int md=0;md<3;md++)for(int busy=0;busy<4;busy++)for(int linked=0;linked<2;linked++)for(int perf=0;perf<2;perf++){
 inject=0;setup(run,md,busy,linked);menu_activePage=perf?PERF_PAGE:0;
 int before=repaints;
 /* Queue B during playback; stopped fixtures retain the same pending state. */
 seq_pendingPattern=1;seq_loadPendigFlag=1;position=37;
 unsigned resets=positionResets;
 activeParameters[PAR_PERF_HP]=100;activeParameters[PAR_PERF_LP]=20;activeParameters[PAR_PERF_RESONANCE]=99;
 seq_patternSet.seq_subStepPattern[0][2][19].note=81;
 press_reload();
 assert(position==37 && positionResets==resets);
 assert(seq_activePattern==0 && seq_pendingPattern==1 && seq_loadPendigFlag==1);
 assert(seq_patternSet.seq_subStepPattern[0][2][19].note==81);
 assert(seq_patternSet.kitNr[0]==0);

 assert(activeParameters[PAR_MORPH]==0);assert(nonzeroTicks==0);
 assert(activeParameters[PAR_PERF_HP]==0 && activeParameters[PAR_PERF_LP]==127 && activeParameters[PAR_PERF_RESONANCE]==0);
 assert(activeParameters[PAR_VOICE_DECIMATION_ALL]==127);
 /* Kit-only Reload repaints PERF, not a pattern activation. */
 assert(repaints-before==perf);
 if(perf){assert(displayMrp==0);assert(displaySrt==activeParameters[PAR_VOICE_DECIMATION_ALL]);}
 seq_setPendingPatternActive();assert(positionResets==resets+1);drain();
 assert(!seq_loadPendigFlag);assert(activeParameters[PAR_PATTERN_MODE]==(md==2?1:md));
 for(int p=0;p<END_OF_SOUND_PARAMETERS;p++)assert(engineValues[p]==activeParameters[p]);
 }
 /* Queue activation at each Reload service boundary, with distinct A/B kits. */
 for(int boundary=1;boundary<=2;boundary++)for(int md=0;md<3;md++)
 for(int busy=0;busy<4;busy++)for(int perf=0;perf<2;perf++){
  inject=0;setup(1,md,busy,0);calls=0;inject=boundary;
  menu_activePage=perf?PERF_PAGE:0;
  unsigned resets=positionResets;
  seq_patternSet.kitNr[1]=1;seq_pendingPattern=1;seq_loadPendigFlag=1;
  press_reload();drain();
  assert(seq_activePattern==1 && seq_pendingPattern==1 && !seq_loadPendigFlag);
  assert(positionResets==resets+1);
  assert(activeParameters[PAR_PATTERN_MODE]==(md==2?1:md));
  assert(activeParameters[PAR_MORPH]==0 && nonzeroTicks==0);
  assert(menu_loadedPresetNr[0]==(md==1?1:0));
  assert(menu_selectedPresetNr[0]==(md==1?1:0));
  assert(activeParameters[0]==(md==1?60:100));
  assert(activeParameters[PAR_VOICE_DECIMATION_ALL]==(md==1?63:127));
  for(int p=0;p<END_OF_SOUND_PARAMETERS;p++)assert(engineValues[p]==activeParameters[p]);
 }
 inject=0;
 /* Real activation/copy/save-as bodies, with endpoint adapters only. */
 for(int run=0;run<2;run++){
  setup(run,0,0,0);
  seq_copyPatternToBackupBuffer(0);
  /* Populate all copied pattern fields AFTER snapshot: outgoing restore loses them. */
  memset(&seq_patternSet.seq_subStepPattern[0],23,sizeof seq_patternSet.seq_subStepPattern[0]);
  memset(&seq_patternSet.seq_stepTiming[0],17,sizeof seq_patternSet.seq_stepTiming[0]);
  memset(&seq_patternSet.length[0],32,sizeof seq_patternSet.length[0]);
  for(int bar=0;bar<NUM_BARS;bar++)for(int t=0;t<NUM_TRACKS;t++)seq_patternSet.seq_mainSteps[bar][0][t]=0xa55a;
  seq_patternSet.shuffle[0]=49;seq_patternSet.kitNr[0]=1;
  seq_copyPattern(0,1); /* expected edited content */
  __typeof__(seq_patternSet) expected=seq_patternSet;
  seq_setNextPattern(1);if(run)seq_setPendingPatternActive();
  assert(seq_activePattern==1);assert(memcmp(&seq_patternSet,&expected,sizeof expected)==0);
  assert(patternBackupBuffer.shuffle==49 && patternBackupBuffer.kitNr==1);
  seq_setNextPattern(0);if(run)seq_setPendingPatternActive();
  assert(seq_activePattern==0);assert(memcmp(&seq_patternSet,&expected,sizeof expected)==0);
  /* Save-as must actually overwrite a different destination and keep source edits. */
  memset(&seq_patternSet.seq_subStepPattern[1],0,sizeof seq_patternSet.seq_subStepPattern[1]);
  seq_patternSet.shuffle[1]=0;
  assert(preset_savePatternRAM(1)==FR_OK);if(run)seq_setPendingPatternActive();
  assert(seq_activePattern==1);assert(memcmp(&seq_patternSet,&expected,sizeof expected)==0);
  assert(preset_savePatternRAM(1)==FR_OK);
  seq_setNextPattern(0);if(run)seq_setPendingPatternActive();
  assert(memcmp(&seq_patternSet,&expected,sizeof expected)==0);
 }
 puts("PASS retention/save-as, 192 Reload cases and 48 service-boundary cases (actual source; endpoint stubs, not hardware/audio)");return 0;
}
'''

p=clean(src('Core/Src/Preset/presetManager.c'));s=clean(src('Core/Src/Soundengine/Sequencer/sequencer.c'))
h=src('Core/Inc/Parameters.h');enum=h[h.index('enum ParamEnums'):];enum=enum[:enum.index('};')+2]
order=clean(src('Core/Src/Parameters.c'));order=order[order.index('uint8_t parameterOrder'):];order=order[:order.index('};')+2]
fs=''.join(fn(p,n) for n in ['interpolate','preset_morph','preset_morph_tick','preset_sendDrumsetParameters','preset_sendDrumsetParametersImmediate','preset_loadDrumsetRam'])
sf=''.join(fn(s,n) for n in ['seq_patternIsUsed','seq_copyPatternToBackupBuffer','seq_copyBackupBufferToPattern','seq_setPendingPatternActive','seq_setNextPattern','seq_copyPattern'])
sf+=fn(p,'preset_savePatternRAM')
b=clean(src('Core/Src/buttonHandler.c'));b=b[b.index('case SEQ_RELOAD:'):];b=b[b.index('{'):b.index('case SEQ_CONFIG:')];b=b[:b.rfind('break;')]
c=pre+enum+stubs+order+fs+sf+'static void press_reload(void) '+b+main
with tempfile.TemporaryDirectory(prefix='lxr-reload-') as d:
 path=Path(d)/'reload.c';path.write_text(c);exe=Path(d)/'reload'
 subprocess.run([os.environ.get('CC','cc'),'-std=c99',str(path),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
