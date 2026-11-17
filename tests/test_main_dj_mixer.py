"""Actual mixer/Soundengine/FX routing and DSP; both DMA halves, canonical St1.
Constant voice, IRQ primitives and unused FX algorithms are host stubs.
"""
from pathlib import Path
import re, subprocess, tempfile, os
root=Path(__file__).resolve().parents[1]
s=(root/'Core/Src/Soundengine/DSPAudio/mixer.c').read_text().replace('/*IN_ITCM_RAM*/','IN_ITCM_RAM')
def extract(name):
 m=re.search(r'(?m)^IN_ITCM_RAM (?:static )?(?:inline )?(?:void|uint8_t) '+name+r'\([^;]*?\)\s*\{',s); assert m,name
 e=m.end();d=1
 while d:d+=(s[e]=='{')-(s[e]=='}');e+=1
 return s[m.start():e].replace('IN_ITCM_RAM ','')
pre=r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "Soundengine/DSPAudio/MainDjFilter.h"
#include "Soundengine/DSPAudio/MainCompressor.h"
#include "Soundengine/AudioOutput24.h"
#define INDTCMZ
#define AUDIO_DMA_HALF_OFFSET 256
#define USE_TRIGGERED_PAN 1
#define OUTPUT_DMA_SIZE 64
static struct {unsigned IDR;} gpio={1};
#define switch_r2_GPIO_Port (&gpio)
#define switch_l2_GPIO_Port (&gpio)
#define switch_r1_GPIO_Port (&gpio)
#define switch_l1_GPIO_Port (&gpio)
#define switch_r2_Pin 1
#define switch_l2_Pin 1
#define switch_r1_Pin 1
#define switch_l1_Pin 1
static int r2_Available,l2_Available,r1_Available,l1_Available;
static struct {int lfo,filter;float triggeredPanL,triggeredPanR;} voiceArray[3],snareVoice,cymbalVoice,hatVoice;
static uint8_t mixer_audioRouting[6];
static void modNode_resetTargets(void){} static void modNode_reassignVeloMod(void){}
static void lfo_dispatchNextValue(void*p){} static void SVF_recalcFreq(void*p){}
static void calcDrumVoiceAsync(int n){} static void Snare_calcAsync(void){} static void Cymbal_calcAsync(void){} static void HiHat_calcAsync(void){}
static void calcDrumVoiceSyncBlock(int n,AudioSample*p,unsigned len){for(unsigned i=0;i<len;i++)p[i]=n==0?1000.f/32768.f:0;}
static void Snare_calcSyncBlock(AudioSample*p,unsigned n){memset(p,0,n*sizeof(*p));}
#define Cymbal_calcSyncBlock Snare_calcSyncBlock
#define HiHat_calcSyncBlock Snare_calcSyncBlock
static void mixer_decimateBlock(int n,AudioSample*p){}
static void bufferTool_clearBuffer(AudioSample*p,unsigned n){memset(p,0,n*sizeof(*p));}
'''
labels=(root/'Core/Inc/menu/MenuText.h').read_text()
for table, expected in (('outputNames', ['St1','St2','L1','R1','L2','R2','FX']), ('outputNamesFx', ['St1','St2','L1','R1','L2','R2'])):
 block=re.search(r'const char '+table+r'\[\]\[7\]\s*=\s*\{(.*?)\n\};',labels,re.S)
 assert block, table
 assert re.findall(r'\{"([^"\n]+)"\}',block[1])==expected, table
h=(root/'Core/Inc/Soundengine/DSPAudio/mixer.h').read_text()
pre+=re.search(r'enum\s*\{.*?\};',h,re.S)[0]+'\n'
def body(path,name):
 s=(root/path).read_text();m=re.search(r'(?m)^(?:IN_ITCM_RAM )?(?:void|uint8_t) '+name+r'\([^;]*?\)\s*\{',s);assert m,name
 p=m.end();d=1
 while d:d+=(s[p]=='{')-(s[p]=='}');p+=1
 return s[m.start():p].replace('IN_ITCM_RAM ','')+'\n'
pre+='''
#define USE_DAC2 1
#define USE_REVERB 0
#define SAMPLE_VALID 2
#define FX_OFF 0
#define FX_DISTORTION 1
#define FX_RING 2
#define FX_COMPRESSOR 3
#define FX_DELAY 4
#define DELAY_NORMAL 0
static struct {int audioRouting,fxType,dryWet,distortion,ringmod,compressor;struct {int delayType;} delay;} fxBus;
#define Distortion_process(...) assert(0)
#define Ringmod_process(...) assert(0)
#define Compressor_process(...) assert(0)
#define Delay_process(...) assert(0)
#define Delay_processPingPong(...) assert(0)
static int16_t dma_buffer[512],dma_buffer2[512];
static uint8_t bCurrentSampleValid;
static uint32_t codec_requestGeneration;
static uint32_t __get_PRIMASK(void){return 0;}
static void __disable_irq(void){}
static void __set_PRIMASK(uint32_t x){}
'''
c=pre+body('Core/Src/Soundengine/FxBus.c','FxBus_process')
c+=''.join(extract(n) for n in ('mixer_checkOutJackAvailable','mixer_addDataToOutput','mixer_calcNextSampleBlock'))
c+=body('Core/Src/Soundengine/Soundengine.c','soundengine_calcNextSampleBlock')
c+='''
static float decoded(const int16_t *p,unsigned i){
 uint32_t v=((uint32_t)(uint16_t)p[2*i]<<8)|((uint16_t)p[2*i+1]>>8);
 return (v&0x800000u?(int32_t)(v|0xff000000u):(int32_t)v)/8388608.f;
}
static void render(unsigned half){bCurrentSampleValid=half;assert(soundengine_calcNextSampleBlock());}
int main(void){
 voiceArray[0].triggeredPanL=voiceArray[0].triggeredPanR=1;
 assert(MIXER_ROUTING_DAC1_STEREO==0 && MIXER_ROUTING_DAC2_STEREO==1);
 assert(MIXER_ROUTING_DAC1_L==2 && MIXER_ROUTING_DAC1_R==3);
 assert(MIXER_ROUTING_DAC2_L==4 && MIXER_ROUTING_DAC2_R==5 && MIXER_ROUTING_FX_BUS==6);
 unsigned failures=0;
 const unsigned routes[]={MIXER_ROUTING_DAC1_STEREO,MIXER_ROUTING_DAC2_STEREO,MIXER_ROUTING_DAC1_L,MIXER_ROUTING_DAC1_R,MIXER_ROUTING_DAC2_L,MIXER_ROUTING_DAC2_R,MIXER_ROUTING_FX_BUS,MIXER_ROUTING_FX_BUS};
 const char *names[]={"St1","St2","L1","R1","L2","R2","FX->St1","FX->St2"};
 const uint8_t settings[][3]={{126,127,127},{0,20,127},{90,100,127},{100,20,127}};
 for(unsigned setting=0;setting<4;setting++)for(unsigned t=0;t<8;t++)for(unsigned half=0;half<2;half++){
  mixer_audioRouting[0]=routes[t];fxBus.audioRouting=t==7?MIXER_ROUTING_DAC2_STEREO:MIXER_ROUTING_DAC1_STEREO;
  for(unsigned i=0;i<512;i++)dma_buffer[i]=dma_buffer2[i]=12345;
  MainDjFilter_reset();for(unsigned j=0;j<120;j++)render(half);
  // Validate actual baseline destinations; do not let silence make invariance vacuous.
  for(unsigned i=0;i<128;i++){
   int left=(i%2)==0;
   int st1=t==0||t==6||(t==2&&left)||(t==3&&!left);
   int st2=t==1||t==7||(t==4&&left)||(t==5&&!left);
   assert(decoded(dma_buffer2,128*half+i)==(st1?1000.f/32768.f:0));
   assert(decoded(dma_buffer,128*half+i)==(st2?1000.f/32768.f:0));
  }
  int16_t a[256],b[256];memcpy(a,dma_buffer+256*half,sizeof a);memcpy(b,dma_buffer2+256*half,sizeof b);
  MainDjFilter_setTargets(settings[setting][0],settings[setting][1],settings[setting][2]);for(unsigned j=0;j<120;j++)render(half);
  int st1Changed=memcmp(b,dma_buffer2+256*half,sizeof b)!=0;
  int st2Changed=memcmp(a,dma_buffer+256*half,sizeof a)!=0;
  int mainRoute=t==0||t==2||t==3||t==6;
  int dcRejected=1;
  if(mainRoute && settings[setting][0])for(unsigned i=0;i<128;i++)dcRejected &= decoded(dma_buffer2,128*half+i)>=-1.f/32768.f && decoded(dma_buffer2,128*half+i)<=1.f/32768.f;
  int ok=mainRoute?(!st2Changed&&dcRejected&&(settings[setting][0]?st1Changed:1)):(!st1Changed&&!st2Changed);
  printf("%s half=%u: St1 changed=%d St2 changed=%d expected main-only: %s\\n",names[t],half,st1Changed,st2Changed,ok?"PASS":"FAIL");
  for(unsigned i=0;i<256;i++){
   assert(dma_buffer[256*(1-half)+i]==12345);
   assert(dma_buffer2[256*(1-half)+i]==12345);
  }
  failures+=!ok;
 }
 // Compressor through actual mixer -> Soundengine -> DMA halves, filters bypassed.
 MainDjFilter_reset();
 MainCompressor_setParameter(302,0);MainCompressor_setParameter(303,19);
 MainCompressor_setParameter(304,0);MainCompressor_setParameter(305,0);
 for(unsigned t=0;t<8;t++)for(unsigned half=0;half<2;half++){
  mixer_audioRouting[0]=routes[t];
  fxBus.audioRouting=t==7?MIXER_ROUTING_DAC2_STEREO:MIXER_ROUTING_DAC1_STEREO;
  for(unsigned i=0;i<512;i++)dma_buffer[i]=dma_buffer2[i]=12345;
  for(unsigned j=0;j<500;j++)render(half);
  for(unsigned i=0;i<128;i++){
   int left=(i%2)==0;
   int st1=t==0||t==6||(t==2&&left)||(t==3&&!left);
   int st2=t==1||t==7||(t==4&&left)||(t==5&&!left);
   assert(decoded(dma_buffer,128*half+i)==(st2?1000.f/32768.f:0));
   /* Settled DC: reduction at input level plus reference makeup minus growing margin. */
   double reductionDb=(20.0*log10(1000.0/32768.0)+48.0)*0.95;
   double expected=(1000.0/32768.0)*pow(10.0,(45.6-4.0*45.6/(45.6+12.0)-reductionDb)/20.0);
   assert(st1?fabs(decoded(dma_buffer2,128*half+i)-expected)<3.0/32768.0:decoded(dma_buffer2,128*half+i)==0);
   assert(dma_buffer[256*(1-half)+i]==12345);
   assert(dma_buffer2[256*(1-half)+i]==12345);
  }
 }
 MainCompressor_setParameter(303,0);
 mixer_audioRouting[0]=MIXER_ROUTING_DAC1_STEREO;
 // Drain the finite DSP-owned bypass ramp before asserting exact routing.
 for(unsigned i=0;i<4;i++)render(i%2);
 render(0);render(1);
 for(unsigned i=0;i<256;i++)assert(decoded(dma_buffer2,i)==1000.f/32768.f);
 printf("%u/64 intended main-only routing checks failed\\n",failures);
 return failures?1:0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'test.c').write_text(c)
 subprocess.run([os.environ.get('CC','cc'),'-O1','-DLXR_HOST_TEST','-fsanitize=address,undefined','-I'+str(root/'tests/shim'),'-I'+str(root/'Core/Inc'),str(p/'test.c'),str(root/'Core/Src/Soundengine/DSPAudio/MainDjFilter.c'),str(root/'Core/Src/Soundengine/DSPAudio/MainCompressor.c'),'-lm','-o',str(p/'test')],check=True)
 raise SystemExit(subprocess.run([str(p/'test')]).returncode)
