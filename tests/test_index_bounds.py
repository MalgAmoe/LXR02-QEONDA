#!/usr/bin/env python3
"""Actual function/prefix regressions with stubbed endpoints, not hardware tests."""
from pathlib import Path
exec((Path(__file__).parent/'test_control_fixes.py').read_text().split('case=os.environ')[0])
parser=implementation('Core/Src/Soundengine/MIDI/MidiParser.c')
seq=implementation('Core/Src/Soundengine/Sequencer/sequencer.c')
case=os.getenv('LXR_TEST_CASE','all')
if case in ('all','nrpn'):
    cache=parser.split('else //MIDI_CC2')[1].split('switch(msg.data1)')[0]
    run('''#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
typedef struct {uint8_t status,data1,data2;} MidiMsg;
#define MIDI_CC2 0xc0
static uint16_t midiParser_activeNrpnNumber;
static unsigned calls,last;
static void midiParser_ccHandler(MidiMsg m,int u,int f,float v){(void)u;(void)f;(void)v;calls++;last=m.data1;}
static uint8_t midiParser_originalCcValues[0xff];
static void cacheWrite(MidiMsg msg){int updateOriginalValue=1,isFloatModulator=0;struct {uint8_t itg;}value={42};
'''+cache+'}}\n'+extract(parser,'midiParser_nrpnHandler')+'''
int main(void){
 for(unsigned i=0;i<16384;i++){
  calls=0;midiParser_activeNrpnNumber=i;midiParser_nrpnHandler(65);
  if(i<=255){assert(calls==1&&last==i);}else assert(calls==0);
 }
 for(unsigned i=0;i<256;i++){MidiMsg m={MIDI_CC2,i,42};cacheWrite(m);}
 assert(midiParser_originalCcValues[254]==42);
}
''')
if case in ('all','step'):
    run('''#include <stdint.h>
#include <assert.h>
#define NUM_STEPS 64
#define NUM_TRACKS 7
static int seq_armedArmedAutomationStep=-1,seq_armedArmedAutomationTrack=-1;
'''+extract(seq,'seq_armAutomationStep')+'''
int main(void){
 for(unsigned s=0;s<256;s++)for(unsigned t=0;t<256;t++){
  seq_armedArmedAutomationStep=seq_armedArmedAutomationTrack=-1;
  seq_armAutomationStep(s,t,1);
  if(s<64&&t<7){assert(seq_armedArmedAutomationStep==(int)s&&seq_armedArmedAutomationTrack==(int)t);}
  else assert(seq_armedArmedAutomationStep==-1&&seq_armedArmedAutomationTrack==-1);
 }
 seq_armAutomationStep(63,6,1);seq_armAutomationStep(255,255,0);
 assert(seq_armedArmedAutomationStep==-1&&seq_armedArmedAutomationTrack==-1);
}
''')
    panel=implementation('Core/Src/buttonHandler.c')
    gesture=extract(panel,'buttonHandler_selectButtonPressed')
    assert 'buttonHandler_selectedStep * 8' not in gesture
print('Index bounds pass: NRPN dispatch/cache; all step/track byte pairs; obsolete gesture absent.')
