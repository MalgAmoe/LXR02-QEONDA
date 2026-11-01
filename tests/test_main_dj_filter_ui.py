#!/usr/bin/env python3
"""Real menu bodies plus arm/disarm and Shift+Reload case; endpoints stubbed.
No physical button dispatch, startup execution, DSP, or hardware claim.
Standalone test: python3 tests/test_main_dj_filter_ui.py (no CMake edits).
"""
from pathlib import Path
import re, os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
# Reuse the established enum/dtype/endpoint fixture, not its routing assertions.
ns={'__file__':str(ROOT/'tests/test_output_order.py')}
fixture=(ROOT/'tests/test_output_order.py').read_text().split("c += ''.join(fn(menu, n)")[0]
exec(fixture,ns)
c=ns['c']; menu=ns['menu']; clean=ns['clean']
def fn(name, source=menu):
 s=clean(source); m=re.search(r'^(?:static )?(?:void|uint8_t) '+name+r'\([^;\n]*\)\s*\{',s,re.M); assert m,name
 p=s.index('{',m.start())+1;d=1
 while d:d+=(s[p]=='{')-(s[p]=='}');p+=1
 return s[m.start():p]+'\n'
c=c.replace('static uint8_t menu_setPerformanceFilter(uint16_t p,int16_t v){assert(p!=PAR_PERF_HP && p!=PAR_PERF_LP);return 0;}','')
c=c.replace('uint16_t bot1,','uint8_t top1,top2,top3,top4,top5,top6,top7,top8; uint16_t bot1,')
c+='''
#define NO_STEP_SELECTED -1
#define NUM_SUB_PAGES 8
static uint16_t buttonHandler_originalParameter[2];
static uint8_t buttonHandler_originalValue[2],buttonHandler_resetLock1,buttonHandler_resetLock2;
static uint8_t editModeActive,saveScreenPots[4];
static int8_t buttonHandler_armedAutomationStep=-1;
static unsigned targets,resets,capture; static uint8_t targetH,targetL,targetR;
static int velocityModulators[6];
static void MainDjFilter_setTargets(uint8_t h,uint8_t l,uint8_t r){targets++;targetH=h;targetL=l;targetR=r;}
static void MainDjFilter_reset(void){resets++;targetH=0;targetL=127;targetR=0;}
static void screensaver_touch(void){}
static void menu_repaintAll(void){}
static void menu_handleSaveScreenKnobValue(unsigned p,int v){assert(0);}
static void menu_processSpecialCaseValues(unsigned p){assert(0);}
static int8_t buttonHandler_getArmedAutomationStep(void){capture++;return buttonHandler_armedAutomationStep;}
static void seq_setActiveAutomationTrack(unsigned p){assert(0);}
static void modNode_setDestination(int *p,int v){assert(0);}
static uint8_t preset_getMorphValue(unsigned p,unsigned v){assert(0);return 0;}
'''
c+=''.join(fn(n) for n in ('menu_setPerformanceFilter','menu_resetPerformanceFilter','menu_stepAudioOutput','menu_encoderChangeParameter','limitPotValue','menu_parseKnobValue','menu_moveToMenuItem'))
# Real arm/restoration and Shift+Reload case; pattern/LED/load endpoints are stubs.
buttons=(ROOT/'Core/Src/buttonHandler.c').read_text()
c+=r"""
#define NUM_STEPS 64
#define NUM_TRACKS 7
#define ARM_AUTOMATION_STEP 80
#define ARM_AUTOMATION 0x40
#define DISARM_AUTOMATION 0
#define SEQ_CC 81
#define SEQ_CHANGE_PAT 82
#define SAVE_TYPE_KIT 0
static uint8_t seq_activePattern,menu_selectedPresetNr[1];
typedef struct {uint16_t param1Nr,param2Nr;uint8_t param1Val,param2Val;} Step;
typedef struct {Step seq_subStepPattern[1][7][64];} PatternSet;
static PatternSet pattern;
static PatternSet *get_seq_patternSet_p(void){return &pattern;}
/* Target decoding is an endpoint model, not sequencer coverage. */
static uint16_t seq_automationTarget(uint16_t p){return p;}
static uint8_t menu_getActiveVoice(void){return 0;}
static uint8_t menu_getActivePage(void){return menu_activePage;}
static unsigned reloads;
static void preset_loadDrumsetRam(unsigned p,unsigned a,unsigned b){reloads++;}
static void menu_repaint(void){}
static int led_idx2StepLed(int p){return p;}
static void led_setBlinkLed(int p,int on){}
"""
c+=fn('buttonHandler_armTimerActionStep',buttons)
c+=fn('buttonHandler_disarmTimerActionStep',buttons)
reload_case=re.search(r'case SEQ_RELOAD:\s*\{.*?(?=case SEQ_CONFIG:)',clean(buttons),re.S)[0]
c+='static void shiftReload(void){switch(0){case 0:'+reload_case.split(':',1)[1]+'}}\n'
# Use the actual performance page text/parameter rows.
pages=(ROOT/'Core/Inc/menu/menuPages.h').read_text()
row=re.search(r'TEXT_BPM,\s*TEXT_ROLL_SPEED,.*?PAR_SHUFFLE,\s*PAR_PERF_HP,\s*PAR_PERF_LP,\s*PAR_PERF_RESONANCE',pages,re.S)[0]
txt=re.findall(r'TEXT_\w+',row); pars=re.findall(r'PAR_\w+',row)
assert len(txt)==len(pars)==8
c+='static const uint8_t texts[8]={'+','.join(txt)+'};\nstatic const uint16_t pars[8]={'+','.join(pars)+'};\n'
c+='''
int main(void){
 _Static_assert(NUM_PARAMS==302 && END_OF_SOUND_PARAMETERS==247 && PAR_BEGINNING_OF_GLOBALS==272,"layout");
 _Static_assert(PAR_PERF_HP==262 && PAR_PERF_LP==265 && PAR_PERF_RESONANCE==263,"aliases");
 menu_activePage=PERF_PAGE;
 for(int i=0;i<8;i++){(&menuPages[PERF_PAGE][0].top1)[i]=texts[i];(&menuPages[PERF_PAGE][0].bot1)[i]=pars[i];}
 for(int i=0;i<8;i++){menuIndex=i;menu_moveToMenuItem(1);assert(menuIndex==(i<7?i+1:7));}
 for(int arm=0;arm<2;arm++)for(int slot=5;slot<=7;slot++)for(int start=0;start<128;start++)for(int delta=-128;delta<128;delta++){
  unsigned p=pars[slot],max=127;int want=start+delta;if(want<0)want=0;if(want>max)want=max;
  buttonHandler_armedAutomationStep=arm?0:NO_STEP_SELECTED;menuIndex=slot;activeParameters[p]=start;capture=sent=0;
  menu_encoderChangeParameter(delta);assert(activeParameters[p]==want && !sent && !capture);
  activeParameters[p]=start;menu_parseKnobValue(slot-4,delta);assert(activeParameters[p]==want && !sent && !capture);
  assert(targetH==activeParameters[PAR_PERF_HP] && targetL==activeParameters[PAR_PERF_LP] && targetR==activeParameters[PAR_PERF_RESONANCE]);
 }
 for(int third=0;third<3;third++)for(int swap=0;swap<2;swap++){
  buttonHandler_originalParameter[swap]=pars[5+third];buttonHandler_originalParameter[1-swap]=pars[5+(third+1)%3];
  buttonHandler_resetLock1=buttonHandler_resetLock2=1;menu_resetPerformanceFilter();
  assert(activeParameters[PAR_PERF_HP]==0 && activeParameters[PAR_PERF_LP]==127 && activeParameters[PAR_PERF_RESONANCE]==0);
  assert(!buttonHandler_originalParameter[0]&&!buttonHandler_originalParameter[1]&&!buttonHandler_resetLock1&&!buttonHandler_resetLock2);
 }
 buttonHandler_originalParameter[0]=PAR_COARSE1;buttonHandler_resetLock1=1;menu_resetPerformanceFilter();
 assert(buttonHandler_originalParameter[0]==PAR_COARSE1 && buttonHandler_resetLock1==1);
 /* Lifecycle: actual arm -> both real edit bodies -> actual reload case ->
    actual disarm. Neither transient edit may consume either restore slot. */
 for(int channel=0;channel<2;channel++)for(int slot=5;slot<=7;slot++){
  memset(&pattern,0,sizeof pattern);
  Step *step=&pattern.seq_subStepPattern[0][0][0];
  step->param1Nr=PAR_COARSE1;step->param1Val=22;
  step->param2Nr=PAR_NONE;
  buttonHandler_originalParameter[0]=buttonHandler_originalParameter[1]=0;
  buttonHandler_resetLock1=buttonHandler_resetLock2=0;
  activeParameters[PAR_COARSE1]=71;
  menu_resetPerformanceFilter();buttonHandler_armTimerActionStep(0);
  assert(buttonHandler_armedAutomationStep==0 && activeParameters[PAR_COARSE1]==22);
  menuIndex=slot;sent=capture=0;
  int change=slot==6?-9:9;
  if(channel)menu_encoderChangeParameter(change);else menu_parseKnobValue(slot-4,change);
  assert(!capture && !sent && activeParameters[pars[slot]]==(slot==6?118:9));
  assert(buttonHandler_originalParameter[0]==PAR_COARSE1 && buttonHandler_originalValue[0]==71);
  assert(buttonHandler_resetLock1 && !buttonHandler_resetLock2 && !buttonHandler_originalParameter[1]);
  shiftReload();
  assert(activeParameters[PAR_PERF_HP]==0 && activeParameters[PAR_PERF_LP]==127 && activeParameters[PAR_PERF_RESONANCE]==0);
  assert(buttonHandler_resetLock1 && buttonHandler_originalParameter[0]==PAR_COARSE1);
  sent=0;buttonHandler_disarmTimerActionStep();
  assert(buttonHandler_armedAutomationStep==NO_STEP_SELECTED);
  assert(activeParameters[PAR_COARSE1]==71 && sent==2);
  assert(status==MIDI_CC && dest==PAR_COARSE1 && value==71);
  assert(activeParameters[PAR_PERF_HP]==0 && activeParameters[PAR_PERF_LP]==127 && activeParameters[PAR_PERF_RESONANCE]==0);
  assert(!buttonHandler_resetLock1 && !buttonHandler_resetLock2);
  assert(!buttonHandler_originalParameter[0] && !buttonHandler_originalParameter[1]);
 }
 /* Defensive reset cancellation: stale transient slots cannot restore on release. */
 for(int third=0;third<3;third++)for(int swap=0;swap<2;swap++){
  buttonHandler_armedAutomationStep=0;
  buttonHandler_originalParameter[swap]=pars[5+third];
  buttonHandler_originalParameter[1-swap]=pars[5+(third+1)%3];
  buttonHandler_originalValue[0]=11;buttonHandler_originalValue[1]=99;
  buttonHandler_resetLock1=buttonHandler_resetLock2=1;
  shiftReload();sent=0;buttonHandler_disarmTimerActionStep();
  assert(sent==1); /* disarm message only; no parameter restoration */
  assert(activeParameters[PAR_PERF_HP]==0 && activeParameters[PAR_PERF_LP]==127 && activeParameters[PAR_PERF_RESONANCE]==0);
 }
 assert(reloads==12);
 for(int slot=5;slot<=7;slot++)assert(parameter_dtypes[pars[slot]]==DTYPE_0B127);
 puts("DJ UI: full knob/encoder bodies, accelerated bounds, armed capture isolation, navigation, arm/edit/ShiftReload/release lifecycle, reset cancellation, unsigned dtypes/layout passed");
}
'''
c=c.replace('#include <stdio.h>','#include <stdio.h>\n#include <string.h>')
# PERF_PAGE exceeds the routing fixture's eight pages.
c=c.replace('menuPages[8][8]','menuPages[64][8]')
assert 'menu_init();\n  menu_resetPerformanceFilter();' in (ROOT/'Core/Src/main.c').read_text()
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(c)
 subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O1','-g','-fsanitize=undefined,address',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)

# Historical next-pattern references must remain inactive when reusing slot 263.
for path in (ROOT/'Core').rglob('*'):
 if path.suffix not in ('.c','.h'): continue
 active=clean(path.read_text())
 refs=re.findall(r'\bPAR_PATTERN_NEXT\b',active)
 if path.name=='Parameters.h': assert len(refs)==2, path
 else: assert not refs, path
