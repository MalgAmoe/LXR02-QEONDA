#!/usr/bin/env python3
"""Actual block functions and tables; fake OscInfo/CMSIS saturating subtraction.
No full mixer, oscillator frequency selection or physical audio timing coverage.
"""
from pathlib import Path
import os,subprocess,tempfile
helpers=(Path(__file__).parent/'test_control_fixes.py').read_text().split('case=os.environ')[0]
exec(helpers)
source=implementation('Core/Src/Soundengine/DSPAudio/Oscillator.c').replace('IN_ITCM_RAM ','')
functions=''.join(extract(source,n) for n in ('calcWavetableOscBlock','calcFmBlock','calcPwmBlock','calcPwmFmBlock'))
code=r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include "Soundengine/DSPAudio/wavetable.h"
#define INTERPOLATE_OSC 1
#define INTERPOLATE_FM_OSC 1
typedef struct {uint32_t phase,phaseInc;unsigned tableOffset;float fmMod;int16_t output;} OscInfo;
static int16_t __QSUB16(int16_t a,int16_t b){int x=(int)a-b;return x>32767?32767:x< -32768?-32768:x;}
'''+functions+r'''
static int16_t sample(const int16_t *t,uint32_t phase){
 unsigned i=phase>>22,next=i==1023?0:i+1;
 int16_t delta=(int16_t)(((int64_t)(t[next]-t[i])*(phase&0x3fffff))>>22);
 return (int16_t)(t[i]+delta);
}
int main(void){
 const int16_t (*tables[])[1024]={sawTable,triTable,recTable};
 unsigned checks=0;
 for(unsigned t=0;t<3;t++)for(unsigned row=0;row<11;row++)
 for(unsigned i=0;i<1024;i++)for(unsigned f=0;f<3;f++){
  uint32_t phase=(i<<22)+(f==0?0:f==1?0x200000:0x3fffff);
  OscInfo o={phase,12345,row,1,0};int16_t out,mod=1;
  calcWavetableOscBlock(&o,tables[t],&out,1,1);
  assert(out==sample(tables[t][row],phase)&&o.phase==phase+12345);checks++;
  o.phase=phase;calcFmBlock(&o,tables[t],&mod,&out,1,1);
  assert(out==sample(tables[t][row],phase+(1u<<19))&&o.phase==phase+12345);checks++;
  if(t==0) for(unsigned setting=0;setting<128;setting++){
   float pwm=setting/127.f;
   uint32_t offset=(uint32_t)((double)pwm*2147483648.0);
   uint32_t p2=phase+offset;
   o.phase=phase;calcPwmBlock(&o,&out,1,1,pwm);
   assert(out==__QSUB16(sample(sawTable[row],phase),sample(sawTable[row],p2)));checks++;
   o.phase=phase;mod=1;calcPwmFmBlock(&o,&mod,&out,1,1,pwm);
   assert(out==__QSUB16(sample(sawTable[row],phase+(1u<<19)),sample(sawTable[row],phase+(1u<<19)+offset)));checks++;
  }
 }
 printf("Wavetable wrap: %u sample comparisons across all rows, normal/FM/PWM paths pass.\n",checks);
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'Soundengine/DSPAudio').mkdir(parents=True)
 (p/'Soundengine/DSPAudio/wavetable.h').write_bytes((root/'Core/Inc/Soundengine/DSPAudio/wavetable.h').read_bytes())
 (p/'stm32f7xx_hal.h').write_text('#include <stdint.h>\n')
 (p/'Soundengine/config.h').write_text('#define INDTCM\n')
 (p/'test.c').write_text(code)
 subprocess.run([os.getenv('CC','cc'),'-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+tmp,str(p/'test.c'),str(root/'Core/Src/Soundengine/DSPAudio/wavetable.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
