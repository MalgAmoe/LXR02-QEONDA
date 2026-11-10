#include "../Core/Src/Soundengine/DSPAudio/MainCompressor.c"
#include "../Core/Src/Soundengine/DSPAudio/MainDjFilter.c"
#include <assert.h>
#include <stdlib.h>

static int32_t unpack(const int16_t *p) {
    uint32_t v=((uint32_t)(uint16_t)p[0]<<8)|((uint16_t)p[1]>>8);
    return v&0x800000u ? (int32_t)(v|0xff000000u) : (int32_t)v;
}
int main(void) {
    int16_t p[6]={123,0,0,0,0,456}; float b[2];
    const float values[]={0,0.25f,-0.25f,32767,-32768,40000,-40000};
    const int32_t codes[]={0,64,-64,8388352,-8388608,8388607,-8388608};
    for(unsigned i=0;i<7;i++) {
        audio_output24_store(p+1,values[i]); assert(unpack(p+1)==codes[i]);
        assert((p[2]&255)==0 && p[0]==123 && p[5]==456);
    }
    /* Settled bypass is exactly the original integer input times 256. */
    b[0]=-32768;b[1]=32767; MainDjFilter_process24(b,p+1,1);
    assert(unpack(p+1)==-8388608 && unpack(p+3)==8388352);
    /* Real LP recurrence creates a signed sub-int16-LSB signal, no model. */
    MainDjFilter_setTargets(0,0,0);
    b[0]=b[1]=0;
    for(unsigned i=0;i<512;i++) MainDjFilter_process24(b,p+1,1);
    b[0]=100;b[1]=-100; MainDjFilter_process24(b,p+1,1);
    unsigned recovered=0;
    b[0]=b[1]=0;
    for(unsigned i=0;i<1000;i++) {
        MainDjFilter_process24(b,p+1,1);
        int32_t a=unpack(p+1),r=unpack(p+3);
        if(a>0 && a<256) {assert(r==-a);recovered++;}
    }
    assert(recovered);
    /* Compressor-only real output: unchanged gain/detector scale and clamp. */
    memset(&state,0,sizeof state); memset(&comp,0,sizeof comp);
    MainDjFilter_reset(); const uint8_t on[]={12,19,0,0};
    MainCompressor_setControls(on);
    b[0]=16000;b[1]=-8000;
    for(unsigned i=0;i<30000;i++) MainDjFilter_process24(b,p+1,1);
    float g=1.f+comp.wet*(comp.gain*comp.makeup-1.f);
    float expected=fminf(32767.f,16000.f*g);
    assert(abs(unpack(p+1)-(int32_t)(expected*256.f))<=2);
    assert(unpack(p+3)<0);
    MainCompressor_setParameter(303,0);
    for(unsigned i=0;i<512;i++) MainDjFilter_process24(b,p+1,1);
    assert(unpack(p+1)==16000*256 && unpack(p+3)==-8000*256);
    memset(&state,0,sizeof state); MainDjFilter_setTargets(80,95,127);
    b[0]=b[1]=0;
    for(unsigned i=0;i<512;i++) MainDjFilter_process24(b,p+1,1);
    unsigned positive=0,negative=0;
    float fc=20.f*powf(400.f,79.f/126.f);
    for(unsigned i=0;i<12000;i++) {
        b[0]=(int16_t)(24000.f*sinf(6.28318530718f*fc*i/44140.f));b[1]=0;
        MainDjFilter_process24(b,p+1,1);
        int32_t a=unpack(p+1);
        positive += a==8388607; negative += a==-8388608;
        assert(a<=8388607 && a>=-8388608 && unpack(p+3)==0);
    }
    assert(positive && negative);
    assert(p[0]==123 && p[5]==456);
}
