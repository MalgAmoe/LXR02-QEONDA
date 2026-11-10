#!/usr/bin/env python3
"""Actual block functions and tables; substitute OscInfo and scalar PWM bounds.
No full mixer, oscillator frequency selection or physical audio timing coverage.
"""
from pathlib import Path
import os,subprocess,tempfile
helpers=(Path(__file__).parent/'test_control_fixes.py').read_text().split('case=os.environ')[0]
exec(helpers)
source=implementation('Core/Src/Soundengine/DSPAudio/Oscillator.c').replace('IN_ITCM_RAM ','')
functions=''.join(extract(source,n) for n in ('calcFmSineBlock','calcWavetableOscBlock','calcFmBlock','calcPwmBlock','calcPwmFmBlock'))
# Only the three exact conversion sites may be adapted for negative host tests.
cast='(uint32_t)(modBuffer[i]*osc->fmMod)'
assert functions.count(cast)==3
for name in ('calcFmSineBlock','calcFmBlock','calcPwmFmBlock'):
 assert extract(source,name).count(cast)==1
adapted=functions.replace(cast,'arm_unsigned_model(modBuffer[i]*osc->fmMod)')
code=r'''
#include <stdint.h>
#include "Soundengine/AudioSample.h"
#include <assert.h>
#include <stdio.h>
#include <math.h>
#include "Soundengine/DSPAudio/wavetable.h"
#define INTERPOLATE_OSC 1
#define INTERPOLATE_FM_OSC 1
typedef struct {uint32_t phase,phaseInc;unsigned tableOffset;float fmMod;float output;} OscInfo;
static float pwm_bound(float a,float b){return audio_sample_bound(a-b);}
'''+r'''
#ifdef TARGET_CONVERSION_MODEL
/* Host model of bounded finite ARM VCVT result, NOT actual target execution. */
static uint32_t arm_unsigned_model(float x){
 assert(isfinite(x) && x>=-32768.f && x<=32768.f);
 return x<0.f?0u:(uint32_t)x;
}
#endif
'''+ 'FUNCTIONS_PLACEHOLDER' +r'''
static float sample(const int16_t *t,uint32_t phase){
 unsigned i=phase>>22,next=(i+1)&1023u;
 return (float)t[i]+(t[next]-t[i])*((phase&0x3fffff)/4194304.f);
}
int main(void){
 const int16_t (*tables[])[1024]={sawTable,triTable,recTable};
 unsigned checks=0;
 for(unsigned t=0;t<3;t++)for(unsigned row=0;row<11;row++)
 for(unsigned i=0;i<1024;i++)for(unsigned f=0;f<3;f++){
  uint32_t phase=(i<<22)+(f==0?0:f==1?0x200000:0x3fffff);
  OscInfo o={phase,12345,row,1,0};float out,mod=1;
  calcWavetableOscBlock(&o,tables[t],&out,1,1);
  assert(out==sample(tables[t][row],phase)&&o.phase==phase+12345);checks++;
  o.phase=phase;calcFmBlock(&o,tables[t],&mod,&out,1,1);
  assert(out==sample(tables[t][row],phase+(1u<<19))&&o.phase==phase+12345);checks++;
  if(t==0) for(unsigned setting=0;setting<128;setting++){
   float pwm=setting/127.f;
   uint32_t offset=(uint32_t)((double)pwm*2147483648.0);
   uint32_t p2=phase+offset;
   o.phase=phase;calcPwmBlock(&o,&out,1,1,pwm);
   assert(out==pwm_bound(sample(sawTable[row],phase),sample(sawTable[row],p2)));checks++;
   o.phase=phase;mod=1;calcPwmFmBlock(&o,&mod,&out,1,1,pwm);
   assert(out==pwm_bound(sample(sawTable[row],phase+(1u<<19)),sample(sawTable[row],phase+(1u<<19)+offset)));checks++;
  }
 }
#ifdef TARGET_CONVERSION_MODEL
 /* Model current ARM unsigned conversion: finite negative products become
    zero. Exhaust every signed16 input, including negative envelope multipliers. */
 for(int m=-32768;m<=32767;m++)for(unsigned g=0;g<5;g++){
  const float amounts[]={-1.f,0.f,0.125f,0.5f,1.f};
  float x=m*amounts[g];uint32_t q=x<0?0:(uint32_t)x;
  uint32_t phase=0xffe00000u;
  OscInfo o={phase,12345,10,amounts[g],0};float mod=m,out;
  calcFmBlock(&o,recTable,&mod,&out,1,1);
  assert(out==sample(recTable[10],phase+(q<<19)));checks++;
  o.phase=phase;calcPwmFmBlock(&o,&mod,&out,1,1,1.f);
  uint32_t index=phase+(q<<19);
  assert(out==pwm_bound(sample(sawTable[10],index),sample(sawTable[10],index+0x80000000u)));checks++;
  o.phase=phase;calcFmSineBlock(&o,&mod,&out,1,1);
  index=phase+(q<<17);unsigned it=index>>20;
  float expected=(float)sine_table[it]+(sine_table[it+1]-sine_table[it])*((index&0xfffff)/1048576.f);
  assert(out==expected);checks++;
 }
#else
 /* Unmodified actual-source FM: exhaustive nonnegative inputs and sine model. */
 for(int m=0;m<=32767;m++)for(unsigned g=0;g<4;g++){
  const float amounts[]={0.f,0.125f,0.5f,1.f};
  uint32_t phase=0xffe00000u,q=(uint32_t)(m*amounts[g]);
  OscInfo o={phase,12345,10,amounts[g],0};float mod=m,out;
  calcFmBlock(&o,recTable,&mod,&out,1,1);
  assert(out==sample(recTable[10],phase+(q<<19)));checks++;
  o.phase=phase;calcPwmFmBlock(&o,&mod,&out,1,1,1.f);
  uint32_t index=phase+(q<<19);
  assert(out==pwm_bound(sample(sawTable[10],index),sample(sawTable[10],index+0x80000000u)));checks++;
  o.phase=phase;calcFmSineBlock(&o,&mod,&out,1,1);
  index=phase+(q<<17);unsigned it=index>>20;
  float expected=(float)sine_table[it]+(sine_table[it+1]-sine_table[it])*((index&0xfffff)/1048576.f);
  assert(out==expected);checks++;
 }
#endif
 printf("Wavetable wrap: %u sample comparisons across all rows, normal/FM/PWM paths pass.\n",checks);
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'Soundengine/DSPAudio').mkdir(parents=True)
 (p/'Soundengine/DSPAudio/wavetable.h').write_bytes((root/'Core/Inc/Soundengine/DSPAudio/wavetable.h').read_bytes())
 (p/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
 (p/'Soundengine/config.h').write_text('#define INDTCM\n')
 for label,body,defines in [('actual-source-nonnegative',functions,[]),('host-ARM-conversion-model',adapted,['-DTARGET_CONVERSION_MODEL'])]:
  print(label,flush=True)
  (p/'test.c').write_text(code.replace('FUNCTIONS_PLACEHOLDER',body))
  subprocess.run([os.getenv('CC','cc'),'-O2','-fsanitize=address,undefined,float-cast-overflow','-fno-sanitize-recover=all',*defines,'-I'+tmp,'-I'+str(root/'Core/Inc'),str(p/'test.c'),str(root/'Core/Src/Soundengine/DSPAudio/wavetable.c'),'-lm','-o',str(p/'test')],check=True)
  subprocess.run([str(p/'test')],check=True)
