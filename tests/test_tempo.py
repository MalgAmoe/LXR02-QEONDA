#!/usr/bin/env python3
"""Actual timing functions with fake globals; arithmetic, not physical clock timing."""
from pathlib import Path
helpers=(Path(__file__).parent/'test_control_fixes.py').read_text().split('case=os.environ')[0]
exec(helpers.replace('void|uint8_t|uint16_t','void|float|uint8_t|uint16_t'))
source=implementation('Core/Src/Soundengine/Sequencer/sequencer.c')
run('''#include <stdint.h>
#include <assert.h>
#include <math.h>
static float seq_deltaT,seq_shuffle,seq_lastShuffle;
'''+extract(source,'seq_calcDeltaT')+extract(source,'seq_getDeltaTShuffleDelay')+'''
static void near(float actual,double expected){assert(fabs(actual-expected)<=fabs(expected)*2e-6+1e-6);}
int main(void){
 for(unsigned bpm=2;bpm<=255;bpm++){
  double base=2500.0/bpm;
  seq_shuffle=seq_lastShuffle=0;
  seq_calcDeltaT(bpm,0);near(seq_deltaT,base);
  near(seq_getDeltaTShuffleDelay(bpm),0);
  for(unsigned s=1;s<=4;s++){
   seq_shuffle=s/16.f;seq_lastShuffle=0;
   near(seq_getDeltaTShuffleDelay(bpm),base*seq_shuffle*16);
   seq_calcDeltaT(bpm,1);near(seq_deltaT,base*(1+seq_shuffle*16));
   seq_calcDeltaT(bpm,0);near(seq_deltaT,base*(1-seq_shuffle*16));
  }
 }
 assert(seq_getDeltaTShuffleDelay(0)==1); /* Existing helper fallback. */
}
''')
print('Tempo arithmetic: BPM2..255, shuffle delay and alternating corrections pass.')
