#!/usr/bin/env python3
"""Compile production non-host PRIMASK path with a pending TIM2 model."""
from pathlib import Path
import os, subprocess, tempfile
root=Path(__file__).resolve().parents[1]
source=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "Parameters.h"
#undef __disable_irq
static uint32_t mask;
static unsigned disables, deliveries;
static uint8_t expected[4];
static uint32_t __get_PRIMASK(void){return mask;}
static void __disable_irq(void){mask=1;disables++;}
static void deliver(void);
static void __set_PRIMASK(uint32_t p){mask=p;if(!mask)deliver();}
#include "Soundengine/DSPAudio/MainCompressor.c"
static void deliver(void){
 deliveries++;
 for(unsigned i=0;i<4;i++)assert(compTargets[i]==expected[i]);
 /* TIM2's actual block snapshot/coefficient path, not a substitute reader. */
 MainCompressor_beginBlock();
}
int main(void){
 const uint8_t a[4]={12,3,9,8}, b[4]={48,19,30,34}, bad[4]={255,255,255,255};
 /* Avoid recursively delivering a pending IRQ while returning from its snapshot. */
 mask=1;memcpy(expected,a,4);MainCompressor_setControls(a);
 assert(mask==1&&deliveries==0);for(unsigned i=0;i<4;i++)assert(compTargets[i]==a[i]);
 mask=0;memcpy(expected,b,4);MainCompressor_setControls(b);
 assert(mask==0&&deliveries==1);
 mask=1;MainCompressor_setControls(bad);assert(mask==1);
 for(unsigned i=0;i<4;i++)assert(compTargets[i]==b[i]);
 assert(disables>=3);
}
'''
# An interrupt runs masked in this deterministic model; restore the foreground
# mask afterwards. This prevents nested self-delivery on beginBlock restoration.
source=source.replace('MainCompressor_beginBlock();','mask=1;MainCompressor_beginBlock();mask=0;')
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);(p/'stm32f7xx.h').write_text('/* Intrinsics supplied by test. */\n')
    (p/'test.c').write_text(source)
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-I'+str(p),'-I'+str(root/'tests/shim'),'-I'+str(root/'Core/Inc'),'-I'+str(root/'Core/Src'),str(p/'test.c'),'-lm','-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
