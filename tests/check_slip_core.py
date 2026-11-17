#!/usr/bin/env python3
"""Compile actual sequencer slip core; no replacement state machine."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
s=(Path(__file__).resolve().parents[1]/'Core/Src/Soundengine/Sequencer/sequencer.c').read_text()
def function(name):
 clean=re.sub(r'/\*.*?\*/|//[^\n]*',lambda m:' '*len(m[0]),s,flags=re.S)
 m=re.search(r'^(?:static )?(?:void|uint8_t) '+name+r'\([^;\n]*\)\s*\{',clean,re.M);assert m,name
 end=clean.index('{',m.start())+1;depth=1
 while depth: depth+=(clean[end]=='{')-(clean[end]=='}');end+=1
 return s[m.start():end]+'\n'
core=s[s.index('/* Slip core:'):s.index('static void seq_triggerSequenced')]
core+=s[s.index('int8_t getShiftValue('):s.index('uint8_t chokeCurrent=0;')]
core+='static uint8_t chokeCurrent,chokeNext;\n'+function('seq_processFlam')
core+=function('seq_setMainStep')+function('seq_addNote')
preamble=r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
static unsigned irq;
static uint32_t __get_PRIMASK(void){return irq;}
static void __disable_irq(void){irq=1;}
static void __set_PRIMASK(uint32_t m){irq=m;}
#define NUM_TRACKS 7
typedef enum {STEP_PREV, STEP_CURRENT, STEP_NEXT} StepPosition;
static uint8_t seq_running=1, seq_activePattern;
static int8_t seq_stepIndex[7];
static struct {uint8_t prev,current,next;} seq_rndValue[7];
typedef struct {uint8_t prob,volume,note;} Step;
static struct {uint16_t seq_mainSteps[4][1][7];uint8_t length[1][7]; Step seq_subStepPattern[1][7][64];struct {uint8_t flam,shift;} seq_stepTiming[1][7][64];} seq_patternSet;
#define STEP_VOLUME_MASK 127
#define STEP_ACTIVE_MASK 128
#define NUM_STEPS 64
#define PERF_PAGE 42
enum {LED_STEP1,LED_STEP2,LED_STEP3,LED_STEP4,LED_STEP5,LED_STEP6,LED_STEP7,LED_STEP8,LED_STEP9,LED_STEP10,LED_STEP11,LED_STEP12,LED_STEP13,LED_STEP14,LED_STEP15,LED_STEP16};
static uint8_t seq_recordActive=1,frontParser_shownPattern,frontParser_activeTrack,menu_activeBar,menu_activePage=PERF_PAGE;
static int8_t seq_stepToSkip[7];
static float elapsed;
static float seq_getElapsedStepTimePercent(void){return elapsed;}
static uint8_t seq_determineNextPattern(uint8_t x){(void)x;return 0;}
static void led_setValue(uint8_t v,uint8_t l){(void)v;(void)l;}
static uint8_t seq_mutedTracks,seq_performanceBreak,lastWasNoteOn[7];
static unsigned hits,offs,lastSource[7];
static void voiceControl_noteOff(uint8_t t){(void)t;offs++;}
static void seq_triggerSequenced(uint8_t t,uint8_t v,uint8_t n,uint8_t source){(void)v;(void)n;assert(!irq);hits++;lastSource[t]=source;}
static uint8_t active[7][64];
static uint8_t seq_intIsMainStepActive(uint8_t t,uint8_t s,uint8_t p) {(void)p; return active[t][s] && (seq_patternSet.seq_mainSteps[s/16][p][t] & (1u<<(s%16)));}
'''
tests=r'''
int main(void) {
 for(unsigned t=0;t<7;t++) {
  seq_patternSet.length[0][t]=t+1;
  for(unsigned bar=0;bar<4;bar++)seq_patternSet.seq_mainSteps[bar][0][t]=0xffff;
  seq_rndValue[t].current=20; seq_rndValue[t].prev=90; seq_rndValue[t].next=30;
  for(unsigned i=0;i<64;i++) {active[t][i]=1;seq_patternSet.seq_subStepPattern[0][t][i].prob=50;}
 }
 assert(seq_slipObserve(0,0,STEP_CURRENT));
 seq_slipPress(0); seq_slipSync(); seq_slipApplyWrites(); assert(seq_slipCount==1 && seq_slipLength==2);
 seq_slipPress(0); seq_slipSync(); seq_slipApplyWrites(); seq_slipPress(3); seq_slipSync(); seq_slipApplyWrites(); seq_slipPress(1); seq_slipSync(); seq_slipApplyWrites(); seq_slipPress(2); seq_slipSync(); seq_slipApplyWrites();
 assert(seq_slipCount==4 && seq_slipQueue[1]==3);
 assert(seq_slipObserve(0,0,STEP_CURRENT));
 assert(!seq_slipObserve(0,0,STEP_PREV)); /* distinct seam role */
 seq_rndValue[0].current=99;
 assert(seq_slipObserve(0,0,STEP_CURRENT)); /* sticky */
 /* Explicit writes invalidate all modulo aliases, even a value restored
  * before the next evaluation. */
 seq_slipStepWritten(0,0,0); seq_slipSync(); seq_slipApplyWrites();
 assert(!seq_slipObserve(0,0,STEP_CURRENT));
 assert(!seq_slipLoop[0][1].role[STEP_CURRENT].seen);
 active[0][0]=0; assert(!seq_slipObserve(0,0,STEP_CURRENT));
 active[0][0]=1; seq_patternSet.seq_subStepPattern[0][0][0].prob=100;
 assert(seq_slipObserve(0,0,STEP_CURRENT)); /* live mutation */
 for(unsigned b=0;b<9;b++) {
  seq_slipBoundary();
  for(unsigned t=0;t<7;t++) seq_stepIndex[t]=(seq_stepIndex[t]+1)%(t+1);
  for(unsigned t=0;t<7;t++) for(unsigned r=0;r<3;r++)
   assert(seq_slipSource(t,r)<t+1);
 }
 int real=seq_stepIndex[6]; seq_slipRelease(0); seq_slipSync(); seq_slipApplyWrites();
 assert(seq_slipLength==8 && seq_slipOrigin[6]==real && seq_slipPhase==0);
 seq_slipRelease(1); seq_slipSync(); seq_slipApplyWrites(); assert(seq_slipCount==2 && seq_slipQueue[0]==3);
 seq_slipClear(); seq_slipSync(); seq_slipApplyWrites(); assert(!seq_slipCount);
 seq_running=0;seq_slipPress(0); seq_slipSync(); seq_slipApplyWrites();assert(!seq_slipCount);
 seq_running=1;seq_slipPress(4); seq_slipSync(); seq_slipApplyWrites();assert(!seq_slipCount);
 for(unsigned pad=0;pad<4;pad++) {
  seq_slipPress(pad); seq_slipSync(); seq_slipApplyWrites();assert(seq_slipLength==2*(pad+1));
  seq_slipRelease(pad); seq_slipSync(); seq_slipApplyWrites();assert(!seq_slipCount);
 }
 /* Real scheduling body and helper: no output or phase/choke reset at publication.
  * A phase10 x2 press only allows its ordinary phase12 continuation. */
 seq_slipClear();seq_slipSync();
 for(unsigned t=0;t<7;t++) {
  seq_stepIndex[t]=0;
  for(unsigned i=0;i<64;i++) {
   seq_patternSet.seq_subStepPattern[0][t][i].prob=100;
   seq_patternSet.seq_stepTiming[0][t][i].shift=7;
   seq_patternSet.seq_stepTiming[0][t][i].flam=1;
  }
 }
 seq_processFlam(10);unsigned before=hits,offBefore=offs;
 chokeCurrent=1;chokeNext=1;seq_slipPress(3);
 assert(hits==before && offs==offBefore && chokeCurrent && chokeNext);
 seq_processFlam(11);assert(hits==before && chokeNext);
 chokeCurrent=chokeNext=0;seq_processFlam(12);assert(hits==before+7);
 before=hits;offBefore=offs;seq_slipRelease(3);
 assert(hits==before && offs==offBefore);seq_processFlam(13);assert(hits==before);
 /* Seven unequal tracks, all four windows, every shift/flam combination. */
 for(unsigned pad=0;pad<4;pad++) {
  seq_slipPress(pad);seq_slipSync();
  for(unsigned boundary=0;boundary<17;boundary++) {
   for(unsigned sh=0;sh<15;sh++)for(unsigned flam=0;flam<6;flam++) {
    for(unsigned t=0;t<7;t++)for(unsigned i=0;i<64;i++) {
     seq_patternSet.seq_stepTiming[0][t][i].shift=sh;
     seq_patternSet.seq_stepTiming[0][t][i].flam=flam;
    }
    for(unsigned pulse=0;pulse<24;pulse++)seq_processFlam(pulse);
    for(unsigned t=0;t<7;t++)assert(lastSource[t]<t+1);
   }
   seq_slipBoundary();for(unsigned t=0;t<7;t++)seq_stepIndex[t]=(seq_stepIndex[t]+1)%(t+1);
  }
  seq_slipRelease(pad);seq_slipSync();
 }
 /* Actual armed note writer still quantizes/writes the real timeline, not
  * the audible source. Erase immediately suppresses cached short-track aliases. */
 seq_stepIndex[6]=0;seq_slipPress(3);seq_slipSync();
 seq_stepIndex[6]=4;elapsed=0;seq_addNote(6,99,61);
 seq_slipApplyWrites();assert(seq_patternSet.seq_subStepPattern[0][6][4].note==61);
 assert(seq_slipSource(6,STEP_CURRENT)==0);
 elapsed=75;seq_addNote(6,101,62);assert(seq_stepToSkip[6]==5);
 assert(seq_patternSet.seq_subStepPattern[0][6][5].note==62);
 seq_patternSet.seq_subStepPattern[0][0][0].prob=100;
 assert(seq_slipObserve(0,0,STEP_CURRENT));
 seq_setMainStep(0,0,0,0);seq_slipApplyWrites();assert(!seq_slipObserve(0,0,STEP_CURRENT));
 seq_addNote(0,80,50);seq_slipApplyWrites();assert(seq_slipObserve(0,0,STEP_CURRENT));
 seq_slipRelease(3);seq_slipSync();
 /* Running before the first clock still captures forward source0, not slot1. */
 for(unsigned t=0;t<7;t++)seq_stepIndex[t]=-1;
 seq_slipPress(0);seq_slipSync();seq_slipBoundary();assert(seq_slipPhase==0);
 for(unsigned t=0;t<7;t++)seq_stepIndex[t]=0;
 seq_slipBoundary();assert(seq_slipPhase==1);seq_slipRelease(0);seq_slipSync();
 /* Saved PRIMASK preserved even when already masked; request work never renders. */
 irq=1;seq_slipPress(0);assert(irq==1);seq_slipRelease(0);assert(irq==1);
 seq_slipClear();assert(irq==1);irq=0;seq_slipSync();
 return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d); (p/'test.c').write_text(preamble+core+tests)
 for opt in ('-O0','-O3'):
  subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',opt,str(p/'test.c'),'-o',str(p/'test')],check=True)
  subprocess.run([str(p/'test')],check=True)
  print('slip production core',opt,'PASS')

# Independent afde83f oracle: compile its actual scheduling/helper bodies beside
# current production bodies. Only symbol names change; no baseline model.
baseline=(Path(__file__).resolve().parent/'fixtures/slip_baseline_afde83f.c').read_text()
current=s
s=baseline
old_helpers=s[s.index('int8_t getShiftValue('):s.index('void seq_processFlam(')]
old_scheduler=function('seq_processFlam')
s=current
old=old_helpers+old_scheduler
for name in ('getShiftValue','flamIdxToPattern','seq_getShiftFlamPattern','seq_processFlam','chokeCurrent','chokeNext'):
 old=re.sub(r'\b'+name+r'\b','baseline_'+name,old)
old='static uint8_t baseline_chokeCurrent,baseline_chokeNext;\n'+old
# Replace the first harness's audio adapter with actual production trigger and
# automation-fetch bodies. Endpoints record ordered calls, including note-offs.
prefix=preamble[:preamble.index('static void voiceControl_noteOff')]
prefix=prefix.replace('static unsigned hits,offs,lastSource[7];', '')
prefix+=preamble[preamble.index('static uint8_t active'):]
prefix+=r'''
typedef struct {int kind,t,a,b;} Event;
static Event trace[256];static unsigned count;
static void event(int k,int t,int a,int b){assert(count<256);trace[count++]=(Event){k,t,a,b};}
static void voiceControl_noteOff(uint8_t t){event(0,t,0,0);}
static void voiceControl_noteOn(uint8_t t,uint8_t n,uint8_t v){event(1,t,n,v);}
static uint8_t midi_MidiChannels[7],activeParameters[7];
#define PAR_MIDI_NOTE1 0
static void seq_sendMidiNoteOn(uint8_t c,uint8_t n,uint8_t v){event(2,c,n,v);}
static void seq_parseAutomationNodes(uint8_t t,Step *p){
 assert(p>=&seq_patternSet.seq_subStepPattern[0][t][0]);
 event(3,t,(int)(p-&seq_patternSet.seq_subStepPattern[0][t][0]),p->prob);
}
static void seq_triggerVoiceSource(uint8_t,uint8_t,uint8_t,int8_t);
'''
prefix+=function('seq_triggerVoice')+function('seq_triggerVoiceSource')
prefix+='static void seq_triggerSequenced(uint8_t,uint8_t,uint8_t,uint8_t);\n'
# Existing core refers to the sink declared above; don't use its fake sink.
checks=r'''
int main(void){
 for(unsigned t=0;t<7;t++){
  seq_patternSet.length[0][t]=t+1;midi_MidiChannels[t]=t;
  for(unsigned b=0;b<4;b++)seq_patternSet.seq_mainSteps[b][0][t]=0xffff;
  for(unsigned i=0;i<64;i++){
   active[t][i]=(i+t)%3!=1;
   seq_patternSet.seq_subStepPattern[0][t][i]=(Step){(i*31+t*17)%101,(i*7+t)%128,30+i};
  }
 }
 unsigned evaluations=0,events=0;
 for(unsigned sh=0;sh<15;sh++)for(unsigned fl=0;fl<6;fl++){
  memset(lastWasNoteOn,0,sizeof lastWasNoteOn);chokeCurrent=chokeNext=0;
  for(unsigned boundary=0;boundary<18;boundary++){
   seq_slipBoundary();
   for(unsigned t=0;t<7;t++){
    seq_stepIndex[t]=boundary%(t+1);
    seq_rndValue[t].prev=(boundary*13+t)%101;
    seq_rndValue[t].current=(boundary*29+t)%101;
    seq_rndValue[t].next=(boundary*43+t)%101;
    for(unsigned i=0;i<64;i++){
     seq_patternSet.seq_stepTiming[0][t][i].shift=(sh+i)%15;
     seq_patternSet.seq_stepTiming[0][t][i].flam=(fl+i)%6;
    }
   }
   for(unsigned t=0;t<7;t++)for(unsigned r=0;r<3;r++){
    unsigned i=(seq_stepIndex[t]+t+1+(r==STEP_PREV?-1:r==STEP_NEXT?1:0))%(t+1);
    assert(seq_getShiftFlamPattern(t,i,r)==baseline_seq_getShiftFlamPattern(t,i,r));
   }
   seq_mutedTracks=boundary%4==0?0x2a:0;
   seq_performanceBreak=boundary%7==6;
   for(unsigned pulse=0;pulse<24;pulse++){
    uint8_t saved[7];memcpy(saved,lastWasNoteOn,7);
    baseline_chokeCurrent=chokeCurrent;baseline_chokeNext=chokeNext;
    count=0;baseline_seq_processFlam(pulse);
    Event expected[256];unsigned n=count;memcpy(expected,trace,n*sizeof(Event));
    uint8_t expectedLast[7];memcpy(expectedLast,lastWasNoteOn,7);
    memcpy(lastWasNoteOn,saved,7);count=0;seq_processFlam(pulse);
    assert(count==n && !memcmp(expected,trace,n*sizeof(Event)));
    assert(!memcmp(expectedLast,lastWasNoteOn,7));
    assert(chokeCurrent==baseline_chokeCurrent && chokeNext==baseline_chokeNext);
    events+=n;evaluations++;
   }
  }
 }
 assert(evaluations==38880 && events>1000);
 /* Exact production trace: owner capture0, real advances to4, FIFO handover
  * captures4, release rejoins real5. Publication itself emits no events. */
 seq_performanceBreak=0;seq_mutedTracks=0x3f;seq_slipClear();seq_slipSync();
 for(unsigned i=0;i<7;i++){
  active[6][i]=1;seq_patternSet.seq_subStepPattern[0][6][i]=(Step){100,80,40+i};
  seq_patternSet.seq_stepTiming[0][6][i].shift=7;
  seq_patternSet.seq_stepTiming[0][6][i].flam=0;
 }
 seq_stepIndex[6]=0;seq_slipPress(0);seq_slipSync();seq_slipPress(3);seq_slipSync();
 seq_stepIndex[6]=4;count=0;seq_processFlam(0);
 Event held[]={{3,6,0,100},{0,6,0,0},{1,6,40,80},{2,6,40,80}};
 assert(count==4 && !memcmp(trace,held,sizeof held));
 count=0;seq_slipRelease(0);assert(count==0);seq_processFlam(0);
 Event handover[]={{3,6,4,100},{0,6,0,0},{1,6,44,80},{2,6,44,80}};
 assert(count==4 && !memcmp(trace,handover,sizeof handover));
 count=0;seq_processFlam(1);assert(count==1 && trace[0].kind==0 && trace[0].t==6);
 seq_stepIndex[6]=5;count=0;seq_slipRelease(3);assert(count==0);seq_processFlam(0);
 Event released[]={{3,6,5,100},{0,6,0,0},{1,6,45,80},{2,6,45,80}};
 assert(count==4 && !memcmp(trace,released,sizeof released));
 /* Direct/manual path remains real; sequenced source fetch remains live. */
 seq_slipPress(0);seq_slipSync();seq_stepIndex[6]=2;
 count=0;seq_triggerVoice(6,70,60);assert(trace[0].kind==3 && trace[0].a==2);
 seq_patternSet.seq_subStepPattern[0][6][5].prob=37;
 count=0;seq_triggerSequenced(6,71,61,5);
 assert(trace[0].kind==3 && trace[0].a==5 && trace[0].b==37);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(prefix+core+function('seq_triggerSequenced')+old+checks)
 for opt in ('-O0','-O3'):
  subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',opt,str(p/'test.c'),'-o',str(p/'test')],check=True)
  subprocess.run([str(p/'test')],check=True)
  print('slip afde83f differential + production automation/transition trace',opt,'PASS')
