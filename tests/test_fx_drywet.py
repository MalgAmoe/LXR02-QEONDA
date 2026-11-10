#!/usr/bin/env python3
"""Actual acceptance/dispatch bodies with bounded fake file/UI endpoints, no DSP model."""
from pathlib import Path
exec((Path(__file__).parent/'test_control_fixes.py').read_text().split('case=os.environ')[0].replace('-fsanitize=address,undefined', '-fsanitize=address,undefined,float-cast-overflow'))
def extract(text,name):
    clean=re.sub(r'/\*.*?\*/|//[^\n]*',lambda m:' '*len(m[0]),text,flags=re.S)
    m=re.search(r'^(?:IN_ITCM_RAM )?(?:static )?(?:void|uint8_t|FRESULT) '+name+r'\([^;]*?\)\s*\{',clean,re.M)
    assert m,name
    pos=clean.index('{',m.start())+1;depth=1
    while depth:
        depth+=(clean[pos]=='{')-(clean[pos]=='}');pos+=1
    return text[m.start():pos]+'\n'
parser=implementation('Core/Src/Soundengine/MIDI/MidiParser.c')
preset=implementation('Core/Src/Preset/presetManager.c')
panel=implementation('Core/Src/frontPanelParser.c')
# Keep the production conversion prefix, NRPN cases, cache write and amount case.
# Unrelated synth cases are excluded (their hardware endpoints are not under test).
f=extract(parser,'midiParser_ccHandler')
prefix=f[:f.index('\n\tif((msg.status &0xF0) == MIDI_CC)')]
cc=f[f.index('\t\tcase NRPN_DATA_ENTRY_COARSE:'):f.index('\t\tcase VOL_SLOPE1:')]
cache=f.split('else //MIDI_CC2')[1].split('switch(msg.data1)')[0]
amount=f[f.index('\t\t\tcase CC2_FX_AMOUNT:'):f.index('\t\t\tcase CC2_FX_DIST_TYPE:')]
c='''#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "Parameters.h"
#include "Soundengine/MIDI/MidiMessages.h"
#define IN_ITCM_RAM
#define USE_SD_CARD 1
#define CC_2 FRONT_CC_2
#define CC_VELO_TARGET 1
#define CC_LFO_TARGET 2
static uint8_t activeParameters[NUM_PARAMS],mainParameters[NUM_KIT_SLOTS][NUM_PARAMS];
static uint8_t *morphParameters=mainParameters[1];
static uint8_t midiParser_originalCcValues[255];
static uint16_t midiParser_activeNrpnNumber;
static struct {float dryWet;} fxBus;
void midiParser_ccHandler(MidiMsg,uint8_t,uint8_t,float);
'''
c+=extract(parser,'midiParser_nrpnHandler')+prefix+'''
if((msg.status&0xf0)==MIDI_CC){switch(msg.data1){
'''+cc+'''default:break;}}else{
'''+cache.lstrip().removeprefix('{')+'switch(msg.data1){'+amount+'default:break;}}}\n'
c+='''
static uint8_t getNumModTargets(void){return 1;}
uint8_t parameterOrder[END_OF_SOUND_PARAMETERS];
static struct {uint8_t param;} modTargets[1];
#define pgm_read_word(p) (*(p))
static void frontPanel_sendData(unsigned a,unsigned b,unsigned d){}
static void soundengine_process(void){}
static uint8_t morph_state,morph_index;
'''
c+=extract(preset,'preset_normalizeKit')+extract(preset,'preset_sendDrumsetParametersImmediate')+extract(preset,'interpolate')+extract(preset,'preset_morph_tick')
c+='''
static uint16_t frontParser_nrpnNr;
static uint8_t paramToModTarget[256];
#define NRPN_MUTE_1 1000
#define NRPN_MUTE_7 1006
static void buttonHandler_muteVoice(unsigned a,unsigned b){}
'''+extract(panel,'frontParser_parseNrpn')
auto=implementation('Core/Src/Soundengine/DSPAudio/automationNode.c')
c+='typedef struct {uint16_t destination;} AutomationNode;\n'
c+=extract(auto,'autoNode_updateValue')+extract(auto,'autoNode_setDestination')
c+='''
int main(void){
 assert(PAR_FX_DRY_WET==128+CC2_FX_AMOUNT);
 for(unsigned i=0;i<END_OF_SOUND_PARAMETERS;i++)parameterOrder[i]=i;
 for(unsigned raw=0;raw<256;raw++){
  unsigned expected=raw>100?100:raw;
  MidiMsg msg={0};msg.status=MIDI_CC2;msg.data1=CC2_FX_AMOUNT;msg.data2=raw;
  midiParser_ccHandler(msg,1,0,0);
  if(fxBus.dryWet!=expected/100.f)fprintf(stderr,"raw=%u expected=%.2f engine=%.2f\\n",raw,expected/100.f,fxBus.dryWet);
  assert(fxBus.dryWet==expected/100.f);
  assert(midiParser_originalCcValues[PAR_FX_DRY_WET]==expected);
  assert(msg.data2==raw); /* by-value acceptance must not rewrite traffic */
  midiParser_originalCcValues[PAR_FX_DRY_WET]=37;
  midiParser_ccHandler(msg,0,0,0);
  assert(fxBus.dryWet==expected/100.f && midiParser_originalCcValues[PAR_FX_DRY_WET]==37);
  midiParser_activeNrpnNumber=CC2_FX_AMOUNT;midiParser_nrpnHandler(raw);
  assert(fxBus.dryWet==expected/100.f && midiParser_originalCcValues[PAR_FX_DRY_WET]==expected);
  AutomationNode node={PAR_FX_DRY_WET};
  midiParser_originalCcValues[PAR_FX_DRY_WET]=37;
  autoNode_updateValue(&node,raw);
  assert(fxBus.dryWet==expected/100.f && midiParser_originalCcValues[PAR_FX_DRY_WET]==37);
  autoNode_setDestination(&node,NO_AUTOMATION);
  assert(fxBus.dryWet==37/100.f);
  frontParser_nrpnNr=CC2_FX_AMOUNT;frontParser_parseNrpn(raw);
  assert(activeParameters[PAR_FX_DRY_WET]==expected);
  for(unsigned morph=0;morph<2;morph++){
   uint8_t *kit = morph ? morphParameters : mainParameters[0];
   memset(kit,0,END_OF_SOUND_PARAMETERS);kit[PAR_FX_DRY_WET]=raw;
   preset_normalizeKit(kit);
   assert((morph?morphParameters:mainParameters[0])[PAR_FX_DRY_WET]==expected);
  }
  memcpy(activeParameters,mainParameters[0],END_OF_SOUND_PARAMETERS);
  preset_sendDrumsetParametersImmediate();
  assert(fxBus.dryWet==expected/100.f && activeParameters[PAR_FX_DRY_WET]==expected);
  assert(midiParser_originalCcValues[PAR_FX_DRY_WET]==expected);
  activeParameters[PAR_MORPH]=127;morph_state=1;morph_index=PAR_FX_DRY_WET;
  preset_morph_tick();assert(fxBus.dryWet==expected/100.f);
 }
 for(unsigned i=0;i<=127;i++){
  MidiMsg msg={0};msg.status=MIDI_CC2;msg.data1=CC2_FX_AMOUNT;
  float v=i/127.f;unsigned expected=(uint8_t)(v*127);if(expected>100)expected=100;
  midiParser_originalCcValues[PAR_FX_DRY_WET]=37;
  midiParser_ccHandler(msg,1,1,v);
  assert(fxBus.dryWet==expected/100.f && midiParser_originalCcValues[PAR_FX_DRY_WET]==37);
 }
 /* Finite positive float values must cap before narrowing, including byte overflow. */
 float high[]={100.f/127.f,101.f/127.f,1.f,2.f,256.f/127.f,1000000.f};
 for(unsigned i=0;i<sizeof high/sizeof *high;i++){
  MidiMsg msg={0};msg.status=MIDI_CC2;msg.data1=CC2_FX_AMOUNT;
  midiParser_ccHandler(msg,0,1,high[i]);assert(fxBus.dryWet==1.f);
 }

 puts("PASS: 256 bytes (including 0/99/100/101/127/255), cache flags, NRPN/UI, kit caches, immediate/morph dispatch, float units/overflow; project ingress normalization");
}
'''
run(c)
