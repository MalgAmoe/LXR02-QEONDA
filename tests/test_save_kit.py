#!/usr/bin/env python3
"""Execute production Save Kit/Morph branches and RAM saver; UI/IRQ endpoints modeled."""
from pathlib import Path
import os, re, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
menu = (root/'Core/Src/menu/menu.c').read_text()
a = menu.index('case SAVE_TYPE_KIT:', menu.index('case SAVE_STATE_OK:'))
b = menu.index('case SAVE_TYPE_GLO:', a)
branch = menu[a:b]
preset = (root/'Core/Src/Preset/presetManager.c').read_text()
a = preset.index('void preset_saveDrumsetRam(')
b = preset.index('//----------------------------------------------------', a)
saver = preset[a:b]
c = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define SAVE_TYPE_KIT 0
#define SAVE_TYPE_MORPH 1
#define CURRENT_KIT 0
#define KIT_SAVE_PAGE_OK 9
#define END_OF_SOUND_PARAMETERS 32
#define PAR_VEL_DEST_1 2
#define PAR_VEL_DEST_6 7
#define PAR_TARGET_LFO1 8
#define PAR_TARGET_LFO6 13
#define PAR_VOICE_LFO1 14
#define PAR_VOICE_LFO6 19
#define PAR_MORPH 31
static uint8_t mainParameters[64][32],activeParameters[32];
static uint8_t menu_selectedPresetNr[2],menu_loadedPresetNr[2],seq_activePattern;
static struct {uint8_t kitNr[64];} seq_patternSet;
static struct {uint8_t kitNr;} patternBackupBuffer;
static unsigned mask, saves, repaints;
static int menu_activePage,sucessTimer,systick_ticks=42;
static unsigned __get_PRIMASK(void){return mask;}
static void __disable_irq(void){mask=1;}
static void __set_PRIMASK(unsigned m){mask=m;}
static void menu_repaint(void){repaints++;}
static uint8_t preset_getMorphValue(unsigned i,unsigned morph){return i+morph;}
'''+saver+r'''
static void save(unsigned category){switch(category){
'''+branch+r'''}}
int main(void){
 for(unsigned initialMask=0;initialMask<2;initialMask++)
 for(unsigned pat=0;pat<64;pat++)
 for(unsigned same=0;same<2;same++){
  memset(seq_patternSet.kitNr,5,64);patternBackupBuffer.kitNr=5;
  memset(activeParameters,23,32);memset(mainParameters,0,sizeof mainParameters);
  menu_loadedPresetNr[0]=5;menu_loadedPresetNr[1]=17;
  seq_activePattern=pat;menu_selectedPresetNr[0]=same?5:63;
  mask=initialMask;save(SAVE_TYPE_KIT);
  assert(mask==initialMask&&menu_loadedPresetNr[0]==menu_selectedPresetNr[0]);
  assert(!memcmp(mainParameters[menu_selectedPresetNr[0]],activeParameters,32));
  for(unsigned i=0;i<64;i++)
   assert(seq_patternSet.kitNr[i]==(!USE_PATTERN_EDIT_BUFFER&&i==pat?menu_selectedPresetNr[0]:5));
  assert(patternBackupBuffer.kitNr==(USE_PATTERN_EDIT_BUFFER?menu_selectedPresetNr[0]:5));
  assert(menu_activePage==KIT_SAVE_PAGE_OK&&sucessTimer==42);
  uint8_t before[64];memcpy(before,seq_patternSet.kitNr,64);
  unsigned loaded=menu_loadedPresetNr[0],backup=patternBackupBuffer.kitNr;
  menu_selectedPresetNr[1]=27;save(SAVE_TYPE_MORPH);
  assert(!memcmp(before,seq_patternSet.kitNr,64));
  assert(patternBackupBuffer.kitNr==backup&&menu_loadedPresetNr[0]==loaded&&menu_loadedPresetNr[1]==17);
  assert(mainParameters[27][0]==23&&mainParameters[27][2]==23);
  /* Shared saver (including Save Project callers) must not relink patterns. */
  preset_saveDrumsetRam(11,0);
  assert(!memcmp(before,seq_patternSet.kitNr,64)&&patternBackupBuffer.kitNr==backup);
 }
}
'''
with tempfile.TemporaryDirectory() as d:
    p = Path(d); (p/'test.c').write_text(c)
    for edit_buffer in (0, 1):
        subprocess.run([os.environ.get('CC','clang'), '-std=c11', '-O2',
                        '-fsanitize=address,undefined', f'-DUSE_PATTERN_EDIT_BUFFER={edit_buffer}',
                        str(p/'test.c'), '-o', str(p/'test')], check=True)
        subprocess.run([str(p/'test')], check=True)
print('Production Save Kit/Morph and shared saver passed (both edit-buffer modes).')
