#!/usr/bin/env python3
"""Real panel/menu/LED event bodies with bounded engine/storage/LCD seams.
Not physical-button, SD, audio scheduling or autoload timing certification.
"""
from pathlib import Path
import os, re, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[1]
def read(p): return (ROOT / p).read_text()
def clean(s): return re.sub(r'/\*.*?\*/|//[^\n]*', '', s, flags=re.S)
def fn(s, name):
    s = clean(s)
    m = re.search(r'^(?:static\s+)?(?:void|uint8_t|int8_t)\s+' + name + r'\([^;]*?\)\s*\{', s, re.M)
    assert m, name
    end = s.index('{', m.start()) + 1
    depth = 1
    while depth:
        depth += (s[end] == '{') - (s[end] == '}'); end += 1
    return s[m.start():end] + '\n'
panel, menu, led = (read(p) for p in ('Core/Src/buttonHandler.c', 'Core/Src/menu/menu.c', 'Core/Src/ledHandler.c'))
c = '''#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "Parameters.h"
#include "frontPanelParser_ui.h"
#define NUM_TRACKS 7
#define NUM_BARS 4
#define NUM_STEPS 64
#define MASK_PARAMETER 7
#define MASK_PAGE 248
#define PAGE_SHIFT 3
#define NUM_SUB_PAGES 8
#define NO_STEP_SELECTED -1
#define TIMER_ACTION_OCCURED -2
#define BUTTON_TIMEOUT 2000
#define ARM_AUTOMATION 0x40
#define DISARM_AUTOMATION 0
#define PRESET_PAT_TIMER 1
#define PRESET_KIT_TIMER 0
#define DISABLE_CONV_WARNING
#define END_DISABLE_CONV_WARNING
#define SKIP_NEXT_KIT_AUTOLOAD 2
#define USE_INTERRUPT_ONLY_DURING_SAVE_PROJ 0
#define FR_OK 0
typedef int FRESULT;
'''
for p in ('Core/Inc/buttonHandler.h','Core/Inc/menu/menu.h','Core/Inc/ledHandler.h','Core/Inc/menu/copyClearTools.h','Core/Inc/Preset/PresetManager.h'):
    c += '\n'.join(re.findall(r'enum\s*\w*\s*\{[^}]*\}\s*;', clean(read(p)))) + '\n'
