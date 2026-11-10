/* Actual Compressor.c + FxBus.c regression. Other effects must never execute. */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Soundengine/FxBus.h"
#include "Soundengine/DSPAudio/mixer.h"
#define INIT(T,N) void N(T *p) { (void)p; }
#define SET(T,N) void N(T *p,float v) { (void)p;(void)v; abort(); }
#define PROCESS(T,N) void N(T *p,AudioSample *b,AudioSample *l,AudioSample *r,uint16_t n,uint8_t c,float w) { (void)p;(void)b;(void)l;(void)r;(void)n;(void)c;(void)w;abort(); }
INIT(MasterDistortion,Distortion_init)
INIT(Ringmod,Ringmod_init)
INIT(Delay,Delay_init)
SET(MasterDistortion,Distortion_setDrive)
SET(MasterDistortion,Distortion_setParam1)
SET(MasterDistortion,Distortion_setParam2)
SET(MasterDistortion,Distortion_setParam3)
SET(Ringmod,Ringmod_setFreq)
SET(Delay,Delay_setRange)
SET(Delay,Delay_setDelayTime)
SET(Delay,Delay_setFilter)
SET(Delay,Delay_setFeedback)
PROCESS(MasterDistortion,Distortion_process)
PROCESS(Ringmod,Ringmod_process)
PROCESS(Delay,Delay_process)
PROCESS(Delay,Delay_processPingPong)
static void setup(int route,int ratio,float wet,float threshold) {
 FxBus_init(); fxBus.fxType=FX_COMPRESSOR; fxBus.audioRouting=route; fxBus.dryWet=wet;
 Compressor_setRatio(&fxBus.compressor,ratio);
 FxBus_setParameter(0,1); FxBus_setParameter(1,0); FxBus_setParameter(2,threshold); FxBus_setParameter(3,1);
}
/* Two independent interleaved physical output buffers, with outer guards. */
static void block(int sample,float expected,int route) {
 _Alignas(4) AudioSample in[128], a[132], b[132];
 for(int i=0;i<128;i++) in[i]=(route<2)?sample:((i%2)?1234:sample);
 memset(a,0,sizeof a);memset(b,0,sizeof b);
 a[0]=a[131]=b[0]=b[131]=777;
 FxBus_process(in,a+2,a+3,b+2,b+3,64);
 AudioSample *target=(route==0 || route==2 || route==3)?b:a;
 int channel=(route==3 || route==5);
 for(int i=0;i<128;i++) {
  assert(a[i+2]==((target==a && (route<2 || i%2==channel))?expected:0));
  assert(b[i+2]==((target==b && (route<2 || i%2==channel))?expected:0));
 }
 assert(a[0]==777 && a[1]==0 && a[130]==0 && a[131]==777);
 assert(b[0]==777 && b[1]==0 && b[130]==0 && b[131]==777);
}
int main(void) {
 for(int r=0;r<=5;r++) {
  const int samples[]={20000,-20000,1000,-1000,0};
  for(int k=0;k<5;k++) for(int w=0;w<3;w++) {
   float wet=w*0.5f; int s=samples[k]; int v=s*3;
   if(v>32767)v=32767; if(v< -32768)v=-32768;
   float expected=s+(v-s)*wet;
   setup(r,0,wet,1); block(s,expected,r);
  }
  for(int ratio=0;ratio<6;ratio++) {
   setup(r,ratio,1,0);
   /* First attack sample must clip for every ratio at slow attack. */
   AudioSample in[2]={20000,-1234}, out[2]={0};
   Compressor_process(&fxBus.compressor,in,out,NULL,1,1,1);
   assert(out[0]==32767); assert(fxBus.compressor.env>0 && fxBus.compressor.env<1);
   double previous=fxBus.compressor.env;
   _Alignas(4) AudioSample buf[128],a[128],b[128];
   for(int i=0;i<128;i++)buf[i]=20000;
   for(int n=0;n<1000;n++) {
    memset(a,0,sizeof a);memset(b,0,sizeof b);
    FxBus_process(buf,a,a+1,b,b+1,64);
    assert(isfinite(fxBus.compressor.env));
    assert(fxBus.compressor.env>=previous && fxBus.compressor.env<=96);
    previous=fxBus.compressor.env;
   }
   assert(previous>90);
   memset(buf,0,sizeof buf);
   for(int n=0;n<1000;n++) {
    memset(a,0,sizeof a);memset(b,0,sizeof b);
    FxBus_process(buf,a,a+1,b,b+1,64);
    assert(fxBus.compressor.env>=0 && fxBus.compressor.env<=previous);
    previous=fxBus.compressor.env;
   }
   assert(previous<1e-12);
  }
 }
 puts("PASS: six FxBus routes (four mono, two stereo), both overflow signs, dry/half/full wet, in-range/silence; six ratios attack/release");
}
