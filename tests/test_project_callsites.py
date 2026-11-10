#!/usr/bin/env python3
"""Runtime boot/control wiring guards plus literal song Save-As branch execution."""
from pathlib import Path
import os, re, subprocess, tempfile
root=Path(__file__).resolve().parents[1]
def text(p): return (root/p).read_text()
def clean(s): return re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
main,menu,panel,seq,front=(clean(text(p)) for p in ['Core/Src/main.c','Core/Src/menu/menu.c','Core/Src/buttonHandler.c','Core/Src/Soundengine/Sequencer/sequencer.c','Core/Src/frontPanelParser.c'])
for source in (main,menu,panel,seq,front):
    assert not re.search(r'\b(?:preset_(?:.*Tmp\w*|touchTimer|processTimer|loadDrumsetSD|loadPatternSD|loadSongSD|saveDrumsetSD|savePatternSD|saveSongSD)|loadTmpFolderFiles)\s*\(',source)
assert 'res = preset_bootProject(&lastUsedProject);' in main
assert 'preset_createProject(0);' in main
assert 'preset_loadProjectNames(i);' in main
assert 'preset_savePatternRAM(' in panel and 'preset_savePatternRAM(' in menu
assert 'preset_saveDrumsetRam(' in menu and 'res = preset_saveGlobals();' in menu
preset=clean(text('Core/Src/Preset/presetManager.c'))
assert preset.count('preset_saveLastUsedProjectNrToSD(presetNr)')==1
assert 'if(res == FR_OK && preset_saveLastUsedProjectNrToSD(presetNr)' in preset
# No transport stop, new lockout, or fixed wait budget in the storage implementation.
assert not re.search(r'\bseq_setRunning\s*\(',preset)
assert 'HAL_Delay(' not in preset
# Execute the actual RAM song Save-As branch, not a replacement implementation.
a=menu.index('case SAVE_TYPE_SONG:',menu.index('case SAVE_STATE_OK:'))
b=menu.index('case SAVE_TYPE_PATTERN:',a)
branch=menu[a:b]
c=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define SAVE_TYPE_SONG 0
#define CURRENT_SONG 0
#define MAX_SONG_LENGTH 64
static uint8_t seq_songData[64][64],*seq_activeSong;
static uint8_t menu_selectedPresetNr[1],menu_loadedPresetNr[1];
static void saveSong(void){switch(0){
'''+branch+r'''}}
int main(void){
 seq_activeSong=seq_songData[3];menu_selectedPresetNr[0]=61;
 for(unsigned i=0;i<64;i++)seq_activeSong[i]=i+11;
 saveSong();assert(seq_activeSong==seq_songData[61]&&menu_loadedPresetNr[0]==61);
 assert(!memcmp(seq_songData[3],seq_songData[61],64));
 seq_activeSong[63]=255;saveSong();assert(seq_songData[61][63]==255&&seq_songData[3][63]==74);
}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'test.c').write_text(c)
    subprocess.run([os.environ.get('CC','clang'),'-std=c11','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
print('Boot/control call sites: no tmp/autosave/slot IO; real song RAM Save-As passed.')

# Execute the interactive load branch with distinct missing leaf/parent errors.
a=menu.rindex('case SAVE_TYPE_PROJECT:',0,menu.index('res = preset_loadProject('))
b=menu.index('case SAVE_TYPE_GLO:',a)
branch=menu[a:b]
c=r'''
#include <assert.h>
#define SAVE_TYPE_PROJECT 0
#define SAVE_TYPE_GLO 1
#define CURRENT_PROJECT 0
#define FR_OK 0
#define FR_NO_FILE 4
#define FR_NO_PATH 5
#define FR_DISK_ERR 1
#define FR_INVALID_PARAMETER 19
typedef int FRESULT;
static int menu_selectedPresetNr[1]={42},menu_loadedPresetNr[1],result,creates,errors,resets;
static int preset_loadProject(int p,int clear){assert(p==42&&clear==1);return result;}
static int preset_createProject(int p){assert(p==42);creates++;return FR_OK;}
static void menu_showSdError(int r){assert(r==result);errors++;}
static void menu_resetSaveParameters(void){resets++;}
static void load(void){switch(0){
'''+branch+r'''}}
int main(void){int results[]={FR_NO_FILE,FR_NO_PATH,FR_DISK_ERR,FR_INVALID_PARAMETER,FR_OK};
 for(int i=0;i<5;i++){result=results[i];creates=errors=resets=0;menu_loadedPresetNr[0]=7;load();
 assert(creates==(i<2));assert(errors==(i==2||i==3));assert(resets==!errors);
 assert(menu_loadedPresetNr[0]==(errors?7:42));}
}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'test.c').write_text(c)
    subprocess.run([os.environ.get('CC','clang'),'-std=c11','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
