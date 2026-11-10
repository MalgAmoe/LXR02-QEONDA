/* Legacy int16 API regression, also retained in experimental suites. */
#undef LXR_MAIN_OUTPUT_24BIT
/* Actual production TU, including inspection of recursive float32 state. */
#include "../Core/Src/Soundengine/DSPAudio/MainDjFilter.c"
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
static int16_t b[128];
static int finiteBits(float x) { uint32_t v; memcpy(&v,&x,4); return (v&0x7f800000u)!=0x7f800000u; }
static void checkStage(FilterStage *s) {
    assert(finiteBits(s->g) && finiteBits(s->wet));
    for(unsigned c=0;c<2;c++) assert(finiteBits(s->s1[c]) && finiteBits(s->s2[c]));
    assert(s->wet>=0.f && s->wet<=1.f);
}
static void check(void) {
    checkStage(&state.hp); checkStage(&state.lp);
    assert(finiteBits(state.k) && state.k>=0.33332f && state.k<1.415f);
}
static void dc(int x,unsigned blocks) {
    while(blocks--) { for(unsigned i=0;i<128;i++) b[i]=x; MainDjFilter_process(b,64); check(); }
}
static void fresh(unsigned hp,unsigned lp,unsigned r) {
    memset(&state,0,sizeof state); MainDjFilter_setTargets(hp,lp,r); dc(0,8);
}
static void dry(void) {
    int16_t original[128];
    for(unsigned i=0;i<128;i++) original[i]=(int16_t)(i*1103u);
    original[0]=-32768; original[1]=32767;
    memcpy(b,original,sizeof b); MainDjFilter_process(b,64);
    assert(!memcmp(b,original,sizeof b));
}
/* Independent scalar recurrence from pre-sample production state. No clamp
 * between stages: this also tests the float intermediate under HP overload. */
static float predict(FilterStage *s,float x,unsigned c,unsigned hp) {
    float a1=1.f/(1.f+s->g*(s->g+state.k));
    float a2=s->g*a1,a3=s->g*a2,v3=x-s->s2[c];
    float v1=a1*s->s1[c]+a2*v3;
    float v2=s->s2[c]+a2*s->s1[c]+a3*v3;
    return hp ? x-state.k*v1-v2 : v2;
}
static void saturation(void) {
    fresh(80,95,127);
    const float fc=20.f*powf(400.f,79.f/126.f);
    unsigned positive=0,negative=0,intermediate=0;
    for(unsigned i=0;i<12000;i++) {
        int16_t x=(int16_t)(24000.f*sinf(6.28318530718f*fc*i/44140.f));
        float hp=predict(&state.hp,(float)x,0,1);
        float y=predict(&state.lp,hp,0,0);
        if(fabsf(hp)>32768.f) ++intermediate;
        int16_t expected=y>32767.f?32767:y< -32768.f?-32768:(int16_t)y;
        b[0]=x; b[1]=0; MainDjFilter_process(b,1); check();
        assert(abs(b[0]-expected)<=1 && b[1]==0);
        if(y>32767.f) {assert(b[0]==32767);++positive;}
        if(y< -32768.f) {assert(b[0]==-32768);++negative;}
    }
    assert(positive && negative && intermediate);
}
int main(void) {
    dry(); MainDjFilter_setTargets(0,127,127); dry();
    fresh(0,0,127); dc(1000,500); assert(abs(b[126]-1000)<=2);
    fresh(1,127,127); dc(1000,1000); assert(abs(b[126])<=1);
    fresh(1,0,127);
    assert(fabsf(state.hp.g-tanf(3.14159265358979323846f*20.f/44140.f))<1.e-6f);
    assert(fabsf(state.lp.g-tanf(3.14159265358979323846f*40.f/44140.f))<1.e-6f);
    assert(fabsf(state.k-1.f/3.f)<1.e-6f);
    fresh(127,126,0);
    assert(fabsf(state.hp.g-tanf(3.14159265358979323846f*8000.f/44140.f))<1.e-6f);
    /* Fast-math pow/tan reassociation differs by ~2.3 ppm at 18 kHz. */
    assert(fabsf(state.lp.g-tanf(3.14159265358979323846f*18000.f/44140.f))<1.e-5f);
    assert(fabsf(state.k-1.f/0.70710678f)<1.e-6f);
    /* Independent sweeps: unrelated target and Q edits cannot restart a ramp. */
    MainDjFilter_setTargets(90,126,0); dc(0,1);
    assert(state.hp.ramp==192 && state.lp.ramp==0);
    float lpG=state.lp.g, hpDg=state.hp.dg;
    MainDjFilter_setTargets(90,20,127); dc(0,1);
    assert(state.hp.ramp==128 && state.hp.dg==hpDg && state.lp.ramp==192);
    assert(state.lp.g!=lpG && state.hp.wet==1.f && state.lp.wet==1.f);
    float hpG=state.hp.goalG,lpGoal=state.lp.goalG;
    MainDjFilter_setTargets(90,20,40); dc(0,4);
    assert(state.hp.g==hpG && state.lp.g==lpGoal);
    /* Independent wet ramps and reset, without response modes or clearing live DSP. */
    fresh(0,127,0); MainDjFilter_setTargets(90,127,127); dc(0,1);
    assert(state.hp.wet==0.25f && state.lp.wet==0.f);
    MainDjFilter_setTargets(90,20,127); dc(0,1);
    assert(state.hp.wet==0.5f && state.lp.wet==0.25f);
    MainDjFilter_reset(); assert(state.hp.wet==0.5f && state.lp.wet==0.25f);
    dc(0,4); assert(state.hp.wet==0.f && state.lp.wet==0.f); dry();
    /* Q3 simultaneous and crossed cutoffs; real stereo recursion, silence decay. */
    const unsigned pairs[][2]={{1,0},{127,0},{127,126},{45,90},{100,10}};
    for(unsigned p=0;p<sizeof pairs/sizeof pairs[0];p++) {
        fresh(pairs[p][0],pairs[p][1],127);
        b[0]=30000; MainDjFilter_process(b,64); check();
        for(unsigned i=1;i<128;i+=2) assert(b[i]==0);
        dc(0,5000);
        for(unsigned c=0;c<2;c++) {
            assert(fabsf(state.hp.s1[c])<0.01f && fabsf(state.hp.s2[c])<0.01f);
            assert(fabsf(state.lp.s1[c])<0.01f && fabsf(state.lp.s2[c])<0.01f);
        }
    }
    saturation();
    for(unsigned j=0;j<2000;j++) {
        MainDjFilter_setTargets((j*17)%128,(j*37)%128,127);
        for(unsigned i=0;i<128;i++) b[i]=(i/2+j)%2?-32768:32767;
        MainDjFilter_process(b,64); check();
    }
    MainDjFilter_reset(); dc(12000,4); dry();
    MainDjFilter_setTargets(255,255,255); dc(0,4);
    assert(targetHp==127 && targetLp==127 && targetResonance==127);
    printf("Dual DJ core passed; static bytes=%zu\n",sizeof(state)+3);
}
