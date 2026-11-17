/* Production oscillator, filter, voice, FX and final encoder integration.
 * Hardware inputs/RNG are substitutes; FM negative conversion remains an ARM check. */
#include "Soundengine/DSPAudio/Oscillator.h"
#include "Soundengine/DSPAudio/BufferTools.h"
#include "Soundengine/DSPAudio/FX/Delay.h"
#include "Soundengine/DSPAudio/FX/Distortion.h"
#include "Soundengine/DSPAudio/FX/Compressor.h"
#include "Soundengine/DSPAudio/FX/Ringmod.h"
#include "Soundengine/DSPAudio/MainDjFilter.h"
#include "Soundengine/DSPAudio/MainCompressor.h"
#include "../Core/Src/Soundengine/DSPAudio/MainCompressor.c"
#include "../Core/Src/Soundengine/DSPAudio/MainDjFilter.c"
#include "Soundengine/DSPAudio/transientGenerator.h"
#include "Soundengine/DSPAudio/DrumVoice.h"
#include "Soundengine/DSPAudio/Snare.h"
#include "Soundengine/DSPAudio/HiHat.h"
#include "Soundengine/DSPAudio/CymbalVoice.h"
/* Control-rate dispatch is substituted so settled voice fixtures are stable;
 * audio-rate voices, complete mixer dispatch, FX and output DSP are production. */
static void test_async_voice(uint8_t v) {(void)v;}
static void test_async(void) {}
static void test_lfo(Lfo *lfo) {(void)lfo;}
#define calcDrumVoiceAsync test_async_voice
#define Snare_calcAsync test_async
#define Cymbal_calcAsync test_async
#define HiHat_calcAsync test_async
#define modNode_resetTargets test_async
#define modNode_reassignVeloMod test_async
#define lfo_dispatchNextValue test_lfo
#define GPIOD GPIOB
#define GPIO_PIN_3 (1u<<3)
#define GPIO_PIN_4 (1u<<4)
#define GPIO_PIN_6 (1u<<6)
#include "../Core/Src/Soundengine/DSPAudio/mixer.c"
#undef calcDrumVoiceAsync
#undef Snare_calcAsync
#undef Cymbal_calcAsync
#undef HiHat_calcAsync
#undef modNode_resetTargets
#undef modNode_reassignVeloMod
#undef lfo_dispatchNextValue
#include <assert.h>

#include <stdio.h>
#include <math.h>
#include <string.h>
GPIO_TypeDef lxr_test_gpio_b;
/* Renderer request/IRQ stand-ins: sequencing is covered separately, not timing. */
volatile uint8_t bCurrentSampleValid;
volatile uint32_t codec_requestGeneration;
int16_t dma_buffer[AUDIO_DMA_HALFWORDS],dma_buffer2[AUDIO_DMA_HALFWORDS];
#define __get_PRIMASK() 0u
#define __set_PRIMASK(mask) ((void)(mask))
#include "float_renderer.h"
float adc_getFaderVolume(uint8_t idx) {(void)idx;return 1.f;}
uint32_t GetRngValue(void) {return 0xffff8001u;}
static int32_t unpack(const int16_t *p) {
 uint32_t v=((uint32_t)(uint16_t)p[0]<<8)|((uint16_t)p[1]>>8);
 return v&0x800000u ? (int32_t)(v|0xff000000u) : (int32_t)v;
}
static float bound(float x) {return fmaxf(-(32768.f/32768.f),fminf((32767.f/32768.f),x));}
static void close_at(float a,float b,unsigned line) {if(fabsf(a-b)>=0.02f/32768.f) fprintf(stderr,"line %u: actual %.9g expected %.9g\n",line,a,b);assert(fabsf(a-b)<0.02f/32768.f);}
#define closef(a,b) close_at(a,b,__LINE__)

/* Independent scalar history oracle: run more than a complete ring in 64-frame
 * calls, including both physical banks, wrap, interpolation and feedback clips. */
