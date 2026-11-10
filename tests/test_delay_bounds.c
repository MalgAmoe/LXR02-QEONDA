#include "Soundengine/DSPAudio/FX/Delay.h"
#include <assert.h>
#include <string.h>
float fxHistoryFast[FX_FLOAT_FAST_SAMPLES];
float fxHistoryRam[FX_BUFFER_SIZE+1-FX_FLOAT_FAST_SAMPLES];
int main(void) {
 Delay d={0}; float input[128]={0};float left[128]={0},right[128]={0};
 Delay_init(&d);
 /* Normal mode can legally leave all three pointers above the ping-pong half. */
 d.oldRead=d.newRead=d.write=FX_BUFFER_SIZE;
 d.interpValue=0.5f;d.interpStep=0.01f;
 Delay_processPingPong(&d,input,left,right,64,2,0.5f);
 assert(d.oldRead <= (FX_BUFFER_SIZE>>1));
 assert(d.newRead <= (FX_BUFFER_SIZE>>1));
 assert(d.write <= (FX_BUFFER_SIZE>>1));
 /* Normal-sized starting pointers remain valid through subsequent blocks. */
 for(int i=0;i<20;i++) Delay_processPingPong(&d,input,left,right,64,2,0.5f);
 return 0;
}
