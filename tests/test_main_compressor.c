/* Real DSP TU and independent full-rate double-precision reference curve. */
#include "../Core/Src/Soundengine/DSPAudio/MainCompressor.c"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../Core/Src/Soundengine/DSPAudio/MainDjFilter.c"
static double oracle(double e) {
    double d=20*log10(fmax(e,1e-20))-comp.threshold;
    double r=d<=-3?0:d>=3?comp.slope*d:comp.slope*(d+3)*(d+3)/12;
    return pow(10,-r/20);
}
static void transitions(void) {
    memset(&comp,0,sizeof comp);
    const uint8_t on[4]={12,19,0,0}, off[4]={30,0,17,20};
    MainCompressor_setControls(on); assert(MainCompressor_beginBlock());
    float last=16000;
    for(unsigned i=0;i<30000;i++){float x[2]={16000,8000};MainCompressor_processPair(x);last=x[0];}
    MainCompressor_setParameter(302,36);MainCompressor_beginBlock();
    float x[2]={16000,8000};MainCompressor_processPair(x);
    /* Relative continuity bound: full makeup changes absolute output level.
     * A 24 dB threshold edit ramps over 221 samples (~1.2%/sample here). */
    assert(fabsf(x[0]-last)<0.02f*fmaxf(fabsf(last),16000.f));
    for(unsigned i=0;i<30000;i++){float y[2]={16000,8000};MainCompressor_processPair(y);last=y[0];}
    MainCompressor_setParameter(303,1);MainCompressor_beginBlock();
    for(unsigned i=0;i<221;i++) {
      float y[2]={16000,8000};MainCompressor_processPair(y);
      assert(fabsf(y[0]-last)<0.02f*fmaxf(fabsf(last),16000.f));last=y[0];
    }
    assert(comp.curveRamp==0 && comp.slope==comp.goalSlope);
    for(unsigned i=0;i<30000;i++){float y[2]={16000,8000};MainCompressor_processPair(y);last=y[0];}
    /* Same complete publication used by project adoption, including ratio1. */
    MainCompressor_setControls(off);assert(MainCompressor_beginBlock());
    assert(comp.envelope>0); /* Not reset at publication/block boundary. */
    for(unsigned i=0;i<300;i++) {
      float y[2]={16000,8000};MainCompressor_processPair(y);
      assert(fabsf(y[0]-last)<0.02f*fmaxf(fabsf(last),16000.f));assert(y[0]==2*y[1]);last=y[0];
    }
    assert(!MainCompressor_beginBlock());assert(last==16000);
    assert(comp.envelope==0 && comp.gain==1 && comp.makeup==1);
    MainCompressor_setControls(on);assert(MainCompressor_beginBlock());
    float y[2]={16000,8000};MainCompressor_processPair(y);assert(fabsf(y[0]-16000)<100);
    /* Reverse a drain before settling: no premature state clear or wet jump. */
    for(unsigned i=0;i<221;i++){float x[2]={16000,8000};MainCompressor_processPair(x);}
    MainCompressor_setControls(off);assert(MainCompressor_beginBlock());
    for(unsigned i=0;i<70;i++){float x[2]={16000,8000};MainCompressor_processPair(x);}
    float wet=comp.wet, env=comp.envelope;
    MainCompressor_setControls(on);assert(MainCompressor_beginBlock());
    assert(comp.wet==wet && comp.envelope==env);
    for(unsigned i=0;i<221;i++){float x[2]={16000,8000};MainCompressor_processPair(x);}
    assert(comp.wet==1 && comp.wetRamp==0 && comp.curveRamp==0);
    /* Disable midway through a curve edit: freeze its current configuration. */
    MainCompressor_setParameter(302,36);MainCompressor_beginBlock();
    for(unsigned i=0;i<70;i++){float x[2]={16000,8000};MainCompressor_processPair(x);}
    float threshold=comp.threshold;
    MainCompressor_setControls(off);assert(MainCompressor_beginBlock());
    assert(comp.threshold==threshold && !comp.curveRamp);
    for(unsigned i=0;i<221;i++){float x[2]={16000,8000};MainCompressor_processPair(x);}
    assert(!MainCompressor_beginBlock() && comp.envelope==0);
    MainCompressor_setControls(on);assert(MainCompressor_beginBlock());
    /* Public filter entry must not skip the disabling compressor. */
    for(unsigned i=0;i<30000;i++){float x[2]={16000,8000};MainCompressor_processPair(x);last=x[0];}
    MainCompressor_setControls(off);
    int16_t frame[2]={16000,8000};MainDjFilter_process(frame,1);
    int previousOutput=last>32767.f?32767:(int)last;
    assert(abs(frame[0]-previousOutput)<0.02f*fmaxf(fabsf(last),16000.f) && frame[0]!=16000);
    for(unsigned i=0;i<220;i++){frame[0]=16000;frame[1]=8000;MainDjFilter_process(frame,1);}
    assert(frame[0]==16000 && frame[1]==8000);
    assert(!MainCompressor_beginBlock() && comp.envelope==0);
    memset(&comp,0,sizeof comp);
}
int main(void) {
    transitions();
    double curveWorst=0;
    for(unsigned th=0;th<=48;th++)for(unsigned ratio=1;ratio<=19;ratio++) {
      MainCompressor_setParameter(302,th);MainCompressor_setParameter(303,ratio);
      MainCompressor_beginBlock();
      for(unsigned i=0;i<221;i++){float x[2]={0,0};MainCompressor_processPair(x);}
      assert(comp.threshold==(float)th-48.f);
      assert(comp.slope==1.f-1.f/(1.f+ratio));
      for(int j=-12000;j<=3600;j+=7) {
        double e=pow(10,j/2000.0);
        double error=fabs(20*log10(attenuation(reduction(envelopeDb((float)e)))/oracle(e)));
        if(error>curveWorst)curveWorst=error;
        assert(error<0.001);
      }
      /* Full reference reduction at 0 dBFS, without a separate cap. */
      double expectedMakeup=1.0/oracle(1.0);
      assert(fabs(comp.makeupGoal/expectedMakeup-1.0)<1.e-5);
      if(th==0 && ratio==19) assert(comp.makeupGoal>190.f);
    }
    printf("static curve worst %.8f dB\n",curveWorst);
    double worst=0, worstFast=0;
    for(unsigned attack=0;attack<=30;attack++) {
      memset(&comp,0,sizeof comp);
      MainCompressor_setParameter(302,0); MainCompressor_setParameter(303,19);
      MainCompressor_setParameter(304,attack); MainCompressor_setParameter(305,0);
      assert(MainCompressor_beginBlock());
      double env=0,errmax=0;
      for(unsigned i=0;i<30000;i++) {
        float v=(i%6000<3000)?32768.f:0.f;
        float x[2]={v,-v*.5f};
        double a=v/32768.>env?comp.attack:comp.release;
        env=v/32768.+a*(env-v/32768.);
        MainCompressor_processPair(x);
        double err=fabs(20*log10(comp.gain/oracle(env)));
        if(err>errmax)errmax=err;
        assert(x[0]==-2*x[1]);
        assert(isfinite(comp.gain) && comp.gain>0 && comp.gain<=1.00001);
      }
      if(attack<14 && errmax>worstFast)worstFast=errmax;
      if(errmax>worst)worst=errmax;
      printf("attack=%u stride=%u max curve lag/error %.6f dB\n",attack,1u,errmax);
      assert(errmax<0.002);
    }
    MainCompressor_setParameter(303,0);assert(MainCompressor_beginBlock());
    for(unsigned i=0;i<221;i++){float x[2]={16000,8000};MainCompressor_processPair(x);}
    assert(!MainCompressor_beginBlock());
    assert(comp.gain==1 && comp.makeup==1 && comp.envelope==0);
    int16_t samples[128], original[128];
    for(unsigned i=0;i<128;i++) original[i]=(int16_t)(i*1103u);
    original[0]=-32768;original[1]=32767;
    memcpy(samples,original,sizeof samples);
    MainDjFilter_process(samples,64);
    assert(!memcmp(samples,original,sizeof samples));
    /* Float HP -> LP -> compressor before sole int16 conversion. Use real
     * stages and restore their state before the public render entry. */
    MainCompressor_setParameter(303,19);MainCompressor_setParameter(302,0);
    MainCompressor_beginBlock();
    MainDjFilter_setTargets(80,95,127);
    memset(samples,0,sizeof samples);
    for(unsigned j=0;j<8;j++)MainDjFilter_process(samples,64);
    unsigned overrange=0;
    for(unsigned i=0;i<12000;i++) {
      int16_t v=(int16_t)(24000*sinf(6.28318530718f*20.f*powf(400.f,79.f/126.f)*i/44140.f));
      unsigned char savedFilter[sizeof state],savedComp[sizeof comp];
      memcpy(savedFilter,&state,sizeof state);memcpy(savedComp,&comp,sizeof comp);
      float x[2]={v,-v};processStage(&state.hp,x,1);processStage(&state.lp,x,0);
      if(fabsf(x[0])>32768)overrange++;
      MainCompressor_processPair(x);
      int16_t expected=x[0]>32767?32767:x[0]<-32768?-32768:(int16_t)x[0];
      memcpy(&state,savedFilter,sizeof state);memcpy(&comp,savedComp,sizeof comp);
      samples[0]=v;samples[1]=-v;MainDjFilter_process(samples,1);
      assert(abs(samples[0]-expected)<=1);
    }
    assert(overrange);
    /* Times are RC 63.2% amplitude constants, logarithmic endpoints/defaults. */
    MainCompressor_setParameter(304,17);MainCompressor_setParameter(305,20);
    MainCompressor_beginBlock();
    for(unsigned i=0;i<221;i++){float x[2]={0,0};MainCompressor_processPair(x);}
    assert(fabs(-1000./(44140*log(comp.attack))-5.01187)<0.01);
    assert(fabs(-1000./(44140*log(comp.release))-99.856)<0.1);
    MainCompressor_setParameter(302,255);MainCompressor_setParameter(304,255);
    MainCompressor_setParameter(305,255);MainCompressor_setParameter(301,255);
    assert(compTargets[0]==48 && compTargets[2]==30 && compTargets[3]==34);
    printf("worst %.6f dB; fast fullrate %.6f dB; state %zu bytes\n",worst,worstFast,sizeof comp+sizeof compTargets);
}
