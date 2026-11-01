/* Include actual TU to inspect finite internal float32 state, not a DSP model. */
#include "../Core/Src/Soundengine/DSPAudio/MainDjFilter.c"
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

static int16_t b[128];
static int finiteBits(float x) { uint32_t bits; memcpy(&bits,&x,4); return (bits & 0x7f800000u)!=0x7f800000u; }
static void check(void) {
    for(unsigned c=0;c<2;c++) { assert(finiteBits(state.s1[c])); assert(finiteBits(state.s2[c])); }
    assert(state.k>=0.499f && state.k<1.415f);
}
static void dc(int x,unsigned blocks) {
    while(blocks--) {for(unsigned i=0;i<128;i++)b[i]=x; MainDjFilter_process(b,64); check();}
}
/* Prove core overload, rather than counting full-scale dry input as clipping. */
static void resonantSaturation(void) {
    /* Filter 33 maps LP to about 981 Hz; resonance 127 gives k=0.5 (Q=2). */
    const float fc=18000.f*powf(40.f/18000.f,30.f/63.f);
    MainDjFilter_setTargets(33,127); dc(0,300);
    assert(state.mode==1 && state.wet==1.f && state.ramp==0);
    assert(fabsf(state.g-tanf(3.14159265358979323846f*fc/44140.f))<1.e-6f);
    assert(fabsf(state.k-0.5f)<1.e-6f);
    unsigned positive=0, negative=0;
    for(unsigned i=0;i<8192;i++) {
        int16_t x=(int16_t)(24000.f*sinf(6.283185307179586f*fc*(float)i/44140.f));
        assert(x> -32768 && x<32767);
        b[0]=x; b[1]=0;
        /* Actual pre-sample state, with settled coefficients and fully wet LP. */
        float a1=1.f/(1.f+state.g*(state.g+state.k));
        float a2=state.g*a1, a3=state.g*a2;
        float v3=(float)x-state.s2[0];
        float v2=state.s2[0]+a2*state.s1[0]+a3*v3;
        float unbounded=(float)x+state.wet*(v2-(float)x);
        assert(finiteBits(unbounded));
        MainDjFilter_process(b,1); check();
        assert(b[1]==0);
        if(unbounded>32767.f) { assert(b[0]==32767); ++positive; }
        else if(unbounded< -32768.f) { assert(b[0]==-32768); ++negative; }
    }
    assert(positive && negative);
}
int main(void) {
    int16_t original[128];
    for(unsigned i=0;i<128;i++) original[i]=i%2?-32768:32767;
    memcpy(b,original,sizeof b); MainDjFilter_process(b,64); assert(!memcmp(b,original,sizeof b));
    MainDjFilter_setTargets(63,127); memcpy(b,original,sizeof b); MainDjFilter_process(b,64); assert(!memcmp(b,original,sizeof b));
    /* DC contracts: lowpass passes DC, highpass rejects it, independent channels. */
    MainDjFilter_setTargets(0,127); dc(1000,300);
    assert(abs(b[126]-1000)<=2);
    MainDjFilter_setTargets(126,127); dc(1000,300); assert(abs(b[126])<=1);
    /* Impulse with silent right channel; real recursive tail decays. */
    dc(0,500); b[0]=30000; MainDjFilter_process(b,64);
    for(unsigned i=1;i<128;i+=2)assert(b[i]==0);
    dc(0,2000); assert(fabsf(state.s1[0])<0.01f && fabsf(state.s2[0])<0.01f);
    MainDjFilter_setTargets(0,127); dc(0,20);
    b[0]=32767; MainDjFilter_process(b,64); dc(0,4000);
    assert(fabsf(state.s1[0])<0.01f && fabsf(state.s2[0])<0.01f);
    /* Response can switch only at zero wet, including sub-block reversals. */
    dc(12000,20); assert(state.mode==1 && state.wet==1.f);
    MainDjFilter_setTargets(126,127);
    for(unsigned i=0;i<256;i++) { b[0]=b[1]=12000; MainDjFilter_process(b,1); assert(state.mode==1); }
    assert(state.wet==0.f);
    MainDjFilter_process(b,1); assert(state.mode==2);
    float wetBefore=state.wet; unsigned modeBefore=state.mode;
    MainDjFilter_reset(); assert(state.wet==wetBefore && state.mode==modeBefore);
    resonantSaturation();
    /* Full-scale DC and alternating overload; transitions every block at maximum Q. */
    for(unsigned j=0;j<1200;j++) {
        unsigned f=(j*17)%127; MainDjFilter_setTargets(f,127);
        for(unsigned i=0;i<128;i++)b[i]=(j%3)?32767:((i/2)%2?-32768:32767);
        MainDjFilter_process(b,64); check();
    }
    /* Sweep the actual audio input and controls, not an endpoint-only matrix. */
    float phase=0;
    for(unsigned j=0;j<1200;j++) {
        MainDjFilter_setTargets((j/8)%127,(j*3)%128);
        float hz=20.f*powf(1000.f,j/1200.f);
        for(unsigned i=0;i<64;i++){ phase+=6.2831853f*hz/44140.f; b[2*i]=(int16_t)(20000.f*sinf(phase)); b[2*i+1]=0; }
        MainDjFilter_process(b,64); check();
    }
    MainDjFilter_reset(); dc(12000,10); assert(state.wet==0.f && state.mode==0);
    memcpy(b,original,sizeof b); MainDjFilter_process(b,64); assert(!memcmp(b,original,sizeof b));
    MainDjFilter_setTargets(255,255); dc(1000,20); assert(targetFilter==126 && targetResonance==127);
    printf("DJ core passed; static bytes=%zu\n",sizeof(state)+2);
}
