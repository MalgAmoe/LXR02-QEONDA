#!/usr/bin/env python3
"""Real project API bodies + production SafeStorage/stream/codec, byte-backed FS.
Engine/UI/timer endpoints are seams; not physical FAT, audio or power-fail proof.
"""
from pathlib import Path
import os, re, subprocess, tempfile, sys
root = Path(__file__).resolve().parents[1]
s = (root/'Core/Src/Preset/presetManager.c').read_text()
def fn(name):
    m = re.search(r'^(?:static )?(?:void|uint8_t|FRESULT|ProjectCodecData) '+name+r'\([^;\n]*\)\s*\{', s, re.M)
    assert m, name
    i=s.index('{',m.start())+1; depth=1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}'); i+=1
    return s[m.start():i]+'\n'
pre = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "Preset/ProjectCodec.h"
#include "Preset/SafeStorage.h"
#define PSTR(x) x
#define PROJECT_NAMES 3
#define KIT_NAMES 0
#define PATTERN_NAMES 1
#define SONG_NAMES 2
#define SAVE_TYPE_KIT 0
#define CURRENT_KIT 0
static FIL SDFile;
uint8_t activeParameters[NUM_PARAMS], mainParameters[NUM_KIT_SLOTS][END_OF_SOUND_PARAMETERS];
uint8_t *morphParameters;
PatternSet seq_patternSet;
uint8_t seq_songData[NUM_KIT_SLOTS][MAX_SONG_LENGTH], *seq_activeSong, seq_activePattern;
static char savefileNames[64][4][8];
static uint8_t menu_loadedPresetNr[6], menu_selectedPresetNr[6], lcd_process_display_interrupt=1;
static unsigned audioDepth, audioBegins, audioEnds, backup, sends, running=1;
static uint8_t targets[4];
static uint8_t soundengine_backgroundAudioBegin(void){audioBegins++;return ++audioDepth==1;}
static void soundengine_backgroundAudioEnd(uint8_t b){(void)b;assert(audioDepth);audioDepth--;audioEnds++;}
static void MainCompressor_setControls(const uint8_t *v){memcpy(targets,v,4);}
static void menu_sendAllGlobals(void){sends++;}
static void menu_parseGlobalParam(unsigned p,uint8_t v){activeParameters[p]=v;}
void seq_slipClear(void){}
void seq_setPerformanceBreak(uint8_t v){assert(!v);}
static void sync_cancelPending(void){}
void seq_copyPatternToBackupBuffer(uint8_t p){(void)p;backup++;}
void seq_setNextPattern(uint8_t p){(void)p;}
void seq_copyPattern(uint8_t a,uint8_t b){seq_patternSet.used[b]=seq_patternSet.used[a];}
void seq_clearPattern(uint8_t p){seq_patternSet.used[p]=0;}
static void preset_init(uint8_t p){memset(mainParameters[p],23,END_OF_SOUND_PARAMETERS);memcpy(savefileNames[p][0],"Init",5);}
static void preset_loadDrumsetRam(uint8_t p,uint8_t m,uint8_t immediate){assert(!m&&immediate);memcpy(activeParameters,mainParameters[p],END_OF_SOUND_PARAMETERS);}
static uint8_t getNumModTargets(void){return 64;}
static uint8_t preset_getMorphValue(uint16_t i,uint8_t m){(void)m;return activeParameters[i];}
static void lcd_clear(void){} static void lcd_home(void){}
static void lcd_string(const char *s){(void)s;} static void lcd_setcursor(int a,int b){(void)a;(void)b;}
static int sendDisplayBuffer(void){return 0;}
struct Node {char path[80];uint8_t data[PROJECT_CODEC_FILE_BYTES+1];unsigned len;uint8_t dir;};
static struct Node nodes[16];
static int count, openNode=-1;
static unsigned cursor, operations, failAt, writes, shortAt, readFailAt, reads;
static uint8_t closeError;
static char wd[80]="/";
static FRESULT fault(void){return ++operations==failAt?FR_DISK_ERR:FR_OK;}
static int find(const char *p){for(int i=0;i<count;i++)if(!strcmp(nodes[i].path,p))return i;return -1;}
static int put(const char *p,int dir){int i=find(p);if(i<0){for(i=0;i<count;i++)if(!nodes[i].path[0])break;if(i==count){assert(count<16);count++;}}memset(&nodes[i],0,sizeof nodes[i]);strcpy(nodes[i].path,p);nodes[i].dir=dir;return i;}
FRESULT f_open(FIL *f,const TCHAR *p,BYTE mode){
 FRESULT r=fault();if(r)return r;assert(openNode<0);char path[80];
 if(*p=='/')snprintf(path,80,"%s",p);else snprintf(path,80,"%s/%s",wd,p);
 // FatFs distinguishes an absent parent directory from an absent leaf.
 char parent[80];strcpy(parent,path);char *slash=strrchr(parent,'/');
 if(slash && slash!=parent){*slash=0;if(find(parent)<0)return FR_NO_PATH;}
 int n=find(path);if(mode&FA_CREATE_ALWAYS)n=put(path,0);if(n<0)return FR_NO_FILE;
 openNode=n;cursor=0;f->obj.objsize=nodes[n].len;return FR_OK;
}
FRESULT f_close(FIL *f){(void)f;FRESULT r=fault();if(r)return r;if(closeError)return FR_DISK_ERR;assert(openNode>=0);openNode=-1;return FR_OK;}
FRESULT f_read(FIL *f,void *p,UINT n,UINT *done){(void)f;assert(openNode>=0);reads++;*done=0;FRESULT r=fault();if(r)return r;if(reads==readFailAt)return FR_DISK_ERR;struct Node *t=&nodes[openNode];if(n>t->len-cursor)n=t->len-cursor;memcpy(p,t->data+cursor,n);cursor+=n;*done=n;return FR_OK;}
FRESULT f_write(FIL *f,const void *p,UINT n,UINT *done){assert(openNode>=0);writes++;*done=0;FRESULT r=fault();if(r)return r;if(writes==shortAt)n--;assert(cursor+n<=PROJECT_CODEC_FILE_BYTES+1);struct Node *t=&nodes[openNode];memcpy(t->data+cursor,p,n);cursor+=n;t->len=cursor;f->obj.objsize=cursor;*done=n;return FR_OK;}
FRESULT f_stat(const TCHAR *p,FILINFO *f){FRESULT r=fault();if(r)return r;int i=find(p);if(i<0)return FR_NO_FILE;memset(f,0,sizeof *f);f->fattrib=nodes[i].dir?AM_DIR:0;return FR_OK;}
FRESULT f_chdir(const TCHAR *p){FRESULT r=fault();if(r)return r;if(strcmp(p,"/")&&find(p)<0)return FR_NO_PATH;strcpy(wd,p);return FR_OK;}
FRESULT f_mkdir(const TCHAR *p){FRESULT r=fault();if(r)return r;if(find(p)>=0)return FR_EXIST;put(p,1);return FR_OK;}
FRESULT f_rename(const TCHAR *a,const TCHAR *b){FRESULT r=fault();if(r)return r;if(find(a)<0)return FR_NO_FILE;if(find(b)>=0)return FR_EXIST;unsigned n=strlen(a);for(int i=0;i<count;i++)if(!strncmp(nodes[i].path,a,n)&&(nodes[i].path[n]==0||nodes[i].path[n]=='/')){char tail[80];strcpy(tail,nodes[i].path+n);snprintf(nodes[i].path,80,"%s%s",b,tail);}return FR_OK;}
static char dirPath[80];static unsigned dirCursor;
FRESULT f_opendir(DIR *d,const TCHAR *p){(void)d;FRESULT r=fault();if(r)return r;if(openNode>=0)return FR_TOO_MANY_OPEN_FILES;if(find(p)<0)return FR_NO_PATH;strcpy(dirPath,p);dirCursor=0;return FR_OK;}
FRESULT f_readdir(DIR *d,FILINFO *f){(void)d;FRESULT r=fault();if(r)return r;memset(f,0,sizeof *f);unsigned n=strlen(dirPath);while(dirCursor<(unsigned)count){struct Node *t=&nodes[dirCursor++];if(!strncmp(t->path,dirPath,n)&&t->path[n]=='/'){strcpy(f->fname,t->path+n+1);f->fattrib=t->dir?AM_DIR:0;break;}}return FR_OK;}
FRESULT f_closedir(DIR *d){(void)d;return fault();}
FRESULT f_unlink(const TCHAR *p){FRESULT r=fault();if(r)return r;int i=find(p);if(i<0)return FR_NO_FILE;if(i==openNode)return FR_LOCKED;nodes[i].path[0]=0;return FR_OK;}
'''
# Run the literal shuffle dispatch branches; UART framing is a synchronous seam.
menu_source=(root/'Core/Src/menu/menu.c').read_text()
cortex_source=(root/'Core/Src/Soundengine/MIDI/CortexParser.c').read_text()
def shuffle_case(source,label):
    start=source.index('case '+label+':')
    return source[start:source.index('break;',start)+len('break;')]
shuffle = r'''
#define SEQ_CC 1
#define SEQ_SHUFFLE 0x25
#define FRONT_SEQ_SHUFFLE SEQ_SHUFFLE
static float seq_shuffle;
void seq_setShuffle(float value){seq_shuffle=value;}
static struct {uint8_t data2;} cortex_midiMsg;
static void frontPanel_sendData(uint8_t status,uint8_t cc,uint8_t value){
 assert(status==SEQ_CC);cortex_midiMsg.data2=value;switch(cc){
'''+shuffle_case(cortex_source,'FRONT_SEQ_SHUFFLE')+r'''}}
static void editShuffle(uint8_t value){
 // Parameter storage is the UI edit seam; execute production global dispatch.
 activeParameters[PAR_SHUFFLE]=value;
 switch(PAR_SHUFFLE){
'''+shuffle_case(menu_source,'PAR_SHUFFLE')+r'''}}
'''
helpers=s[s.index('static FRESULT preset_writeResult'):s.index('unsigned char preset_projectCleanupWarning;')]
body='unsigned char preset_projectCleanupWarning, preset_fileCleanupWarning;\n'
body+='static const uint8_t preset_masterCompDefaults[4]={36,0,17,20};\n'
body+=''.join(fn(n) for n in ['preset_applyMasterComp','preset_saveDrumsetRam','preset_savePatternRAM','preset_saveDrumsetSD','preset_savePatternSD','preset_saveSongSD','preset_saveGlobals','preset_loadGlobals','preset_loadDefaultGlobals','preset_loadLastUsedProjectNrFromSD','preset_saveLastUsedProjectNrToSD','preset_createProject'])
body+='static uint8_t preset_projectSlot, preset_projectCompressor[4];\nstatic ProjectStream preset_projectStream;\n'
body+=''.join(fn(n) for n in ['preset_normalizeKit','preset_projectData','preset_writeProjectFiles','preset_saveProject','preset_loadProject','preset_loadProjectNames'])
body+=fn('preset_bootProject')
tests=r'''
static void reset(void){count=0;openNode=-1;operations=failAt=writes=shortAt=reads=readFailAt=0;closeError=0;preset_writeOpen=preset_writeSession=0;audioDepth=audioBegins=audioEnds=0;strcpy(wd,"/");memset(activeParameters,0,sizeof activeParameters);memset(mainParameters,0,sizeof mainParameters);memset(&seq_patternSet,0,sizeof seq_patternSet);memset(seq_songData,0,sizeof seq_songData);memset(savefileNames,0,sizeof savefileNames);menu_loadedPresetNr[0]=7;seq_activePattern=3;}
static void seed(void){
 for(unsigned p=0;p<64;p++){memset(mainParameters[p],p,END_OF_SOUND_PARAMETERS);memset(seq_songData[p],p,MAX_SONG_LENGTH);seq_patternSet.used[p]=p&1;seq_patternSet.kitNr[p]=p;seq_patternSet.length[p][0]=64;}
 memset(activeParameters,99,END_OF_SOUND_PARAMETERS);activeParameters[PAR_PATTERN_MODE]=0;activeParameters[PAR_BPM]=123;
 const uint8_t comp[4]={48,19,30,34};preset_applyMasterComp(comp);memcpy(savefileNames[1][PROJECT_NAMES],"TESTNAME",8);
 mainParameters[63][PAR_FX_DRY_WET]=255;mainParameters[63][PAR_VEL_DEST_1]=255;
 seq_patternSet.seq_subStepPattern[63][6][63].param2Val=181;seq_patternSet.seq_mainSteps[3][63][6]=0xabcd;
}
static void old(void){put("/proj01",1);int i=put("/proj01/project.qpr",0);memcpy(nodes[i].data,"OLD",3);nodes[i].len=3;}
static int oldAt(const char *p){int i=find(p);return i>=0&&nodes[i].len==3&&!memcmp(nodes[i].data,"OLD",3);}
static int newAt(const char *p){int i=find(p);return i>=0&&nodes[i].len==PROJECT_CODEC_FILE_BYTES&&!memcmp(nodes[i].data,"QEONDAPR",8);}
static void roundtrip(void){
 reset();
 assert(preset_loadProject(1,0)==FR_NO_PATH);
 put("/proj01",1);assert(preset_loadProject(1,0)==FR_NO_FILE);
 reset();seed();unsigned before=operations;
 assert(preset_saveGlobals()==FR_OK);assert(preset_saveDrumsetSD(9,0)==FR_OK);assert(mainParameters[9][0]==99);
 assert(preset_savePatternSD(3)==FR_OK&&backup);assert(preset_saveSongSD(4)==FR_OK);assert(operations==before);
 // Live edit, no pad-save: active slot differs from the viewed bank/slot.
 editShuffle(73);assert(seq_shuffle==73/127.f);seq_patternSet.shuffle[3]=11;seq_patternSet.shuffle[42]=29;
 assert(preset_saveProject(1)==FR_OK);assert(newAt("/proj01/project.qpr"));assert(mainParameters[7][0]==99);
 assert(seq_patternSet.shuffle[3]==73&&seq_patternSet.shuffle[42]==29);
 assert(find("/proj01/prj.nfo")<0&&find("/proj01/glo.cfg")<0&&find("/tmp")<0);assert(find("/proj.idx")>=0);
 memset(mainParameters,0,sizeof mainParameters);memset(&seq_patternSet,0,sizeof seq_patternSet);memset(seq_songData,0,sizeof seq_songData);memset(activeParameters,0,sizeof activeParameters);
 assert(preset_loadProject(1,1)==FR_OK);assert(mainParameters[7][0]==99&&mainParameters[63][0]==63);assert(activeParameters[PAR_BPM]==123);assert(mainParameters[63][PAR_FX_DRY_WET]==100&&mainParameters[63][PAR_VEL_DEST_1]==0);
 assert(seq_patternSet.shuffle[3]==73&&seq_patternSet.shuffle[42]==29);
 assert(seq_songData[63][63]==63&&seq_patternSet.used[63]==1);assert(seq_patternSet.seq_subStepPattern[63][6][63].param2Val==181&&seq_patternSet.seq_mainSteps[3][63][6]==0xabcd);
 const uint8_t expected[4]={48,19,30,34};assert(!memcmp(targets,expected,4));assert(!memcmp(activeParameters+MASTER_COMP_THRESHOLD,expected,4));
 // Name browsing uses the same single file, no slot loads or cwd changes.
 strcpy(wd,"/");preset_loadProjectNames(1);assert(!memcmp(savefileNames[1][PROJECT_NAMES],"TESTNAME",8)&&!strcmp(wd,"/"));
 // Boot ignores unsaved kit/global/pattern edits and loads the last SAVED project.
 memset(activeParameters,0,sizeof activeParameters);uint8_t slot=63;assert(preset_bootProject(&slot)==FR_OK&&slot==1&&activeParameters[PAR_BPM]==123);
 // Loading a different project must not change the saved boot selection.
 assert(preset_createProject(2)==FR_OK);assert(preset_saveProject(2)==FR_OK);assert(preset_loadProject(1,0)==FR_OK);slot=0;assert(preset_bootProject(&slot)==FR_OK&&slot==2);
 assert(running==1&&!audioDepth&&audioBegins==audioEnds&&lcd_process_display_interrupt);
 // Missing index/project means initialized RAM, never automatic disk persistence.
 reset();seq_patternSet.shuffle[63]=99;slot=255;assert(preset_bootProject(&slot)==FR_OK&&slot==0);assert(count==0&&seq_patternSet.shuffle[63]==0);assert(!memcmp(savefileNames[0][3],"Init",4));assert(seq_songData[0][0]==0&&seq_songData[63][63]==SONG_END);assert(activeParameters[MASTER_COMP_RATIO]==0&&activeParameters[PAR_BPM]==120);
 // Invalid index and incompatible length reject, without guessing legacy formats.
 int i=put("/proj.idx",0);nodes[i].data[0]=255;nodes[i].len=1;assert(preset_bootProject(&slot)==FR_INVALID_PARAMETER);
 reset();old();seed();assert(preset_loadProject(1,0)==FR_INVALID_PARAMETER);assert(activeParameters[PAR_BPM]==123&&!audioDepth);
 reset();seed();assert(preset_saveProject(1)==FR_OK);i=find("/proj01/project.qpr");nodes[i].data[0]^=1;assert(preset_loadProject(1,0)==FR_INVALID_PARAMETER);
 reset();seed();assert(preset_saveProject(1)==FR_OK);readFailAt=reads+2;assert(preset_loadProject(1,0)==FR_DISK_ERR&&!audioDepth&&lcd_process_display_interrupt);
}
static void faults(void){
 reset();seed();old();assert(preset_saveProject(1)==FR_OK);unsigned total=operations,totalWrites=writes;
 for(unsigned n=1;n<=total;n++){
  reset();seed();old();failAt=n;FRESULT r=preset_saveProject(1);
  assert(oldAt("/proj01/project.qpr")||oldAt("/proj01o/project.qpr")||newAt("/proj01/project.qpr"));
  if(r==FR_OK)assert(newAt("/proj01/project.qpr"));assert(!audioDepth&&lcd_process_display_interrupt);
  // If a read-close fault left the model handle open, this wasn't a write close.
  failAt=0;assert(preset_saveProject(1)==FR_OK);assert(newAt("/proj01/project.qpr"));
 }
 for(unsigned n=1;n<=totalWrites;n++){
  reset();seed();old();shortAt=n;FRESULT r=preset_saveProject(1);
  if(n<totalWrites){assert(r!=FR_OK&&oldAt("/proj01/project.qpr"));}
  else {assert(r==FR_OK&&preset_projectCleanupWarning&&newAt("/proj01/project.qpr"));}
  shortAt=0;assert(preset_saveProject(1)==FR_OK);
 }
 reset();seed();old();closeError=1;assert(preset_saveProject(1)!=FR_OK&&preset_writeOpen&&oldAt("/proj01/project.qpr"));
 unsigned savedWrites=writes, savedOps=operations;int owner=openNode;
 assert(preset_saveProject(1)==FR_DISK_ERR&&writes==savedWrites);
 // Only the retained close may run; no recovery/stat/directory cleanup first.
 assert(operations==savedOps+1&&preset_writeOpen&&openNode==owner);
 closeError=0;assert(preset_saveProject(1)==FR_OK);
 printf("Runtime writer: %u injected FS faults, %u short writes, retained failed close; playback state unchanged\n",total,totalWrites);
}
int main(int argc,char **argv){(void)argc;if(!strcmp(argv[1],"save"))faults();else roundtrip();return 0;}
'''
with tempfile.TemporaryDirectory(prefix='lxr-project-runtime-') as d:
    p=Path(d); c=p/'test.c';exe=p/'test';c.write_text(pre+shuffle+helpers+body+tests)
    cmd=[os.environ.get('CC','clang'),'-std=c11','-g','-O1','-Wno-unknown-pragmas','-Wno-deprecated-declarations','-fsanitize=address,undefined','-fno-sanitize-recover=all','-DLXR_HOST_TEST']
    cmd += ['-I'+str(root/q) for q in ['tests/shim','Core/Inc','FATFS/App','FATFS/Target','Middlewares/Third_Party/FatFs/src']]
    cmd += [str(c)]+[str(root/'Core/Src/Preset'/q) for q in ['SafeStorage.c','ProjectStream.c','ProjectCodec.c']]+['-o',str(exe)]
    subprocess.run(cmd,check=True)
    subprocess.run([str(exe),sys.argv[1] if len(sys.argv)>1 else 'persistence'],check=True)
