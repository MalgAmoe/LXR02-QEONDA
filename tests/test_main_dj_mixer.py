"""Real mixer block/routing bodies, fake voice producers and FX return endpoint."""
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
#include <stdio.h>
#include "Soundengine/DSPAudio/MainDjFilter.h"
#define USE_TRIGGERED_PAN 1
#define OUTPUT_DMA_SIZE 64
#define MIXER_ROUTING_DAC1_STEREO 0
#define MIXER_ROUTING_DAC2_STEREO 1
#define MIXER_ROUTING_DAC1_L 2
#define MIXER_ROUTING_DAC1_R 3
#define MIXER_ROUTING_DAC2_L 4
#define MIXER_ROUTING_DAC2_R 5
#define MIXER_ROUTING_FX_BUS 6
static int sat(int x){return x>32767?32767:x< -32768?-32768:x;}
#define __PKHBT(a,b,n) (((uint32_t)(a)&65535u)|((uint32_t)(b)<<16))
static int32_t __QADD16(int32_t a,int32_t b){return __PKHBT(sat((int16_t)a+(int16_t)b),sat((int16_t)((uint32_t)a>>16)+(int16_t)((uint32_t)b>>16)),16);}
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
static void calcDrumVoiceSyncBlock(int n,int16_t*p,unsigned len){for(unsigned i=0;i<len;i++)p[i]=n==0?1000:0;}
static void Snare_calcSyncBlock(int16_t*p,unsigned n){memset(p,0,n*2);}
#define Cymbal_calcSyncBlock Snare_calcSyncBlock
#define HiHat_calcSyncBlock Snare_calcSyncBlock
static void mixer_decimateBlock(int n,int16_t*p){}
static void bufferTool_clearBuffer(int16_t*p,unsigned n){memset(p,0,n*2);}
static int fxSecond;
static void FxBus_process(int16_t*fx,int16_t*l,int16_t*r,int16_t*l2,int16_t*r2,unsigned n){for(unsigned i=0;i<n;i++){(fxSecond?l2:l)[2*i]+=fx[2*i];(fxSecond?r2:r)[2*i]+=fx[2*i+1];}}
'''
main=r'''
int main(void){
 voiceArray[0].triggeredPanL=voiceArray[0].triggeredPanR=1;
 int16_t a[128],b[128];
 for(unsigned route=0;route<7;route++)for(fxSecond=0;fxSecond<2;fxSecond++){
  MainDjFilter_reset();mixer_audioRouting[0]=route;
  for(unsigned j=0;j<20;j++)mixer_calcNextSampleBlock(a,b);
  int16_t baseline[128];memcpy(baseline,b,sizeof b);
  MainDjFilter_setTargets(126,127);
  for(unsigned j=0;j<100;j++){mixer_calcNextSampleBlock(a,b);assert(!memcmp(b,baseline,sizeof b));}
  if(route==1||route==4||route==5||(route==6&&!fxSecond))assert(a[126]==0&&a[127]==0);
  if(route==0||route==2||(route==6&&fxSecond))assert(b[126]==1000);
  if(route==0||route==3||(route==6&&fxSecond))assert(b[127]==1000);
 }
 puts("Actual mixer routes and post-FX Stereo2 invariance passed");
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'test.c').write_text(pre+extract('mixer_checkOutJackAvailable')+extract('mixer_addDataToOutput')+extract('mixer_calcNextSampleBlock')+main)
 subprocess.run([os.environ.get('CC','cc'),'-O1','-DLXR_HOST_TEST','-fsanitize=address,undefined','-I'+str(root/'Core/Inc'),str(p/'test.c'),str(root/'Core/Src/Soundengine/DSPAudio/MainDjFilter.c'),'-lm','-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
