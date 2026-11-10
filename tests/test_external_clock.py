#!/usr/bin/env python3
"""Compile actual clock source, IRQs and sequencer/parser handoffs with fake endpoints.
Not a measurement of device timing, storage latency or interrupt priority hardware.
"""
from pathlib import Path
import re, subprocess, tempfile, os
root=Path(__file__).resolve().parents[1]
def source(path): return (root/path).read_text()
def extract(text,name):
    clean=re.sub(r'/\*.*?\*/|//[^\n]*',lambda m:' '*len(m[0]),text,flags=re.S)
    m=re.search(r'^[ 	]*(?:static )?(?:inline )?(?:void|float|uint8_t|uint16_t) '+name+r'\([^;\n]*\)\s*\{',clean,re.M)
    assert m,name
    pos=clean.index('{',m.start())+1;depth=1
    while depth:
        depth+=(clean[pos]=='{')-(clean[pos]=='}');pos+=1
    return text[m.start():pos]+'\n'
seq=source('Core/Src/Soundengine/Sequencer/sequencer.c')
trigger=source('Core/Src/Soundengine/TriggerOut.c')
# Select the active HAL IRQs, not the obsolete #if 0 implementation.
trigger=trigger[trigger.index('static SyncPulseHistory trigger_history;'):]
header=source('Core/Inc/Soundengine/Sequencer/clockSync.h')
api=header[header.index('typedef struct'):header.index('#endif')]
clock=source('Core/Src/Soundengine/Sequencer/clockSync.c')
clock=re.sub(r'^#include[^\n]*','',clock,flags=re.M)
c=r'''
void seq_slipClear(void);
static void seq_slipSync(void);
static void seq_slipBoundary(void);
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define WINDOW_SIZE 8
#define WINDOW_MASK 7
#define HANDLE_SEQ_IN_CLOCK_INTERRUPT 0
#define PRE_4_PPQ_IN 6
#define PRE_24_PPQ_IN 1
#define MIDI_START 250
#define MIDI_CONTINUE 251
#define MIDI_FILTER_SYSTEM 1
#define MIDI_STOP 252
#define MIDI_CLOCK 248
#define MIDI_PRESCALER_MASK 4
#define PRESET_PAT_TIMER 0
#define PRESET_STOP_PAT_TIMER 1
#define RESET 0
#define GPIO_PIN_4 16
#define GPIO_PIN_5 32
static uint32_t primask, systick_ticks;
static unsigned criticals;
static uint32_t __get_PRIMASK(void){return primask;}
static void __disable_irq(void){primask=1;criticals++;}
static void __set_PRIMASK(uint32_t mask){primask=mask;}
static volatile uint8_t trigger_clockReceived;
static uint8_t trigger_clockCnt,trigger_prescaleCounterClockInput,trigger_prescalerClockInput=PRE_4_PPQ_IN;
static uint8_t seq_running,seq_isSyncExternal=2,seq_prescaleCounter,isStepShuffled;
static uint16_t seq_tempo=100;
static unsigned steps,resets,starts,stops,indexResets,bpmWrites,seq_masterStepCnt,kitWork,heavyIrq,sourceIrq;
static uint32_t seq_lastTick;
static float seq_deltaT=1000000,seq_lastShuffle,seq_midiRemaining;
static unsigned noteOffs,breakCancels,echoes,cleanupIrq;
#define NUM_TRACKS 7
static int8_t seq_stepIndex[NUM_TRACKS];
static uint8_t seq_lastMasterStep[NUM_TRACKS];
static int seq_songPositionPointer;
static struct {uint16_t IDR;} resetPort;
#define Reset_In_EXTI5_GPIO_Port (&resetPort)
#define Reset_In_EXTI5_Pin 32
#define __HAL_GPIO_EXTI_GET_IT(pin) (1)
#define __HAL_GPIO_EXTI_CLEAR_IT(pin) ((void)(pin))
static void trigger_ResetPosition(void);
static void seq_setRunning(uint8_t);
static void seq_resetPosition(void);
static void EXTI9_5_IRQHandler(void);
void EXTI4_IRQHandler(void);
static uint8_t seq_getExtSync(void){return seq_isSyncExternal;}
static uint8_t seq_isRunning(void){return seq_running;}
static uint16_t seq_getMasterStepCnt(void){return seq_masterStepCnt;}
static uint16_t seq_getBpm(void){return seq_tempo;}
static void seq_setBpm(uint16_t bpm){seq_tempo=bpm;bpmWrites++;}
static float delayTicks=100;
static float seq_getDeltaTShuffleDelay(uint16_t bpm){(void)bpm;return delayTicks;}

/* Inject a reset IRQ DURING a simulated heavy step/kit operation. It must
 * only publish a request, not reenter transport or mask the heavy work. */
void seq_setExtSync(uint8_t);
static void seq_nextStep(void){
 assert(!primask);if(!seq_running)return;seq_slipSync();seq_slipBoundary();steps++;seq_masterStepCnt++;
 if(sourceIrq){unsigned mode=sourceIrq-1;sourceIrq=0;seq_setExtSync(mode);}
 if(heavyIrq){heavyIrq=0;kitWork=1;resetPort.IDR=0;EXTI9_5_IRQHandler();kitWork=0;assert(seq_running);}
}
static void seq_sendRealtime(uint8_t v);
void seq_setMidiRunning(uint8_t);
void seq_midiRunCleanup(uint8_t);
void seq_midiClockAnchor(void);
void seq_MidiSyncQueue(uint8_t);
static void seq_setPerformanceBreak(uint8_t v){(void)v;breakCancels++;}
static void preset_touchTimer(uint8_t t){assert(!primask);(void)t;if(cleanupIrq){cleanupIrq=0;EXTI4_IRQHandler();}}
static void trigger_reset(uint8_t v){assert(!primask);if(v)starts++;else stops++;}
static void seq_setStepIndexToStart(void);
static void led_resetBlinkTimer(void){assert(!kitWork);assert(!primask);resets++;}
static void voiceControl_noteOff(uint8_t t){(void)t;assert(!primask);noteOffs++;if(cleanupIrq){cleanupIrq=0;EXTI4_IRQHandler();}}
static void midiParser_checkMtc(void);
#define FRONT_SEQ_CC 0
#define FRONT_SEQ_RUN_STOP 0
static uint8_t midiParser_mtcIsRunning;
static uint32_t midiParser_lastMtcReceived;
static void uart_sendFrontpanelByte(uint8_t b){(void)b;}
static void seq_calcDeltaT(uint16_t b,uint8_t s){(void)b;(void)s;seq_deltaT=1000000;}
static void trigger_clockTick(uint8_t v,uint8_t c){(void)v;(void)c;}
static void seq_processFlam(uint8_t c){(void)c;}
'''+api
# Clock source has public declarations; these extracted definitions use the same linkage.
c=c.replace('static void trigger_ResetPosition(void);','void trigger_ResetPosition(void);').replace('static void seq_setRunning(uint8_t);','void seq_setRunning(uint8_t);').replace('static void seq_resetPosition(void);','void seq_resetPosition(void);').replace('static void EXTI9_5_IRQHandler(void);','void EXTI9_5_IRQHandler(void);')
c += r'''
typedef enum {STEP_PREV, STEP_CURRENT, STEP_NEXT} StepPosition;
static uint8_t seq_activePattern;
static struct {uint8_t prev,current,next;} seq_rndValue[7];
static struct {uint8_t length[1][7];struct {uint8_t prob;} seq_subStepPattern[1][7][64];} seq_patternSet;
static uint8_t seq_intIsMainStepActive(uint8_t t,uint8_t s,uint8_t p){(void)t;(void)s;(void)p;return 1;}
'''
c += seq[seq.index('/* Slip core:'):seq.index('static void seq_triggerSequenced')]
c+=extract(source('Core/Src/Soundengine/MIDI/MidiParser.c'),'midiParser_checkMtc')
c+=clock
c+='static SyncPulseHistory trigger_history;\n'
for name in ['trigger_ResetPosition','EXTI4_IRQHandler','EXTI9_5_IRQHandler']:
    c+=extract(trigger,name)
