#!/usr/bin/env python3
"""Byte-backed FatFs endpoints around extracted production persistence/project bodies.
No physical FAT/card, DSP, timer, or whole-main simulation is claimed.
"""
from pathlib import Path
import re, os, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
s = (root/'Core/Src/Preset/presetManager.c').read_text()
def fn(name):
    m = re.search(r'^(?:static )?(?:void|uint8_t|FRESULT) '+name+r'\([^;\n]*\)\s*\{', s, re.M)
    assert m, name
    i=s.index('{',m.start())+1; depth=1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}'); i+=1
    return s[m.start():i]+'\n'
params=(root/'Core/Inc/Parameters.h').read_text()
enum=params[params.index('enum ParamEnums'):params.index('extern uint8_t')]
helpers=s[s.index('static FRESULT preset_writeResult'):s.index('unsigned char preset_projectCleanupWarning;')]
const=s[s.index('#define PRESET_LEGACY_GLOBAL_BYTES'):s.index('static void preset_applyMasterComp')]
pre=r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdlib.h>
typedef int FRESULT; typedef unsigned UINT; typedef unsigned char BYTE; typedef char TCHAR;
typedef struct {int node; unsigned pos;} FIL;
typedef int FILINFO;
#define FR_DISK_ERR 1
#define FR_OK 0
#define FR_NO_FILE 4
#define FR_DENIED 7
#define FR_INVALID_OBJECT 9
#define FA_WRITE 2
#define FA_READ 1
#define FA_CREATE_ALWAYS 8
#define FA_OPEN_EXISTING 0
#define USE_SD_CARD 1
#define USE_INTERRUPT_ONLY_DURING_SAVE_PROJ 0
#define NUM_KIT_SLOTS 2
#define NUM_PATTERN 2
#define MAX_SONG_LENGTH 4
#define SONG_END 255
#define PROJECT_NAMES 0
#define SAVE_TYPE_KIT 0
#define CURRENT_KIT 0
#define PSTR(x) x
'''
stubs=r'''
static uint8_t activeParameters[NUM_PARAMS];
static FIL SDFile;
struct Node {char path[80]; uint8_t data[1024]; unsigned len;} nodes[20];
static int count, cwd=0, openError, closeError, readCall, readFault, shortRead, shortWriteAt, writes;
static int dirError, nameError, slotError, indexError, recoverError, sends, parses, clears;
static char currentFolder[13],savefileNames[64][1][8];
static uint8_t mainParameters[1][247], *morphParameters,seq_activePattern;
static struct {uint8_t kitNr[1];} seq_patternSet;
static uint8_t menu_selectedPresetNr[1],menu_loadedPresetNr[1], lcd_process_display_interrupt;
static uint8_t seq_songData[2][4], *seq_activeSong;
static int find(const char *path){for(int i=0;i<count;i++)if(!strcmp(nodes[i].path,path))return i;return -1;}
static int put(const char *path,const void *data,unsigned n){int i=find(path);if(i<0){i=count++;strcpy(nodes[i].path,path);}memcpy(nodes[i].data,data,n);nodes[i].len=n;return i;}
static FRESULT f_open(FIL*f,const TCHAR*p,BYTE mode){
 if(openError)return openError;
 if(!strcmp(p,"prj.nfo") && nameError)return nameError;
 char path[80]; if(*p=='/')snprintf(path,sizeof path,"%s",p);else if(cwd<0)snprintf(path,sizeof path,"/tmp/%s",p);else snprintf(path,sizeof path,"/proj%02d/%s",cwd,p);
 int i=find(path);if(mode&FA_CREATE_ALWAYS)i=put(path,"",0);
 if(i<0)return FR_NO_FILE;f->node=i;f->pos=0;return FR_OK;
}
static FRESULT f_read(FIL*f,void*p,UINT n,UINT*r){
 readCall++;struct Node*t=&nodes[f->node];*r=t->len-f->pos;if(*r>n)*r=n;
 if(readCall==shortRead && *r)(*r)--;
 memcpy(p,t->data+f->pos,*r);f->pos+=*r;
 return readCall==readFault?FR_DENIED:FR_OK;
}
static FRESULT f_write(FIL*f,const void*p,UINT n,UINT*w){writes++;*w=writes==shortWriteAt?n-1:n;struct Node*t=&nodes[f->node];memcpy(t->data+f->pos,p,*w);f->pos+=*w;t->len=f->pos;return FR_OK;}
static FRESULT f_close(FIL*f){(void)f;return closeError;}
static FRESULT f_stat(const char*p,FILINFO*f){(void)p;(void)f;return FR_OK;}
static FRESULT f_mkdir(const char*p){(void)p;return FR_OK;}
static FRESULT f_chdir(const char*p){if(dirError)return dirError;if(!strcmp(p,"/tmp"))cwd=-1;else sscanf(p,"/proj%d",&cwd);return FR_OK;}
static FRESULT storage_recoverProject(uint8_t n){(void)n;return recoverError;}
static void seq_setPerformanceBreak(int x){(void)x;}
static void sync_cancelPending(void){}
static void preset_clearTmpFolder(void){clears++;}
static FRESULT preset_initTmpFolder(void){cwd=-1;return FR_OK;}
static int sendDisplayBuffer(void){return 0;}
static void HAL_Delay(int n){(void)n;}
static void lcd_clear(void){}
static void lcd_home(void){}
static void lcd_string(const char*s){(void)s;}
static void lcd_setcursor(int x,int y){(void)x;(void)y;}
static void menu_parseGlobalParam(uint16_t p,uint8_t v){assert(p>=302&&p<=305);assert(activeParameters[p]==v);parses++;}
static uint8_t dspTargets[4];
static void MainCompressor_setControls(const uint8_t v[4]){memcpy(dspTargets,v,4);}
static void menu_sendAllGlobals(void){sends++;assert(!memcmp(dspTargets,activeParameters+302,4));}
static FRESULT preset_loadDrumsetSD(uint8_t n,int m){(void)n;(void)m;return slotError?slotError:FR_NO_FILE;}
static FRESULT preset_loadPatternSD(uint8_t n){(void)n;return FR_NO_FILE;}
static FRESULT preset_loadSongSD(uint8_t n){(void)n;return FR_NO_FILE;}
static void preset_loadDrumsetRam(int n,int m,int a){(void)n;(void)m;(void)a;}
static void seq_copyPatternToBackupBuffer(int n){(void)n;}
static FRESULT preset_saveLastUsedProjectNrToSD(uint8_t n){(void)n;return indexError;}
static void seq_setNextPattern(int n){(void)n;}
static int preset_isNameEmpty(char*s){return !*s;}
static void seq_clearPattern(int n){(void)n;}
static void preset_init(int n){(void)n;}
static uint8_t getNumModTargets(void){return 64;}
static void preset_sendDrumsetParameters(void){}
'''
body=const+''.join(fn(n) for n in ['preset_applyMasterComp','preset_writeGlobalData','preset_saveGlobals','preset_readGlobalData','preset_loadGlobals','preset_loadDefaultGlobals','preset_createGlobals','preset_createProject','preset_loadProject','loadTmpFolderFiles','preset_LoadTmpKit'])
main=(root/'Core/Src/main.c').read_text()
# Compile the literal boot call seams, not a replacement loader or fixed boot result.
a=main.index('uint8_t lastUsedProject;')
b=main.index('if(res != FR_OK)', a)
selected_boot=main[a:b]
assert 'preset_loadProject(lastUsedProject, 0);' in selected_boot
no_card='copyClear_clearCurrentPattern();\n  preset_init(0);\n  preset_loadDefaultGlobals();'
assert no_card in main
boot_helpers = "static void preset_loadLastUsedProjectNrFromSD(uint8_t *p){*p=1;}\nstatic void copyClear_clearCurrentPattern(void){}\n"
boot_helpers += 'static void selectedBoot(void){'+selected_boot+'}\n'
boot_helpers += 'static void noCardBoot(void){'+no_card+'}\n'
a=main.index('if(!preset_loadGlobals())');i=main.index('{',a)+1;depth=1
while depth:
    depth+=(main[i]=='{')-(main[i]=='}');i+=1
boot_helpers += 'static void earlyBoot(void){'+main[a:i]+'}\n'
# Current boot never loads tmp globals; inspect the real overlay implementations.
for name in ('loadTmpFolderFiles','preset_LoadTmpKit','preset_LoadTmpPat'):
    assert 'preset_loadGlobals' not in fn(name)
assert 'loadTmpFolderFiles();' in main and 'preset_LoadTmpKit();' in main and 'preset_LoadTmpPat();' in main
tests=r'''
static const uint8_t defaults[4]={30,0,17,20}, selected[4]={48,19,30,34};
static uint8_t fixture[80];
static void check(const uint8_t*v){assert(activeParameters[302]==v[0]);assert(activeParameters[303]==v[1]);assert(activeParameters[304]==v[2]);assert(activeParameters[305]==v[3]);assert(!memcmp(dspTargets,v,4));}
static void reset(void){openError=closeError=readFault=shortRead=shortWriteAt=readCall=writes=0;dirError=nameError=slotError=indexError=recoverError=0;preset_writeOpen=preset_writeSession=0;cwd=0;}
static void seed(unsigned len){put("/proj00/glo.cfg",fixture,len);readCall=0;preset_applyMasterComp(selected);}
int main(void){
 assert(PAR_BEGINNING_OF_GLOBALS==272 && MASTER_COMP_THRESHOLD==302 && NUM_PARAMS==306);
 for(int i=0;i<30;i++)fixture[i]=(uint8_t)(i+11);
 memcpy(fixture+30,"MC\1\0",4);memcpy(fixture+34,selected,4);
 // Every length, including oversize and exact-30 ambiguity; prefix remains direct.
 for(unsigned n=0;n<=70;n++){
  reset();seed(n);int r=preset_loadGlobals();assert(r==(n>=30));check(n==38?selected:defaults);
  assert(!memcmp(activeParameters+272,fixture,n<30?n:30));
 }
 // Each signature byte and each out-of-range control rejects whole candidate.
 for(int j=30;j<38;j++){
  uint8_t old=fixture[j];fixture[j]=255;reset();seed(38);assert(preset_loadGlobals());check(defaults);fixture[j]=old;
 }
 // Exhaustive acceptance for every byte in each field, no partial candidate.
 const unsigned maxima[4]={48,19,30,34};
 for(int field=0;field<4;field++)for(unsigned v=0;v<256;v++){
  uint8_t expected[4];memcpy(expected,selected,4);expected[field]=v;
  fixture[34+field]=v;reset();seed(38);assert(preset_loadGlobals());
  check(v<=maxima[field]?expected:defaults);fixture[34+field]=selected[field];
 }
 // Valid min/max encodings and defaults round trip all 30 legacy fields.
 for(int mode=0;mode<3;mode++){
  reset();memcpy(activeParameters+272,fixture,30);
  const uint8_t zero[4]={0,0,0,0};const uint8_t*v=mode==0?zero:mode==1?defaults:selected;
  preset_applyMasterComp(v);assert(preset_saveGlobals()==FR_OK);
  struct Node*t=&nodes[find("/proj00/glo.cfg")];assert(t->len==38);assert(!memcmp(t->data,fixture,30));assert(!memcmp(t->data+30,"MC\1\0",4));assert(!memcmp(t->data+34,v,4));
  preset_applyMasterComp(selected);readCall=0;assert(preset_loadGlobals());check(v);
  // Old reader ignores suffix; old rewrite retains prefix and drops suffix.
  uint8_t old[30];FIL f;UINT n;assert(f_open(&f,"glo.cfg",FA_READ)==0);assert(f_read(&f,old,30,&n)==0&&n==30);assert(!memcmp(old,fixture,30));
  put("/proj00/glo.cfg",old,30);readCall=0;assert(preset_loadGlobals());check(defaults);
 }
 for(int phase=1;phase<=2;phase++){
  reset();seed(38);readFault=phase;assert(preset_loadGlobals());check(defaults);
  reset();seed(38);shortRead=phase;assert(preset_loadGlobals()==(phase==2));check(defaults);
 }
 reset();seed(38);closeError=7;assert(preset_loadGlobals());check(defaults);
 reset();seed(38);openError=7;assert(!preset_loadGlobals());check(defaults);
 // First prefix or trailer write fault propagates; failed close also propagates.
 for(int n=1;n<=31;n++){reset();shortWriteAt=n;assert(preset_saveGlobals()==FR_DENIED);assert(writes==n);}
 reset();closeError=7;assert(preset_saveGlobals()==7);assert(preset_writeOpen);closeError=0;
 reset();preset_applyMasterComp(selected);preset_loadDefaultGlobals();check(defaults);
 preset_applyMasterComp(selected);assert(preset_createProject(0)==0);check(defaults);
 // Actual full project loader: failure before globals retains A; later errors adopt B.
 put("/proj01/prj.nfo","ProjectB",8);put("/proj01/glo.cfg",fixture,30);
 for(int phase=0;phase<3;phase++){
  reset();preset_applyMasterComp(selected);if(phase==0)recoverError=7;if(phase==1)dirError=7;if(phase==2)nameError=7;
  assert(preset_loadProject(1,1)==7);check(selected);
 }
 reset();assert(preset_loadProject(1,1)==0);check(defaults);assert(cwd==-1);
 put("/proj01/glo.cfg",fixture,38);
 reset();slotError=7;assert(preset_loadProject(1,1)==7);check(selected);
 reset();indexError=7;assert(preset_loadProject(1,1)==7);check(selected);
 // Missing globals at reached boundary: return ignored by existing project body.
 strcpy(nodes[find("/proj01/glo.cfg")].path,"/removed");reset();assert(preset_loadProject(1,1)==0);check(defaults);
 // Target B valid controls, partial suffix, and prefix truncation.
 const uint8_t middle[4]={12,3,9,8};memcpy(fixture+34,middle,4);
 put("/proj01/glo.cfg",fixture,38);reset();assert(preset_loadProject(1,0)==0);check(middle);
 put("/proj01/glo.cfg",fixture,35);reset();assert(preset_loadProject(1,0)==0);check(defaults);
 put("/proj01/glo.cfg",fixture,12);reset();assert(preset_loadProject(1,0)==0);check(defaults);
 strcpy(nodes[find("/proj01/glo.cfg")].path,"/removed2");memcpy(fixture+34,selected,4);
 // Literal early boot fallback: old file must not be rewritten, missing file creates bypass.
 reset();seed(30);earlyBoot();assert(writes==0);check(defaults);
 strcpy(nodes[find("/proj00/glo.cfg")].path,"/removed3");reset();earlyBoot();check(defaults);
 assert(nodes[find("/proj00/glo.cfg")].len==38);
 // Selected boot project invocation preserves tmp, supersedes early proj00.
 reset();seed(38);assert(preset_loadGlobals());int before=clears;
 selectedBoot();assert(clears==before);check(defaults);
 preset_applyMasterComp(selected);noCardBoot();check(defaults);
 // Actual tmp-numbered loop and active-kit overlay leave project globals alone.
 reset();cwd=-1;put("/tmp/glo.cfg",fixture,38);preset_applyMasterComp(defaults);
 assert(loadTmpFolderFiles()==0);check(defaults);
 uint8_t kit[248]={0};put("/tmp/tmp.snd",kit,sizeof kit);
 assert(preset_LoadTmpKit()==0);check(defaults);
 // Direct globals /tmp save/load is isolated from saved project.
 reset();cwd=-1;preset_applyMasterComp(selected);assert(preset_saveGlobals()==0);
 preset_applyMasterComp(defaults);assert(preset_loadGlobals());check(selected);
 assert(nodes[find("/proj00/glo.cfg")].len==38);
 // Direct save truncation is not transactional; legacy-complete truncation bypasses.
 writes=0;shortWriteAt=31;assert(preset_saveGlobals()==7);assert(nodes[find("/tmp/glo.cfg")].len==37);
 shortWriteAt=0;readCall=0;assert(preset_loadGlobals());check(defaults);
 puts("Master compressor byte persistence/project boundary tests passed");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)/'test.c';exe=Path(tmp)/'test';p.write_text(pre+enum+stubs+helpers+body+boot_helpers+tests)
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Werror','-Wno-misleading-indentation','-Wno-deprecated-declarations','-fsanitize=address,undefined',str(p),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
