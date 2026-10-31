#!/usr/bin/env python3
"""Actual source functions, compiled with bounded fake endpoints; not hardware timing."""
from pathlib import Path
import re, os, subprocess, tempfile
root=Path(__file__).resolve().parents[1]
def extract(text,name):
    clean=re.sub(r'/\*.*?\*/|//[^\n]*',lambda m:' '*len(m[0]),text,flags=re.S)
    m=re.search(r'^(?:static )?(?:inline )?(?:void|uint8_t|uint16_t) '+name+r'\([^;\n]*\)\s*\{',clean,re.M)
    assert m,name
    pos=clean.index('{',m.start())+1;depth=1
    while depth:
        depth+=(clean[pos]=='{')-(clean[pos]=='}');pos+=1
    return text[m.start():pos]+'\n'
def run(code):
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'case.c';exe=Path(tmp)/'case';p.write_text(code)
        subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Werror','-Wno-unused-function',
            '-fsanitize=address,undefined','-I'+str(root/'tests/shim'),'-I'+str(root/'Core/Inc'),str(p),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
def implementation(path):
    revision=os.environ.get('LXR_BASE_REV')
    return subprocess.check_output(['git','-C',str(root),'show',revision+':'+path],text=True) if revision else (root/path).read_text()
case=os.environ.get('LXR_TEST_CASE','all')
seq=implementation('Core/Src/Soundengine/Sequencer/sequencer.c')
header=(root/'Core/Inc/Soundengine/Sequencer/sequencer.h').read_text()
c=r'''
#include <stdint.h>
#include <assert.h>
#define NUM_TRACKS 7
#define NUM_STEPS 64
#define USE_PATTERN_EDIT_BUFFER 0
#define STEP_VOLUME_MASK 127
#define PAR_MIDI_NOTE1 10
#define PAR_NONE 0
static int8_t seq_stepIndex[7];
static uint8_t seq_activePattern,seq_recordActive=1,seq_activeAutomTrack;
static int8_t seq_armedArmedAutomationStep=-1,seq_armedArmedAutomationTrack=-1;
static uint8_t midi_MidiChannels[8],activeParameters[300];
typedef struct {uint8_t volume,note,param1Nr,param1Val,param2Nr,param2Val;} Step;
static struct {Step seq_subStepPattern[1][7][64];} seq_patternSet;
static unsigned synth,notes,automation,velocity,lastNote;
static void seq_parseAutomationNodes(uint8_t v,Step*s){(void)v;(void)s;automation++;}
static void voiceControl_noteOff(uint8_t v){(void)v;}
static void voiceControl_noteOn(uint8_t v,uint8_t n,uint8_t vol){(void)v;(void)n;(void)vol;synth++;}
static void seq_sendMidiNoteOn(uint8_t c,uint8_t n,uint8_t v){(void)c;notes++;velocity=v;lastNote=n;}
static uint8_t seq_intIsMainStepActive(uint8_t v,uint8_t s,uint8_t p){assert(v<7&&s<64&&p==0);return 1;}
'''
c+=extract(header,'seq_automationTarget')+extract(seq,'seq_triggerVoice')+extract(seq,'seq_recordAutomation')
c+=r'''
int main(void){
 for(unsigned v=0;v<7;v++)seq_stepIndex[v]=-1;
 seq_triggerVoice(3,99,60);assert(synth==1&&notes==1&&velocity==99&&automation==0);
 activeParameters[PAR_MIDI_NOTE1+3]=42;
 seq_triggerVoice(3,90,60);assert(lastNote==42&&velocity==90);
 seq_recordAutomation(3,22,33);assert(seq_patternSet.seq_subStepPattern[0][3][0].param1Nr==0);
 seq_armedArmedAutomationStep=9;seq_armedArmedAutomationTrack=3;
 seq_recordAutomation(3,22,33);assert(seq_patternSet.seq_subStepPattern[0][3][9].param1Nr==22);
 seq_stepIndex[3]=4;seq_patternSet.seq_subStepPattern[0][3][4].volume=88;
 seq_triggerVoice(3,99,60);assert(automation==1&&velocity==99);
 seq_recordAutomation(3,44,55);assert(seq_patternSet.seq_subStepPattern[0][3][4].param1Nr==44);
 for(unsigned i=0;i<256;i++)assert(seq_automationTarget(i)==((i==0||i==255)?0:(i<128?i-1:i)));
 return 0;}
'''
if case != "midi": run(c)
# Preview/restore real panel functions, including two lanes targeting the same parameter.
panel=(root/'Core/Src/buttonHandler.c').read_text()
preview=c[:c.index('int main(void)')]+r"""
#define NO_STEP_SELECTED -1
#define ARM_AUTOMATION_STEP 1
#define ARM_AUTOMATION 128
#define DISARM_AUTOMATION 0
#define MIDI_CC 0xb0
#define CC_2 0xc0
#define END_OF_SOUND_PARAMETERS 247
typedef __typeof__(seq_patternSet) PatternSet;
static PatternSet *get_seq_patternSet_p(void){return &seq_patternSet;}
static uint8_t previewVoice=3;
static uint8_t menu_getActiveVoice(void){return previewVoice;}
static uint8_t led_idx2StepLed(uint8_t s){return s;}
static void led_setBlinkLed(uint8_t a,uint8_t b){(void)a;(void)b;}
static unsigned restoredParameter,restoredValue;
static void frontPanel_sendData(unsigned a,unsigned b,unsigned d){if(a==MIDI_CC||a==CC_2){restoredParameter=b+(a==CC_2?128:0);restoredValue=d;}}
static void menu_repaintAll(void){}
static void menu_parseGlobalParam(unsigned p,unsigned v){(void)p;(void)v;}
static int8_t buttonHandler_armedAutomationStep=-1;
static uint16_t buttonHandler_originalParameter[2];
static uint8_t buttonHandler_originalValue[2],buttonHandler_resetLock1,buttonHandler_resetLock2;
"""
preview+=extract(panel,'buttonHandler_armTimerActionStep')+extract(panel,'buttonHandler_disarmTimerActionStep')+r"""
int main(void){
 buttonHandler_armTimerActionStep(-1);buttonHandler_armTimerActionStep(64);
 assert(buttonHandler_armedAutomationStep==-1);
 previewVoice=7;buttonHandler_armTimerActionStep(0);
 assert(buttonHandler_armedAutomationStep==-1);previewVoice=3;
 Step *step=&seq_patternSet.seq_subStepPattern[0][3][5];
 step->param1Nr=step->param2Nr=200;step->param1Val=20;step->param2Val=30;
 activeParameters[200]=10;
 buttonHandler_armTimerActionStep(5);assert(activeParameters[200]==30);
 buttonHandler_disarmTimerActionStep();assert(activeParameters[200]==10);
 assert(restoredParameter==200&&restoredValue==10);
 assert(!buttonHandler_originalParameter[0]&&!buttonHandler_originalParameter[1]);
 step->param1Nr=22;step->param2Nr=0;step->param1Val=80;activeParameters[21]=40;
 buttonHandler_armTimerActionStep(5);assert(activeParameters[21]==80);
 buttonHandler_disarmTimerActionStep();assert(activeParameters[21]==40);
 assert(restoredParameter==21&&restoredValue==40);
 previewVoice=1;step=&seq_patternSet.seq_subStepPattern[0][1][7];
 step->param1Nr=129;step->param2Nr=255;step->param1Val=66;activeParameters[129]=55;
 buttonHandler_armTimerActionStep(7);assert(activeParameters[129]==66);
 buttonHandler_disarmTimerActionStep();assert(activeParameters[129]==55);
 assert(restoredParameter==129&&restoredValue==55);
 return 0;}
"""
if case != "midi": run(preview)
parser=implementation('Core/Src/Soundengine/MIDI/MidiParser.c')
if 'midiParser_handleStatusByte' in parser:
    framing = extract(parser,'midiParser_handleStatusByte')
    state = 'static uint8_t parserState,checkMIDIprocPAR_t; static int8_t checkMIDIprocPAR; static MidiMsg midiMsg_tmp;'
    reset = 'memset(&midiMsg_tmp,0,sizeof midiMsg_tmp);parserState=MIDI_STATUS;'
