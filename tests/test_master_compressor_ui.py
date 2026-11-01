#!/usr/bin/env python3
"""Production menu edit/navigation/format bodies and actual PERF records; endpoint stubs.
No hardware, ADC/button dispatch, audio, or persistence claim.
"""
from pathlib import Path
import re, os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
ns={'__file__':str(ROOT/'tests/test_output_order.py')}
exec((ROOT/'tests/test_output_order.py').read_text().split("c += ''.join(fn(menu, n)")[0],ns)
c,menu,clean=ns['c'],ns['menu'],ns['clean']
def fn(name):
 s=clean(menu);m=re.search(r'^(?:static )?(?:void|uint8_t) '+name+r'\([^;\n]*\)\s*\{',s,re.M);assert m,name
 p=s.index('{',m.start())+1;d=1
 while d:d+=(s[p]=='{')-(s[p]=='}');p+=1
 return s[m.start():p]+'\n'
c=re.sub(r'static uint8_t menu_setMasterCompressor[^\n]*\n','',c)
c=c.replace('static void preset_touchTimer(int t){(void)t;}','static unsigned dirty; static void preset_touchTimer(int t){dirty++;}')
c=c.replace('uint16_t bot1,','uint8_t top1,top2,top3,top4,top5,top6,top7,top8; uint16_t bot1,').replace('menuPages[8][8]','menuPages[64][8]')
c+='''
#include <math.h>
#include <string.h>
#define NUM_SUB_PAGES 8
#define NO_STEP_SELECTED -1
static uint8_t editModeActive,saveScreenPots[4];
static uint16_t buttonHandler_originalParameter[2];
static uint8_t buttonHandler_bulkOriginal[2],buttonHandler_originalValue[2],buttonHandler_resetLock1,buttonHandler_resetLock2;
static unsigned updates,capture;static uint16_t lastParameter;static uint8_t lastValue;
static void MainCompressor_setParameter(uint16_t p,uint8_t v){updates++;lastParameter=p;lastValue=v;}
static void screensaver_touch(void){}
static void menu_repaintAll(void){}
static void menu_handleSaveScreenKnobValue(unsigned p,int v){assert(0);}
static void menu_processSpecialCaseValues(unsigned p){assert(0);}
static int8_t buttonHandler_getArmedAutomationStep(void){capture++;return 0;}
static void seq_setActiveAutomationTrack(unsigned p){assert(0);}
static int velocityModulators[6];
static void modNode_setDestination(int *p,int v){assert(0);}
static uint8_t preset_getMorphValue(unsigned p,unsigned v){assert(0);return 0;}
static void numtostrpu(char *s,unsigned n,char pad){s[0]=n>=100?'0'+n/100:pad;s[1]=n>=10?'0'+n/10%10:pad;s[2]='0'+n%10;}
'''
text=(ROOT/'Core/Inc/menu/MenuText.h').read_text()
for name,size in [('shortNames',4),('longNames',16)]:
 table=re.search(r'const char '+name+r'\[\]\['+str(size)+r'\]\s*=\s*\{.*?\};',text,re.S)[0]
 c+=table+'\n'
