#!/usr/bin/env python3
"""Production rotation and encoder bodies; IRQ/UI endpoints are host seams."""
from pathlib import Path
import os, re, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
def fn(path,name):
 s=(ROOT/path).read_text(); s=re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
 m=re.search(r'^(?:static )?void '+name+r'\([^;]*?\)\s*\{',s,re.M); assert m
 end=s.index('{',m.start())+1; depth=1
 while depth:
  depth+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[m.start():end]
c=r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include "Preset/SeqStep.h"
#undef __disable_irq
#define NUM_TRACKS 7
#define NUM_PATTERN 2
#define NUM_STEPS 64
typedef struct {Step seq_subStepPattern[2][7][64];StepTiming seq_stepTiming[2][7][64];uint16_t seq_mainSteps[4][2][7];uint8_t length[2][7];} PatternSet;
static PatternSet seq_patternSet, original, expected;
static uint8_t frontParser_shownPattern,seq_activePattern;
static int8_t seq_stepToSkip[7];
static unsigned primask,locks;
static unsigned __get_PRIMASK(void){return primask;}
static void __disable_irq(void){primask=1;locks++;}
static void __set_PRIMASK(unsigned m){primask=m;}
'''
c+=fn('Core/Src/Soundengine/Sequencer/sequencer.c','seq_rotateTrack')
c+=r'''
enum {VOICE7_PAGE=6,LOAD_PAGE,SAVE_PAGE,SONG_MODE_PAGE,MENU_LAST_STEP_PAGE};
enum {MODE_NONE,MODE_CLEAR,MODE_COPY};
enum {SELECT_MODE_VOICE,SELECT_MODE_LAST_STEP_TRACK,SELECT_MODE_LAST_STEP_ALL};
#define CLEAR_AUTOMATION2 2
static uint8_t lastEncoderButton,copyClear_Mode,screensaver_Active,editModeActive,menu_activePage,menu_activeVoice,mode,shift;
static unsigned edits,moves,clicks,leds;
static void copyClear_executeClear(void){clicks++;}
static void menu_repaintAll(void){}
static void menu_repaint(void){}
static void screensaver_touch(void){}
static void menu_handleLoadSaveMenu(int8_t i,uint8_t b){(void)i;(void)b;}
static void menu_handleSongMenu(int8_t i,uint8_t b){(void)i;(void)b;}
static uint8_t buttonHandler_getMode(void){return mode;}
static uint8_t buttonHandler_getShift(void){return shift;}
static uint8_t seq_getTrackLength(uint8_t t){return seq_patternSet.length[0][t];}
static void seq_setTrackLength(uint8_t t,uint8_t l){(void)t;(void)l;}
static uint8_t copyClear_isClearModeActive(void){return copyClear_Mode==MODE_CLEAR;}
static uint8_t copyClear_getClearTarget(void){return 0;}
static void copyClear_setClearTarget(uint8_t t){(void)t;}
static void menu_encoderChangeParameter(int8_t i){(void)i;edits++;}
static void menu_moveToMenuItem(int8_t i){(void)i;moves++;}
static void led_updateSeqLeds(void){leds++;}
'''
c+=fn('Core/Src/menu/menu.c','menu_parseEncoder')
c+=r'''
int main(void){
 for(int len=1;len<=64;len++)for(int inc=-128;inc<=127;inc++){
  unsigned char *p=(void*)&original;for(unsigned i=0;i<sizeof original;i++)p[i]=(i*37+i/13)&255;
  original.length[1][3]=len;seq_patternSet=original;expected=original;
  frontParser_shownPattern=1;seq_activePattern=1;seq_stepToSkip[3]=len-1;
  int right=(inc%len+len)%len;
  for(int s=0;s<len;s++){
   int d=(s+right)%len;
   expected.seq_subStepPattern[1][3][d]=original.seq_subStepPattern[1][3][s];
   expected.seq_stepTiming[1][3][d]=original.seq_stepTiming[1][3][s];
   int hit=(original.seq_mainSteps[s/16][1][3]>>(s%16))&1;
   expected.seq_mainSteps[d/16][1][3]=(expected.seq_mainSteps[d/16][1][3]&~(1u<<(d%16)))|(hit<<(d%16));
  }
  primask=inc&1;seq_rotateTrack(3,inc);assert(primask==(unsigned)(inc&1));
  assert(!memcmp(&expected,&seq_patternSet,sizeof expected));assert(seq_stepToSkip[3]==len-1);
  if(inc!=-128){seq_rotateTrack(3,-inc);assert(!memcmp(&original,&seq_patternSet,sizeof original));}
 }
 for(int bad=0;bad<2;bad++){
  seq_patternSet=original;seq_patternSet.length[1][3]=bad?65:0;expected=seq_patternSet;
  frontParser_shownPattern=1;seq_rotateTrack(3,1);assert(!memcmp(&expected,&seq_patternSet,sizeof expected));
 }
 seq_patternSet=original;expected=original;frontParser_shownPattern=2;seq_rotateTrack(3,1);
 frontParser_shownPattern=1;seq_rotateTrack(7,1);seq_rotateTrack(3,0);assert(!memcmp(&expected,&seq_patternSet,sizeof expected));
 seq_patternSet=original;frontParser_shownPattern=0;seq_activePattern=1;seq_stepToSkip[3]=5;seq_patternSet.length[0][3]=16;
 seq_rotateTrack(3,1);assert(seq_stepToSkip[3]==5);
 for(int page=0;page<=10;page++)for(int m=0;m<12;m++)for(int cc=0;cc<3;cc++)for(int sh=0;sh<2;sh++)for(int edit=0;edit<2;edit++){
  menu_activePage=page;mode=m;copyClear_Mode=cc;shift=sh;editModeActive=edit;menu_activeVoice=3;
  unsigned before=leds;menu_parseEncoder(1,0);
  assert(leds-before==(unsigned)(page<=6&&m==0&&cc==0&&sh));
 }
 menu_activePage=0;mode=0;copyClear_Mode=0;shift=1;editModeActive=0;unsigned before=leds;
 menu_parseEncoder(0,1);assert(editModeActive==1&&leds==before);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(c)
 subprocess.run([os.environ.get('CC','clang'),'-std=c11','-fsanitize=address,undefined','-I'+str(ROOT/'tests/shim'),'-I'+str(ROOT/'Core/Inc'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('Track rotation and encoder gates passed')
