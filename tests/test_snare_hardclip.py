#!/usr/bin/env python3
"""Actual mix and smoother bodies; bounded producer stubs isolate pre-envelope clipping.
The real transient producer is exercised separately by the float integration test. LXR_BASE_REV selects the historical actual Snare.c for red tests.
"""
from pathlib import Path
import os, re, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
dsp = root/'Core/Src/Soundengine/DSPAudio'
def extract(text, name):
    m = re.search(r'(?m)^(?:IN_ITCM_RAM )?(?:void|float) '+name+r'\([^;]*?\)\s*\{', text)
    end = m.end(); depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}'); end += 1
    return text[m.start():end].replace('IN_ITCM_RAM ', '')
source = (dsp/'Snare.c').read_text()
if os.environ.get('LXR_BASE_REV'):
    source = subprocess.check_output(['git', '-C', str(root), 'show', os.environ['LXR_BASE_REV']+':Core/Src/Soundengine/DSPAudio/Snare.c'], text=True)
pre = r'''
#include <stdint.h>
#include "Soundengine/AudioSample.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#define USE_REVERB 0
#ifndef FIRST_MODE
#define FIRST_MODE 0
#endif
typedef struct {float b,r;} OnePoleFilter;
typedef struct {
 int osc,noiseOsc,transGen,filter,filterType,distortion,volumeMod;
 float vol,velo,egValueOscVol,mix,pwm,combinedVolume;
 OnePoleFilter FaderVolumeFilter;
} SnareVoice;
static SnareVoice snareVoice;
static float tone,noise,transient;
static float fader;
static unsigned reads,dist_calls;
static int32_t __SSAT(int32_t x,int n){assert(n==16);return x>32767?32767:x< -32768?-32768:x;}
static float adc_getFaderVolume(int v){assert(v==3);reads++;return fader;}
static void calcNoiseBlock(int*o,AudioSample*b,uint8_t n,float g){assert(g==0.9f);for(int i=0;i<n;i++)b[i]=noise;}
static void SVF_calcBlockZDF(int*f,int t,AudioSample*b,uint8_t n){}
static void calcNextOscSampleBlock(int*o,AudioSample*b,uint8_t n,float g,float p){for(int i=0;i<n;i++)b[i]=(tone*g);}
static void transient_calcBlock(int*t,AudioSample*b,uint8_t n){for(int i=0;i<n;i++)b[i]=transient;}
static void calcDistBlock(int*d,AudioSample*b,uint8_t n){dist_calls++;}
'''
main = r'''
int main(void){
 unsigned cases=0,positive=0,negative=0,fractional=0;
 for(int mode=FIRST_MODE;mode<2;mode++)for(int velocity=0;velocity<3;velocity++)
 for(int sign=-1;sign<=1;sign+=2)for(int tr=0;tr<2;tr++)
 for(int level=0;level<3;level++)for(int ramp=0;ramp<2;ramp++)
 for(int mix=0;mix<2;mix++){
  snareVoice=(SnareVoice){.volumeMod=mode,.vol=0.83f,.velo=velocity*0.5f,
   .egValueOscVol=1,.mix=mix*0.5f,.FaderVolumeFilter={ramp?0:1,0.1f}};
  tone=sign*(30001.f/32768.f);noise=sign*(29001.f/32768.f);transient=tr?sign*(32001.f/32768.f):0;
  fader=level*0.5f;reads=dist_calls=0;
  float state=snareVoice.FaderVolumeFilter.b;
  float expected[64],out[64];
  for(int i=0;i<64;i++){
   state=fmaf(0.1f,fader-state,state);
   float combined=snareVoice.vol*(mode?snareVoice.velo:1)*snareVoice.egValueOscVol;
   float tmp=fmaf(noise,snareVoice.mix,(tone*(1-snareVoice.mix)));
   tmp+=transient;
   if(tmp>(32767.f/32768.f)){tmp=(32767.f/32768.f);positive++;}
   else if(tmp< -(32768.f/32768.f)){tmp=-(32768.f/32768.f);negative++;}
   float value=combined*tmp*state;
   int32_t integral=(int32_t)(value*32768.f);
   if(value>(32767.f/32768.f)){expected[i]=(32767.f/32768.f);}
   else if(value< -1.f){expected[i]=-(32768.f/32768.f);}
   else {expected[i]=value;if(value*32768.f!=integral)fractional++;}
  }
  Snare_calcSyncBlock(out,64);
  /* Float reassociation under production fast-math may differ by a few ULP. */
  for(int i=0;i<64;i++)assert(fabsf(out[i]-expected[i])<=2e-6f*fmaxf(1.f/32768.f,fabsf(expected[i])));
  /* Target read once per block; output/state checks above retain per-sample smoothing. */
  assert(reads==1 && dist_calls==1);
  assert(fabsf(state-snareVoice.FaderVolumeFilter.b)<0.000001f);
  cases++;
 }

 /* Explicit overload witnesses: attenuation must follow clipping, not hide it.
    Exercise each gain independently, both branches and both signs. */
 for(int mode=FIRST_MODE;mode<2;mode++)for(int sign=-1;sign<=1;sign+=2)
 for(int gain=0;gain<4;gain++){
  snareVoice=(SnareVoice){.volumeMod=mode,.vol=gain==2?0.5f:1,
   .velo=gain==1?0.5f:1,.egValueOscVol=gain==0?0.5f:1,
   .FaderVolumeFilter={gain==3?0.5f:1,0.1f}};
  fader=gain==3?0.5f:1;tone=sign*(30000.f/32768.f);noise=0;transient=sign*(30000.f/32768.f);
  float out;Snare_calcSyncBlock(&out,1);
  float scale=(gain==1&&!mode)?1:0.5f;
  assert(out==((sign>0?(32767.f/32768.f):-(32768.f/32768.f))*scale));
 }
 /* Fractional mix survives until final conversion: 100.5 * 2 = 201. */
 for(int mode=FIRST_MODE;mode<2;mode++){
  snareVoice=(SnareVoice){.volumeMod=mode,.vol=2,.velo=1,.egValueOscVol=1,
   .mix=0.5f,.FaderVolumeFilter={1,0.1f}};
  fader=1;tone=0;noise=(201.f/32768.f);transient=0;
  float out;Snare_calcSyncBlock(&out,1);assert(out==(201.f/32768.f));
  /* Signed envelope undershoot and asymmetric endpoint; extended invalid gains. */
  tone=-(32768.f/32768.f);noise=0;transient=-(32768.f/32768.f);snareVoice.mix=0;
  snareVoice.vol=1;snareVoice.egValueOscVol=-1;
  Snare_calcSyncBlock(&out,1);assert(out==(32767.f/32768.f));
  snareVoice.vol=1e38f;
  Snare_calcSyncBlock(&out,1);assert(out==(32767.f/32768.f));
  snareVoice.egValueOscVol=1;
  Snare_calcSyncBlock(&out,1);assert(out==-(32768.f/32768.f));
 }
 assert(positive && negative && fractional);
 printf("snare: %u cases; positive overload %u negative overload %u fractional inrange %u\n",cases,positive,negative,fractional);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)
    (p/'test.c').write_text(pre+extract((dsp/'1PoleLp.c').read_text(),'calcOnePole')+'\n'+extract(source,'Snare_calcSyncBlock')+'\n'+main)
    for flags in (['-O1'], ['-O3','-ffast-math','-freciprocal-math']):
        print('snare flags:',flags,flush=True)
        subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-DFIRST_MODE='+os.environ.get('LXR_FIRST_MODE','0'),*flags,'-fsanitize=address,undefined,float-cast-overflow','-fno-sanitize-recover=all','-I'+str(root/'Core/Inc'),str(p/'test.c'),'-lm','-o',str(p/'test')],check=True)
        subprocess.run([str(p/'test')],check=True)