names=re.search(r'const Name valueNames\[NUM_NAMES\]\s*=\s*\{.*?\};',menu,re.S)[0]
c+='typedef struct {uint8_t shortName,category,longName;} Name;\n'+names+'\n'
c+='static uint8_t limitPotValueFromOriginal(int8_t diff,uint16_t paramNr,uint8_t originalValue);\nstatic uint8_t limitPotValue(int8_t diff, uint16_t paramNr);\nstatic uint8_t buttonHandler_getShift(void){return 0;}\nstatic void frontParser_dispatchNonRecording(uint8_t s,uint8_t a,uint8_t b){assert(0); }\n'
c+=''.join(fn(n) for n in ('menu_getHeldOriginal','menu_dispatchParameter','menu_applyKnobParameter','menu_restoreHeldParameter','menu_dispatchHeldOriginal','menu_updateHeldOriginal','menu_changeAllKnob','menu_formatMasterCompressor','menu_setMasterCompressor','menu_stepAudioOutput','menu_encoderChangeParameter','limitPotValueFromOriginal','limitPotValue','menu_parseKnobValue','has2ndPage','checkScrollSign','menu_switchSubPage','menu_moveToMenuItem'))
pages=(ROOT/'Core/Inc/menu/menuPages.h').read_text();a=pages.index('//Page 10');b=pages.index('//Page 11',a)
records=re.findall(r'\{\s*(TEXT_.*?PAR_NONE|TEXT_BPM.*?)\s*\}',clean(pages[a:b]),re.S)
# Parse actual first two records, all 16 fields per record.
fields=re.findall(r'\b(?:TEXT_\w+|PAR_\w+|MASTER_COMP_\w+)\b',clean(pages[a:b]))
assert len(fields)==128,len(fields)
c+='static const typeof(menuPages[0][0]) perf[8]={'+','.join('{'+','.join(fields[i:i+16])+'}' for i in range(0,128,16))+'};\n'
case=re.search(r'case PERF_PAGE:.*?(?=case MENU_LAST_STEP_PAGE:)',clean(menu),re.S)[0]
c+='static uint8_t menu_getSubPage(void){return menuIndex>>3;}\n'
c+='static void selectPerf(void){unsigned pageNr=PERF_PAGE;switch(pageNr){'+case+'menu_activePage=pageNr;editModeActive=0;break;}}\n'
c+='''
int main(void){
 _Static_assert(MASTER_COMP_THRESHOLD==302 && MASTER_COMP_RATIO==303 && MASTER_COMP_ATTACK==304 && MASTER_COMP_RELEASE==305 && NUM_PARAMS==306,"append only");
 _Static_assert(PAR_PATTERN_MODE==301 && END_OF_SOUND_PARAMETERS==247,"old boundaries");
 memcpy(menuPages[PERF_PAGE],perf,sizeof perf);menu_activePage=PERF_PAGE;
 for(int page=0;page<10;page++)for(int pos=0;pos<64;pos++){
  menu_activePage=page;menuIndex=pos;selectPerf();assert(menu_activePage==PERF_PAGE&&menuIndex==0);
 }
 menu_activePage=PERF_PAGE;
 assert(checkScrollSign(0,0)=='>' && checkScrollSign(0,4)=='*' && checkScrollSign(1,0)=='<');
 /* Actual PERF button navigation body: A -> B -> C -> A, any focus. */
 for(int i=0;i<12;i++){
  menuIndex=i;editModeActive=1;selectPerf();
  assert(menuIndex==(i<4?4:i<8?8:0));assert(!editModeActive);
 }
 menuIndex=0;
 for(int i=1;i<=11;i++){menu_moveToMenuItem(127);assert(menuIndex==i);}
 menu_moveToMenuItem(1);assert(menuIndex==11);
 for(int i=10;i>=0;i--){menu_moveToMenuItem(-128);assert(menuIndex==i);}
 menu_moveToMenuItem(-1);assert(menuIndex==0);
 assert(has2ndPage(0)&&!has2ndPage(1));
 /* Enter from another menu using real switch body, then focus all C controls. */
 menuIndex=7;menu_switchSubPage(0,0);assert(menuIndex==4);
 menu_switchSubPage(0,1);assert(menuIndex==8);
 const unsigned maxima[]={48,19,30,34};
 for(int slot=0;slot<4;slot++){
  unsigned p=MASTER_COMP_THRESHOLD+slot;
  assert((&menuPages[PERF_PAGE][1].bot1)[slot]==p);
  assert(parameter_dtypes[p]==DTYPE_0B127);
  for(int start=0;start<=maxima[slot];start++)for(int delta=-128;delta<=127;delta++){
   int want=start+delta;if(want<0)want=0;if(want>maxima[slot])want=maxima[slot];
   for(int viaKnob=0;viaKnob<2;viaKnob++){
    /* Knobs address screen, not selected control. */
    menuIndex=8+(viaKnob?(slot+1)%4:slot);activeParameters[p]=start;
    updates=sent=dirty=capture=0;
    if(viaKnob)assert(menu_parseKnobValue(slot,delta)==1);else menu_encoderChangeParameter(delta);
    assert(activeParameters[p]==want&&updates==1&&lastParameter==p&&lastValue==want);
    assert(!sent&&!dirty&&!capture);
   }
  }
  for(int delta=-32768;delta<=32767;delta+=257){
   menuIndex=8;activeParameters[p]=0;menu_parseKnobValue(slot,delta);
   assert(activeParameters[p]==(delta<0?0:maxima[slot]));
  }
 }
 const unsigned texts[]={TEXT_MASTER_THRESHOLD,TEXT_MASTER_RATIO,TEXT_MASTER_ATTACK,TEXT_MASTER_RELEASE};
 const char *labels[]={"thr","rat","atk","rel"};
 const char *units[]={"Thr dB","Ratio :1","Atk ms","Rel ms"};
 for(int i=0;i<4;i++){
  assert((&perf[1].top1)[i]==texts[i]);
  assert(!memcmp(shortNames[valueNames[texts[i]].shortName],labels[i],3));
  assert(!strcmp(longNames[valueNames[texts[i]].longName],units[i]));
 }
 char text[3];
 assert(menu_formatMasterCompressor(MASTER_COMP_THRESHOLD,0,text)&&!memcmp(text,"-48",3));
 menu_formatMasterCompressor(MASTER_COMP_THRESHOLD,30,text);assert(!memcmp(text,"-18",3));
 menu_formatMasterCompressor(MASTER_COMP_THRESHOLD,36,text);assert(!memcmp(text,"-12",3));
 menu_formatMasterCompressor(MASTER_COMP_THRESHOLD,48,text);assert(!memcmp(text,"  0",3));
 menu_formatMasterCompressor(MASTER_COMP_RATIO,0,text);assert(!memcmp(text,"  1",3));
 menu_formatMasterCompressor(MASTER_COMP_RATIO,19,text);assert(!memcmp(text," 20",3));
 menu_formatMasterCompressor(MASTER_COMP_ATTACK,0,text);assert(!memcmp(text,"0.1",3));
 menu_formatMasterCompressor(MASTER_COMP_ATTACK,17,text);assert(!memcmp(text,"5.0",3));
 menu_formatMasterCompressor(MASTER_COMP_ATTACK,30,text);assert(!memcmp(text,"100",3));
 menu_formatMasterCompressor(MASTER_COMP_RELEASE,0,text);assert(!memcmp(text," 10",3));
 menu_formatMasterCompressor(MASTER_COMP_RELEASE,20,text);assert(!memcmp(text,"100",3));
 menu_formatMasterCompressor(MASTER_COMP_RELEASE,34,text);assert(!memcmp(text,"500",3));
 for(int slot=2;slot<4;slot++)for(int v=0;v<=maxima[slot];v++){
  menu_formatMasterCompressor(MASTER_COMP_THRESHOLD+slot,v,text);
  float ms=slot==2?0.1f*powf(1000.f,v/30.f):10.f*powf(50.f,v/34.f);
  char buf[4];memcpy(buf,text,3);buf[3]=0;
  assert(fabsf(strtof(buf,0)-ms)<(ms<9.95f?.051f:.501f));
 }
 puts("Master compressor UI: real PERF records, switch/focus navigation, full encoder/knob bodies, accelerated saturation, capture/MIDI/kit-dirty exclusion and physical formatting passed");
}
'''
# NRPN must retain its legacy upper bound, not grow with NUM_PARAMS.
front=(ROOT/'Core/Src/frontPanelParser.c').read_text()
assert 'if(paramNr < MASTER_COMP_THRESHOLD)' in front
# Both actual rendering branches invoke the physical formatter.
assert 'menu_formatMasterCompressor(parNr, curParmVal, &editDisplayBuffer[1][13])' in menu
assert 'menu_formatMasterCompressor(parNr, curParmVal, valueAsText)' in menu
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(c)
 subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-O1','-g','-fsanitize=undefined,address',str(p/'test.c'),'-lm','-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
