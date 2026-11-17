#!/usr/bin/env python3
"""Exercise actual break/trigger/roll function bodies with deterministic stubs.
Mask generation, synth/MIDI endpoints and panel dispatch are not simulated hardware.
"""
from pathlib import Path
import subprocess
import tempfile
import os
root = Path(__file__).resolve().parents[1]
seq = (root/'Core/Src/Soundengine/Sequencer/sequencer.c').read_text()
panel = (root/'Core/Src/buttonHandler.c').read_text()
def function(text, name):
    # Match the definition rather than an earlier call/prototype.
    import re
    m = re.search(r'^(?:static )?(?:void|uint8_t) '+name+r'\([^;\n]*\)\n\{', text, re.M)
    assert m, name
    start = m.start()
    pos = text.index('{', start)+1
    depth = 1
    while depth:
        depth += (text[pos]=='{') - (text[pos]=='}')
        pos += 1
    return text[start:pos]+'\n'
c = r'''
#include <stdint.h>
#include <assert.h>
#define NUM_TRACKS 7
#define STEP_CURRENT 0
#define STEP_NEXT 1
#define STEP_PREV 2
#define STEP_VOLUME_MASK 127
#define ROLL_VOLUME 100
#define SEQ_DEFAULT_NOTE 60
#define SELECT_MODE_PERF 8
static volatile uint8_t seq_performanceBreak;
static uint8_t seq_running=1,seq_mutedTracks,seq_activePattern;
static int8_t seq_stepIndex[7];
static uint8_t lastWasNoteOn[7],chokeCurrent,chokeNext;
static uint8_t seq_rollState,seq_rollRate;
static uint8_t performanceBreakButtonHeld;
static struct {uint8_t selectButtonMode;} buttonHandler_stateMemory;
struct Step {uint8_t volume,note;};
static struct {uint8_t length[1][7];struct Step seq_subStepPattern[1][7][16];} seq_patternSet;
static unsigned hits,offs,recordings,led,ledWrites;
static uint32_t masks[3];
static uint8_t led_idx2StepLed(uint8_t b) {assert(b==7);return b;}
static void led_setValue(uint8_t v,uint8_t b) {assert(b==7);led=v;ledWrites++;}
static uint32_t seq_getShiftFlamPattern(uint8_t t,uint8_t s,uint8_t which)
{(void)t;(void)s;return masks[which];}
static void seq_triggerVoice(uint8_t t,uint8_t v,uint8_t n)
{(void)t;(void)v;(void)n;hits++;}
static void voiceControl_noteOff(uint8_t t) {(void)t;offs++;}
static uint8_t seq_isRunning(void) {return seq_running;}
static void seq_addNote(uint8_t t,uint8_t v,uint8_t n)
{(void)t;(void)v;(void)n;recordings++;}
'''
c += r'''
/* Slip inactive adapter: this fixture isolates break gating, not slip mapping. */
static void seq_slipSync(void) {}
static void seq_slipApplyWrites(void) {}
static void seq_slipClear(void) {}
static uint8_t seq_slipSource(uint8_t t,uint8_t r) {
 unsigned n=seq_patternSet.length[0][t];
 return (seq_stepIndex[t]+n+(r==STEP_PREV?-1:r==STEP_NEXT?1:0))%n;
}
static void seq_triggerSequenced(uint8_t t,uint8_t v,uint8_t n,uint8_t s)
{(void)s;seq_triggerVoice(t,v,n);}
'''
for name in ('seq_setPerformanceBreak' ,'seq_processFlam','seq_setRoll'):
    c += function(seq,name)
for name in ('buttonHandler_releasePerformanceBreak','buttonHandler_setMode'):
    c += function(panel,name)
