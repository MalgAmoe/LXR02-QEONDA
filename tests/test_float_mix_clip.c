/* Reuse production integration wiring, not its unclipped expectations. */
#define main unclipped_fixture_main
#include "test_audio_float32.c"
#undef main
static float bound(float x) {return fmaxf(-32768.f,fminf(32767.f,x));}
int main(void) {
 assert(audio_mix_add(0.125f,0.25f)==0.375f);
 assert(audio_mix_add(-0.125f,-0.25f)==-0.375f);
 assert(audio_mix_add(30000.25f,30000.5f)==32767.f);
 assert(audio_mix_add(-30000.25f,-30000.5f)==-32768.f);
 assert(audio_mix_add(audio_mix_add(30000,10000),-10000)==22767);
 assert(bound(30000+10000-10000)==30000); /* final-only is different */
 float x[2]={30000.25f,-30000.25f},y[2]={10000.5f,-10000.5f};
 bufferTool_addBuffersSaturating(x,y,2);assert(x[0]==32767 && x[1]==-32768);
 r1_Available=l1_Available=r2_Available=l2_Available=1;
 for(unsigned route=0;route<=MIXER_ROUTING_FX_BUS;++route)
 for(int sign=-1;sign<=1;sign+=2) for(unsigned hot=0;hot<2;++hot) {
  float a[128]={0},b[128]={0},bus[128]={0},voice[64];
  float value=sign*(hot?30000.25f:0.125f);
  for(unsigned i=0;i<64;++i) voice[i]=value;
  for(unsigned n=0;n<2;++n) mixer_addDataToOutput(route,0.5f,0.75f,voice,a,a+1,b,b+1,bus);
  float *dest=route==MIXER_ROUTING_FX_BUS?bus:route==MIXER_ROUTING_DAC1_STEREO||route==MIXER_ROUTING_DAC1_L||route==MIXER_ROUTING_DAC1_R?b:a;
  unsigned lane=route==MIXER_ROUTING_DAC1_R||route==MIXER_ROUTING_DAC2_R;
  for(unsigned i=0;i<64;++i) {
   if(route<2||route==MIXER_ROUTING_FX_BUS) {
    closef(dest[2*i],bound(value));closef(dest[2*i+1],bound(1.5f*value));
   } else closef(dest[2*i+lane],bound(2*value));
  }
 }
 /* Cancellation through every route proves clipping occurs per voice add. */
 for(unsigned route=0;route<=MIXER_ROUTING_FX_BUS;++route) {
  float a[128]={0},b[128]={0},bus[128]={0},voice[64];
  const float values[]={30000.f,10000.f,-10000.f};
  for(unsigned n=0;n<3;++n) {
   for(unsigned i=0;i<64;++i) voice[i]=values[n];
   mixer_addDataToOutput(route,1,1,voice,a,a+1,b,b+1,bus);
  }
  float *dest=route==MIXER_ROUTING_FX_BUS?bus:route==MIXER_ROUTING_DAC1_STEREO||route==MIXER_ROUTING_DAC1_L||route==MIXER_ROUTING_DAC1_R?b:a;
  unsigned lane=route==MIXER_ROUTING_DAC1_R||route==MIXER_ROUTING_DAC2_R;
  assert(dest[lane]==22767.f);
 }
 /* Every FX return, physical route, mono/stereo, positive/negative and
  * fractional subthreshold; dryWet=0 isolates destination saturation. */
 for(unsigned fx=FX_OFF;fx<=FX_DELAY;++fx)
 for(unsigned mode=0;mode<2;++mode)
 for(unsigned route=0;route<=MIXER_ROUTING_DAC2_R;++route)
 for(int sign=-1;sign<=1;sign+=2) for(unsigned hot=0;hot<2;++hot) {
  FxBus_init();fxBus.fxType=fx;fxBus.audioRouting=route;fxBus.delay.delayType=mode;
  fxBus.delay.tone.r=fxBus.delay.tone2.r=1;
  float a[128],b[128],in[128];float initial=sign*(hot?30000.25f:0.125f);
  float value=sign*(hot?10000.5f:0.25f);
  for(unsigned i=0;i<128;++i) {a[i]=b[i]=initial;in[i]=value;}
  FxBus_process(in,a,a+1,b,b+1,64);
  float *dest=route==MIXER_ROUTING_DAC1_STEREO||route==MIXER_ROUTING_DAC1_L||route==MIXER_ROUTING_DAC1_R?b:a;
  unsigned lane=route==MIXER_ROUTING_DAC1_R||route==MIXER_ROUTING_DAC2_R;
  for(unsigned i=0;i<64;++i) {
   closef(dest[2*i+lane],bound(initial+value));
   closef(dest[2*i+1-lane],route<2?bound(initial+value):initial);
  }
 }
 /* Each distortion variant, compressor, ring and delays: wet output must
  * saturate on adding to either sign's destination, not just FX OFF. */
 for(unsigned ch=1;ch<=2;++ch) for(int sign=-1;sign<=1;sign+=2) {
  float in[2]={sign*1000.25f,sign*1000.25f},out[2];
  for(unsigned type=0;type<3;++type) {
   MasterDistortion d;Distortion_init(&d);d.distortionType=type;d.p3=0.7f;
   out[0]=out[1]=sign*100000.f;Distortion_process(&d,in,out,out+1,1,ch,1);
   assert(out[0]==(sign>0?32767:-32768));
  }
  Compressor c;Compressor_init(&c);c.ratio=1;c.markupGain=2;
  out[0]=out[1]=sign*100000.f;Compressor_process(&c,in,out,out+1,1,ch,1);
  assert(out[0]==(sign>0?32767:-32768));
  Ringmod r={0};r.osc.waveform=SINE;r.osc.phase=1024u<<20;
  out[0]=out[1]=sign*100000.f;Ringmod_process(&r,in,out,out+1,1,ch,1);
  assert(out[0]==(sign>0?32767:-32768));
 }
 /* Fractional wet returns below clip retain both signs. */
 for(unsigned ch=1;ch<=2;++ch) for(int sign=-1;sign<=1;sign+=2) {
  float in[2]={sign*1000.25f,sign*1000.25f};
  for(unsigned type=0;type<3;++type) {
   MasterDistortion d,e;Distortion_init(&d);d.distortionType=type;d.p3=0.7f;e=d;
   float wet[2]={0},out[2]={0.125f,0.125f};
   Distortion_process(&d,in,wet,wet+1,1,ch,0.7f);
   Distortion_process(&e,in,out,out+1,1,ch,0.7f);
   closef(out[0],wet[0]+0.125f);assert(out[0]!=truncf(out[0]));
   if(ch==2) closef(out[1],wet[1]+0.125f);
  }
  Compressor c;Compressor_init(&c);c.ratio=1;c.markupGain=2;
  float out[2]={0.125f,0.125f};Compressor_process(&c,in,out,out+1,1,ch,1);
  closef(out[0],0.125f+2*in[0]);
  Ringmod r={0};r.osc.waveform=SINE;r.osc.phase=1024u<<20;
  out[0]=out[1]=0.125f;Ringmod_process(&r,in,out,out+1,1,ch,1);
  closef(out[0],0.125f+in[0]*sine_table[1024]/65536.f+(ch==1?0.125f:0));
 }
 /* Baseline delta clip is distinct from clipping the full interpolation.
  * Dry+delta originally narrows/wraps: deliberately leave that sum float,
  * then apply only the baseline destination saturation. */
 for(unsigned ch=1;ch<=2;++ch) for(int sign=-1;sign<=1;sign+=2) {
  for(unsigned type=0;type<3;++type) {
   MasterDistortion wetD,d;Distortion_init(&d);d.distortionType=type;d.p3=0.7f;wetD=d;
   float in[2]={sign*60000.25f,sign*60000.25f},wet[2]={0},out[2]={-sign*10000.125f,-sign*10000.125f};
   Distortion_process(&wetD,in,wet,wet+1,1,ch,1);
   /* Recover actual source independently using dryWet=0 on a quiet input
    * is not possible; dryWet=1 itself clips the DELTA for this hot input.
    * Thus check its independently calculable plateau for all three curves. */
   Distortion_process(&d,in,out,out+1,1,ch,1);
   closef(out[0],bound(-sign*10000.125f+wet[0]));
  }
  for(unsigned mode=0;mode<2;++mode) {
   Delay d={0};Delay_init(&d);d.oldRead=20;d.write=100;d.tone.r=d.tone2.r=1;d.feedback=0;
   FX_HISTORY(20)=FX_HISTORY(21)=-sign*0.5f;
   FX_HISTORY((FX_BUFFER_SIZE>>1)+20)=FX_HISTORY((FX_BUFFER_SIZE>>1)+21)=-sign*0.5f;
   float in[2]={sign*60000.25f,sign*60000.25f},out[2]={-sign*10000.125f,-sign*10000.125f};
   if(mode) Delay_processPingPong(&d,in,out,out+1,1,ch,1);
   else Delay_process(&d,in,out,out+1,1,ch,1);
   float expected=bound(-sign*10000.125f+bound(in[0]+bound(-sign*16383.5f-in[0])));
   closef(out[0],expected);if(ch==2) closef(out[1],expected);
  }
 }
 return 0;
}
