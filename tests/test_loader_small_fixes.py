#!/usr/bin/env python3
"""Narrow loader regressions using extracted production C, not Python models.
LXR_BASE_REV selects git sources (4c38398 is expected red). Endpoints are
stubbed: no claim about FatFs/media timing, audio continuity or whole-TU builds.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    if os.getenv('LXR_BASE_REV'):
        return subprocess.check_output(['git', '-C', str(ROOT), 'show',
                                       os.environ['LXR_BASE_REV'] + ':' + path], text=True)
    return (ROOT / path).read_text()


def function(text, name):
    # Balanced braces, ignoring comments/strings, so disabled historical code
    # inside a function is retained for the C preprocessor.
    import re
    start = re.search(r'^(?:static )?(?:uint8_t|FRESULT) ' + name + r'\(', text, re.M).start()
    opening = text.index('{', start)
    tokens = re.finditer(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', text[opening:], re.S)
    depth = 0
    for token in tokens:
        if token.group() == '{':
            depth += 1
        elif token.group() == '}':
            depth -= 1
            if not depth:
                return text[start:opening + token.end()]
    raise AssertionError(name)


parameters = source('Core/Inc/Parameters.h')
enum_start = parameters.index('enum ParamEnums')
parameter_enum = parameters[enum_start:parameters.index('};', enum_start) + 2]

COMMON = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int FRESULT; typedef unsigned UINT; typedef int FIL; typedef int FILINFO;
#define FR_OK 0
#define FR_DISK_ERR 1
#define FR_NO_FILE 4
#define USE_SD_CARD 1
#define USE_INTERRUPT_ONLY_DURING_SAVE_PROJ 0
#define FA_OPEN_EXISTING 0
#define FA_READ 1
#define NUM_KIT_SLOTS 2
#define PROJECT_NAMES 0
#define CURRENT_PROJECT 0
#define SAVE_TYPE_PROJECT 0
#define CURRENT_KIT 1
#define SAVE_TYPE_KIT 1
#define PSTR(x) x
int menu_loadedPresetNr[2], menu_selectedPresetNr[2];
int errors[8], error_count, resets, creates, load_calls, last_clear, last_nr;
int load_result, load_warning, index_result, last_result, create_result;
void menu_showSdError(int r) { errors[error_count++]=r; }
void menu_resetSaveParameters(void) { resets++; }
int preset_createProject(int n) { assert(n==7); creates++; return create_result; }
int preset_loadLastUsedProjectNrFromSD(uint8_t *n) { *n=7; return last_result; }
'''

COMMON += parameter_enum + '\n_Static_assert(NUM_PARAMS - PAR_BEGINNING_OF_GLOBALS == 30, \"globals layout\");\n'

p = source('Core/Src/Preset/presetManager.c')
m = source('Core/Src/main.c')
u = source('Core/Src/menu/menu.c')
boot_start = m.index('#if LOAD_PROJECT_ON_BOOT', m.index('preset_loadProjectNames(i);'))
boot = m[boot_start:m.index('#else', boot_start)] + '\n#endif\n'
menu_start = u.index('case SAVE_TYPE_PROJECT:', u.index('void menu_handleLoadSaveMenu'))
# Skip the save-side case, selecting the load-side branch by its loader call.
call = u.index('res = preset_loadProject', menu_start)
menu_start = u.rfind('case SAVE_TYPE_PROJECT:', menu_start, call)
menu_end = u.index('break;', call) + len('break;')
menu = u[menu_start:menu_end]

ui = COMMON + r'''
int preset_loadProjectWithWarning(uint8_t n,uint8_t c,FRESULT *w) {
 load_calls++; last_nr=n; last_clear=c; *w=load_warning; return load_result;
}
int preset_loadProject(uint8_t n,uint8_t c) {
 FRESULT w; int r=preset_loadProjectWithWarning(n,c,&w); return r?r:w;
}
#define LOAD_PROJECT_ON_BOOT 1
void boot(void) { FRESULT res=0;
''' + boot + '\n}\nvoid menu(void) { switch(0) {\n' + menu + r'''
} }
void reset(void) {
 memset(errors,0,sizeof errors); error_count=resets=creates=load_calls=0;
 load_result=load_warning=last_result=create_result=0;
 menu_loadedPresetNr[0]=3; menu_selectedPresetNr[0]=7;
}
int main(void) {
 reset(); last_result=FR_DISK_ERR; boot();
 assert(error_count==1 && errors[0]==FR_DISK_ERR && load_calls==1);
 reset(); load_result=FR_DISK_ERR; boot();
 assert(menu_loadedPresetNr[0]==3 && error_count==1 && last_clear==0);
 reset(); load_warning=FR_DISK_ERR; boot();
 assert(menu_loadedPresetNr[0]==7 && menu_selectedPresetNr[0]==7);
 assert(error_count==1 && errors[0]==FR_DISK_ERR);
 reset(); load_result=FR_DISK_ERR; menu();
 assert(menu_loadedPresetNr[0]==3 && resets==0 && error_count==1 && last_clear==1);
 reset(); load_warning=FR_DISK_ERR; menu();
 assert(menu_loadedPresetNr[0]==7 && resets==1 && error_count==1);
 reset(); load_result=FR_NO_FILE; menu();
 assert(creates==1 && menu_loadedPresetNr[0]==7 && resets==1);
 reset(); load_result=FR_NO_FILE; create_result=FR_DISK_ERR; menu();
 assert(creates==1 && menu_loadedPresetNr[0]==3 && error_count==1);
 return 0;
}
'''

# Include the entire active project implementation, stopping only at the
# legacy #else after its final return (not at an earlier nested #else).
name = 'preset_loadProjectWithWarning' if 'FRESULT preset_loadProjectWithWarning(' in p else 'preset_loadProject'
start = p.index('FRESULT ' + name + '(')
end = p.index('\n#else\n#if USE_SD_CARD', start)
loader = p[start:end] + '\n#endif\n}\n'
wrapper = function(p, 'preset_loadProject') if name != 'preset_loadProject' else ''
globals_code = function(p, 'preset_readGlobalData') + '\n' + function(p, 'preset_loadGlobals')
real = COMMON + r'''
FIL SDFile; uint8_t activeParameters[NUM_PARAMS];
int open_result, read_result, close_result, sent, closed, skip_globals;
UINT read_bytes=30;
int preset_openFile(FIL *f,const char *n,int mode) { return skip_globals ? (strcmp(n,"glo.cfg")==0 ? FR_DISK_ERR : FR_OK) : open_result; }
int f_read(FIL *f,void *out,UINT n,UINT *got) {
 *got=read_bytes<n?read_bytes:n; memset(out,9,*got); return read_result;
}
int preset_closeFile(FIL *f) { closed++; return close_result; }
void menu_sendAllGlobals(void) {
 for(int i=PAR_BEGINNING_OF_GLOBALS;i<NUM_PARAMS;i++) assert(activeParameters[i]==9);
 assert(closed==1); sent++;
}
''' + globals_code + r'''
int lcd_process_display_interrupt; char currentFolder[32],savefileNames[16][1][16];
uint8_t mainParameters[2][NUM_PARAMS], *morphParameters;
struct { uint8_t kitNr[2]; } seq_patternSet;
int seq_activePattern, recovery_result, slot_result, next_calls;
void seq_setPerformanceBreak(int n) {} void sync_cancelPending(void) {}
int storage_recoverProject(int n) { return recovery_result; }
int sendDisplayBuffer(void) { return 0; }
void preset_clearTmpFolder(void) {} void preset_initTmpFolder(void) {}
void lcd_clear(void) {} void lcd_home(void) {} void lcd_string(const char *s) {}
void lcd_setcursor(int a,int b) {}
int f_stat(const char *s,FILINFO *f) { return 0; }
int f_mkdir(const char *s) { return 0; } int f_chdir(const char *s) { return 0; }
int preset_isNameEmpty(void *p) { return 0; }
int preset_loadDrumsetSD(int a,int b) { return slot_result; }
int preset_loadPatternSD(int a) { return slot_result; }
int preset_loadSongSD(int a) { return slot_result; }
void preset_loadDrumsetRam(int a,int b,int c) {}
void seq_copyPatternToBackupBuffer(int a) {}
int preset_saveLastUsedProjectNrToSD(int n) { return index_result; }
void seq_setNextPattern(int n) { next_calls++; }
'''
if name != 'preset_loadProject':
    real += 'FRESULT preset_loadProjectWithWarning(uint8_t,uint8_t,FRESULT*);\n'
real += wrapper + '\n' + loader
real += r'''
void reset_globals(void) {
 memset(activeParameters,3,sizeof activeParameters);
 open_result=read_result=close_result=sent=closed=0; read_bytes=30;
}
int main(void) {
 for(int fault=0;fault<4;fault++) {
  reset_globals();
  if(fault==0) read_bytes=29;
  if(fault==1) read_result=FR_DISK_ERR; /* full bytes plus error */
  if(fault==2) close_result=FR_DISK_ERR;
  if(fault==3) open_result=FR_DISK_ERR;
  assert(preset_loadGlobals()==0);
  for(int i=0;i<NUM_PARAMS;i++) assert(activeParameters[i]==3);
  assert(sent==0 && closed==(fault==3?0:1));
 }
 reset_globals(); assert(preset_loadGlobals()==1 && sent==1);
 for(int i=0;i<PAR_BEGINNING_OF_GLOBALS;i++) assert(activeParameters[i]==3);
 reset_globals(); skip_globals=1; index_result=FR_DISK_ERR;
 FRESULT warning=99;
'''
if name == 'preset_loadProject':
    # Baseline has no warning API: exercise its real activation result, which
    # must fail the new contract rather than substituting a model implementation.
    real += 'assert(preset_loadProject(7,0)==FR_OK);\n'
else:
    real += '''assert(preset_loadProjectWithWarning(7,0,&warning)==FR_OK);
 assert(warning==FR_DISK_ERR && next_calls==1);
 assert(preset_loadProject(7,0)==FR_DISK_ERR);
 recovery_result=FR_NO_FILE; warning=99;
 assert(preset_loadProjectWithWarning(7,0,&warning)==FR_NO_FILE && warning==FR_OK);
'''
real += 'return 0;\n}\n'

failures = []
with tempfile.TemporaryDirectory(prefix='lxr-loader-') as tmp:
    for label, code in [('ui', ui), ('loader_globals', real)]:
        path = Path(tmp) / (label + '.c')
        path.write_text(code)
        exe = path.with_suffix('')
        try:
            subprocess.run([os.getenv('CC', 'cc'), '-std=c11', '-g',
                            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                            '-Wno-deprecated-declarations',
                            str(path), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
            print(label + ': PASS', flush=True)
        except subprocess.CalledProcessError:
            failures.append(label)
if failures:
    raise SystemExit('FAILED: ' + ', '.join(failures))
