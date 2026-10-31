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
static float seq_deltaT=1000000,seq_lastShuffle;
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
static uint8_t seq_getExtSync(void){return seq_isSyncExternal;}
static uint8_t seq_isRunning(void){return seq_running;}
static uint16_t seq_getMasterStepCnt(void){return seq_masterStepCnt;}
static uint16_t seq_getBpm(void){return seq_tempo;}
static void seq_setBpm(uint16_t bpm){seq_tempo=bpm;bpmWrites++;}
static float delayTicks=100;
static float seq_getDeltaTShuffleDelay(uint16_t bpm){(void)bpm;return delayTicks;}
static void seq_MidiSyncQueue(uint8_t x){(void)x;}
/* Inject a reset IRQ DURING a simulated heavy step/kit operation. It must
 * only publish a request, not reenter transport or mask the heavy work. */
void seq_setExtSync(uint8_t);
static void seq_nextStep(void){
 assert(!primask);if(!seq_running)return;steps++;seq_masterStepCnt++;
 if(sourceIrq){unsigned mode=sourceIrq-1;sourceIrq=0;seq_setExtSync(mode);}
 if(heavyIrq){heavyIrq=0;kitWork=1;resetPort.IDR=0;EXTI9_5_IRQHandler();kitWork=0;assert(seq_running);}
}
static void seq_sendRealtime(uint8_t v){assert(!primask);(void)v;}
static void seq_setPerformanceBreak(uint8_t v){(void)v;}
static void preset_touchTimer(uint8_t t){assert(!primask);(void)t;}
static void trigger_reset(uint8_t v){assert(!primask);if(v)starts++;else stops++;}
static void seq_setStepIndexToStart(void){assert(!kitWork);assert(!primask);indexResets++;}
static void led_resetBlinkTimer(void){assert(!kitWork);assert(!primask);resets++;}
static void voiceControl_noteOff(uint8_t t){(void)t;assert(!primask);}
static void midiParser_checkMtc(void){assert(!primask);}
static void seq_calcDeltaT(uint16_t b,uint8_t s){(void)b;(void)s;seq_deltaT=1000000;}
static void trigger_clockTick(uint8_t v,uint8_t c){(void)v;(void)c;}
static void seq_processFlam(uint8_t c){(void)c;}
'''+api
# Clock source has public declarations; these extracted definitions use the same linkage.
c=c.replace('static void trigger_ResetPosition(void);','void trigger_ResetPosition(void);').replace('static void seq_setRunning(uint8_t);','void seq_setRunning(uint8_t);').replace('static void seq_resetPosition(void);','void seq_resetPosition(void);').replace('static void EXTI9_5_IRQHandler(void);','void EXTI9_5_IRQHandler(void);')
c+=clock
c+='static SyncPulseHistory trigger_history;\n'
for name in ['trigger_ResetPosition','EXTI4_IRQHandler','EXTI9_5_IRQHandler']:
    c+=extract(trigger,name)
for name in ['seq_setExtSync','seq_resetPosition','seq_setRunning','seq_tick','seq_sync']:
    c+=extract(seq,name)
# Actual DIN owner + dequeue function, endpoints inject a competing TIM2/main call.
c+=r'''
static unsigned dinQueued,parsedDin,usbQueued,parsedUsb;
static int fifo_midiRx,injectParser;
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
typedef uint8_t MidiMsg;
static int usb_getMidi(MidiMsg *msg){if(!usbQueued)return 0;usbQueued--;*msg=0;return 1;}
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
 /* MIDI stop preserves divider phase; stopped pulses still advance it.
  * Start retains existing track-index reset but reacquires a fresh tempo window. */
 init(0,2);pulse(0);pulse(100);assert(sync_getClockCnt()==2);
 unsigned indexBefore=indexResets;
 sync_midiStartStop(0);assert(sync_getClockCnt()==2);
 for(unsigned i=2;i<5;i++){pulse(i*100);assert(!sync_delayedStepPending);}
 assert(sync_getClockCnt()==5&&steps==1);
 sync_midiStartStop(1);assert(sync_getClockCnt()==5&&indexResets==indexBefore+2);
 assert(!sync_midiHistory.baseline&&!sync_midiHistory.count&&!sync_midiHistory.pos);
 pulse(500);assert(steps==1&&sync_getClockCnt()==0);
 pulse(700);assert(seq_tempo==50&&sync_delayedStepPending);
 poll(800);assert(steps==2);
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
