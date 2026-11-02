#!/usr/bin/env python3
"""Actual LED overlay/chase bodies, fake register bytes and owner endpoint."""
from pathlib import Path
import os, re, subprocess, tempfile
s=(Path(__file__).resolve().parents[1]/'Core/Src/ledHandler.c').read_text()
def fn(name):
    clean=re.sub(r'/\*.*?\*/|//[^\n]*',lambda m:' '*len(m[0]),s,flags=re.S)
    m=re.search(r'^(?:static )?(?:void|uint8_t) '+name+r'\([^;\n]*\)\s*\{',clean,re.M);assert m,name
    i=clean.index('{',m.start())+1;d=1
    while d:d+=(clean[i]=='{')-(clean[i]=='}');i+=1
    return s[m.start():i]+'\n'
c=r'''
#include <stdint.h>
#include <assert.h>
#define SELECT_MODE_PERF 4
#define NUM_OF_PULSABLE_LEDS 8
static uint8_t owner=0xff,mode=SELECT_MODE_PERF;
static uint8_t dout_outputData[8],led_originalLedState[8],led_currentStepLed;
static uint8_t led_stepChaseActive;
static uint8_t led_pulsingLeds,led_pulseLedNumber[8];
static uint32_t systick_ticks,led_pulseEndTime[8];
static uint8_t seq_slipOwner(void){return owner;}
static uint8_t buttonHandler_getMode(void){return mode;}
static uint8_t led_idx2StepLed(uint8_t x){return x;}
static void led_reset(uint8_t);
'''
for n in ('led_setValueTemp','led_isSlipOwner','led_toggleTemp','led_setActive_step','led_clearActive_step','led_reset','led_tickHandler'):c+=fn(n)
c+=r'''
static unsigned on(unsigned pad){return !!(dout_outputData[pad/8]&(1u<<(pad%8)));}
int main(void){
 led_setActive_step(8);assert(on(8));
 owner=8;led_tickHandler();assert(on(8));
 led_setActive_step(9);assert(on(8)&&on(9));
 led_setActive_step(10);assert(on(8)&&!on(9)&&on(10));
 owner=11;led_tickHandler();assert(!on(8)&&on(11)&&on(10));
 led_setActive_step(11);assert(on(11)&&!on(10));
 owner=0xff;led_tickHandler();assert(on(11)); /* chase survives release */
 led_setActive_step(12);assert(!on(11)&&on(12));
 owner=9;led_tickHandler();assert(on(9)&&on(12));
 mode=0;led_tickHandler();assert(!on(9)&&on(12));
 mode=SELECT_MODE_PERF;owner=12;led_tickHandler();led_clearActive_step();
 owner=0xff;led_tickHandler();assert(!on(12));
 return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'test.c').write_text(c)
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
print('Slip LED owner overlay + ordinary real chase: PASS')
