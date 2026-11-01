#!/usr/bin/env python3
"""Actual menu/table and Cortex dispatch extraction regression.

Hardware parameter storage/reset endpoints and morph interpolation are models; real automation recorder; this is not
an ADC, complete MIDI parser or physical button-event integration test. Held-step
arm/disarm are real C with a reduced pattern container and the real Step layout.
Real recorder lanes are checked; physical transport timing is not covered.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
def read(p):
    return (ROOT / p).read_text()
def clean(s):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', s, flags=re.S)
def fn(s, name):
    s = clean(s)
    m = re.search(r'^(?:static\s+)?(?:void|uint8_t|uint16_t)\s+' + name + r'\([^;]*?\)\s*\{', s, re.M)
    assert m, name
    end = s.index('{', m.start()) + 1
    depth = 1
    while depth:
        depth += (s[end] == '{') - (s[end] == '}')
        end += 1
    return s[m.start():end] + '\n'
menu = read('Core/Src/menu/menu.c')
h = clean(read('Core/Inc/menu/menu.h'))
text = read('Core/Inc/menu/MenuText.h')
cc = read('Core/Src/menu/Cc2Text.c')
c = '''#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define PROGMEM
#define pgm_read_word(p) (*(p))
#define pgm_read_byte(p) (*(p))
#define MASK_PARAMETER 7
#define MASK_PAGE 248
#define PAGE_SHIFT 3
#define NUM_SUB_PAGES 8
#define PRESET_KIT_TIMER 0
#define NO_STEP_SELECTED 255
#define DISABLE_CONV_WARNING
#define END_DISABLE_CONV_WARNING
#define MIDI_CC 0xb0
#define CC_2 0xf1
#define CC_LFO_TARGET 0xf2
#define CC_VELO_TARGET 0xf3
#define FRONT_CC_2 CC_2
#define FRONT_CC_LFO_TARGET CC_LFO_TARGET
'''
c += '\n'.join(re.findall(r'enum\s*\w*\s*\{[^}]*\}\s*;', clean(read('Core/Inc/Parameters.h')) + h))
for name in ('Page', 'ModTarg', 'ModTargetVoiceOffset'):
    c += re.search(r'typedef struct '+name+r'Struct\s*\{.*?\}\s*'+name+r';', h, re.S)[0]
c += '\n' + '\n'.join(re.findall(r'^#define MENU_.*', text, re.M)) + '\n'
c += '\n'.join(re.findall(r'const char \w+\[\]\[\d+\]\s*=\s*\{.*?\};', text, re.S))
c += re.search(r'const enum Datatypes PROGMEM parameter_dtypes\[NUM_PARAMS\] = \{.*?\};', menu, re.S)[0]
c += re.search(r'const Page menuPages.*?=\s*\{.*?\n\};', read('Core/Inc/menu/menuPages.h'), re.S)[0]
for pattern in (r'const ModTarg modTargets\[\].*?=\s*\{.*?\};', r'const ModTargetVoiceOffset modTargetVoiceOffsets\[6\].*?=\s*\{.*?\};', r'const uint8_t modTargetGapMap\[\].*?=\s*\{.*?\};'):
    c += re.search(pattern, cc, re.S)[0]
c += '''
#define NUM_TOT_TARGETS sizeof(modTargetGapMap)
uint8_t activeParameters[NUM_PARAMS], menu_activePage, menuIndex, menu_TargetVoiceGapIndex;
uint8_t menu_numSamples, editModeActive, saveScreenPots[4];
uint8_t buttonHandler_bulkOriginal[2],buttonHandler_originalValue[2], buttonHandler_resetLock1, buttonHandler_resetLock2;
uint16_t buttonHandler_originalParameter[2];
static uint8_t armed=NO_STEP_SELECTED, shift;
static unsigned normal, bulk, morphs, lanes, calls[NUM_PARAMS], nodeCalls[12];
static unsigned lastStatus,lastDest,lastValue, dispatched[NUM_PARAMS];
static uint8_t buttonHandler_getArmedAutomationStep(void){return armed;}
static uint8_t buttonHandler_getShift(void){return shift;}
static void screensaver_touch(void){}
static void menu_repaintAll(void){}
static void led_clearSequencerLeds(void){}
static void preset_touchTimer(int t){}
static void menu_handleSaveScreenKnobValue(int p,int v){}
static uint8_t menu_setMasterCompressor(uint16_t p,int32_t v){return 0;}
static uint8_t menu_setPerformanceFilter(uint16_t p,int16_t v){return 0;}
static void menu_parseGlobalParam(unsigned p,unsigned v){assert(p>=END_OF_SOUND_PARAMETERS);}
static unsigned seq_activeAutomTrack;
static void seq_setActiveAutomationTrack(unsigned t){lanes++;seq_activeAutomTrack=t;}
static uint8_t preset_getMorphValue(uint16_t p,uint8_t m){morphs++;return activeParameters[p]/2;}
typedef struct {uint8_t status,data1,data2;} MidiMsg;
typedef union {uint32_t itg;float flt;} ptrValue;
typedef struct {void *ptr;uint8_t type;} Parameter;
enum {TYPE_UINT8,TYPE_FLT,TYPE_SPECIAL_F,TYPE_UINT32,TYPE_SPECIAL_P,TYPE_SPECIAL_FILTER_F};
typedef struct {uint16_t destination;uint8_t type;ptrValue originalValue;float amount,lastVal;} ModulationNode;
typedef ModulationNode Node;
static Parameter parameterArray[NUM_PARAMS];
static uint8_t storage[NUM_PARAMS];
static unsigned resetCalls;
static uint16_t resetTrace[12];
/* Reset endpoint model, NOT production paramArray_setParameter: production
   replays activeParameters through MIDI, not originalValue into memory. */
static void paramArray_setParameter(uint16_t p,ptrValue original){
 assert(p<NUM_PARAMS);resetTrace[resetCalls%12]=p;resetCalls++;
 if(parameterArray[p].ptr && parameterArray[p].type==TYPE_UINT8)
  *(uint8_t*)parameterArray[p].ptr=activeParameters[p];
}
static void actual_modNode_setDestination(ModulationNode*,uint16_t);
static Node velocityModulators[6];
static struct {struct {Node modTarget;} lfo;} voiceArray[3],snareVoice,cymbalVoice,hatVoice;
static void modNode_setDestination(Node *n,uint8_t v){
 unsigned i; for(i=0;i<6;i++)if(n==&velocityModulators[i])break;
 if(i==6){Node *nodes[]={&voiceArray[0].lfo.modTarget,&voiceArray[1].lfo.modTarget,&voiceArray[2].lfo.modTarget,&snareVoice.lfo.modTarget,&cymbalVoice.lfo.modTarget,&hatVoice.lfo.modTarget};
 for(i=0;i<6;i++)if(n==nodes[i])break;assert(i<6);i+=6;}
 nodeCalls[i]++;actual_modNode_setDestination(n,v);
}
static void midiParser_ccHandler(MidiMsg msg,int direct,int record,float f){
 assert(direct==1 && record==0 && f==0.f);bulk++;
 unsigned p=msg.status==MIDI_CC?((msg.data1-1)&127):msg.data1+128;
 assert(p<END_OF_SOUND_PARAMETERS);calls[p]++;dispatched[p]=msg.data2;lastStatus=msg.status;lastDest=p;lastValue=msg.data2;
}
static void ordinaryCortex(uint8_t status,uint8_t p,uint8_t v);
static void frontPanel_sendData(unsigned s,unsigned p,unsigned v){
 normal++;lastStatus=s;lastDest=p;lastValue=v;
 if(s==MIDI_CC || s==CC_2)ordinaryCortex(s,p,v);
 else if(s==0xf4){extern int seq_armedArmedAutomationStep,seq_armedArmedAutomationTrack;
 seq_armedArmedAutomationStep=v? p:-1;seq_armedArmedAutomationTrack=v?(v&7):-1;}
}
'''
mod_source = read('Core/Src/Soundengine/DSPAudio/modulationNode.c').replace('IN_ITCM_RAM ', '')
c += fn(mod_source, 'modNode_resetTargets')
c += fn(mod_source, 'modNode_setDestination').replace('void modNode_setDestination(', 'static void actual_modNode_setDestination(')
c += fn(cc, 'voiceFromModTargValue')
for name in ('getModTargetGapIndex', 'getModTargetIdxFromGapIdx', 'getNumModTargets'):
    c += fn(cc, name)
cortex = read('Core/Src/Soundengine/MIDI/CortexParser.c')
for name in ('frontParser_applyLfoTarget', 'frontParser_dispatchNonRecording'):
    c += fn(cortex, name)
for name in ('getMaxEntriesForMenu', 'menu_stepAudioOutput', 'limitPotValueFromOriginal','limitPotValue', 'menu_processSpecialCaseValues', 'menu_getHeldOriginal','menu_dispatchParameter', 'menu_applyKnobParameter', 'menu_restoreHeldParameter', 'menu_dispatchHeldOriginal', 'menu_updateHeldOriginal', 'menu_changeAllKnob', 'menu_parseKnobValue'):
    c += fn(menu, name)
# Real held-step arm/disarm, with a reduced pattern container (real Step layout).
step_header = clean(read('Core/Inc/Preset/SeqStep.h'))
c += re.search(r'typedef struct StepStruct.*?}Step;', step_header, re.S)[0]
c += fn(read('Core/Inc/Soundengine/Sequencer/sequencer.h').replace('static inline ', 'static '), 'seq_automationTarget')
c += r"""
#define NUM_STEPS 64
#define NUM_TRACKS 7
#define ARM_AUTOMATION_STEP 0xf4
#define ARM_AUTOMATION 0x40
#define DISARM_AUTOMATION 0
#define buttonHandler_armedAutomationStep armed
typedef struct {Step seq_subStepPattern[1][NUM_TRACKS][NUM_STEPS];} PatternSet;
static PatternSet pattern;
static unsigned seq_activePattern;
static PatternSet *get_seq_patternSet_p(void){return &pattern;}
static uint8_t menu_getActiveVoice(void){return menu_activePage;}
static unsigned led_idx2StepLed(unsigned n){return n;}
static void led_setBlinkLed(unsigned n,unsigned v){}
"""
for name in ('buttonHandler_restoreOriginal', 'buttonHandler_armTimerActionStep', 'buttonHandler_disarmTimerActionStep'):
    c += fn(read('Core/Src/buttonHandler.c'), name)
# Compile the actual ordinary CC switch arms as a recording-positive control.
# Extract the production recorder, checking actual live and armed lane bytes.
ordinary = clean(cortex)
start = ordinary.index('case MIDI_CC:', ordinary.index('static void frontParser_handleMidiMessage', ordinary.index('void frontParser_dispatchNonRecording')))
end = ordinary.index('case FRONT_CC_LFO_TARGET:', start)
c += r"""
static MidiMsg cortex_midiMsg;
static unsigned frontParser_activeTrack;
static uint8_t seq_isAutomationStepArmed(void){return armed!=NO_STEP_SELECTED;}
#define seq_patternSet pattern
static uint8_t seq_recordActive;
static int seq_stepIndex[NUM_TRACKS];
int seq_armedArmedAutomationStep=-1,seq_armedArmedAutomationTrack=-1;
static uint8_t mainStepActive=1;
static uint8_t seq_intIsMainStepActive(uint8_t v,uint8_t s,uint8_t p){return mainStepActive;}
""" + fn(read('Core/Src/Soundengine/Sequencer/sequencer.c'), 'seq_recordAutomation') + r"""
static void ordinaryCortex(uint8_t status,uint8_t p,uint8_t v){
 cortex_midiMsg=(MidiMsg){status,p,v};switch(status){
""" + ordinary[start:end] + 'default: assert(0);}}\n'
c += r'''
static unsigned param(unsigned page,unsigned sub,unsigned slot){return *(&menuPages[page][sub].bot1+slot);}
static void reset(void){
 memset(activeParameters,0,sizeof activeParameters);memset(calls,0,sizeof calls);memset(nodeCalls,0,sizeof nodeCalls);
 memset(buttonHandler_originalParameter,0,sizeof buttonHandler_originalParameter);
 buttonHandler_resetLock1=buttonHandler_resetLock2=0;armed=NO_STEP_SELECTED;
 memset(velocityModulators,0,sizeof velocityModulators);
 memset(voiceArray,0,sizeof voiceArray);memset(&snareVoice,0,sizeof snareVoice);
 memset(&cymbalVoice,0,sizeof cymbalVoice);memset(&hatVoice,0,sizeof hatVoice);
 for(unsigned p=0;p<NUM_PARAMS;p++)parameterArray[p]=(Parameter){&storage[p],TYPE_UINT8};
 resetCalls=0;
 normal=bulk=morphs=lanes=0;shift=1;seq_recordActive=0;seq_activeAutomTrack=0;
 memset(buttonHandler_bulkOriginal,0,sizeof buttonHandler_bulkOriginal);
 seq_armedArmedAutomationStep=seq_armedArmedAutomationTrack=-1;
 for(unsigned i=0;i<6;i++){activeParameters[PAR_VOICE_LFO1+i]=i+1;activeParameters[PAR_TARGET_LFO1+i]=modTargetVoiceOffsets[i].start;}
}
int main(void){
 /* Actual reset visits all twelve nodes in production order, then setter
    reads the destination address AFTER reset. Endpoint models MIDI replay. */
 reset();
 Node *nodes[]={&velocityModulators[0],&velocityModulators[1],&velocityModulators[2],
 &velocityModulators[3],&velocityModulators[4],&velocityModulators[5],
 &voiceArray[0].lfo.modTarget,&voiceArray[1].lfo.modTarget,&voiceArray[2].lfo.modTarget,
 &snareVoice.lfo.modTarget,&cymbalVoice.lfo.modTarget,&hatVoice.lfo.modTarget};
 for(unsigned i=0;i<12;i++){
  nodes[i]->destination=i+1;nodes[i]->originalValue.itg=99;
  activeParameters[i+1]=20+i;storage[i+1]=200;
 }
 actual_modNode_setDestination(nodes[0],12);
 for(unsigned i=0;i<12;i++)assert(resetTrace[i]==i+1);
 assert(resetCalls==12 && nodes[0]->destination==12 && nodes[0]->originalValue.itg==31);
 for(unsigned i=1;i<=12;i++)assert(storage[i]==19+i);
 /* Menu selector resolves the table index to the actual destination address
    and caches that address's value (not the UI selector byte). */
 reset();unsigned selector=modTargetVoiceOffsets[0].start;
 unsigned destination=modTargets[selector].param;
 storage[destination]=93;
 menu_applyKnobParameter(PAR_VEL_DEST_1,selector,1,1);
 assert(velocityModulators[0].destination==destination);
 assert(velocityModulators[0].originalValue.itg==93);
 /* Scalar width, float variants, special-F constant, special-P/default and
    null-pointer retained-cache semantics (destination still changes). */
 uint32_t wide=0xfedcba98;float real=2.75f;uint8_t byte=231;
 parameterArray[30]=(Parameter){&wide,TYPE_UINT32};
 actual_modNode_setDestination(nodes[0],30);assert(nodes[0]->originalValue.itg==wide);
 parameterArray[31]=(Parameter){&real,TYPE_FLT};
 actual_modNode_setDestination(nodes[0],31);assert(nodes[0]->originalValue.flt==real);
 parameterArray[32]=(Parameter){&real,TYPE_SPECIAL_FILTER_F};
 actual_modNode_setDestination(nodes[0],32);assert(nodes[0]->originalValue.flt==real);
 parameterArray[33]=(Parameter){&real,TYPE_SPECIAL_F};
 actual_modNode_setDestination(nodes[0],33);assert(nodes[0]->originalValue.flt==1.f);
 parameterArray[34]=(Parameter){&byte,TYPE_UINT8};
 actual_modNode_setDestination(nodes[0],34);assert(nodes[0]->originalValue.itg==byte);
 for(unsigned type=TYPE_SPECIAL_P;type<=99;type+=95){
  parameterArray[35]=(Parameter){&real,type};nodes[0]->originalValue.itg=12345;
  actual_modNode_setDestination(nodes[0],35);assert(nodes[0]->originalValue.itg==12345);
 }
 parameterArray[36]=(Parameter){0,TYPE_FLT};
 actual_modNode_setDestination(nodes[0],36);
 assert(nodes[0]->destination==36 && nodes[0]->originalValue.itg==12345);
 /* Every real voice/subpage/slot, both banks, mixed starting values, both
    directions and native endpoints; no selected-voice-max shortcut. */
 for(unsigned selected=0;selected<7;selected++)for(unsigned sub=0;sub<8;sub++)
 for(unsigned slot=0;slot<8;slot++)for(int delta=-127;delta<=127;delta+=127){
  reset();menu_activePage=selected;menuIndex=(sub<<3)|(slot&4);
  unsigned expected[NUM_PARAMS]={0};uint8_t before[NUM_PARAMS],want[NUM_PARAMS];
  for(unsigned p=0;p<END_OF_SOUND_PARAMETERS;p++)
   if((parameter_dtypes[p]&255)!=DTYPE_VOICE_LFO && (parameter_dtypes[p]&255)!=DTYPE_TARGET_SELECTION_LFO && (parameter_dtypes[p]&255)!=DTYPE_TARGET_SELECTION_VELO)activeParameters[p]=(p*17)%128;
  memcpy(before,activeParameters,sizeof before);memcpy(want,before,sizeof want);
  for(unsigned page=0;page<7;page++){
   unsigned p=param(page,sub,slot);if(p==PAR_NONE || p>=END_OF_SOUND_PARAMETERS)continue;
   expected[p]=1;want[p]=limitPotValue(delta,p);
   unsigned type=parameter_dtypes[p]&255;
   if(type==DTYPE_TARGET_SELECTION_VELO || type==DTYPE_TARGET_SELECTION_LFO){
    unsigned voice=type==DTYPE_TARGET_SELECTION_VELO?p-PAR_VEL_DEST_1:before[PAR_VOICE_LFO1+p-PAR_TARGET_LFO1]-1;
    if(want[p]<modTargetVoiceOffsets[voice].start)want[p]=delta<0?0:modTargetVoiceOffsets[voice].start;
    if(want[p]>modTargetVoiceOffsets[voice].end)want[p]=modTargetVoiceOffsets[voice].end;
   }
  }
  unsigned any=0;for(unsigned p=0;p<NUM_PARAMS;p++)any+=expected[p];
  unsigned result=menu_parseKnobValue(slot%4,delta);
  if(any){assert(result==1);assert(normal==0 && lanes==0);
   for(unsigned p=0;p<NUM_PARAMS;p++){
    if(expected[p]){assert(activeParameters[p]==want[p]);
     unsigned type=parameter_dtypes[p]&255;
     if(type!=DTYPE_VOICE_LFO && type!=DTYPE_TARGET_SELECTION_LFO && type!=DTYPE_TARGET_SELECTION_VELO)assert(calls[p]==1);
    }else if(!(sub==6 && slot==6 && p>=PAR_TARGET_LFO1 && p<=PAR_TARGET_LFO6))assert(activeParameters[p]==before[p]);
   }
  }
 }
 /* Special setters: destinations reach the actual velocity node addresses;
    voice changes preserve each LFO's own gap rather than selected cache. */
 reset();menu_activePage=0;menuIndex=2<<3|4;menu_parseKnobValue(0,1);
 for(unsigned i=0;i<4;i++){assert(nodeCalls[i]==1);assert(velocityModulators[i].destination==modTargets[modTargetVoiceOffsets[i].start].param);}
 reset();menu_activePage=6;menuIndex=6<<3|4;
 unsigned targets[6];for(unsigned i=0;i<6;i++){
  activeParameters[PAR_TARGET_LFO1+i]=modTargetVoiceOffsets[i].start+i;
  unsigned gap=getModTargetGapIndex(activeParameters[PAR_TARGET_LFO1+i]);
  targets[i]=getModTargetIdxFromGapIdx(i<5?i+1:5,gap);
 }
 menu_TargetVoiceGapIndex=0xff;menu_parseKnobValue(2,1);
 for(unsigned i=0;i<6;i++){assert(activeParameters[PAR_TARGET_LFO1+i]==targets[i]);assert(nodeCalls[i+6]==1);}
 assert(menu_TargetVoiceGapIndex==getModTargetGapIndex(targets[5]));
 /* Explicit regressions: mismatched OSC/ENV/FM rows, empty selected slots,
    HH shared targets deduplicated but separate decay enums both visited. */
 assert(param(0,0,2)!=param(3,0,2));assert(param(0,1,2)!=param(3,1,2));
 assert(param(0,3,0)!=param(3,3,0));
 assert(param(3,0,2)==PAR_NOISE_FREQ1 && param(3,0,4)==PAR_OSC_WAVE_SNARE);
 assert(param(3,1,2)==PAR_REPEAT4 && param(3,1,3)==PAR_VOL_SLOPE4);
 assert(param(0,3,0)==PAR_FMAMNT1 && param(0,3,1)==PAR_FM_FREQ1);
 reset();menu_activePage=0;menuIndex=0|4;assert(param(0,0,4)==PAR_NONE);
 menu_parseKnobValue(0,1);assert(activeParameters[PAR_OSC_WAVE_SNARE]==1);
 reset();menu_activePage=0;menuIndex=1<<3;menu_parseKnobValue(1,1);
 assert(calls[PAR_VELOD6_CLOSED]==1 && calls[PAR_VELOD6_OPEN]==1);
 menu_parseKnobValue(0,1);assert(calls[PAR_VELOA6]==1);
 for(unsigned sub=0;sub<8;sub++)for(unsigned slot=0;slot<8;slot++){
  reset();menu_activePage=6;menuIndex=(sub<<3)|(slot&4);menu_parseKnobValue(slot%4,1);
  unsigned a=param(5,sub,slot),b=param(6,sub,slot);
  if(a!=PAR_NONE && a<END_OF_SOUND_PARAMETERS && (parameter_dtypes[a]&255)<DTYPE_TARGET_SELECTION_VELO && calls[a])assert(calls[a]==1);
  (void)b;
 }
 /* Selected waveform already at its own maximum must not block peers. */
 reset();menu_activePage=0;menuIndex=0;
 unsigned max=getMaxEntriesForMenu(parameter_dtypes[PAR_OSC_WAVE_DRUM1]>>8)-1;
 activeParameters[PAR_OSC_WAVE_DRUM1]=max;menu_parseKnobValue(2,1);
 assert(activeParameters[PAR_OSC_WAVE_DRUM1]==max && activeParameters[PAR_NOISE_FREQ1]==1);
 /* Held companion destination must persist when changing LFO target voice. */
 reset();menu_activePage=0;menuIndex=6<<3|4;armed=3;
 buttonHandler_resetLock1=buttonHandler_resetLock2=1;
 buttonHandler_originalParameter[0]=PAR_VOICE_LFO1;buttonHandler_originalParameter[1]=PAR_TARGET_LFO1;
 buttonHandler_originalValue[0]=activeParameters[PAR_VOICE_LFO1];buttonHandler_originalValue[1]=activeParameters[PAR_TARGET_LFO1];
 menu_parseKnobValue(2,1);
 assert(buttonHandler_originalValue[0]==2);
 assert(buttonHandler_originalValue[1]==activeParameters[PAR_TARGET_LFO1]);
 /* Held voice preview must not change persistent LFO destination limits. */
 reset();menu_activePage=0;menuIndex=(6<<3)|4;armed=3;
 buttonHandler_resetLock1=1;buttonHandler_originalParameter[0]=PAR_VOICE_LFO1;
 buttonHandler_originalValue[0]=1;activeParameters[PAR_VOICE_LFO1]=4;
 activeParameters[PAR_TARGET_LFO1]=modTargetVoiceOffsets[0].end;
 menu_parseKnobValue(3,1);
 assert(activeParameters[PAR_TARGET_LFO1]==modTargetVoiceOffsets[0].end);
 assert(activeParameters[PAR_VOICE_LFO1]==4 && buttonHandler_originalValue[0]==1);
 /* OUT uses local order, not canonical numeric order; no morph on routing. */
 reset();menu_activePage=0;menuIndex=(7<<3)|4;menu_parseKnobValue(0,1);
 for(unsigned p=PAR_AUDIO_OUT1;p<=PAR_AUDIO_OUT6;p++){assert(activeParameters[p]==6);assert(calls[p]==1);}assert(morphs==0);
 /* Real Cortex LFO addresses and CC/CC2 normalization. */
 reset();for(unsigned i=0;i<6;i++)frontParser_dispatchNonRecording(CC_LFO_TARGET,i*2|1,3);
 for(unsigned i=6;i<12;i++)assert(nodeCalls[i]==1);
 assert(voiceArray[0].lfo.modTarget.destination==131 && hatVoice.lfo.modTarget.destination==131);
 frontParser_dispatchNonRecording(MIDI_CC,127,7);assert(lastDest==127 && lastValue==7);
 frontParser_dispatchNonRecording(CC_2,0,9);assert(lastDest==128 && lastValue==9);
 /* Recording-positive control uses actual ordinary Cortex CC branches.
    Bulk must bypass capture with recording enabled, even while step armed. */
 reset();seq_recordActive=1;frontParser_activeTrack=0;seq_stepIndex[0]=5;
 ordinaryCortex(MIDI_CC,4,7);
 assert(pattern.seq_subStepPattern[0][0][5].param1Nr==5 && pattern.seq_subStepPattern[0][0][5].param1Val==7);
 seq_activeAutomTrack=1;ordinaryCortex(CC_2,4,9);
 assert(pattern.seq_subStepPattern[0][0][5].param2Nr==132 && pattern.seq_subStepPattern[0][0][5].param2Val==9);
 seq_armedArmedAutomationStep=3;seq_armedArmedAutomationTrack=0;armed=3;
 ordinaryCortex(CC_2,4,11);assert(pattern.seq_subStepPattern[0][0][3].param2Val==11);
 PatternSet bulkSnapshot=pattern;
 menu_activePage=0;menuIndex=0;menu_parseKnobValue(0,1);
 menuIndex=7<<3|4;menu_parseKnobValue(0,1);
 assert(!memcmp(&pattern,&bulkSnapshot,sizeof pattern));
 seq_recordActive=0;
 /* Bulk changes source values while dispatching the real setter's morph
    result; interpolation math itself remains a deterministic endpoint spy. */
 reset();menu_activePage=0;menuIndex=0;activeParameters[PAR_COARSE1]=40;
 activeParameters[PAR_MORPH]=64;menu_parseKnobValue(0,2);
 assert(activeParameters[PAR_COARSE1]==42 && morphs==6 && normal==0);
 /* Observe the selected source individually through the same real setter. */
 menu_applyKnobParameter(PAR_COARSE1,44,2,1);
 assert(activeParameters[PAR_COARSE1]==44 && lastValue==22);
 /* Ordinary edits still route through recording-capable transport and morph. */
 reset();shift=0;menu_activePage=0;menuIndex=0;activeParameters[PAR_COARSE1]=40;activeParameters[PAR_MORPH]=64;
 menu_parseKnobValue(0,2);assert(normal==1 && bulk==1 && morphs==1 && lastValue==21);
 /* Held originals: bulk updates both lanes without allocation, ordinary
    follow-up stays temporary. Real arm/disarm lifecycle exercised below (physical event handlers are not compiled). */
 reset();armed=3;buttonHandler_resetLock1=buttonHandler_resetLock2=1;
 buttonHandler_originalParameter[0]=PAR_COARSE1;buttonHandler_originalParameter[1]=PAR_FINE1;
 activeParameters[PAR_COARSE1]=30;activeParameters[PAR_FINE1]=40;
 buttonHandler_originalValue[0]=30;buttonHandler_originalValue[1]=40;
 menu_activePage=0;menuIndex=0;menu_parseKnobValue(0,2);menu_parseKnobValue(1,3);
 assert(buttonHandler_originalValue[0]==32 && buttonHandler_originalValue[1]==43 && lanes==0);
 shift=0;menu_parseKnobValue(0,1);assert(buttonHandler_originalValue[0]==32 && activeParameters[PAR_COARSE1]==33);
 /* Duplicate held IDs retain the same persistent original in BOTH slots. */
 reset();menu_activePage=0;menuIndex=0;activeParameters[PAR_COARSE1]=30;
 Step *duplicate=&pattern.seq_subStepPattern[0][0][3];
 duplicate->param1Nr=duplicate->param2Nr=PAR_COARSE1+1;
 duplicate->param1Val=70;duplicate->param2Val=80;
 buttonHandler_armTimerActionStep(3);
 assert(buttonHandler_originalValue[0]==30 && buttonHandler_originalValue[1]==30);
 menu_parseKnobValue(0,2);
 assert(buttonHandler_originalValue[0]==32 && buttonHandler_originalValue[1]==32);
 assert(buttonHandler_bulkOriginal[0] && buttonHandler_bulkOriginal[1]);
 buttonHandler_disarmTimerActionStep();assert(activeParameters[PAR_COARSE1]==32);
 /* Replacing an occupied held lane: bulk-original restore bypasses recorder;
    replacement clears its bypass flag so subsequent ordinary capture works. */
 reset();menu_activePage=0;menuIndex=0;seq_recordActive=1;seq_stepIndex[0]=5;
 Step *occupied=&pattern.seq_subStepPattern[0][0][3];
 occupied->param1Nr=PAR_COARSE1+1;occupied->param1Val=70;
 occupied->param2Nr=PAR_FINE1+1;occupied->param2Val=80;
 activeParameters[PAR_COARSE1]=30;buttonHandler_armTimerActionStep(3);
 menu_parseKnobValue(0,2);assert(buttonHandler_bulkOriginal[0]);
 seq_activeAutomTrack=0;shift=0;
 PatternSet replaceSnapshot=pattern;
 menu_parseKnobValue(2,1); /* waveform replaces coarse in occupied lane zero */
 unsigned replacement=param(0,0,2);
 assert(buttonHandler_originalParameter[0]==replacement && !buttonHandler_bulkOriginal[0]);
 assert(activeParameters[PAR_COARSE1]==32);
 assert(occupied->param1Nr==replacement+1);
 assert(pattern.seq_subStepPattern[0][0][5].param1Nr==replacement+1);
 assert(occupied->param2Nr==replaceSnapshot.seq_subStepPattern[0][0][3].param2Nr);
 unsigned captured=occupied->param1Val;
 menu_parseKnobValue(2,1);assert(occupied->param1Val==captured+1);
 /* Bulk protects both originals. An ordinary fine edit re-enables only
    fine restoration through the recording-capable transport. */
 reset();menu_activePage=0;menuIndex=0;
 Step *mixed=&pattern.seq_subStepPattern[0][0][3];
 mixed->param1Nr=PAR_COARSE1+1;mixed->param1Val=70;
 mixed->param2Nr=PAR_FINE1+1;mixed->param2Val=80;
 activeParameters[PAR_COARSE1]=30;activeParameters[PAR_FINE1]=40;
 buttonHandler_armTimerActionStep(3);
 assert(!buttonHandler_bulkOriginal[0] && !buttonHandler_bulkOriginal[1]);
 menu_parseKnobValue(0,2);
 assert(buttonHandler_bulkOriginal[0] && buttonHandler_bulkOriginal[1]);
 assert(buttonHandler_originalValue[1]==40);
 shift=0;menu_parseKnobValue(1,1);
 assert(!buttonHandler_bulkOriginal[1] && buttonHandler_originalValue[1]==40);
 unsigned normalBefore=normal;
 buttonHandler_disarmTimerActionStep();
 assert(normal==normalBefore+2); /* slot one restore + disarm; slot zero bypass */
 assert(activeParameters[PAR_COARSE1]==32 && activeParameters[PAR_FINE1]==40);
 assert(!buttonHandler_bulkOriginal[0] && !buttonHandler_bulkOriginal[1]);
 /* Normal -> bulk -> normal, actual held preview/restoration. Both Shift/
    step release orders; only the subsequent ordinary restore records.
    Real recorder writes both liveREC and armed destinations. */
 for(unsigned order=0;order<2;order++){
  reset();menu_activePage=0;menuIndex=0;
  seq_recordActive=1;seq_stepIndex[0]=5;
  memset(&pattern,0xa5,sizeof pattern);
  Step *st=&pattern.seq_subStepPattern[0][0][3];
  st->param1Nr=PAR_COARSE1+1;st->param1Val=70;
  st->param2Nr=PAR_FINE1+1;st->param2Val=80;
  PatternSet snapshot=pattern;
  activeParameters[PAR_COARSE1]=30;activeParameters[PAR_FINE1]=40;
  buttonHandler_armTimerActionStep(3);
  assert(activeParameters[PAR_COARSE1]==70 && activeParameters[PAR_FINE1]==80);
  shift=0;menu_parseKnobValue(0,1);assert(buttonHandler_originalValue[0]==30);
  snapshot=pattern;
  shift=1;menu_parseKnobValue(0,2);menu_parseKnobValue(1,3);
  assert(!memcmp(&pattern,&snapshot,sizeof pattern));
  assert(buttonHandler_bulkOriginal[0] && buttonHandler_bulkOriginal[1]);
  assert(buttonHandler_originalValue[0]==32 && buttonHandler_originalValue[1]==43);
  shift=0;menu_parseKnobValue(0,1);assert(activeParameters[PAR_COARSE1]==33);
  snapshot=pattern;
  if(order)shift=1; /* step first; otherwise Shift already released */
  buttonHandler_disarmTimerActionStep();shift=0;
  assert(activeParameters[PAR_COARSE1]==32 && activeParameters[PAR_FINE1]==43);
  assert(!buttonHandler_resetLock1 && !buttonHandler_resetLock2);
  assert(memcmp(&pattern,&snapshot,sizeof pattern)); /* ordinary coarse restore intentionally records */
  assert(pattern.seq_subStepPattern[0][0][5].param1Nr==PAR_COARSE1+1);
  assert(pattern.seq_subStepPattern[0][0][5].param1Val==32);
  assert(pattern.seq_subStepPattern[0][0][5].param2Nr==snapshot.seq_subStepPattern[0][0][5].param2Nr);
  assert(pattern.seq_subStepPattern[0][0][5].param2Val==snapshot.seq_subStepPattern[0][0][5].param2Val);
 }

 /* Review 2: only coarse is bulk-edited; untouched fine release must not
    record. Nonzero morph applies on both restores, sources stay canonical. */
 for(unsigned order=0;order<2;order++)for(unsigned capped=0;capped<2;capped++){
  reset();menu_activePage=0;menuIndex=0;seq_recordActive=1;seq_stepIndex[0]=5;
  memset(&pattern,0xa5,sizeof pattern);
  Step *st=&pattern.seq_subStepPattern[0][0][3];
  st->param1Nr=PAR_COARSE1+1;st->param1Val=70;
  st->param2Nr=PAR_FINE1+1;st->param2Val=80;
  activeParameters[PAR_COARSE1]=capped?127:30;activeParameters[PAR_FINE1]=40;
  activeParameters[PAR_MORPH]=64;
  shift=order; /* held first versus Shift first */
  buttonHandler_armTimerActionStep(3);
  shift=1;
  PatternSet snapshot=pattern;
  menu_parseKnobValue(0,2);
  if(!order)shift=0;
  unsigned before=morphs, coarseCalls=calls[PAR_COARSE1];
  buttonHandler_disarmTimerActionStep();shift=0;
  assert(calls[PAR_COARSE1]==coarseCalls+1 && dispatched[PAR_COARSE1]==(capped?63:16));
  assert(!memcmp(&pattern,&snapshot,sizeof pattern));
  assert(activeParameters[PAR_COARSE1]==(capped?127:32) && activeParameters[PAR_FINE1]==40);
  assert(morphs==before+2 && lastDest==PAR_FINE1 && lastValue==20);
 }

 /* Real held release of coupled selectors: canonical voice/target survives,
    selected page is another voice, and no ordinary CC reaches the wrong node. */
 reset();menu_activePage=0;menuIndex=(6<<3)|4;seq_recordActive=1;seq_stepIndex[0]=5;
 memset(&pattern,0xa5,sizeof pattern);
 Step *selectors=&pattern.seq_subStepPattern[0][0][3];
 selectors->param1Nr=PAR_VOICE_LFO1;selectors->param1Val=4;
 selectors->param2Nr=PAR_TARGET_LFO1;selectors->param2Val=modTargetVoiceOffsets[3].start;
 unsigned sourceTarget=activeParameters[PAR_TARGET_LFO1];
 buttonHandler_armTimerActionStep(3);
 PatternSet selectorSnapshot=pattern;
 activeParameters[PAR_MORPH]=64;
 menu_parseKnobValue(2,1);
 unsigned target=getModTargetIdxFromGapIdx(1,getModTargetGapIndex(sourceTarget));
 assert(buttonHandler_originalValue[0]==2 && buttonHandler_originalValue[1]==target);
 menu_activePage=4; /* release cannot use selected voice's cached gap */
 unsigned otherNodeCalls=nodeCalls[10];
 buttonHandler_disarmTimerActionStep();
 assert(activeParameters[PAR_VOICE_LFO1]==2 && activeParameters[PAR_TARGET_LFO1]==target);
 assert(voiceArray[0].lfo.modTarget.destination==modTargets[target].param);
 assert(nodeCalls[10]==otherNodeCalls);
 assert(!memcmp(&pattern,&selectorSnapshot,sizeof pattern));
 puts("change-all: actual menu rows/all banks/native clamps/dedup/setters/Cortex dispatch/morph/held arm-disarm passed");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / 'test.c'
    exe = Path(tmp) / 'test'
    src.write_text(c)
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', str(src), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
