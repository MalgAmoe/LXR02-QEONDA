#!/usr/bin/env python3
"""Compile actual helper, complete encoder/limiter and dtype table.
Page fixture uses actual MIX parameter rows; non-routing endpoints are stubs.
Not a full knob/ADC, MIDI parser, automation, or hardware integration test.
"""
from pathlib import Path
import os, re, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[1]
def read(p): return (ROOT / p).read_text()
def clean(s): return re.sub(r'/\*.*?\*/|//[^\n]*', '', s, flags=re.S)
def fn(s, name):
    s = clean(s)
    m = re.search(r'^static (?:void|uint8_t) '+name+r'\([^;\n]*\)\s*\{', s, re.M)
    assert m, name
    end = s.index('{', m.start()) + 1
    depth = 1
    while depth:
        depth += (s[end] == '{') - (s[end] == '}'); end += 1
    return s[m.start():end] + '\n'
menu = read('Core/Src/menu/menu.c')
# Real enums preserve parameter IDs, dtype and menu meanings.
enums = '\n'.join(re.findall(r'enum\s*\w*\s*\{[^}]*\}\s*;', clean(read('Core/Inc/Parameters.h')) + clean(read('Core/Inc/menu/menu.h'))))
table = re.search(r'const enum Datatypes PROGMEM parameter_dtypes\[NUM_PARAMS\] = \{.*?\};', menu, re.S)[0].replace('PROGMEM', '')
rows = re.findall(r'PAR_VOL[1-6],\s*PAR_PAN[1-6],\s*PAR_VOICE_DECIMATION[1-6],\s*PAR_\w+,\s*(PAR_AUDIO_OUT[1-6]),', clean(read('Core/Inc/menu/menuPages.h')))
assert rows == ['PAR_AUDIO_OUT1','PAR_AUDIO_OUT2','PAR_AUDIO_OUT3','PAR_AUDIO_OUT4','PAR_AUDIO_OUT5','PAR_AUDIO_OUT6','PAR_AUDIO_OUT6'], rows
c = '''#include <stdint.h>
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>
#define MASK_PARAMETER 7
#define MASK_PAGE 248
#define PAGE_SHIFT 3
#define PRESET_KIT_TIMER 0
#define DISABLE_CONV_WARNING
#define END_DISABLE_CONV_WARNING
#define pgm_read_word(p) (*(p))
#define pgm_read_byte(p) (*(p))
#define MIDI_CC 1
#define CC_2 2
#define CC_VELO_TARGET 3
#define CC_LFO_TARGET 4
''' + '\n'.join(re.findall(r'^#define MENU_.*', read('Core/Inc/menu/MenuText.h'), re.M)) + '\n' + enums + table + '''
uint8_t activeParameters[NUM_PARAMS];
static uint8_t menuIndex, menu_activePage, menu_TargetVoiceGapIndex;
static struct {uint16_t bot1[8];} menuPages[8][8];
static struct {uint8_t start,end;} modTargetVoiceOffsets[6];
static struct {uint16_t param;} modTargets[256];
static unsigned sent, status, dest, value;
static void frontPanel_sendData(unsigned a,unsigned b,unsigned c){sent++;status=a;dest=b;value=c;}
static void preset_touchTimer(int t){(void)t;}
static void menu_parseGlobalParam(unsigned p,unsigned v){assert(0);}
static uint8_t menu_setMasterCompressor(uint16_t p,int32_t v){assert(p<MASTER_COMP_THRESHOLD);return 0;}
static uint8_t menu_setPerformanceFilter(uint16_t p,int16_t v){assert(p!=PAR_PERF_HP && p!=PAR_PERF_LP);return 0;}
static uint8_t getNumModTargets(void){return 1;}
static uint8_t getModTargetIdxFromGapIdx(unsigned a,unsigned b){return 0;}
static uint8_t getModTargetGapIndex(unsigned a){return 0;}
static uint8_t getMaxEntriesForMenu(uint8_t m){
 assert(m==MENU_AUDIO_OUT || m==MENU_AUDIO_OUT_FX);
 return m==MENU_AUDIO_OUT?7:6;
}
'''
# Correct fixture layout for production &bot1 + activeParameter address arithmetic.
c = c.replace('uint16_t bot1[8];', 'uint16_t bot1,bot2,bot3,bot4,bot5,bot6,bot7,bot8;')
# Compile real label/count tables and menu-count function as well.
text = read('Core/Inc/menu/MenuText.h')
# getMaxEntriesForMenu references other menu tables; only these two counts
# are needed here, with its routing cases extracted unchanged.
labels = '\n'.join(re.search(r'const char '+n+r'\[\]\[7\]\s*=\s*\{.*?\};', text, re.S)[0] for n in ('outputNames', 'outputNamesFx'))
c = c[:c.index('static uint8_t getMaxEntriesForMenu')] + labels + '''
static uint8_t getMaxEntriesForMenu(uint8_t menuId){switch(menuId){
''' + re.search(r'case MENU_AUDIO_OUT:.*?(?=case MENU_FILTER:)', fn(menu, 'getMaxEntriesForMenu'), re.S)[0] + '''
default: assert(0); return 0;}}
'''
c += ''.join(fn(menu, n) for n in ('menu_stepAudioOutput','menu_encoderChangeParameter','limitPotValueFromOriginal','limitPotValue'))
c += 'static const uint16_t routes[7] = {' + ','.join(rows) + '};\n'
c += '''
static const uint8_t order[7]={0,6,1,2,3,4,5};
static uint8_t expected(unsigned start,int delta){
 int rank=0;
 for(int i=0;i<7;i++)if(order[i]==start)rank=i;
 rank+=delta; if(rank<0)rank=0;if(rank>6)rank=6;
 return order[rank];
}
int main(void){
 for(unsigned start=0;start<256;start++)for(int d=-128;d<=127;d++)
  assert(menu_stepAudioOutput(start,d)==expected(start,d));
 for(unsigned voice=0;voice<7;voice++){
  unsigned p=routes[voice]; menu_activePage=voice; menuIndex=(7<<3)|4;
  menuPages[voice][7].bot5=p;
  for(unsigned start=0;start<7;start++)for(int d=-128;d<=127;d++){
   unsigned want=expected(start,d);
   activeParameters[p]=start;
   assert(limitPotValue(d,p)==want);
   assert(activeParameters[p]==start); /* limiter must not disturb old-value bookkeeping */
   sent=0;menu_encoderChangeParameter(d);
   assert(activeParameters[p]==want && sent==1);
   assert(status==CC_2 && dest==p-128 && value==want);
  }
 }
 /* Repeated gestures and both saturating endpoints. */
 unsigned p=routes[0];menu_activePage=0;menuPages[0][7].bot5=p;
 activeParameters[p]=0;
 for(int i=0;i<20;i++){menu_encoderChangeParameter(1);assert(activeParameters[p]==order[i<6?i+1:6]);}
 for(int i=0;i<20;i++){menu_encoderChangeParameter(-1);assert(activeParameters[p]==order[i<6?5-i:0]);}
 assert(outputNames[7][0]=='F' && outputNames[2][2]=='2');
 /* Actual FX dtype entry, normal numeric traversal and saturation unchanged. */
 unsigned fx=0;
 for(unsigned p=0;p<NUM_PARAMS;p++)
  if(parameter_dtypes[p]==(DTYPE_MENU|(MENU_AUDIO_OUT_FX<<8)))fx=p;
 assert(fx && (fx<PAR_AUDIO_OUT1 || fx>PAR_AUDIO_OUT6));
 menu_activePage=0;menuPages[0][7].bot5=fx;
 for(unsigned start=0;start<6;start++)for(int d=-128;d<=127;d++){
  activeParameters[fx]=start;
  int want=(int)start+d;if(want<0)want=0;if(want>5)want=5;
  assert(limitPotValue(d,fx)==want);
  /* Existing encoder ignores negative overshoots, unlike the pot. */
  unsigned enc=(d<0 && -d>(int)start)?start:(unsigned)want;
  sent=0;menu_encoderChangeParameter(d);
  assert(activeParameters[fx]==enc && sent==1 && value==enc);
 }
 puts("OUT: exhaustive helper bytes/full int8 deltas; all six IDs/seven MIX rows; canonical encoder sends; FX unchanged");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src=Path(tmp)/'test.c'; exe=Path(tmp)/'test'; src.write_text(c)
    subprocess.run([os.environ.get('CC','cc'), '-std=c11', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', str(src), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
