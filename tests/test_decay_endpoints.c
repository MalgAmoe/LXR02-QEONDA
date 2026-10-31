/* Actual Decay.c is compiled separately, including a fast-math variant.
 * This observer deliberately uses strict floating point for finite checks. */
#include "Soundengine/DSPAudio/Decay.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
static void check(DecayEg *e, unsigned slope) {
 float out=DecayEg_calc(e);
 assert(isfinite(out));
 if(!(slope==0 && e->value==1.f)) {
  double x=e->value,s=e->slope;
  double expected=(1+s)*x/(1+s*fabs(x));
  assert(fabs(out-expected)<1e-4*(1+fabs(expected)));
 }
}
int main(void) {
 unsigned long count=0;
 for(unsigned s=0;s<128;s++)for(unsigned d=0;d<128;d++) {
  DecayEg e;DecayEg_init(&e);DecayEg_setSlope(&e,s);DecayEg_setDecay(&e,d);
  assert(isfinite(e.slope)&&isfinite(e.decay));
  if(s<127) {
   float a=((s/127.f)-0.5f)*2;
   float expected=2*a/(1-a);
   assert(fabsf(e.slope-expected)<1e-4f*(1+fabsf(expected)));
  } else assert(e.slope>3900&&e.slope<4100);
  check(&e,s);assert(e.value==0);
  DecayEg_trigger(&e);
  if(d==127) {
   assert(e.decay==0);
   for(unsigned i=0;i<8;i++){float out=DecayEg_calc(&e);assert(isfinite(out)&&fabsf(out-1)<1e-6f&&e.value==1);}
  } else {
   unsigned ticks=0;
   do {check(&e,s);assert(++ticks<200000);count++;} while(e.value>0);
   check(&e,s);assert(e.value==0);
  }
 }
 printf("All 16384 slope/decay pairs: idle, trigger, finite decay, expiration and infinite hold pass (%lu decay ticks).\n",count);
}
