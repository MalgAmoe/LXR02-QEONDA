/* Deterministic production DSP probe, shared unchanged with baseline 20e6e6b.
 * AUDIO_PROBE_SCALE is 1 for baseline signed16 units, 32768 for normalized.
 * Control-rate/hardware seams are the integration fixture's documented stubs.
 * FM here uses nonnegative modulation; negative ARM semantics have a separate
 * explicitly labeled exhaustive host model and production instruction check. */
#define main unused_integration_main
#include "test_audio_float32.c"
#undef main
#ifndef AUDIO_PROBE_SCALE
#define AUDIO_PROBE_SCALE 32768.f
#endif
#define N(x) ((x)/AUDIO_PROBE_SCALE)
/* Production internal entry is not exposed in Oscillator.h. */
void calcPwmFmBlock(OscInfo *,AudioSample *,AudioSample *,uint8_t,float,float);
static void emit(const char *name,const float *x,unsigned n) {
 for(unsigned i=0;i<n;++i) {
  assert(isfinite(x[i]));
  printf("%s %.9g\n",name,x[i]*(AUDIO_PROBE_SCALE/32768.f));
 }
}
static void encode(const char *name,float *x) {
 int16_t p[256];
 MainDjFilter_process24(x,p,64);
 for(unsigned i=0;i<128;++i) printf("%s %.9g\n",name,unpack(p+2*i)/8388608.0);
 for(unsigned i=0;i<128;++i) audio_output24_store(p+2*i,x[i]);
 for(unsigned i=0;i<128;++i) printf("secondary %.9g\n",unpack(p+2*i)/8388608.0);
}
int main(void) {
 float a[128]={0},b[128]={0},mod[64];
 /* Table wrap, interpolated phase, noninteger gain, nonnegative FM quantization. */
 for(unsigned type=0;type<3;++type) for(unsigned row=0;row<11;++row) {
  OscInfo o={.phase=0xffeabcde,.phaseInc=123456789,.tableOffset=row,.fmMod=0.73125f};
  for(unsigned i=0;i<64;++i) mod[i]=N((i*953u)%32768+0.375f);
  if(type==0) calcFmSineBlock(&o,mod,a,64,0.83f);
  if(type==1) calcFmBlock(&o,recTable,mod,a,64,0.83f);
  if(type==2) calcPwmFmBlock(&o,mod,a,64,0.83f,0.731f);
  emit("fm",a,64);
 }
 /* Six actual voice paths, fractional held noise and nonlinear voice filters. */
 for(unsigned mode=0;mode<2;++mode) {
  memset(voiceArray,0,sizeof voiceArray);
  memset(&snareVoice,0,sizeof snareVoice);
  memset(&hatVoice,0,sizeof hatVoice);
  memset(&cymbalVoice,0,sizeof cymbalVoice);
  for(unsigned v=0;v<3;++v) {
   DrumVoice *d=&voiceArray[v];d->osc.waveform=NOISE;d->osc.output=N(21000.375f-v*9000.f);
   d->filterType=mode?FILTER_LP:FILTER_OFF;
   d->filter.g=0.13f;d->filter.f=0.12f;d->filter.q=0.73f;d->filter.drive=2.3f;
   d->ampFilterInput=d->lastGain=0.67f;d->vol=d->MixerPageFilter[0].b=0.73f;
   d->FaderVolumeFilter.b=1;d->distortion.shape=1.7f;
   for(unsigned k=0;k<4;++k) {calcDrumVoiceSyncBlock(v,a,64);emit("drums",a,64);}
  }
  snareVoice.osc.waveform=NOISE;snareVoice.osc.output=N(-29000.25f);
  snareVoice.noiseOsc.output=N(13000.5f);snareVoice.mix=0.73f;
  snareVoice.filterType=mode?FILTER_HP:FILTER_OFF;
  snareVoice.filter.g=0.13f;snareVoice.filter.f=0.12f;snareVoice.filter.q=0.73f;snareVoice.filter.drive=2.3f;
  snareVoice.vol=0.71f;snareVoice.egValueOscVol=0.83f;snareVoice.FaderVolumeFilter.b=1;
  snareVoice.distortion.shape=1.7f;
  for(unsigned k=0;k<4;++k) {Snare_calcSyncBlock(a,64);emit("snare",a,64);}
  hatVoice.osc.waveform=cymbalVoice.osc.waveform=NOISE;
  hatVoice.osc.output=cymbalVoice.osc.output=N(23000.125f);
  hatVoice.filterType=cymbalVoice.filterType=mode?FILTER_BP:FILTER_OFF;
  hatVoice.filter.g=cymbalVoice.filter.g=0.13f;hatVoice.filter.f=cymbalVoice.filter.f=0.12f;
  hatVoice.filter.q=cymbalVoice.filter.q=0.73f;hatVoice.filter.drive=cymbalVoice.filter.drive=2.3f;
  hatVoice.vol=cymbalVoice.vol=0.71f;hatVoice.egValueOscVol=cymbalVoice.egValueOscVol=0.83f;
  hatVoice.FaderVolumeFilter.b=cymbalVoice.FaderVolumeFilter.b=1;
  for(unsigned k=0;k<4;++k) {
   HiHat_calcSyncBlock(a,64);emit("hat",a,64);
   Cymbal_calcSyncBlock(a,64);emit("cymbal",a,64);
  }
 }
 for(unsigned type=0;type<3;++type) for(unsigned channels=1;channels<=2;++channels) {
  MasterDistortion d;Distortion_init(&d);d.distortionType=type;d.p1=0.63f;d.p2=0.83f;d.p3=0.71f;
  for(unsigned k=0;k<8;++k) {
   for(unsigned i=0;i<128;++i) {a[i]=N(((int)((i+k*128)*997u%120001)-60000)*0.731f);b[i]=N(i%2?1234.125f:-2345.375f);}
   Distortion_process(&d,a,b,b+1,64,channels,0.83f);emit(type==0?"tube":type==1?"fold":"rat",b,128);
  }
 }
 for(unsigned mode=0;mode<2;++mode) {
  Delay d={0};Delay_init(&d);d.oldRead=13;d.write=31;d.fracReadOld=0.37f;d.feedback=0.91f;d.tone.r=d.tone2.r=0.73f;
  for(unsigned i=0;i<=FX_BUFFER_SIZE;++i) FX_HISTORY(i)=((int)(i%31)-15)*0.037f;
  for(unsigned k=0;k<12;++k) {
   for(unsigned i=0;i<128;++i) {a[i]=N(((int)((i+k*128)*997u%120001)-60000)*0.731f);b[i]=0;}
   if(mode) Delay_processPingPong(&d,a,b,b+1,64,2,0.73f);else Delay_process(&d,a,b,b+1,64,2,0.73f);
   emit("delay",b,128);
  }
 }
 for(unsigned ch=1;ch<=2;++ch) {
  Ringmod r={0};r.osc.waveform=SAW;r.osc.phaseInc=123456789;
  Compressor c;Compressor_init(&c);c.ratio=0.73f;c.markupGain=2.3f;
  for(unsigned k=0;k<8;++k) {
   for(unsigned i=0;i<128;++i) {a[i]=N(((int)((i+k*128)*997u%80001)-40000)*0.731f);b[i]=N(1234.375f);}
   Ringmod_process(&r,a,b,b+1,64,ch,0.73f);emit("ring",b,128);
   memset(b,0,sizeof b);Compressor_process(&c,a,b,b+1,64,ch,0.83f);emit("fxcomp",b,128);
  }
 }
 /* Actual router, cancellation/overload, all routes, both encoders; St1 active
  * HP/LP/compressor versus unprocessed St2. Every source has both signs. */
 r1_Available=l1_Available=r2_Available=l2_Available=1;
 const uint8_t controls[]={12,19,0,0};MainCompressor_setControls(controls);MainDjFilter_setTargets(80,95,127);
 for(unsigned route=0;route<=MIXER_ROUTING_FX_BUS;++route) {
  float out1[128]={0},out2[128]={0},bus[128]={0},voice[64];
  for(unsigned v=0;v<6;++v) {
   for(unsigned i=0;i<64;++i) voice[i]=N(((int)((i+v*64)*997u%100001)-50000)*0.731f);
   mixer_addDataToOutput(route,0.37f,0.83f,voice,out1,out1+1,out2,out2+1,bus);
  }
  if(route==MIXER_ROUTING_FX_BUS) {fxBus.fxType=FX_OFF;fxBus.audioRouting=MIXER_ROUTING_DAC1_STEREO;FxBus_process(bus,out1,out1+1,out2,out2+1,64);}
  emit("route",out1,128);emit("route",out2,128);encode("main",out2);encode("main",out1);
 }
 return 0;
}