static float historyOracle[FX_BUFFER_SIZE+1];
static void test_delay_history(void) {
 for(unsigned mode=0;mode<2;++mode) for(unsigned ch=1;ch<=2;++ch) {
  unsigned mask=mode?FX_BUFFER_SIZE>>1:FX_BUFFER_SIZE;
  unsigned half=FX_BUFFER_SIZE>>1;
  for(unsigned i=0;i<=FX_BUFFER_SIZE;++i)
   FX_HISTORY(i)=historyOracle[i]=((int)(i%31)-15)*0.013579f;
  Delay d={0};Delay_init(&d);d.delayType=mode;
  d.oldRead=FX_FLOAT_FAST_SAMPLES-17;d.write=mask-23;
  d.fracReadOld=0.375f;d.feedback=0.91f;d.tone.r=d.tone2.r=1;
  unsigned rd=d.oldRead,wr=d.write;
  for(unsigned block=0;block<(mask+1)/64+3;++block) {
   float in[128],out[128],expected[128];
   for(unsigned i=0;i<128;++i) {in[i]=((int)((block*128+i)%19)-9)*(10000.125f/32768.f);out[i]=expected[i]=(40000.25f/32768.f);}
   for(unsigned i=0;i<64;++i) {
    unsigned next=(rd+1)&mask;
    float l=(historyOracle[rd]*0.625f+historyOracle[next]*0.375f)*(32767.f/32768.f);
    float r=mode?(historyOracle[half+rd]*0.625f+historyOracle[half+next]*0.375f)*(32767.f/32768.f):l;
    expected[2*i]=bound(expected[2*i]+bound(in[2*i]+bound((l-in[2*i])*0.7f)));
    if(ch==2) expected[2*i+1]=bound(expected[2*i+1]+bound(in[2*i+1]+bound((r-in[2*i+1])*0.7f)));
    if(mode) {
     historyOracle[half+wr]=fmaxf(-1,fminf(1,(in[2*i]+l*0.91f)/(32767.f/32768.f)));
     historyOracle[wr]=fmaxf(-1,fminf(1,(in[2*i+1]+r*0.91f)/(32767.f/32768.f)));
    } else {
     float sum=fmaxf(-1.f,fminf(32767.f/32768.f,in[2*i]+in[2*i+1]));
     historyOracle[wr]=fmaxf(-1,fminf(1,(sum+l*0.91f)/(32767.f/32768.f)));
    }
    rd=next;wr=(wr+1)&mask;
   }
   if(mode) Delay_processPingPong(&d,in,out,out+1,64,ch,0.7f);
   else Delay_process(&d,in,out,out+1,64,ch,0.7f);
   for(unsigned i=0;i<128;++i) assert(fabsf(out[i]-expected[i])<0.1f/32768.f);
   assert(d.oldRead==rd && d.write==wr);
   for(unsigned i=0;i<=FX_BUFFER_SIZE;++i) {
    assert(fabsf(FX_HISTORY(i)-historyOracle[i])<0.00001f);
    assert(FX_HISTORY(i)>=-1 && FX_HISTORY(i)<=1);
   }
  }
 }
 /* Distinct taps make fade weights observable; queued requests are last-wins.
  * Force a four-sample fade to cover completion exactly, then let the real
  * setter's 10ms fade finish over multiple production blocks. */
 for(unsigned mode=0;mode<2;++mode) {
  for(unsigned i=0;i<=FX_BUFFER_SIZE;++i) FX_HISTORY(i)=i<100?0.1f:0.3f;
  Delay d={0};Delay_init(&d);d.delayType=mode;d.range=0.5f;
  d.oldRead=10;d.newRead=200;d.write=2000;d.fracReadNew=0.25f;
  d.interpValue=1;d.interpStep=0.25f;d.tone.r=d.tone2.r=1;d.feedback=0;
  Delay_setDelayTime(&d,0.2f);Delay_setDelayTime(&d,0.7f);
  assert(d.timePending && d.pendingDelayTime==0.7f);
  float in[128]={0},out[128]={0};
  if(mode) Delay_processPingPong(&d,in,out,out+1,4,2,1);
  else Delay_process(&d,in,out,out+1,4,2,1);
  for(unsigned i=0;i<4;++i) closef(out[2*i],(0.1f+0.05f*i)*(32767.f/32768.f));
  assert(d.oldRead==204 && d.fracReadOld==0.25f && d.interpValue==0 && d.timePending);
  memset(out,0,sizeof out);
  if(mode) Delay_processPingPong(&d,in,out,out+1,1,2,1);
  else Delay_process(&d,in,out,out+1,1,2,1);
  closef(out[0],0.3f*(32767.f/32768.f));
  assert(!d.timePending && d.delayTime==0.7f && d.interpValue==1);
  for(unsigned i=0;i<8;++i) {
   if(mode) Delay_processPingPong(&d,in,out,out+1,64,2,1);
   else Delay_process(&d,in,out,out+1,64,2,1);
  }
  assert(d.interpValue<=0 && !d.timePending && d.fracReadOld==d.fracReadNew);
 }
}
extern const double ecc83Table[129];
extern const float table_1n914[257];
static void test_distortion_numbers(void) {
 const float samples[]={-(1000.125f/32768.f),-(40000.375f/32768.f),(40000.625f/32768.f)};
 for(unsigned ch=1;ch<=2;++ch) for(unsigned k=0;k<3;++k) {
  MasterDistortion d;Distortion_init(&d);d.p3=0.7f;
  float in[2]={samples[k],samples[k]},out[2]={(40000.25f/32768.f),-(40000.25f/32768.f)};
  float x=samples[k]*(ch==2?5.f:2.f);
  /* Table cell is clipped, but the overload fractional remainder is not. */
  unsigned cell=(unsigned)((fmaxf(-1.f,fminf(32767.f/32768.f,x))+1.f)*64.f);
  float fraction=x*64.f-floorf(x*64.f);
  double v=ecc83Table[cell]+(ecc83Table[cell+1]-ecc83Table[cell])*fraction;
  float wet=fmaxf(-1.f,fminf(32767.f/32768.f,(float)(v*0.06537948995454451662*2.1*0.7)));
  Distortion_process(&d,in,out,out+1,1,ch,0.75f);
  closef(out[0],bound((40000.25f/32768.f)+samples[k]+bound((wet-samples[k])*0.75f)));
  if(ch==2) closef(out[1],bound(-(40000.25f/32768.f)+samples[k]+bound((wet-samples[k])*0.75f)));
  else assert(out[1]==-(40000.25f/32768.f));
 }
 /* Fold wet expectation includes an actual triangle-fold excursion. */
 for(unsigned ch=1;ch<=2;++ch) for(int sign=-1;sign<=1;sign+=2) {
  MasterDistortion d;Distortion_init(&d);d.distortionType=DISTORTION_FOLD;
  d.p2=1;d.p3=0.7f;
  float in[2]={sign*(30000.25f/32768.f),sign*(30000.25f/32768.f)},out[2]={0};
  double filtered=(in[0]*5+1)*(0.06537948995454451662+0.92410701734426630737);
  double folded=fabs(fabs(fmod(filtered-1,4))-2)-1;
  Distortion_process(&d,in,out,out+1,1,ch,1);
  closef(out[0],bound(in[0]+bound((float)(folded*0.7)-in[0])));
  if(ch==2) closef(out[1],out[0]);else assert(out[1]==0);
 }
 /* High drive reaches both diode endpoints through the actual RAT chain. */
 for(unsigned ch=1;ch<=2;++ch) for(int sign=-1;sign<=1;sign+=2) {
  MasterDistortion d;Distortion_init(&d);d.distortionType=DISTORTION_RAT;d.p3=0.7f;
  float in[2]={sign*(32768.f/32768.f),sign*(32768.f/32768.f)},out[2]={0};
  Distortion_process(&d,in,out,out+1,1,ch,1);
  assert(d.slewState[0]==sign*4.2f);
  float endpoint=sign>0?table_1n914[256]:table_1n914[0];
  closef(out[0],endpoint*0.06537948995454451662f*0.7f*(32768.f/32768.f));
  if(ch==2) closef(out[1],out[0]);else assert(out[1]==0);
 }
}
int main(void) {
 test_delay_history();
 test_distortion_numbers();
 _Static_assert(sizeof(AudioSample)==4,"production float32");
 _Static_assert(sizeof(sawTable[0][0])==2,"original tables");
 float a[128]={0},b[128]={0},mod[64]={0};
 /* Genuine interpolated fractional values, signs, table wrap and PWM bound. */
 for(unsigned row=0;row<11;++row) for(unsigned i=0;i<1024;++i) {
  OscInfo o={.phase=(i<<22)+0x200000,.phaseInc=123,.tableOffset=row};
  calcWavetableOscBlock(&o,sawTable,a,1,0.125f);
  float expected=(sawTable[row][i]+sawTable[row][(i+1)&1023u])*(0.0625f/32768.f);
  closef(a[0],expected);assert(o.phase==(i<<22)+0x200000+123);
  o.phase=(i<<22)+0x200000;calcFmBlock(&o,sawTable,mod,a,1,0.125f);closef(a[0],expected);
  o.phase=(i<<22)+0x200000;calcPwmBlock(&o,a,1,1,1);
  assert(a[0]>=-1 && a[0]<=32767.f/32768.f);
 }
 OscInfo noise={.phase=UINT32_MAX,.phaseInc=2};calcNoiseBlock(&noise,a,1,0.5f);assert(a[0]==-(16383.5f/32768.f));
 a[0]=(30000.25f/32768.f);b[0]=(30000.5f/32768.f);bufferTool_addBuffersSaturating(a,b,1);assert(a[0]==(32767.f/32768.f));
 bufferTool_addGain(a,0.5f,1);assert(a[0]==(16383.5f/32768.f));
 bufferTool_clearBuffer(a,127);for(unsigned i=0;i<127;++i) assert(a[i]==0);
 /* Real transient reads normalize signed8 directly by /128: both signs,
  * no signed-left-shift C UB and no table/storage change. */
 unsigned negativeTransients=0;
 for(unsigned t=0;t<NUM_TRANSIENTS;++t) for(unsigned i=0;i<TRANSIENT_SAMPLE_LENGTH;++i) {
  TransientGenerator tg={.waveform=t+2,.phase=i<<20,.volume=0.73125f};
  transient_calcBlock(&tg,a,1);
  /* Existing phase gate excludes the last stored element (index 2204). */
  closef(a[0],i<2204 ? transientData[t][i]*(0.73125f/128.f) : 0);
  negativeTransients += transientData[t][i]<0;
 }
 assert(negativeTransients);
 /* Legacy single-sample click/read entry uses the same normalized convention. */
 TransientGenerator click={.waveform=0,.volume=0.73125f};
 transient_calc(&click);closef(click.output,0.73125f*(127.f/128.f)*transientVolumeTable[0]);
 unsigned transientIndex=0;
 while(transientIndex<TRANSIENT_SAMPLE_LENGTH && transientData[0][transientIndex]<=0) ++transientIndex;
 assert(transientIndex<TRANSIENT_SAMPLE_LENGTH);
 TransientGenerator transient={.waveform=2,.phase=transientIndex<<20,.volume=0.00037f};
 transient_calcBlock(&transient,a,1);
 closef(a[0],transientData[0][transientIndex]*(1.f/128.f)*0.00037f);
 assert(a[0]!=truncf(a[0]));
 ResonantFilter filter={0};filter.g=0.1f;filter.f=0.1f;filter.q=0.7f;filter.drive=1;
 a[0]=0.25f;SVF_calcBlockZDF(&filter,FILTER_LP,a,1);
 assert(a[0]!=0 && a[0]!=truncf(a[0]));
 /* Full history capacity and split boundary, float precision and delay gain. */
 for(unsigned i=0;i<=FX_BUFFER_SIZE;++i) FX_HISTORY(i)=(i&1)?0.1234567f:-0.1234567f;
 assert(FX_HISTORY(FX_FLOAT_FAST_SAMPLES-1)==0.1234567f);
 assert(FX_HISTORY(FX_FLOAT_FAST_SAMPLES)==-0.1234567f);
 Delay read={0};read.oldRead=FX_FLOAT_FAST_SAMPLES-1;read.fracReadOld=0.37f;
 FX_HISTORY(FX_FLOAT_FAST_SAMPLES-1)=0.1234567f;FX_HISTORY(FX_FLOAT_FAST_SAMPLES)=0.2345678f;
 Delay_calcBuffer(&read,0);
 closef(read.tmpBuffer[0],(0.1234567f*0.63f+0.2345678f*0.37f)*(32767.f/32768.f));
 assert(read.tmpBuffer[0]!=truncf(read.tmpBuffer[0]));
 for(unsigned ch=1;ch<=2;++ch) for(unsigned mode=0;mode<2;++mode) {
  Delay d={0};Delay_init(&d);d.oldRead=d.newRead=20;d.write=100;d.feedback=0;d.tone.r=d.tone2.r=1;
  a[0]=(200.25f/32768.f);a[1]=-(100.125f/32768.f);b[0]=(40000.5f/32768.f);b[1]=-(40000.5f/32768.f);
  if(mode) Delay_processPingPong(&d,a,b,b+1,1,ch,0);else Delay_process(&d,a,b,b+1,1,ch,0);
  assert(b[0]==(32767.f/32768.f));assert(b[1]==(ch==2?-(32768.f/32768.f):-(40000.5f/32768.f)));
 }
 /* All musical distortion algorithms, bypass and fractional wet path. */
 for(unsigned type=0;type<3;++type) for(unsigned ch=1;ch<=2;++ch) {
  MasterDistortion d;Distortion_init(&d);d.distortionType=type;d.p3=0.7f;
  a[0]=(1000.25f/32768.f);a[1]=-(1000.125f/32768.f);b[0]=(40000.5f/32768.f);b[1]=-(40000.5f/32768.f);
  Distortion_process(&d,a,b,b+1,1,ch,0);
  assert(b[0]==(32767.f/32768.f));assert(b[1]==(ch==2?-(32768.f/32768.f):-(40000.5f/32768.f)));
  b[0]=b[1]=0;Distortion_process(&d,a,b,b+1,1,ch,1);
  assert(isfinite(b[0]) && b[0]!=truncf(b[0]));
 }
 /* FX compressor law is unaltered: unity ratio, markup=2, source saturation. */
 for(unsigned ch=1;ch<=2;++ch) {
  Compressor c;Compressor_init(&c);c.ratio=1;c.markupGain=2;
  a[0]=(1000.25f/32768.f);a[1]=-(500.125f/32768.f);b[0]=(40000.5f/32768.f);b[1]=-(40000.5f/32768.f);
  Compressor_process(&c,a,b,b+1,1,ch,1);
  assert(b[0]==(32767.f/32768.f));assert(b[1]==(ch==2?-(32768.f/32768.f):-(40000.5f/32768.f)));
 }
 /* Ring stereo divisor and historical mono destination-in-wet law. */
 for(unsigned ch=1;ch<=2;++ch) {
  Ringmod r={0};r.osc.waveform=SINE;r.osc.phase=1024u<<20;
  a[0]=(1000.25f/32768.f);a[1]=-(500.125f/32768.f);b[0]=(40000.5f/32768.f);b[1]=-(40000.5f/32768.f);
  Ringmod_process(&r,a,b,b+1,1,ch,1);
  closef(b[0],bound((40000.5f/32768.f)+(1000.25f/32768.f)+bound((ch==1?bound((1000.25f/32768.f)*(sine_table[1024]/32768.f)*0.5f+(40000.5f/32768.f)):(1000.25f/32768.f)*(sine_table[1024]/32768.f)*0.5f)-(1000.25f/32768.f))));
 }
 /* Actual six voice block paths, settled smoothers and no modulation offset.
  * Expected sine peak*gain retains fractions through each voice's envelopes. */
 for(unsigned v=0;v<3;++v) {
  DrumVoice *d=&voiceArray[v];memset(d,0,sizeof *d);
  d->osc.waveform=SINE;d->osc.phase=1024u<<20;
  d->filterType=FILTER_OFF;d->ampFilterInput=0.5f;d->lastGain=0.5f;
  d->vol=0.37f;d->MixerPageFilter[0].b=0.37f;d->FaderVolumeFilter.b=1;
  calcDrumVoiceSyncBlock(v,a,64);
  assert(a[0]!=truncf(a[0]) && a[63]!=truncf(a[63]));
 }
 memset(&snareVoice,0,sizeof snareVoice);snareVoice.osc.phase=1024u<<20;
 snareVoice.osc.waveform=SINE;snareVoice.filterType=FILTER_OFF;
 snareVoice.vol=0.37f;snareVoice.egValueOscVol=0.5f;snareVoice.FaderVolumeFilter.b=1;
 Snare_calcSyncBlock(a,64);assert(a[0]!=truncf(a[0]));
 memset(&hatVoice,0,sizeof hatVoice);hatVoice.osc.phase=1024u<<20;
 hatVoice.osc.waveform=SINE;hatVoice.filterType=FILTER_OFF;
 hatVoice.vol=0.5f;hatVoice.egValueOscVol=0.5f;hatVoice.FaderVolumeFilter.b=1;
 HiHat_calcSyncBlock(a,64);assert(a[0]!=truncf(a[0]));
 memset(&cymbalVoice,0,sizeof cymbalVoice);cymbalVoice.osc.phase=1024u<<20;
 cymbalVoice.osc.waveform=SINE;cymbalVoice.filterType=FILTER_OFF;
 cymbalVoice.vol=0.37f;cymbalVoice.egValueOscVol=0.5f;cymbalVoice.FaderVolumeFilter.b=1;
 Cymbal_calcSyncBlock(a,64);assert(a[0]!=truncf(a[0]));
 /* Deliberate snare clip remains before volume/EG attenuation, both signs. */
 for(int sign=-1;sign<=1;sign+=2) {
  memset(&snareVoice,0,sizeof snareVoice);
  snareVoice.osc.waveform=NOISE;snareVoice.osc.output=sign*(30000.25f/32768.f);
  snareVoice.noiseOsc.output=sign*(30000.5f/32768.f);snareVoice.filterType=FILTER_OFF;
  snareVoice.transGen=(TransientGenerator){.waveform=2,.phase=transientIndex<<20,
   .volume=sign*30000.f/(transientData[0][transientIndex]*256.f)};
  snareVoice.mix=0.5f;snareVoice.vol=0.5f;snareVoice.egValueOscVol=0.5f;
  snareVoice.FaderVolumeFilter.b=1;
  Snare_calcSyncBlock(a,1);closef(a[0],(sign>0?(32767.f/32768.f):-(32768.f/32768.f))*0.25f);
 }
 /* Every mixer route: float pan, mono pan bypass, per-add clipping and
  * decimator held fractions. FX OFF adds its bus with per-add clipping. */
 r1_Available=l1_Available=r2_Available=l2_Available=1;
 for(unsigned route=0;route<=MIXER_ROUTING_FX_BUS;++route) {
  float out1[128]={0},out2[128]={0},bus[128]={0},voice[64];
  for(unsigned i=0;i<64;++i) voice[i]=(40000.25f/32768.f);
  mixer_addDataToOutput(route,0.25f,0.75f,voice,out1,out1+1,out2,out2+1,bus);
  mixer_addDataToOutput(route,0.25f,0.75f,voice,out1,out1+1,out2,out2+1,bus);
  float *dest=route==MIXER_ROUTING_FX_BUS?bus:route==MIXER_ROUTING_DAC1_STEREO || route==MIXER_ROUTING_DAC1_L || route==MIXER_ROUTING_DAC1_R?out2:out1;
  if(route<2 || route==MIXER_ROUTING_FX_BUS) {
   assert(dest[0]==(20000.125f/32768.f) && dest[1]==(32767.f/32768.f));
  } else assert(dest[route==MIXER_ROUTING_DAC1_R || route==MIXER_ROUTING_DAC2_R]==(32767.f/32768.f));
  if(route==MIXER_ROUTING_FX_BUS) {
   fxBus.fxType=FX_OFF;fxBus.audioRouting=MIXER_ROUTING_DAC1_STEREO;
   FxBus_process(bus,out1,out1+1,out2,out2+1,64);
   assert(out2[1]==(32767.f/32768.f));
  }
 }
 r1_Available=l1_Available=0;
 assert(mixer_checkOutJackAvailable(MIXER_ROUTING_DAC1_STEREO)==MIXER_ROUTING_DAC2_STEREO);
 r2_Available=0;
 assert(mixer_checkOutJackAvailable(MIXER_ROUTING_DAC1_L)==MIXER_ROUTING_DAC2_L);
 mixer_decimation_rate[0]=0;mixer_decimation_rate[6]=1;mixer_voice_samples[0]=-0.375f;
 mixer_decimateBlock(0,a);assert(a[0]==-0.375f && a[63]==-0.375f);
 /* Full mixer dispatch: six settled production voices feed both outputs and
  * FX OFF through every route. Held decimator values provide exact signed,
  * fractional bus expectations independent of oscillator phase. */
 lxr_test_gpio_b.IDR=GPIO_PIN_3|GPIO_PIN_4|GPIO_PIN_6|GPIO_PIN_7;
 for(unsigned route=0;route<=MIXER_ROUTING_FX_BUS;++route) {
  float out1[128],out2[128];int16_t encoded[256];
  mixer_init();
  for(unsigned v=0;v<6;++v) {
   mixer_audioRouting[v]=route;mixer_decimation_rate[v]=0;
   mixer_voice_samples[v]=(v&1)?-(1000.125f/32768.f):(2000.25f/32768.f);
  }
  for(unsigned v=0;v<3;++v) {voiceArray[v].pan=0;voiceArray[v].triggeredPanL=1;voiceArray[v].triggeredPanR=0;}
  snareVoice.triggeredPanL=cymbalVoice.triggeredPanL=hatVoice.triggeredPanL=1;
  snareVoice.triggeredPanR=cymbalVoice.triggeredPanR=hatVoice.triggeredPanR=0;
  snareVoice.pan=cymbalVoice.pan=hatVoice.pan=0;
  fxBus.fxType=FX_OFF;fxBus.audioRouting=MIXER_ROUTING_DAC1_STEREO;
  mixer_calcNextSampleBlock(out1,out2);
  float *dest=(route==MIXER_ROUTING_DAC1_STEREO || route==MIXER_ROUTING_DAC1_L ||
    route==MIXER_ROUTING_DAC1_R || route==MIXER_ROUTING_FX_BUS)?out2:out1;
  unsigned lane=(route==MIXER_ROUTING_DAC1_R || route==MIXER_ROUTING_DAC2_R);
  for(unsigned i=0;i<64;++i) {
   closef(dest[2*i+lane],(3000.375f/32768.f));assert(dest[2*i+1-lane]==0);
   float *other=dest==out1?out2:out1;assert(other[2*i]==0 && other[2*i+1]==0);
  }
  /* Actual renderer dispatches the complete mixer into static float scratch,
   * then the real secondary encoder and main filter/compressor/encoder.
   * Check both halves and leave the non-requested half untouched. */
  for(unsigned half=0;half<2;++half) {
   for(unsigned i=0;i<AUDIO_DMA_HALFWORDS;++i) dma_buffer[i]=dma_buffer2[i]=1234;
   bCurrentSampleValid=half;
   assert(soundengine_calcNextSampleBlock()==1 && bCurrentSampleValid==SAMPLE_VALID);
   for(unsigned i=0;i<128;++i) {
    assert(unpack(dma_buffer+half*AUDIO_DMA_HALF_OFFSET+2*i)==(int32_t)(out1[i]*8388608.f));
    assert(unpack(dma_buffer2+half*AUDIO_DMA_HALF_OFFSET+2*i)==(int32_t)(out2[i]*8388608.f));
   }
   for(unsigned i=0;i<AUDIO_DMA_HALF_OFFSET;++i) {
    assert(dma_buffer[(1-half)*AUDIO_DMA_HALF_OFFSET+i]==1234);
    assert(dma_buffer2[(1-half)*AUDIO_DMA_HALF_OFFSET+i]==1234);
   }
   assert(soundengine_calcNextSampleBlock()==0);
  }
  /* Real main output DSP/encoder, plus secondary output encoder. */
  MainDjFilter_process24(out2,encoded,64);
  for(unsigned i=0;i<128;++i) assert(unpack(encoded+2*i)==(int32_t)(out2[i]*8388608.f));
  for(unsigned i=0;i<128;++i) audio_output24_store(encoded+2*i,out1[i]);
  for(unsigned i=0;i<128;++i) assert(unpack(encoded+2*i)==(int32_t)(out1[i]*8388608.f));
 }
 /* St1 real HP/LP/compressor accepts float and only encoder bounds final. */
 int16_t packed[4];a[0]=0.25f/32768.f;a[1]=-0.25f/32768.f;
 MainDjFilter_process24(a,packed,1);assert(unpack(packed)==64 && unpack(packed+2)==-64);
 a[0]=(32767.75f/32768.f);a[1]=-(40000.f/32768.f);MainDjFilter_process24(a,packed,1);
 assert(unpack(packed)==8388544 && unpack(packed+2)==-8388608);
 a[0]=40000.f/32768.f;MainDjFilter_process24(a,packed,1);assert(unpack(packed)==8388607);
 /* LP recurrence and compressor process fractional float input, not int16. */
 MainDjFilter_setTargets(0,0,0);a[0]=a[1]=0;
 for(unsigned i=0;i<512;++i) MainDjFilter_process24(a,packed,1);
 a[0]=(100.25f/32768.f);a[1]=-(100.25f/32768.f);MainDjFilter_process24(a,packed,1);
 unsigned tails=0;a[0]=a[1]=0;
 for(unsigned i=0;i<1000;++i) {
  MainDjFilter_process24(a,packed,1);int32_t v=unpack(packed);
  if(v>0 && v<256) {assert(unpack(packed+2)==-v);++tails;}
 }
 assert(tails);
 memset(&state,0,sizeof state);memset(&comp,0,sizeof comp);
 MainDjFilter_reset();const uint8_t controls[]={12,19,0,0};MainCompressor_setControls(controls);
 a[0]=(16000.25f/32768.f);a[1]=-(8000.125f/32768.f);
 for(unsigned i=0;i<30000;++i) MainDjFilter_process24(a,packed,1);
 float g=1.f+comp.wet*(comp.gain*comp.makeup-1.f);
 float expected=fminf(8388607.f,a[0]*g*8388608.f);
 assert(fabsf(unpack(packed)-expected)<3);
 assert(unpack(packed+2)<0);
 return 0;
}