c += r'''
int main(void) {
 for(unsigned t=0;t<7;t++) seq_patternSet.length[0][t]=16;
 seq_setPerformanceBreak(0);assert(ledWrites==0); /* don't alter normal step LED */
 /* Test current, early-next and late-previous hits, at every flam sub-tick. */
 for(unsigned source=0;source<3;source++) {
  for(unsigned tick=0;tick<24;tick++) {
   for(unsigned j=0;j<3;j++) masks[j]=0;
   masks[source]=1u<<(23-tick);
   chokeCurrent=chokeNext=0;hits=0;offs=0;
   seq_setPerformanceBreak(0);seq_processFlam(tick);assert(hits==7);
   seq_setPerformanceBreak(1);assert(led==1);
   seq_processFlam(tick);assert(hits==7 && offs==7);
   seq_processFlam(tick);assert(hits==7 && offs==7);
   assert(seq_mutedTracks==0 && seq_running==1);
   seq_setPerformanceBreak(0);chokeCurrent=chokeNext=0;
   seq_processFlam(tick);assert(hits==14); /* current position, not replay */
  }
 }
 /* Overlapping masks: next wins; break suppresses all eligible sources. */
 for(unsigned j=0;j<3;j++) masks[j]=1u<<23;
 hits=0;seq_setPerformanceBreak(0);seq_processFlam(0);assert(hits==7);
 seq_setPerformanceBreak(1);seq_processFlam(0);assert(hits==7);
 seq_setPerformanceBreak(0);seq_processFlam(0);assert(hits==14);
 for(unsigned t=0;t<7;t++) seq_stepIndex[t]=-1;
 unsigned negativeBefore=hits;seq_processFlam(0);assert(hits==negativeBefore);
 for(unsigned t=0;t<7;t++) seq_stepIndex[t]=0;
 /* Manual one-shot and stopped rolls remain live; recording path preserved. */
 seq_setPerformanceBreak(1);seq_rollRate=0xff;
 unsigned before=hits;seq_setRoll(2,1);assert(hits==before+1 && recordings==1);
 seq_setRoll(2,0);assert(!(seq_rollState & 4));
 seq_running=0;seq_rollRate=1;seq_setRoll(3,1);
 assert(hits==before+2 && recordings==2);
 seq_running=1;
 seq_mutedTracks=0x55;seq_processFlam(0);assert(seq_mutedTracks==0x55);
 /* Event ownership survives modifier/mode changes; wrong button cannot release. */
 performanceBreakButtonHeld=1;
 assert(!buttonHandler_releasePerformanceBreak(6));assert(seq_performanceBreak);
 buttonHandler_setMode(SELECT_MODE_PERF);assert(seq_performanceBreak);
 buttonHandler_setMode(1);assert(!seq_performanceBreak && !led);
 assert(buttonHandler_releasePerformanceBreak(7));assert(!performanceBreakButtonHeld);
 assert(!buttonHandler_releasePerformanceBreak(7));
 performanceBreakButtonHeld=1;seq_setPerformanceBreak(1);
 assert(buttonHandler_releasePerformanceBreak(7));assert(!seq_performanceBreak);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)/'break.c';exe=Path(tmp)/'break'
    p.write_text(c)
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Werror',
                    '-fsanitize=address,undefined',str(p),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
release=panel[panel.index('static void buttonHandler_seqButtonReleased(uint8_t seqButtonPressed)\n{'):][:5000]
assert release.index('buttonHandler_releasePerformanceBreak') < release.index('buttonHandler_getShift')
assert release.index('buttonHandler_releasePerformanceBreak') < release.index('buttonHandler_getLoad')
assert 'if(!isRunning) seq_setPerformanceBreak(0);' in function(seq,'seq_setRunning')
preset=(root/'Core/Src/Preset/presetManager.c').read_text()
assert 'seq_setPerformanceBreak(0);' in preset[preset.index('FRESULT preset_loadProject(uint8_t presetNr, uint8_t clearTmp)\n{'):][:500]
# The shared trigger and repeating roll code must not suppress manual or incoming notes.
assert 'seq_performanceBreak' not in seq[seq.index('void seq_triggerVoice('):seq.index('void seq_triggerVoice(')+3500]
assert 'seq_performanceBreak' not in function(seq,'seq_setRoll')
print('Performance break: real function bodies pass with stubbed masks/output; panel dispatch order guards pass.')