c += re.search(r'enum saveStateEnum.*?};', clean(menu), re.S).group() + '\n'
c += re.search(r'typedef struct PageStruct.*?}Page;', clean(read('Core/Inc/menu/menu.h')), re.S).group() + '\n'
pages = clean(read('Core/Inc/menu/menuPages.h'))
c += pages[pages.index('const Page menuPages'):pages.rindex('};') + 2] + '\n'
c += r'''
#define pgm_read_byte(p) (*(p))
/* Real Page layout and menuPages metadata above, including PERF A/B/C. */
static uint8_t menuIndex, editModeActive, menu_activePage, menu_activeVoice, menu_activeBar;
static uint8_t menu_playedPattern,menu_shownPattern,menu_activePatternBank,menu_muteModeActive;
static uint8_t performanceSlipButtons;

static uint8_t menu_selectedPresetNr[6], copyClear_Mode, preset_fileCleanupWarning;
static uint8_t activeParameters[NUM_PARAMS],seq_activePattern,performanceBreakButtonHeld;
static uint8_t lastActiveSubPage, buttonHandler_mutedVoices,buttonHandler_selectedStep;
static int8_t buttonHandler_buttonTimerStepNr=-1;
static uint16_t heldSeqButtons, consumedSeqReleases;
static uint32_t systick_ticks=123,sucessTimer;
static struct {unsigned selectButtonMode:4; unsigned seqRunning:1,seqRecording:1,seqErasing:1;} buttonHandler_stateMemory;
static struct {uint8_t fxType;} fxBus;
static struct {uint8_t category,state,nameBuffer;} menu_saveOptions;
typedef struct {Step seq_subStepPattern[64][7][64];uint16_t seq_mainSteps[4][64][7];uint8_t shuffle[64],length[64][7],used[64],kitNr[64];} PatternSet;
static PatternSet seq_patternSet;
static int8_t buttonHandler_armedAutomationStep=NO_STEP_SELECTED;
static uint16_t buttonHandler_originalParameter[2];
static uint8_t buttonHandler_originalValue[2],buttonHandler_bulkOriginal[2],buttonHandler_resetLock1,buttonHandler_resetLock2;
static uint32_t buttonHandler_buttonTimer;
static PatternSet *get_seq_patternSet_p(void){return &seq_patternSet;}
static uint16_t seq_automationTarget(uint8_t p){return p ? p-1 : PAR_NONE;}
static unsigned stepWrites,loads,saves,saveRam,errors,warnings,touches,changes,rolls,breakHeld,enteredStep,repaints;
static uint8_t shift,load,save,copy,pending,leds[64],blinks[64],chase,lastMode;
static unsigned chaseCalls, lengthWrites;
static uint8_t selectedSection;
static unsigned panelMessages;
#define NUM_OF_BLINKABLE_LEDS 4
static uint8_t led_blinkPrescaler,led_blinkToggleState,led_blinkingLeds,led_blinkLedNumber[4];
static uint8_t frontParser_activeTrack;
static int8_t seq_stepIndex[7];
static uint8_t seq_recordActive,seq_activeAutomTrack;
static int seq_armedArmedAutomationStep=-1,seq_armedArmedAutomationTrack=-1;
static uint8_t seq_patternIsUsed(uint8_t p);
static uint8_t seq_intIsMainStepActive(uint8_t v,uint8_t s,uint8_t p){(void)v;(void)s;(void)p;return 1;}
static int saveResult;
static uint8_t buttonHandler_getShift(void){return shift;}
static uint8_t buttonHandler_getLoad(void){return load;}
static uint8_t buttonHandler_getSave(void){return save;}
static uint8_t buttonHandler_getCopy(void){return copy;}
static uint8_t buttonHandler_getMode(void){return buttonHandler_stateMemory.selectButtonMode;}
static uint8_t menu_getActiveVoice(void){return menu_activeVoice;}
static void menu_setActiveVoice(uint8_t v){menu_activeVoice=v;}
static uint8_t menu_getActivePage(void){return menu_activePage;}
static uint8_t menu_getViewedPattern(void){return menu_shownPattern;}
static void menu_setShownPattern(uint8_t p){menu_shownPattern=p;}
static uint8_t led_idx2StepLed(uint8_t p);
static void led_setValue(uint8_t v,uint8_t l){assert(l<64);leds[l]=v;}
static void led_setBlinkLed(uint8_t l,uint8_t v){
 assert(l<64);blinks[l]=v;
 for(int i=0;i<4;i++)if((v && !(led_blinkingLeds&(1<<i))) || (!v && led_blinkLedNumber[i]==l)){
  led_blinkLedNumber[i]=l;
  if(v)led_blinkingLeds|=1<<i;else led_blinkingLeds&=~(1<<i);
  break;
 }
}
static void led_setValueTemp(uint8_t v,uint8_t l){assert(l<64);leds[l]=v;}
static void led_clearAllBlinkLeds(void){memset(blinks,0,sizeof blinks);led_blinkingLeds=0;}
static void led_clearSequencerLeds(void){for(int p=0;p<16;p++)leds[led_idx2StepLed(p)]=0;}
static void led_clearActive_step(void){chase=0;chaseCalls++;}
static void led_setActive_step(uint8_t s){(void)s;chase=1;chaseCalls++;}
static void led_clearSelectLeds(void){}
static void led_clearVoiceLeds(void){}
static void led_setActiveSelectButton(uint8_t b){selectedSection=b;}
static void led_setActiveVoiceLeds(uint8_t b){for(int v=0;v<7;v++)leds[LED_VOICE1+v]=(b>>v)&1;}
static void led_setActiveVoice(uint8_t v){led_setActiveVoiceLeds(1u<<v);}
static void led_setMode2(uint8_t m){lastMode=m;}
static uint8_t seq_isMainStepActive(uint8_t t,uint8_t s,uint8_t p){(void)t;(void)s;(void)p;return 1;}
static uint8_t seq_getTrackLength(uint8_t t){(void)t;return 64;}
static uint8_t seq_getStepIndex(uint8_t t){(void)t;return 32;}
static void seq_setTrackLength(uint8_t t,uint8_t n){(void)t;(void)n;lengthWrites++;}
static uint8_t seq_isPerformanceBreak(void){return breakHeld;}
static void seq_setPerformanceBreak(uint8_t v){breakHeld=v;}
static void seq_setSongModeEnabled(uint8_t v){(void)v;}
static void seq_addPatternToSong(uint8_t p){(void)p;}
static void seq_deleteRow(void){}
static void seq_insertRow(void){}
static void preset_touchTimer(uint8_t t){(void)t;touches++;}
static void preset_savePatternRAM(uint8_t p){(void)p;saveRam++;}
static FRESULT preset_savePatternSD(uint8_t p){(void)p;saves++;return saveResult;}
static void preset_loadDrumsetRam(uint8_t a,uint8_t b,uint8_t d){(void)a;(void)b;(void)d;loads++;}
static uint8_t mainParameters[1][END_OF_SOUND_PARAMETERS];
static void soundengine_process(void){}
static void preset_sendDrumsetParameters(void){loads++;}
static void menu_showSdError(FRESULT e){assert(e);errors++;}
static void menu_showSaveCleanupWarning(void){warnings++;}
static void menu_repaint(void){repaints++;}
static void menu_repaintAll(void){repaints++;}
static void screensaver_touch(void){}
static void menu_resetPerformanceFilter(void){}
static uint8_t has2ndPage(uint8_t p){return p<6;}
static void copyClear_executeClear(void){}
static void copyClear_armClearMenu(uint8_t b){(void)b;}
static void copyClear_reset(void){copyClear_Mode=MODE_NONE;}
static uint8_t copyClear_srcSet(void){return 0;}
static void copyClear_setSrc(int8_t s,uint8_t m){(void)s;(void)m;}
static void copyClear_setDst(int8_t s,uint8_t m){(void)s;(void)m;}
static void copyClear_copyTrack(void){}
static void menu_parseGlobalParam(uint16_t p,uint8_t v){activeParameters[p]=v;}
static void menu_restoreHeldParameter(uint16_t p,uint8_t v){activeParameters[p]=v;}
static void buttonHandler_setRemoveStep(uint8_t l,uint8_t p){(void)l;(void)p;stepWrites++;}
static void buttonHandler_selectActiveStep(uint8_t l,uint8_t p){(void)l;(void)p;}
static void buttonHandler_enterSeqModeStepMode(void){enteredStep++;menu_activePage=SEQ_PAGE;}
static void buttonHandler_setRunStopState(uint8_t r){buttonHandler_stateMemory.seqRunning=r;}
void frontPanel_sendData(uint8_t s,uint8_t p,uint8_t v){
 panelMessages++;
 if(s==SEQ_CC && p==SEQ_CHANGE_PAT){changes++;pending=v;}
 if(s==SEQ_CC && p==SEQ_ROLL_ON_OFF){if(v>>4)rolls|=1u<<(v&15);else rolls&=~(1u<<v);}
}
#define NUM_PATTERN 64
#define NUM_CHARS 76
#define NUM_CURRENT 4
#define CURRENT_KIT 0
#define CURRENT_MORPH 1
#define CURRENT_SONG 2
#define CURRENT_PROJECT 3
#define MAX_SONG_LENGTH 64
#define FR_NO_FILE 4
#define FR_NO_PATH 5
static char savefileNames[64][NUM_SAVEFILE_NAMES][8],nameEditBuffer[8];
static uint8_t menu_loadedPresetNr[4],seq_songData[64][64],*seq_activeSong;
static uint8_t preset_projectCleanupWarning;
static unsigned __get_PRIMASK(void);
#undef __disable_irq
static void __disable_irq(void);
static void __set_PRIMASK(unsigned);
static uint8_t preset_isNameEmpty(char *s){return !s[0];}
static void preset_saveDrumsetRam(uint8_t p,uint8_t m){(void)p;(void)m;saves++;}
static FRESULT preset_saveGlobals(void){saves++;return 0;}
static FRESULT preset_saveProject(uint8_t p){(void)p;saves++;return 0;}
static FRESULT preset_loadProject(uint8_t p,uint8_t x){(void)p;(void)x;loads++;return 0;}
static FRESULT preset_createProject(uint8_t p){(void)p;saves++;return 0;}
static void preset_loadGlobals(void){loads++;}
static void preset_loadPatternRAM(uint8_t p){(void)p;loads++;}
static void menu_kitLoaded(uint8_t p){menu_loadedPresetNr[CURRENT_KIT]=p;}
static uint8_t soundengine_backgroundAudioBegin(void){return 0;}
static void soundengine_backgroundAudioEnd(uint8_t b){(void)b;}
static int lcd_process_display_interrupt;
static uint8_t sendDisplayBuffer(void){return 0;}
static void lcd_clear(void){}
static void lcd_home(void){}
static void lcd_string(char *s){(void)s;}
static void lcd_setcursor(int a,int b){(void)a;(void)b;}
void HAL_Delay(uint32_t n){(void)n;}
static void buttonHandler_disarmTimerActionStep(void);
static void buttonHandler_handleModeButtons(uint8_t);

static void menu_switchPage(uint8_t);
static void buttonHandler_handleSelectButton(uint8_t);
static void buttonHandler_selectButtonPressed(uint8_t);
static void buttonHandler_voiceButtonPressed(uint8_t);
static void buttonHandler_partButtonReleased(uint8_t);
static void buttonHandler_showMuteLEDs(void);
static void led_updateBarLeds(void);
static void led_updateSeqLeds(void);
static void led_initPatternSelectLeds(void);
'''
c += re.search(r'const uint8_t characterOrder\[NUM_CHARS\].*?};', clean(menu), re.S).group() + '\n'
for name in ('copyNameToEditBuffer', 'copyEditBufferToName', 'menu_setLoadSaveCategory', 'menu_resetSaveParameters'):
    c += fn(menu, name)
# Actual slip publication/capture paired with the real panel dispatcher.
c += r'''

static uint8_t seq_running=1;
static struct {uint8_t prev,current,next;} seq_rndValue[7];
static uint32_t primask;
static uint32_t __get_PRIMASK(void){return primask;}
#undef __disable_irq
static void __disable_irq(void){primask=1;}
static void __set_PRIMASK(uint32_t m){primask=m;}
'''
slip = read('Core/Src/Soundengine/Sequencer/sequencer.c')
c += slip[slip.index('/* Slip core:'):slip.index('static void seq_triggerSequenced')]
# All listed functions are actual firmware bodies, not reimplemented event logic.
for s, names in ((panel, ('buttonHandler_setMode','buttonHandler_showMuteLEDs','buttonHandler_muteVoice')),
                 (led, ('led_blinkHandler','led_idx2StepLed','led_initPatternSelectLeds','led_updateBarLeds','led_updateSeqLeds')),
                 (menu, ('menu_getSubPage','menu_resetActiveParameter','menu_endParameterEdit','menu_switchSubPage','menu_switchSubPageFirstScreen','menu_switchPage','menu_handleLoadSaveMenu')),
                 (panel, ('buttonHandler_isLoadSavePage','buttonHandler_leaveDialogForVoice','buttonHandler_restoreOriginal','buttonHandler_armTimerActionStep','buttonHandler_disarmTimerActionStep','buttonHandler_TimerActionOccured','buttonHandler_setTimeraction','buttonHandler_tick','buttonHandler_handleModeButtons','buttonHandler_handleSelectButton','buttonHandler_enterLivePatternSelect','buttonHandler_selectLivePattern','buttonHandler_seqButtonPressed','buttonHandler_releasePerformanceBreak','buttonHandler_releaseSlip','buttonHandler_seqButtonReleased','buttonHandler_selectButtonPressed','buttonHandler_partButtonReleased','buttonHandler_voiceButtonPressed','buttonHandler_buttonPressed','buttonHandler_buttonReleased'))):
    for name in names: c += fn(s, name)