c+='typedef struct {uint8_t status;} MidiMsg;\nstatic uint8_t midiParser_txRxFilter=MIDI_FILTER_SYSTEM | (MIDI_FILTER_SYSTEM<<4);\nstatic void seq_sendMidi(MidiMsg msg){assert(!primask);echoes++;(void)msg;}\n'
c+=extract(seq,'seq_sendRealtime')
for name in ['seq_setStepIndexToStart','seq_MidiSyncQueue','seq_setMidiRunning','seq_midiRunCleanup','seq_midiClockAnchor','seq_setExtSync','seq_resetPosition','seq_setRunning','seq_tick','seq_sync']:
    c+=extract(seq,name)
midi=source('Core/Src/Soundengine/MIDI/MidiParser.c')
dispatch=midi[midi.index('      case MIDI_CLOCK:'):midi.index('      case MIDI_SONG_POSITION_POINTER:')]
c+='static void received(uint8_t status){switch(status){'+dispatch+'default: break;}}\n'
# Actual DIN owner + dequeue function, endpoints inject a competing TIM2/main call.
c+=r'''
static unsigned dinQueued,parsedDin,usbQueued,parsedUsb;
static int fifo_midiRx,injectParser;
static uint8_t midiRxLost;
static uint32_t midiRxResyncCount;
static void midiParser_resetUart(void){assert(!primask);}
static void uart_abortMidiSource(uint8_t source){(void)source;assert(!primask);}
static int fifo_bufferOut(int *fifo,uint8_t *data){(void)fifo;if(!dinQueued)return 0;dinQueued--;*data=0;return 1;}
void uart_processMidi(void);
static void midiParser_parseUartData(uint8_t data){
 (void)data;assert(!primask);parsedDin++;
 if(injectParser){injectParser=0;uart_processMidi();seq_tick();}
}
'''+extract(source('Core/Src/Soundengine/MIDI/Uart.c'),'uart_processMidi')
main=source('Core/Src/main.c')
usb_start=main.index('if(sync_tryControl())',main.index('//check if we have some usb midi'))
usb_end=main.index('//process midi on midi port',usb_start)
usb=main[usb_start:usb_end]
c+=r'''
static int usb_getMidi(MidiMsg *msg){if(!usbQueued)return 0;usbQueued--;msg->status=0;return 1;}
static void midiParser_parseMidiMessage(MidiMsg msg){(void)msg;assert(!primask);parsedUsb++;uart_processMidi();seq_tick();}
static void usbMain(void){MidiMsg msg;
'''+usb+'}\n'
c+=r'''
static void init(uint32_t now,uint8_t mode){
 assert(!primask);systick_ticks=now;seq_setExtSync(mode);sync_sourceChanged();
 seq_running=1;seq_masterStepCnt=0;steps=0;seq_tempo=100;bpmWrites=0;
 seq_deltaT=1000000;seq_lastTick=now;delayTicks=100;seq_prescaleCounter=0;
}
static void pulse(uint32_t now){systick_ticks=now;if(seq_getExtSync()==2)seq_sync();else EXTI4_IRQHandler();}
static void poll(uint32_t now){systick_ticks=now;seq_tick();}
int main(void){
 /* Real clock/transport bodies publish cancellation to the real slip core.
  * Step/DSP endpoints remain bounded adapters, not whole-sequencer simulation. */
 init(0,2);seq_stepIndex[0]=0;
 seq_slipPress(0);seq_slipPress(3);seq_slipSync();assert(seq_slipCount==2);
 pulse(0);assert(seq_slipPhase==1); /* real MIDI clock boundary adapter */
 received(MIDI_STOP);seq_slipSync();assert(!seq_slipCount && seq_slipOwner()==0xff);
 received(MIDI_CONTINUE);pulse(100);seq_slipSync();assert(!seq_slipCount);
 seq_slipRelease(0);seq_slipRelease(3);seq_slipPress(1);seq_slipSync();assert(seq_slipLength==4);
 received(MIDI_START);seq_slipSync();assert(!seq_slipCount);
 seq_slipPress(2);seq_slipSync();seq_resetPosition();seq_slipSync();assert(!seq_slipCount);
 seq_slipPress(0);seq_slipSync();seq_setRunning(0);seq_slipSync();assert(!seq_slipCount);
 const uint32_t bases[]={0,16777217,67108865,268435457,0xffffff00u};
 for(unsigned b=0;b<sizeof(bases)/sizeof(*bases);b++)for(unsigned mode=1;mode<=2;mode++){
  init(bases[b],mode);trigger_prescalerClockInput=PRE_24_PPQ_IN;
  for(unsigned p=0;p<48;p++){
   uint32_t now=bases[b]+100*p;pulse(now);poll(now);poll(now+99);
  }
  assert(steps==8);assert(seq_tempo==100);assert(bpmWrites==47);
 }
 /* First pulse is baseline; average actual valid samples, not eight zeros. */
 init(0,2);pulse(100);assert(bpmWrites==0&&seq_tempo==100);
 pulse(300);assert(seq_tempo==50);pulse(400);assert(seq_tempo==66);
 pulse(400);assert(seq_tempo==66); /* zero: hold prior BPM, fresh window */
 pulse(70400);assert(seq_tempo==66);pulse(70500);assert(seq_tempo==100);
 for(unsigned i=0;i<20;i++)pulse(70501+i);assert(seq_tempo==10000);
 /* Analogue 4PPQ intervals are normalised to 24PPQ before averaging. */
 init(123,1);trigger_prescalerClockInput=PRE_4_PPQ_IN;
 pulse(123);assert(bpmWrites==0);pulse(723);assert(seq_tempo==100);
 pulse(723);assert(seq_tempo==100);pulse(70723);assert(seq_tempo==100);
 pulse(71323);assert(seq_tempo==100);
 /* Supported slow analogue clocks: 2 BPM at both 4 and 24 PPQ. */
 for(unsigned ppq=0;ppq<2;ppq++){
  init(0,1);trigger_prescalerClockInput=ppq?PRE_24_PPQ_IN:PRE_4_PPQ_IN;
  uint32_t period=ppq?5000:30000;
  pulse(0);assert(!bpmWrites);
  for(unsigned i=1;i<=12;i++){pulse(i*period);assert(seq_tempo==2);}
  assert(bpmWrites==12);
 }
 /* Threshold is inclusive; a larger gap holds BPM and starts a fresh window. */
 init(0,2);pulse(0);pulse(60000);assert(bpmWrites==1);
 pulse(120001);assert(bpmWrites==1);pulse(120101);assert(seq_tempo==100);
 /* Received Stop/Continue preserve actual track arrays and all scalar phase. */
 init(0,2);pulse(0);pulse(100);assert(sync_getClockCnt()==2);
 for(unsigned i=0;i<NUM_TRACKS;i++){seq_stepIndex[i]=i*3+1;seq_lastMasterStep[i]=i+2;}
 uint8_t indices[NUM_TRACKS],masters[NUM_TRACKS];
 memcpy(indices,seq_stepIndex,sizeof indices);memcpy(masters,seq_lastMasterStep,sizeof masters);
 seq_songPositionPointer=9;seq_masterStepCnt=31;seq_prescaleCounter=7;
 seq_lastTick=80;seq_deltaT=60;systick_ticks=100;
 unsigned echoBefore=echoes,offBefore=noteOffs,breakBefore=breakCancels;
 midiParser_mtcIsRunning=1;midiParser_lastMtcReceived=0;
 received(MIDI_STOP);assert(!seq_running&&seq_midiRemaining==40&&!midiParser_mtcIsRunning);
 assert(seq_lastTick==80&&seq_deltaT==60&&seq_prescaleCounter==7);
 assert(noteOffs==offBefore+1&&breakCancels==breakBefore+1);
 for(unsigned i=2;i<40;i++){pulse(i*100);poll(i*100);}
 assert(sync_getClockCnt()==2&&seq_prescaleCounter==7&&seq_deltaT==60);
 received(MIDI_STOP);assert(noteOffs==offBefore+1);
 received(MIDI_CONTINUE);poll(9000);assert(seq_prescaleCounter==7);
 received(MIDI_CONTINUE);assert(sync_midiAwaitClock);
 received(MIDI_STOP);received(MIDI_CONTINUE);assert(seq_midiRemaining==40);
 pulse(10000);poll(10039);assert(seq_prescaleCounter==7);
 poll(10040);assert(seq_prescaleCounter==8);
 assert(!memcmp(indices,seq_stepIndex,sizeof indices)&&!memcmp(masters,seq_lastMasterStep,sizeof masters));
 assert(seq_songPositionPointer==9&&seq_masterStepCnt==31&&echoes==echoBefore);
 received(MIDI_CONTINUE);assert(!sync_midiAwaitClock&&seq_prescaleCounter==8);
 /* Start while paused resets actual arrays, song/master and divider, but waits. */
 received(MIDI_STOP);received(MIDI_START);assert(seq_running&&sync_midiAwaitClock);
 assert(!seq_masterStepCnt&&seq_songPositionPointer==-1&&!sync_clockCnt);
 for(unsigned i=0;i<NUM_TRACKS;i++)assert(seq_stepIndex[i]==-1&&!seq_lastMasterStep[i]);
 unsigned beforeStartSteps=steps;poll(20000);assert(steps==beforeStartSteps&&echoes==echoBefore);
 pulse(20100);assert(steps==beforeStartSteps+1&&!sync_midiAwaitClock);
 /* Freeze remaining shuffled delay across stopped clocks and repeated transport. */
 init(1000,2);seq_masterStepCnt=1;pulse(1000);assert(sync_delayedStepPending);
 systick_ticks=1040;received(MIDI_STOP);assert(!sync_delayedStepPending&&sync_savedDelay==60);
 for(unsigned i=0;i<20;i++){pulse(2000+i*100);poll(2000+i*100);}
 received(MIDI_CONTINUE);poll(9000);assert(!steps);
 received(MIDI_STOP);received(MIDI_CONTINUE);pulse(10000);
 poll(10059);assert(!steps);poll(10060);assert(steps==1);
 poll(10061);assert(steps==1);
 /* A long frozen shuffle survives faster clocks crossing the next divider zero.
  * Overload drops later step requests, rather than replacing/queuing them. */
 init(1000,2);seq_masterStepCnt=1;delayTicks=1000;pulse(1000);
 systick_ticks=1040;received(MIDI_STOP);assert(sync_savedDelay==960);
 for(unsigned i=0;i<20;i++)pulse(2000+i*10);
 delayTicks=10;received(MIDI_CONTINUE);pulse(10000);
 for(unsigned i=1;i<=6;i++){pulse(10000+i*10);poll(10000+i*10);}
 assert(sync_clockCnt==2&&sync_delayedStepTimer==10960&&!steps);
 poll(10959);assert(!steps);poll(10960);poll(10961);assert(steps==1);
 /* IRQs in Stop cleanup see frozen phase; Continue callbacks see await gating. */
 init(0,1);trigger_prescalerClockInput=PRE_24_PPQ_IN;
 trigger_clockCnt=3;seq_lastTick=0;seq_deltaT=100;systick_ticks=40;
 cleanupIrq=1;received(MIDI_STOP);
 assert(!cleanupIrq&&trigger_clockCnt==3&&!trigger_clockReceived&&seq_midiRemaining==60);
 trigger_clockCnt=0;seq_masterStepCnt=1;received(MIDI_CONTINUE);
 /* Continue has no autosave cleanup callback now. Inject the eligible edge
  * immediately after publication, before foreground polling instead. */
 assert(!primask);EXTI4_IRQHandler();
 assert(!cleanupIrq&&sync_midiAwaitClock&&!sync_interpolationAllowed());
 assert(trigger_clockReceived==1); /* eligible edge retained, not executed in callback */
 poll(1000);assert(!sync_midiAwaitClock&&!steps&&seq_deltaT==60);
 /* Received transport is still accepted with analogue selected. Its 24PPQ
  * musical divider freezes too; ordinary analogue stop behavior is unchanged. */
 init(0,1);trigger_prescalerClockInput=PRE_24_PPQ_IN;
 pulse(0);pulse(100);poll(100);assert(trigger_clockCnt==2);
 received(MIDI_STOP);for(unsigned i=0;i<20;i++){pulse(200+i*100);poll(200+i*100);}
 assert(trigger_clockCnt==2&&seq_tempo==100);
 received(MIDI_CONTINUE);unsigned analogBefore=steps;
 for(unsigned i=0;i<4;i++){pulse(3000+i*100);poll(3000+i*100);assert(steps==analogBefore);}
 pulse(3400);poll(3400);assert(steps==analogBefore); /* odd master: shuffle */
 poll(3500);assert(steps==analogBefore+1&&!sync_midiAwaitClock);
 /* Every divider phase, including zero, resumes without an early step. */
 for(unsigned phase=0;phase<6;phase++){
  init(1000,2);sync_clockCnt=phase;seq_masterStepCnt=2;seq_prescaleCounter=13;
  received(MIDI_STOP);for(unsigned i=0;i<17;i++)pulse(1100+100*i);
  assert(sync_clockCnt==phase);received(MIDI_CONTINUE);poll(9000);
  assert(!steps&&seq_prescaleCounter==13);pulse(9100);
  assert(steps==(phase==0)&&sync_clockCnt==(phase+1)%6);
 }
 /* Paused shuffle over timestamp wrap, including already-due remainder zero. */
 for(unsigned due=0;due<2;due++){
  init(0xffffffb0u,2);seq_masterStepCnt=1;pulse(systick_ticks);
  systick_ticks+=due?101:40;received(MIDI_STOP);
  assert(sync_savedDelay==(due?0:60));received(MIDI_CONTINUE);poll(1000);assert(!steps);
  pulse(2000);poll(2000+(due?0:59));assert(steps==due);
  poll(2060);assert(steps==1);
 }
 /* Start is a reset even when already running, unlike Continue. */
 init(0,2);pulse(0);seq_stepIndex[0]=9;received(MIDI_START);
 assert(seq_stepIndex[0]==-1&&!seq_masterStepCnt&&!sync_clockCnt&&!seq_prescaleCounter);
 assert(sync_midiAwaitClock&&!sync_midiHistory.baseline);poll(9000);assert(steps==1);
 pulse(9100);assert(steps==2);
 /* Source/panel/reset invalidate paused resume; panel still resets tracks. */
 for(unsigned action=0;action<4;action++){
  init(0,2);pulse(0);systick_ticks=20;received(MIDI_STOP);
  if(action==0)seq_setExtSync(1);
  if(action==1)seq_setRunning(0);
  if(action==2)seq_resetPosition();
  if(action==3)seq_setExtSync(0);
  assert(!sync_midiPaused&&!sync_savedDelayed&&!sync_midiAwaitClock);
 }
 init(0,2);seq_stepIndex[0]=12;seq_prescaleCounter=9;seq_setRunning(0);
 assert(seq_stepIndex[0]==-1);seq_setRunning(1);assert(!seq_prescaleCounter&&seq_stepIndex[0]==-1);
 /* Actual acceptance cases: RX filter/internal mode ignore received transport. */
 init(0,2);midiParser_txRxFilter=0;received(MIDI_STOP);assert(seq_running);
 midiParser_txRxFilter=MIDI_FILTER_SYSTEM | (MIDI_FILTER_SYSTEM<<4);seq_setExtSync(0);received(MIDI_STOP);assert(seq_running);
 init(0,1);received(MIDI_STOP);assert(!seq_running);received(MIDI_CONTINUE);assert(seq_running);
 /* Deadline zero is valid; unsigned half-range comparison across wrap. */
 init(0xffffff9cu,2);seq_masterStepCnt=1;pulse(systick_ticks);
 assert(sync_delayedStepPending&&sync_delayedStepTimer==0);
 poll(0xffffffffu);assert(steps==0);poll(0);assert(steps==1&&!sync_delayedStepPending);
 init(0xfffffff0u,2);seq_masterStepCnt=1;pulse(systick_ticks);
 poll(83);assert(steps==0);poll(84);assert(steps==1);poll(85);assert(steps==1);
 /* Stopped clocks may estimate tempo but must not queue or schedule steps. */
 for(unsigned mode=1;mode<=2;mode++){
  init(0,mode);trigger_prescalerClockInput=PRE_24_PPQ_IN;seq_setRunning(0);
  for(unsigned i=0;i<48;i++){pulse(i*100);poll(i*100);}
  assert(!steps&&!sync_delayedStepPending&&!trigger_clockReceived);
  assert(seq_tempo==100);
 }
 /* All stop/reset/source paths cancel delayed AND queued analogue work. */
 for(unsigned action=0;action<5;action++){
  init(1000,2);seq_masterStepCnt=1;pulse(1000);trigger_clockReceived=2;
  if(action==0)seq_setRunning(0);
  if(action==1)seq_resetPosition();
  if(action==2)seq_setExtSync(1);
  if(action==3)sync_midiResetPosition();
  if(action==4)sync_midiStartStop(0);
  assert(!sync_delayedStepPending&&!trigger_clockReceived);poll(1100);assert(!steps);
 }
 /* No phantom step after stop/reset/start with no new clock. */
 init(1000,2);seq_masterStepCnt=1;pulse(1000);
 sync_midiStartStop(0);sync_midiResetPosition();sync_midiStartStop(1);poll(1100);assert(!steps);
 /* IRQ handoff: no direct reset; latest run level + sticky reset. */
 init(1000,1);unsigned before=resets;
 resetPort.IDR=0;EXTI9_5_IRQHandler();assert(seq_running&&resets==before);
 pulse(1100);assert(!trigger_clockReceived);
 resetPort.IDR=32;EXTI9_5_IRQHandler();poll(1200);
 assert(seq_running&&resets==before+1&&!steps);
 /* IRQ during kit work doesn't enter transport; next seq_tick consumes it. */
 init(0,1);heavyIrq=1;pulse(0);poll(0);assert(steps==1&&seq_running);
 assert(sync_transportPending);poll(1);assert(!seq_running&&!sync_transportPending);
 /* Source switch injected after a step has entered: that one step may
  * complete, but old queued pulses/deadlines cannot produce another step. */
 for(unsigned from=1;from<=2;from++)for(unsigned to=0;to<=2;to++){
  if(from==to)continue;
  init(0,from);trigger_prescalerClockInput=PRE_4_PPQ_IN;
  sourceIrq=to+1;pulse(0);poll(0);
  assert(steps==1&&seq_getExtSync()==to&&!sourceIrq);
  assert(!sync_delayedStepPending&&!trigger_clockReceived);
  assert(!sync_midiHistory.baseline&&!trigger_history.baseline);
  poll(1);assert(steps==1);
 }
 /* Switch immediately before a shuffled deadline becomes due. */
 for(unsigned mode=1;mode<=2;mode++){
  init(1000,mode);trigger_prescalerClockInput=PRE_4_PPQ_IN;
  seq_masterStepCnt=1;pulse(1000);poll(1000);assert(sync_delayedStepPending);
  seq_setExtSync(mode==1?2:1);poll(1100);assert(!steps&&!sync_delayedStepPending);
 }
 /* Source change discards old analogue transport requests. */
 init(0,1);sync_requestAnalogTransport(0);seq_setExtSync(2);poll(0);assert(seq_running);
 /* IRQ reset ignored in internal/MIDI modes; transport MIDI remains accepted
  * in both external modes by unchanged MidiParser dispatch (checked below). */
 for(unsigned mode=0;mode<=2;mode+=2){init(0,mode);resetPort.IDR=0;EXTI9_5_IRQHandler();assert(!sync_transportPending);}
 /* An IRQ while the parser owns control stays pending until the next tick. */
 init(0,1);assert(sync_tryControl());sync_requestAnalogTransport(0);
 seq_tick();assert(seq_running&&sync_transportPending);
 sync_releaseControl();seq_tick();assert(!seq_running&&!sync_transportPending);
 /* Analogue deadline zero uses the same actual scheduling path. */
 init(0xffffff9cu,1);trigger_prescalerClockInput=PRE_4_PPQ_IN;seq_masterStepCnt=1;
 pulse(systick_ticks);poll(systick_ticks);assert(sync_delayedStepPending&&sync_delayedStepTimer==0);
 poll(0xffffffffu);assert(!steps);poll(0);assert(steps==1);
 /* Saved/restored PRIMASK, including nested transactions and busy failure. */
 primask=1;assert(sync_tryControl());assert(primask==1);assert(!sync_tryControl());
 sync_cancelPending();assert(primask==1);sync_releaseControl();assert(primask==1);primask=0;
 /* Ownership includes dequeue: contention cannot drop USB or DIN data. */
 init(0,2);assert(sync_tryControl());dinQueued=3;usbQueued=1;
 uart_processMidi();usbMain();seq_tick();assert(dinQueued==3&&usbQueued==1);
 sync_releaseControl();injectParser=1;uart_processMidi();assert(parsedDin==3&&!dinQueued);
 usbMain();assert(parsedUsb==1&&!usbQueued);assert(sync_tryControl());sync_releaseControl();
 /* At most 255 pending analogue pulses; no uint8_t overflow to zero. */
 init(0,1);trigger_prescalerClockInput=PRE_4_PPQ_IN;
 for(unsigned i=0;i<300;i++)pulse(i*600);assert(trigger_clockReceived==255);
 puts("external clock: pulse/uptime/wrap/averaging/cancellation/IRQ handoff/parser ownership pass");
}
'''
# Contract check: MIDI transport intentionally accepted in both external modes.
midi=source('Core/Src/Soundengine/MIDI/MidiParser.c')
for status in ['MIDI_START','MIDI_CONTINUE','MIDI_STOP']:
    block=midi[midi.index('case '+status+':'):].split('break;',1)[0]
    assert '&& seq_getExtSync())' in block
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);(p/'test.c').write_text(c)
    for flags in [[], ['-O3','-ffast-math','-freciprocal-math']]:
        subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Werror','-Wno-unused-function','-Wno-unused-variable','-fsanitize=address,undefined',*flags,str(p/'test.c'),'-o',str(p/'test')],check=True)
        subprocess.run([str(p/'test')],check=True)