else:
    framing = (root/'Core/Src/Soundengine/MIDI/MidiStream.c').read_text()
    framing += extract(parser,'midiParser_resetUart')
    state = 'static MidiDecoder dinDecoder; static void uart_abortMidiSource(uint8_t source){(void)source;} static void usb_abortMidiSource(uint8_t source){(void)source;}'
    reset = 'midiParser_resetUart();'
c=r'''
#include "Soundengine/MIDI/MidiMessages.h"
#include "Soundengine/MIDI/MidiStream.h"
#include <assert.h>
#include <string.h>
enum {MIDI_STATUS,MIDI_DATA1,MIDI_DATA2,SYSEX_DATA,IGNORE};
static MidiMsg received[32];static unsigned count;
static void midiParser_parseMidiMessage(MidiMsg m){assert(count<32);received[count++]=m;}
'''+state+framing+extract(parser,'midiParser_parseUartData')+r'''
int main(void){
 unsigned char stream[]={0x90,60,0xf8,100,61,0xfa,110};
 for(unsigned i=0;i<sizeof stream;i++)midiParser_parseUartData(stream[i]);
 assert(count==4);
 assert(received[0].status==0xf8&&received[0].bits.length==0);
 assert(received[1].status==0x90&&received[1].data1==60&&received[1].data2==100);
 assert(received[2].status==0xfa&&received[2].bits.length==0);
 assert(received[3].status==0x90&&received[3].data1==61&&received[3].data2==110);
 count=0;RESET_DECODER;
 unsigned char sysex[]={0xf0,1,0xf8,2,0xf7};
 for(unsigned i=0;i<sizeof sysex;i++)midiParser_parseUartData(sysex[i]);
 assert(count==5&&received[2].status==0xf8&&!received[2].bits.sysxbyte);
 assert(received[3].bits.sysxbyte&&received[3].status==2);
 count=0;RESET_DECODER;
 unsigned char common[]={0x90,60,100,0xf3,4,61,101,0xf6,62,102};
 for(unsigned i=0;i<sizeof common;i++)midiParser_parseUartData(common[i]);
 assert(count==3);
 assert(received[1].status==0xf3&&received[1].bits.length==1&&received[1].data1==4);
 assert(received[2].status==0xf6&&received[2].bits.length==0);
 return 0;}
'''
if case != "seq": run(c.replace("RESET_DECODER;",reset))
# Both callers explicitly emit MIDI; low-level voice triggering must not duplicate it.
voice=(root/'Core/Src/Soundengine/MIDI/MidiVoiceControl.c').read_text()
assert 'seq_sendMidiNoteOn' not in extract(voice,'voiceControl_noteOn')
# Admission guards preserve the independent held-step recording branch.
if not os.environ.get('LXR_BASE_REV'): assert 'seq_stepIndex[trackNr] >= 0' in seq[seq.index('void seq_addNote('):][:600]
if not os.environ.get('LXR_BASE_REV'): assert 'midi_MidiChannels[voiceNr-1]' in parser
print('Control fixes: stopped trigger/automation and all target codes; realtime interleaving/running status/SysEx pass. Routing/recording guards checked.')