# Actual bar-follow and direct chase segment, without unrelated clock/MIDI work.
seq = read('Core/Src/Soundengine/Sequencer/sequencer.c')
c += fn(seq, 'seq_patternIsUsed')
c += fn(seq, 'seq_recordAutomation')
# Ordinary knob routing remains page-based; the existing change-all target
# exercises its actual normal, bulk, held-lock and recording transport paths.
assert 'SELECT_MODE_PATTERN' not in fn(menu, 'menu_parseKnobValue')
segment = seq[seq.index('//TODO can maybe be combined with pattern change follow above?!'):seq.index('// check mtc, which might stop')]
c += 'static void follow_and_chase(void) {\n' + clean(segment) + '\n}\n'
# Actual FX-type UI branch; DSP endpoints are stubs, as in a kit autoload.
fx = clean(read('Core/Src/Soundengine/MIDI/MidiParser.c'))
fx = fx[fx.index('case CC2_FX_TYPE:'):fx.index('case CC2_FX_ROUTING:')]
c += '''static void FxBus_prepareFxChange(void){}\nstatic void FxBus_updateParameter(void){}\nstatic void change_fx(unsigned type) {\nstruct {unsigned itg;} value={type};\nswitch(0) {\n'''
c += fx.replace('case CC2_FX_TYPE:', 'case 0:') + '\n}}\n'
timer = fn(menu, 'menu_uiTick')
a = timer.index('if((menu_activePage == PATTERN_SAVE_PAGE_OK)')
b = timer.index('if(display_needs_clear_all', a)
c += 'static void success_tick(void){' + timer[a:b] + '}\n'
c += r'''
static void reset(uint8_t page,uint8_t index){
 memset(leds,0,sizeof leds);memset(blinks,0,sizeof blinks);
 memset(seq_patternSet.used,1,sizeof seq_patternSet.used);
 memset(seq_patternSet.seq_mainSteps,0,sizeof seq_patternSet.seq_mainSteps);
 led_blinkingLeds=led_blinkPrescaler=led_blinkToggleState=0;
 buttonHandler_stateMemory.selectButtonMode=SELECT_MODE_VOICE;
 buttonHandler_stateMemory.seqErasing=0;
 menu_activePage=page;menuIndex=index;editModeActive=1;
 menu_activeVoice=page<7?page:2;menu_activeBar=0;menu_activePatternBank=0;
 menu_shownPattern=menu_playedPattern=0;heldSeqButtons=consumedSeqReleases=0;
 shift=load=save=copy=0;rolls=breakHeld=performanceBreakButtonHeld=0;
 saves=saveRam=changes=touches=stepWrites=errors=warnings=0;saveResult=0;
 loads=lengthWrites=panelMessages=repaints=0;
 buttonHandler_stateMemory.seqRunning=buttonHandler_stateMemory.seqRecording=0;
 memset(&menu_saveOptions,0,sizeof menu_saveOptions);
 memset(menu_selectedPresetNr,0,sizeof menu_selectedPresetNr);
 memset(savefileNames,0,sizeof savefileNames);memset(nameEditBuffer,0,sizeof nameEditBuffer);
 enteredStep=0;copyClear_Mode=MODE_NONE;activeParameters[PAR_PATTERN_MODE]=1;
}
static void enter(int route){
 if(route)load=1;else shift=1;
 buttonHandler_seqButtonPressed(SEQ_PATTERN);
 shift=load=0;buttonHandler_seqButtonReleased(SEQ_PATTERN);
 assert(buttonHandler_getMode()==SELECT_MODE_PATTERN_LIVE);
}
static void pads(unsigned p,int blink){
 for(unsigned i=0;i<16;i++)assert(blinks[led_idx2StepLed(i)]==(blink && i==p));
}
static void shifted_pad(uint8_t pad){
 shift=1;buttonHandler_seqButtonPressed(pad);shift=0;
 buttonHandler_seqButtonReleased(pad);
}
static void occupancy_and_slip(void){
 /* Production occupancy painter/query/blinker: all banks, silent used, and
    empty current/queued. Only engine, LED registers and blink registration
    are seams; normal step/bar chase suppression is exercised below. */
 for(unsigned bank=0;bank<4;bank++){
  reset(2,19);memset(seq_patternSet.used,0,sizeof seq_patternSet.used);
  seq_patternSet.used[bank*16+2]=1; /* used but silent */
  seq_patternSet.seq_mainSteps[3][bank*16+3][6]=1; /* first hit latches */
  enter(0);menu_activePatternBank=bank;
  menu_playedPattern=bank*16;menu_shownPattern=bank*16+1;
  led_initPatternSelectLeds();
  assert(seq_patternSet.used[bank*16+3]);
  for(unsigned pad=0;pad<16;pad++)
   assert(leds[led_idx2StepLed(pad)]==(pad==0 || pad==2 || pad==3));
  pads(1,1);
  for(unsigned tick=0;tick<8;tick++){
   led_blinkHandler();
   assert(leds[led_idx2StepLed(0)]==!(tick%2));
   assert(leds[led_idx2StepLed(1)]==!((tick/2)%2));
   assert(leds[led_idx2StepLed(2)] && leds[led_idx2StepLed(3)]);
   assert(!leds[led_idx2StepLed(4)]);
  }
  /* Hide both markers in a different bank, then return without stale LEDs. */
  menu_activePatternBank=(bank+1)%4;led_initPatternSelectLeds();pads(0,0);
  for(unsigned pad=0;pad<16;pad++)assert(!leds[led_idx2StepLed(pad)]);
  menu_activePatternBank=bank;led_initPatternSelectLeds();pads(1,1);
  /* Empty queued becomes current after ACK; no slow marker remains. */
  menu_playedPattern=menu_shownPattern;led_initPatternSelectLeds();pads(0,0);
  led_blinkHandler();led_blinkHandler();assert(!leds[led_idx2StepLed(1)]);
  buttonHandler_handleModeButtons(SELECT_MODE_VOICE);pads(0,0);
  /* Normal voice step LEDs and chase resume, unaffected by occupancy. */
  led_updateSeqLeds();for(unsigned pad=0;pad<16;pad++)assert(leds[led_idx2StepLed(pad)]);
  unsigned before=chaseCalls;follow_and_chase();assert(chaseCalls>before);
 }
 reset(PERF_PAGE,0); buttonHandler_setMode(SELECT_MODE_PERF);
 for(unsigned t=0;t<7;t++) {seq_patternSet.length[0][t]=t+1;seq_stepIndex[t]=0;}
 seq_slipSync();
 /* Plain physical press, FIFO waiters and fresh real-origin handover. */
 buttonHandler_seqButtonPressed(8);seq_slipSync();assert(seq_slipOwner()==8 && seq_slipLength==2);
 buttonHandler_seqButtonPressed(11);buttonHandler_seqButtonPressed(9);seq_slipSync();
 assert(seq_slipCount==3 && seq_slipQueue[1]==3);
 seq_stepIndex[6]=4; shift=1;buttonHandler_seqButtonReleased(8);seq_slipSync();
 assert(seq_slipOwner()==11 && seq_slipOrigin[6]==4 && seq_slipLength==8);
 /* Cancellation consumes releases across modifiers and mode changes. */
 buttonHandler_setMode(SELECT_MODE_VOICE);seq_slipSync();assert(!seq_slipCount);
 shift=load=save=copy=1;buttonHandler_seqButtonReleased(11);buttonHandler_seqButtonReleased(9);
 assert(!performanceSlipButtons && !stepWrites);
 shift=load=save=copy=0;buttonHandler_setMode(SELECT_MODE_PERF);
 seq_running=0;buttonHandler_seqButtonPressed(8);seq_slipSync();assert(!seq_slipCount);
 buttonHandler_seqButtonReleased(8);seq_running=1;
 /* Modifier and copy/clear routes may not acquire slip ownership. */
 for(unsigned modifier=0;modifier<5;modifier++) {
  buttonHandler_setMode(SELECT_MODE_PERF);
  shift=modifier==0;load=modifier==1;save=modifier==2;copy=modifier==3;
  copyClear_Mode=modifier==4?MODE_CLEAR:MODE_NONE;
  buttonHandler_seqButtonPressed(9);seq_slipSync();assert(!seq_slipCount);
  buttonHandler_seqButtonReleased(9);
 }
 shift=load=save=copy=0;copyClear_Mode=MODE_NONE;buttonHandler_setMode(SELECT_MODE_PERF);
 buttonHandler_seqButtonPressed(10);seq_slipSync();assert(seq_slipLength==6);
 seq_slipClear();seq_slipSync();assert(!seq_slipCount);
 /* A waiter held across cancellation never restarts without another press. */
 buttonHandler_seqButtonReleased(10);seq_slipSync();assert(!seq_slipCount);
 assert(SELECT_MODE_PATTERN_LIVE==12 && SELECT_MODE_PATTERN==8);
 for(int route=0;route<2;route++)for(int page=0;page<NUM_PAGES;page++)for(int index=0;index<64;index++){
  reset(page,index);chase=1;rolls=127;breakHeld=1;
  enter(route);assert(!chase&&!rolls&&!breakHeld&&!editModeActive);
  if(page<7 || page==PERF_PAGE || page==FX_MODE_PAGE)assert(menu_activePage==page && menuIndex==index);
  else assert(menu_activePage==PERF_PAGE && menuIndex==0);
  assert(!saves&&!changes&&!stepWrites && buttonHandler_buttonTimerStepNr==NO_STEP_SELECTED);
  unsigned savedIndex=menuIndex;buttonHandler_enterLivePatternSelect();assert(menuIndex==savedIndex);
 }
}
static void live_selection_navigation(void){
 /* Bank bounds, pending selection, ordinary LED painters, immediate ACK seam. */
 reset(2,19);enter(0);
 for(int bank=0;bank<4;bank++){
  assert(menu_activePatternBank==bank);
  buttonHandler_seqButtonPressed(5);buttonHandler_seqButtonReleased(5);
  assert(pending==bank*16+5 && menu_shownPattern==pending && menuIndex==19 && menu_activePage==2);
  pads(5,1);led_updateSeqLeds();led_updateBarLeds();pads(5,1);
  activeParameters[PAR_FOLLOW]=FOLLOW_BAR;
  for(int step=0;step<64;step++){
   seq_stepIndex[menu_activeVoice]=step;frontParser_activeTrack=menu_activeVoice;
   unsigned beforeChase=chaseCalls;follow_and_chase();
   assert(chaseCalls==beforeChase && menu_activeBar==0 && menu_shownPattern==pending);pads(5,1);
  }
  assert(leds[LED_PAGE_DOWN]==(bank>>1) && leds[LED_PAGE_UP]==(bank&1));
  menu_playedPattern=menu_shownPattern;led_initPatternSelectLeds();pads(0,0);
  assert(leds[led_idx2StepLed(5)]);
  buttonHandler_buttonPressed(BUT_PAGE_UP);
 }
 assert(menu_activePatternBank==3);
 for(int i=0;i<5;i++)buttonHandler_buttonPressed(BUT_PAGE_DOWN);
 assert(!menu_activePatternBank && !saves && changes==4 && !touches);
 /* Every physical pad maps to its bank slot, including same-slot reload. */
 reset(2,19);enter(0);
 for(int bank=0;bank<4;bank++)for(int pad=0;pad<16;pad++){
  menu_activePatternBank=bank;buttonHandler_seqButtonPressed(pad);buttonHandler_seqButtonReleased(pad);
  assert(pending==bank*16+pad && menuIndex==19);pads(pad,1);
  menu_playedPattern=menu_shownPattern;led_initPatternSelectLeds();pads(0,0);
  assert(leds[led_idx2StepLed(pad)]);
 }
 assert(changes==64 && !touches && !saves);
 /* Explicit exits don't enter STEP or cycle a retained PERF bank/index. */
 reset(3,21);enter(0);buttonHandler_handleModeButtons(SELECT_MODE_VOICE);
 assert(buttonHandler_getMode()==SELECT_MODE_VOICE && menu_activePage==3 && menuIndex==21 && !enteredStep);
 assert(menuPages[PERF_PAGE][0].bot1==PAR_BPM);
 assert(menuPages[PERF_PAGE][0].bot5==PAR_SHUFFLE);
 assert(menuPages[PERF_PAGE][1].bot1==MASTER_COMP_THRESHOLD);
 for(int index=0;index<12;index++){
  reset(PERF_PAGE,index);enter(1);menu_activePatternBank=3;led_initPatternSelectLeds();
  buttonHandler_handleModeButtons(SELECT_MODE_PERF);
  assert(!leds[LED_PAGE_UP] && !leds[LED_PAGE_DOWN]);pads(0,0);
  for(int p=0;p<16;p++)assert(!leds[led_idx2StepLed(p)]);
  assert(buttonHandler_getMode()==SELECT_MODE_PERF && menuIndex==index && menu_activePage==PERF_PAGE);
 }
 /* All voices/sections/backgrounds/screens use the real physical dispatch. */
 for(int bg=0;bg<3;bg++)for(int section=0;section<8;section++)for(int screen=0;screen<2;screen++)for(int v=0;v<7;v++){
  int page=(int[]){2,FX_MODE_PAGE,PERF_PAGE}[bg];
  reset(page,section*8+screen*4+2);enter(0);
  buttonHandler_seqButtonPressed(5);unsigned changesBefore=changes;
  uint16_t consumed=consumedSeqReleases;unsigned played=menu_playedPattern,shown=menu_shownPattern;
  buttonHandler_mutedVoices=0;menu_muteModeActive=1;
  buttonHandler_voiceButtonPressed(v);
  if(bg==2){assert(buttonHandler_getMode()==SELECT_MODE_PATTERN_LIVE && menu_activePage==PERF_PAGE);assert(buttonHandler_mutedVoices==(1u<<v));}
  else {
   assert(buttonHandler_getMode()==SELECT_MODE_VOICE && menu_activePage==v && menu_activeVoice==v);
   assert(menuIndex==section*8 && !menu_muteModeActive && leds[LED_VOICE1+v]);
   assert(lastMode==SELECT_MODE_VOICE);pads(0,0);
  }
  assert(menu_playedPattern==played && menu_shownPattern==shown && changes==changesBefore);
  assert(consumedSeqReleases==consumed);buttonHandler_seqButtonReleased(5);assert(!stepWrites);
  for(int target=0;target<8;target++){
   reset(page,section*8+screen*4+2);enter(0);buttonHandler_seqButtonPressed(6);
   consumed=consumedSeqReleases;shown=menu_shownPattern;played=menu_playedPattern;
   buttonHandler_selectButtonPressed(target);
   assert(buttonHandler_getMode()==SELECT_MODE_VOICE && menu_activePage==2 && menu_activeVoice==2);
   assert(menuIndex==target*8 && !editModeActive && !menu_muteModeActive);
   assert(lastMode==SELECT_MODE_VOICE && leds[LED_VOICE1+2]);pads(0,0);
   assert(consumedSeqReleases==consumed && menu_shownPattern==shown && menu_playedPattern==played);
   buttonHandler_seqButtonReleased(6);assert(!stepWrites);
   buttonHandler_selectButtonPressed(target);assert(menuIndex==target*8+(has2ndPage(target)?4:0));
  }
 }
}
static void last_step_navigation(void){
 /* Last Step: actual entry, both modes, every current voice and requested
    section, retained second-screen/focus. Navigation must be UI-only. */
 for(int all=0;all<2;all++)for(int v=0;v<7;v++)for(int target=0;target<8;target++)for(int index=0;index<64;index++){
  reset(v,index);menu_activeVoice=v;
  shifted_pad(SEQ_LAST_STEP);
  if(all)shifted_pad(SEQ_LAST_STEP);
  assert(buttonHandler_getMode()==(all?SELECT_MODE_LAST_STEP_ALL:SELECT_MODE_LAST_STEP_TRACK));
  menuIndex=index;menu_activeBar=2;
  buttonHandler_stateMemory.seqRunning=1;buttonHandler_stateMemory.seqRecording=1;
  pending=37;menu_playedPattern=4;menu_shownPattern=9;
  unsigned messages=panelMessages,writes=lengthWrites;
  uint16_t held=heldSeqButtons,consumed=consumedSeqReleases;
  buttonHandler_selectButtonPressed(target);
  assert(buttonHandler_getMode()==SELECT_MODE_VOICE && menu_activePage==v && menu_activeVoice==v);
  assert(menuIndex==target*8 && !editModeActive && selectedSection==target);
  assert(lastMode==SELECT_MODE_VOICE && leds[LED_VOICE1+v]);pads(0,0);
  assert(!led_blinkingLeds && menu_activeBar==2);
  for(int pad=0;pad<16;pad++)assert(leds[led_idx2StepLed(pad)]);
  assert(lengthWrites==writes && panelMessages==messages && !changes && !stepWrites);
  assert(menu_playedPattern==4 && menu_shownPattern==9 && pending==37);
  assert(buttonHandler_stateMemory.seqRunning && buttonHandler_stateMemory.seqRecording);
  assert(heldSeqButtons==held && consumedSeqReleases==consumed);
  buttonHandler_selectButtonPressed(target);
  assert(menuIndex==target*8+(has2ndPage(target)?4:0));
 }
 /* Shift, physical Copy, every active copy/clear state and erase retain mode. */
 for(int all=0;all<2;all++)for(int target=0;target<8;target++)for(int modifier=0;modifier<3+MODE_COPY_TRACK;modifier++){
  reset(2,12);shifted_pad(SEQ_LAST_STEP);
  if(all)shifted_pad(SEQ_LAST_STEP);
  unsigned mode=buttonHandler_getMode();
  shift=modifier==0;copy=modifier==1;buttonHandler_stateMemory.seqErasing=modifier==2;
  if(modifier>=3)copyClear_Mode=modifier-2;
  buttonHandler_selectButtonPressed(target);
  assert(buttonHandler_getMode()==mode && menu_activePage==MENU_LAST_STEP_PAGE);
 }
 /* Ordinary voice selection remains in Last Step for length editing. */
 for(int all=0;all<2;all++)for(int v=0;v<7;v++){
  reset(2,12);shifted_pad(SEQ_LAST_STEP);
  if(all)shifted_pad(SEQ_LAST_STEP);
  unsigned mode=buttonHandler_getMode(),writes=lengthWrites;
  buttonHandler_voiceButtonPressed(v);
  assert(buttonHandler_getMode()==mode && menu_activePage==MENU_LAST_STEP_PAGE && menu_activeVoice==v);
  assert(lengthWrites==writes);
 }
}
static void config_navigation(void){
 /* Actual Config entry (also from Last Step), every index, voice/section.
    Global indices must never become voice sections. Only normal voice requests
    are allowed; no settings, length, transport or pattern mutation. */
 for(int current=0;current<7;current++)for(int origin=0;origin<3;origin++)for(int index=0;index<64;index++)for(int kind=0;kind<3;kind++)for(int target=0;target<(kind==0?7:kind==1?8:1);target++){
  reset(current,12);
  if(origin){shifted_pad(SEQ_LAST_STEP);if(origin==2)shifted_pad(SEQ_LAST_STEP);}
  shifted_pad(SEQ_CONFIG);
  assert(menu_activePage==MENU_MIDI_PAGE && buttonHandler_getMode()==SELECT_MODE_MENU);
  menuIndex=index;editModeActive=1;
  buttonHandler_stateMemory.seqRunning=buttonHandler_stateMemory.seqRecording=1;
  pending=37;menu_playedPattern=4;menu_shownPattern=9;
  uint8_t settings[NUM_PARAMS];memcpy(settings,activeParameters,sizeof settings);
  unsigned writes=lengthWrites,messages=panelMessages,steps=enteredStep;
  uint16_t held=heldSeqButtons,consumed=consumedSeqReleases;
  if(kind==0)buttonHandler_voiceButtonPressed(target);
  else if(kind==1)buttonHandler_selectButtonPressed(target);
  else buttonHandler_handleModeButtons(SELECT_MODE_VOICE);
  assert(buttonHandler_getMode()==SELECT_MODE_VOICE && menu_activePage==(kind==0?target:current));
  assert(menu_activeVoice==(kind==0?target:current) && !editModeActive);
  if(kind<2)assert(menuIndex==(kind==0?0:target*8) && selectedSection==(kind==0?0:target));
  assert(enteredStep==steps && lastMode==SELECT_MODE_VOICE && !led_blinkingLeds);
  assert(lengthWrites==writes && !changes && !stepWrites && !saves && !saveRam);
  assert(panelMessages==messages+(kind==0?2:0));
  assert(!memcmp(settings,activeParameters,sizeof settings));
  assert(menu_playedPattern==4 && menu_shownPattern==9 && pending==37);
  assert(buttonHandler_stateMemory.seqRunning && buttonHandler_stateMemory.seqRecording);
  assert(heldSeqButtons==held && consumedSeqReleases==consumed);
 }
 /* Config must never alias length-editing mode, at any index/pad. */
 for(int index=0;index<64;index++)for(int pad=0;pad<16;pad++){
  reset(2,index);shifted_pad(SEQ_CONFIG);menuIndex=index;menu_activeBar=2;
  unsigned writes=lengthWrites;
  buttonHandler_seqButtonPressed(pad);buttonHandler_seqButtonReleased(pad);
  led_updateBarLeds();
  assert(buttonHandler_getMode()==SELECT_MODE_MENU && lengthWrites==writes && !stepWrites);
  assert(!leds[LED_PAGE_UP] && leds[LED_PAGE_DOWN]);
 }
 for(int all=0;all<2;all++)for(int pad=0;pad<16;pad++){
  reset(2,0);shifted_pad(SEQ_LAST_STEP);if(all)shifted_pad(SEQ_LAST_STEP);
  menu_activeBar=2;unsigned writes=lengthWrites;
  buttonHandler_seqButtonPressed(pad);buttonHandler_seqButtonReleased(pad);
  assert(lengthWrites==writes+(all?7:1));
  led_updateBarLeds();assert(!leds[LED_PAGE_UP] && leds[LED_PAGE_DOWN]);
 }
 /* Excluded gestures keep existing Config navigation, not a Voice exit. */
 for(int kind=0;kind<2;kind++)for(int target=0;target<(kind?8:7);target++)for(int modifier=0;modifier<3+MODE_COPY_TRACK;modifier++){
  reset(2,12);shifted_pad(SEQ_CONFIG);
  shift=modifier==0;copy=modifier==1;buttonHandler_stateMemory.seqErasing=modifier==2;
  if(modifier>=3)copyClear_Mode=modifier-2;
  if(kind)buttonHandler_selectButtonPressed(target);else buttonHandler_voiceButtonPressed(target);
  assert(menu_activePage==MENU_MIDI_PAGE && buttonHandler_getMode()==SELECT_MODE_MENU);
 }
 buttonHandler_stateMemory.seqRunning=buttonHandler_stateMemory.seqRecording=0;
 /* Modifiers and active erase must not trigger either new exit route. */
 for(int bg=0;bg<3;bg++)for(int modifier=0;modifier<4;modifier++)for(int kind=0;kind<2;kind++){
  reset((int[]){2,FX_MODE_PAGE,PERF_PAGE}[bg],12);enter(0);
  shift=modifier==0;copy=modifier==1;copyClear_Mode=modifier==2?MODE_CLEAR:MODE_NONE;
  buttonHandler_stateMemory.seqErasing=modifier==3;
  if(kind)buttonHandler_voiceButtonPressed(3);else buttonHandler_selectButtonPressed(3);
  assert(buttonHandler_getMode()==SELECT_MODE_PATTERN_LIVE);
  buttonHandler_stateMemory.seqErasing=0;
 }

}
static void dialog_navigation(void){
 /* Actual shortcut entry for every reachable shared category, all states,
    both exits and held shortcut releases. UI selectors/names are not rolled
    back; exit must not invoke the production confirmation handler. */
 for(int saving=0;saving<2;saving++)for(int cat=0;cat<4;cat++)
 for(int state=SAVE_STATE_EDIT_PRESET_NR;state<=SAVE_STATE_OK;state++)
 for(int kind=0;kind<2;kind++)for(int target=0;target<(kind?8:7);target++){
  reset(2,51);loads=0;
  uint8_t padsByCat[]={SEQ_KIT,SEQ_MORPH,SEQ_SONG,SEQ_PROJECT};
  uint8_t cats[]={SAVE_TYPE_KIT,SAVE_TYPE_MORPH,SAVE_TYPE_SONG,SAVE_TYPE_PROJECT};
  save=saving;load=!saving;
  buttonHandler_seqButtonPressed(padsByCat[cat]);
  assert(menu_activePage==(saving?SAVE_PAGE:LOAD_PAGE) && menu_saveOptions.category==cats[cat]);
  save=load=0;
  menu_saveOptions.state=state;editModeActive=1;menuIndex=51;
  menu_selectedPresetNr[cats[cat]]=23;memset(nameEditBuffer,7,sizeof nameEditBuffer);
  buttonHandler_stateMemory.seqRunning=buttonHandler_stateMemory.seqRecording=1;
  pending=37;menu_playedPattern=4;menu_shownPattern=9;
  unsigned writes=lengthWrites,beforeLoads=loads;
  if(kind)buttonHandler_selectButtonPressed(target);else buttonHandler_voiceButtonPressed(target);
  assert(menu_activePage==(kind?2:target) && buttonHandler_getMode()==SELECT_MODE_VOICE);
  assert(menuIndex==(kind?target*8:0) && !editModeActive && !menu_muteModeActive);
  assert(selectedSection==(kind?target:0) && !led_blinkingLeds);
  assert(!saves && !saveRam && loads==beforeLoads && !changes && !stepWrites && lengthWrites==writes);
  assert(menu_selectedPresetNr[cats[cat]]==23 && nameEditBuffer[0]==7);
  assert(menu_playedPattern==4 && menu_shownPattern==9 && pending==37);
  assert(buttonHandler_stateMemory.seqRunning && buttonHandler_stateMemory.seqRecording);
  buttonHandler_seqButtonReleased(padsByCat[cat]);assert(!stepWrites);
  systick_ticks+=5000;success_tick();assert(menu_activePage==(kind?2:target));
 }
 /* Dedicated pattern save: before save and after real completed save; Kit
    success reached through real confirmation. Every target and route. */
 for(int stage=0;stage<3;stage++)for(int kind=0;kind<2;kind++)
 for(int target=0;target<(kind?8:7);target++){
  reset(2,51);loads=0;save=1;
  buttonHandler_seqButtonPressed(stage==2?SEQ_KIT:SEQ_PATTERN);save=0;
  if(stage==2){
   menu_saveOptions.state=SAVE_STATE_CHANGE_NAME_DIALOG_N;
   menu_handleLoadSaveMenu(0,1);assert(menu_activePage==KIT_SAVE_PAGE_OK && saves==1);
  }else if(stage==1){
   buttonHandler_seqButtonPressed(6);assert(menu_activePage==PATTERN_SAVE_PAGE_OK && saveRam==1);
  }else assert(menu_activePage==PATTERN_SAVE_PAGE);
  unsigned saved=saves,ram=saveRam,writes=lengthWrites;menuIndex=51;
  if(kind)buttonHandler_selectButtonPressed(target);else buttonHandler_voiceButtonPressed(target);
  assert(menu_activePage==(kind?2:target) && buttonHandler_getMode()==SELECT_MODE_VOICE);
  assert(menuIndex==(kind?target*8:0) && !editModeActive && !menu_muteModeActive);
  buttonHandler_seqButtonReleased(stage==2?SEQ_KIT:SEQ_PATTERN);
  if(stage==1)buttonHandler_seqButtonReleased(6);
  systick_ticks+=5000;success_tick();
  assert(menu_activePage==(kind?2:target) && saves==saved && saveRam==ram);
  assert(!loads && !changes && !stepWrites && lengthWrites==writes);
 }
 /* Modifier exclusions on each dialog, independent of its mode alias. */
 for(int p=0;p<5;p++)for(int kind=0;kind<2;kind++)
 for(int mod=0;mod<3+MODE_COPY_TRACK;mod++){
  uint8_t pageList[]={LOAD_PAGE,SAVE_PAGE,PATTERN_SAVE_PAGE,KIT_SAVE_PAGE_OK,PATTERN_SAVE_PAGE_OK};
  reset(pageList[p],51);buttonHandler_setMode(p==0?SELECT_MODE_LOAD:p==1?SELECT_MODE_SAVE:SELECT_MODE_PATTERN);
  unsigned mode=buttonHandler_getMode();
  shift=mod==0;copy=mod==1;buttonHandler_stateMemory.seqErasing=mod==2;
  if(mod>=3)copyClear_Mode=mod-2;
  if(kind)buttonHandler_selectButtonPressed(3);else buttonHandler_voiceButtonPressed(3);
  assert(menu_activePage==pageList[p] && buttonHandler_getMode()==mode);
 }

}
static void names_and_confirmation(void){
 /* Real empty-name prompt eagerly initializes the name; cancellation must
    neither claim rollback nor commit the later edit buffer. */
 reset(2,0);save=1;buttonHandler_seqButtonPressed(SEQ_KIT);save=0;
 menu_selectedPresetNr[SAVE_TYPE_KIT]=11;menu_saveOptions.nameBuffer=0;
 savefileNames[11][0][0]=0;menu_saveOptions.state=SAVE_STATE_EDIT_PRESET_NR;
 menu_handleLoadSaveMenu(0,1);
 assert(menu_saveOptions.state==SAVE_STATE_EDIT_NAME1 && !memcmp(savefileNames[11][0],"Unnamed",8));
 memset(nameEditBuffer,9,sizeof nameEditBuffer);
 buttonHandler_selectButtonPressed(3);buttonHandler_seqButtonReleased(SEQ_KIT);
 assert(!memcmp(savefileNames[11][0],"Unnamed",8) && !saves && !stepWrites);
 /* Reentry regenerates indices, unsupported characters become spaces. */
 save=1;buttonHandler_seqButtonPressed(SEQ_KIT);save=0;
 assert(menu_saveOptions.state==SAVE_STATE_EDIT_PRESET_NR);
 assert(nameEditBuffer[0]==21); /* U in the real table */
 memcpy(savefileNames[11][KIT_NAMES],"Ab9_?~+\001",8);
 copyNameToEditBuffer(11,KIT_NAMES);
 assert(nameEditBuffer[7]==0);
 copyEditBufferToName(11,KIT_NAMES);
 assert(!memcmp(savefileNames[11][KIT_NAMES],"Ab9_?~+ ",8));
 buttonHandler_voiceButtonPressed(2);buttonHandler_seqButtonReleased(SEQ_KIT);
 assert(!saves && !stepWrites);
 /* Ordinary confirmed shared save/load operations are still reachable. */
 for(int saving=0;saving<2;saving++)for(int cat=0;cat<4;cat++){
  reset(2,0);loads=0;seq_activeSong=seq_songData[0];save=saving;load=!saving;
  uint8_t shortcuts[]={SEQ_KIT,SEQ_MORPH,SEQ_SONG,SEQ_PROJECT};
  buttonHandler_seqButtonPressed(shortcuts[cat]);save=load=0;
  menu_selectedPresetNr[menu_saveOptions.category]=3;
  menu_saveOptions.state=SAVE_STATE_CHANGE_NAME_DIALOG_N;
  menu_handleLoadSaveMenu(0,1);
  if(cat==2)assert(seq_activeSong==seq_songData[3]);
  else assert(saving?saves==1:loads==1);
 }
 buttonHandler_stateMemory.seqRunning=buttonHandler_stateMemory.seqRecording=0;
}
static void retained_controls(void){
 /* Standalone FX routing is unchanged. */
 for(int mode=0;mode<1;mode++)for(int kind=0;kind<2;kind++){
  reset(mode?PATTERN_SAVE_PAGE:FX_MODE_PAGE,12);
  buttonHandler_setMode(mode?SELECT_MODE_PATTERN:SELECT_MODE_FX);
  unsigned oldMode=buttonHandler_getMode();
  if(kind)buttonHandler_voiceButtonPressed(3);else buttonHandler_selectButtonPressed(3);
  if(!mode && !kind)assert(buttonHandler_getMode()==SELECT_MODE_VOICE && menu_activePage==2 && menuIndex==28);
  else assert(buttonHandler_getMode()==oldMode && menu_activePage==(mode?PATTERN_SAVE_PAGE:FX_MODE_PAGE));
 }
 reset(1,11);enter(0);shift=1;buttonHandler_handleModeButtons(0);shift=0;
 assert(buttonHandler_getMode()==SELECT_MODE_STEP && enteredStep==1);
 /* Old held step, old held roll, and new pattern-pad release after exit. */
 reset(1,11);buttonHandler_seqButtonPressed(2);assert(buttonHandler_buttonTimerStepNr==2);
 enter(0);assert(buttonHandler_buttonTimerStepNr==NO_STEP_SELECTED);
 systick_ticks+=10000;buttonHandler_tick();assert(buttonHandler_armedAutomationStep==NO_STEP_SELECTED);
 buttonHandler_handleModeButtons(0);buttonHandler_seqButtonReleased(2);assert(!stepWrites);
 buttonHandler_seqButtonPressed(2);buttonHandler_seqButtonReleased(2);assert(stepWrites==1);
 reset(PERF_PAGE,4);buttonHandler_stateMemory.selectButtonMode=SELECT_MODE_PERF;
 buttonHandler_seqButtonPressed(3);buttonHandler_seqButtonPressed(7);assert(rolls && breakHeld);
 enter(1);assert(!rolls&&!breakHeld);buttonHandler_handleModeButtons(0);
 buttonHandler_seqButtonReleased(3);buttonHandler_seqButtonReleased(7);assert(!stepWrites && !performanceBreakButtonHeld);
 reset(1,2);enter(0);buttonHandler_seqButtonPressed(4);buttonHandler_handleModeButtons(0);
 buttonHandler_seqButtonReleased(4);assert(!stepWrites);
 /* An already armed lock restores before live entry and cannot arm again. */
 reset(1,11);seq_patternSet.seq_subStepPattern[seq_activePattern][1][2].param1Nr=11;
 seq_patternSet.seq_subStepPattern[seq_activePattern][1][2].param1Val=99;
 activeParameters[10]=23;buttonHandler_seqButtonPressed(2);systick_ticks+=10000;buttonHandler_tick();
 assert(buttonHandler_armedAutomationStep==2 && activeParameters[10]==99);
 enter(0);assert(buttonHandler_armedAutomationStep==NO_STEP_SELECTED && activeParameters[10]==23 && !buttonHandler_resetLock1);
 buttonHandler_seqButtonReleased(2);assert(!stepWrites);
 /* FX autoload still updates its retained live background. */
 reset(FX_MODE_PAGE,17);enter(0);
 for(unsigned type=0;type<6;type++){
  change_fx(type);assert(menu_getSubPage()==type && fxBus.fxType==type && buttonHandler_getMode()==12);
 }
 reset(PERF_PAGE,8);enter(0);buttonHandler_mutedVoices=0;buttonHandler_voiceButtonPressed(2);
 assert(buttonHandler_mutedVoices==4 && menu_activePage==PERF_PAGE);
 shift=1;buttonHandler_buttonPressed(BUT_SHIFT);shift=0;buttonHandler_buttonReleased(BUT_SHIFT);
 assert(leds[LED_VOICE1+2]==0 && leds[LED_VOICE1]==1);
 /* Recording flag survives selection. Other operations retire live ownership. */
 reset(2,9);buttonHandler_stateMemory.seqRecording=1;enter(0);buttonHandler_seqButtonPressed(4);
 assert(buttonHandler_stateMemory.seqRecording);buttonHandler_seqButtonReleased(4);
 seq_recordActive=1;seq_activeAutomTrack=0;seq_stepIndex[2]=5;
 memset(&seq_patternSet.seq_subStepPattern[0][2][5],0,sizeof(Step));
 memset(&seq_patternSet.seq_subStepPattern[4][2][5],0,sizeof(Step));
 seq_recordAutomation(2,11,73);
 assert(seq_patternSet.seq_subStepPattern[0][2][5].param1Val==73);
 assert(!seq_patternSet.seq_subStepPattern[4][2][5].param1Nr);
 seq_recordActive=0;
 shift=1;buttonHandler_buttonPressed(BUT_REC);shift=0;
 assert(menu_activePage==RECORDING_PAGE && buttonHandler_getMode()==SELECT_MODE_PATTERN);
 unsigned before=changes;buttonHandler_seqButtonPressed(6);buttonHandler_seqButtonReleased(6);
 assert(changes==before+1 && pending==6 && !stepWrites && menu_activePage==RECORDING_PAGE);
 for(int context=0;context<3;context++){
  int page=(int[]){2,FX_MODE_PAGE,PERF_PAGE}[context];
  reset(page,8);enter(0);menu_activePatternBank=3;led_initPatternSelectLeds();
  buttonHandler_buttonPressed(BUT_COPY);
  assert(buttonHandler_getMode()==SELECT_MODE_PATTERN_LIVE);
  assert(menu_activePage==page && menuIndex==8 && copyClear_Mode==MODE_COPY_TRACK);
  assert(leds[LED_PAGE_UP] && leds[LED_PAGE_DOWN]);
  copyClear_reset();unsigned before=changes;
  buttonHandler_seqButtonPressed(4);buttonHandler_seqButtonReleased(4);
  assert(changes==before+1 && pending==52 && !stepWrites);
 }
 /* Held pad -> shifted shortcut -> PERF exit -> Shift up -> pad up. */
 reset(PERF_PAGE,8);buttonHandler_setMode(SELECT_MODE_PERF);buttonHandler_seqButtonPressed(4);shift=1;
 buttonHandler_seqButtonPressed(SEQ_PATTERN);buttonHandler_seqButtonReleased(SEQ_PATTERN);
 assert(buttonHandler_getMode()==SELECT_MODE_PATTERN_LIVE);
 menu_activePatternBank=3;led_initPatternSelectLeds();
 buttonHandler_buttonPressed(BUT_COPY);
 assert(copyClear_Mode==MODE_CLEAR);
 assert(menu_activePage==PERF_PAGE && menuIndex==8 && buttonHandler_getMode()==SELECT_MODE_PATTERN_LIVE);
 shift=0;buttonHandler_handleModeButtons(SELECT_MODE_PERF);
 shift=0;buttonHandler_buttonReleased(BUT_SHIFT);buttonHandler_seqButtonReleased(4);
 assert(!stepWrites && !rolls && !heldSeqButtons && !consumedSeqReleases);
 assert(!leds[LED_PAGE_UP] && !leds[LED_PAGE_DOWN]);pads(0,0);

 /* Overlapping Config/Last Step shortcuts must not become step releases. */
 for(int context=0;context<3;context++)for(int kind=0;kind<(context?1:2);kind++){
  reset(2,0);
  if(context==2)shifted_pad(SEQ_LAST_STEP);
  shift=1;
  uint8_t pad=context?SEQ_LAST_STEP:SEQ_CONFIG;
  buttonHandler_seqButtonPressed(pad);shift=0;
  if(kind)buttonHandler_voiceButtonPressed(3);
  else buttonHandler_selectButtonPressed(3);
  assert(buttonHandler_getMode()==SELECT_MODE_VOICE);
  unsigned before=stepWrites;buttonHandler_seqButtonReleased(pad);
  assert(stepWrites==before && !heldSeqButtons && !consumedSeqReleases);
  buttonHandler_seqButtonPressed(pad);buttonHandler_seqButtonReleased(pad);
  assert(stepWrites==before+1); /* next ordinary press still works */
 }
 /* Save+Pattern commits RAM only, independent of disk faults. */
 for(int fail=0;fail<2;fail++){
  reset(3,13);enter(0);save=1;buttonHandler_seqButtonPressed(SEQ_PATTERN);save=0;
  assert(buttonHandler_getMode()==SELECT_MODE_PATTERN && menu_activePage==PATTERN_SAVE_PAGE);
  buttonHandler_seqButtonReleased(SEQ_PATTERN);saveResult=fail;
  buttonHandler_seqButtonPressed(6);assert(saves==0 && saveRam==1 && !changes);
  assert(activeParameters[PAR_PATTERN_MODE]==SKIP_NEXT_KIT_AUTOLOAD);
  assert(!errors && menu_activePage==PATTERN_SAVE_PAGE_OK && menu_selectedPresetNr[SAVE_TYPE_PATTERN]==6);
 }
}
int main(void){
 occupancy_and_slip();live_selection_navigation();last_step_navigation();
 config_navigation();dialog_navigation();names_and_confirmation();retained_controls();
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='lxr-pattern-') as d:
    p=Path(d);(p/'test.c').write_text(c)
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Werror=implicit-function-declaration',
        '-Wno-unused-function','-Wno-unused-variable','-fsanitize=address,undefined','-fno-sanitize-recover=all',
        '-I'+str(ROOT/'tests/shim'),'-I'+str(ROOT/'Core/Inc'),'-I'+str(ROOT/'Drivers/STM32F7xx_HAL_Driver/Inc'),
        str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
print('Retained pattern controls: real panel/menu/LED bodies passed (stubbed engine/storage/LCD).')

# Real sequencer activation and RAM kit-load bodies, using the established
# bounded preset/MIDI seams. Covers stopped, quantized-running and same-slot ACK.
ns = {'__file__': str(ROOT / 'tests/test_perf_reload.py')}
fixture = read('tests/test_perf_reload.py')
exec(fixture.split('p=clean(src(')[0], ns)
stubs = ns['stubs'].replace('static int buttonHandler_getMode(void){return 0;}',
    'static int buttonHandler_getMode(void){return SELECT_MODE_PATTERN_LIVE;}')
# The fixture's reload-only MRP=0 assertion is not a selection invariant.
stubs = stubs.replace('assert(activeParameters[PAR_MORPH]==0);', '')
stubs = stubs.replace('static void led_initPatternSelectLeds(void){}',
    'static void led_initPatternSelectLeds(void){selectionPaints++;}')
h = read('Core/Inc/Parameters.h')
enum = h[h.index('enum ParamEnums'):]; enum = enum[:enum.index('};') + 2]
order = clean(read('Core/Src/Parameters.c'))
order = order[order.index('uint8_t parameterOrder'):]; order = order[:order.index('};') + 2]
preset = read('Core/Src/Preset/presetManager.c')
c = ns['pre'] + enum + 'static unsigned selectionPaints;\n' + stubs + order
c += ''.join(ns['fn'](clean(preset), n) for n in ('interpolate','preset_morph','preset_morph_tick',
    'preset_sendDrumsetParameters','preset_sendDrumsetParametersImmediate','preset_loadDrumsetRam'))
c += ''.join(ns['fn'](clean(seq), n) for n in ('seq_patternIsUsed','seq_copyPatternToBackupBuffer',
    'seq_copyBackupBufferToPattern','seq_setPendingPatternActive','seq_setNextPattern'))
c += ns['main'].split('int main(void){')[0]
c += r'''
int main(void){
 for(int running=0;running<2;running++)for(int md=0;md<3;md++)for(int page=0;page<3;page++){
  setup(running,md,0,1);menu_activePage=(int[]){0,15,PERF_PAGE}[page];
  seq_patternSet.kitNr[1]=1;selectionPaints=0;
  int oldPage=menu_activePage;
  seq_setNextPattern(1);
  if(running){assert(seq_activePattern==0 && seq_loadPendigFlag && !selectionPaints);seq_setPendingPatternActive();}
  drain();
  assert(seq_activePattern==1 && !seq_loadPendigFlag && !midi_process_block);
  assert(menu_shownPattern==1 && menu_playedPattern==1 && selectionPaints==1);
  assert(menu_activePage==oldPage && repaints>0);
  assert(menu_selectedPresetNr[0]==(md==1?1:0));
  if(md==1)for(int p=0;p<END_OF_SOUND_PARAMETERS;p++)assert(engineValues[p]==activeParameters[p]);
  seq_setPendingPatternActive();assert(selectionPaints==2 && menu_activePage==oldPage);
 }
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='lxr-pattern-activation-') as d:
    p=Path(d);(p/'test.c').write_text(c)
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-fsanitize=address,undefined',
        '-fno-sanitize-recover=all',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
print('Live selection activation: stopped/running/same-slot + actual RAM kit load passed.')
