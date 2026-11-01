#!/usr/bin/env python3
"""One byte-backed harness: production project writer + SafeStorage promotion."""
from pathlib import Path
import os, subprocess, tempfile
p = Path(__file__).with_name('test_master_comp_persistence.py')
g = dict(__file__=str(p))
exec(compile(p.read_text().split('with tempfile.TemporaryDirectory() as tmp:')[0], str(p), 'exec'), g)
root=g['root']; fn=g['fn']
pre=g['pre'].replace('typedef int FILINFO;', '''typedef struct {unsigned char fattrib; char fname[80];} FILINFO;
typedef struct {char path[80]; unsigned cursor;} DIR;
#define AM_DIR 16
#define FR_INVALID_NAME 6
#define FR_NO_PATH 5
#define FR_EXIST 8
''')
# Reuse byte IO endpoints, replacing only directory/recovery endpoints with a
# filesystem which actually carries staged bytes across directory renames.
stubs=g['stubs']
a=stubs.index('static FRESULT f_stat('); b=stubs.index('static void seq_setPerformanceBreak',a)
stubs=stubs[:a]+stubs[b:]
stubs=stubs.replace('static void preset_clearTmpFolder(void){clears++;}', 'static FRESULT preset_clearTmpFolder(void){clears++;return FR_OK;}')
a=stubs.index(' char path[80]; if(*p');b=stubs.index(' int i=find(path);',a)
stubs=stubs[:a]+''' char path[80]; if(*p=='/')snprintf(path,sizeof path,"%s",p);else snprintf(path,sizeof path,"%s/%s",wd,p);
'''+stubs[b:]
fs=r'''
static char wd[80]="/";
static unsigned operations, failAt, renames, failRename, failRollback;
static FRESULT fault(void){return ++operations==failAt?FR_DISK_ERR:FR_OK;}
static FRESULT f_stat(const char*p,FILINFO*f){FRESULT r=fault();if(r)return r;int i=find(p);if(i<0)return FR_NO_FILE;memset(f,0,sizeof *f);f->fattrib=AM_DIR;return 0;}
static FRESULT f_chdir(const char*p){FRESULT r=fault();if(r)return r;if(strcmp(p,"/")&&find(p)<0)return FR_NO_PATH;strcpy(wd,p);return 0;}
static FRESULT f_mkdir(const char*p){FRESULT r=fault();if(r)return r;if(find(p)>=0)return FR_EXIST;put(p,"",0);return 0;}
static FRESULT f_rename(const char*a,const char*b){FRESULT r=fault();++renames;if(r||renames==failRename||(failRollback&&renames>=2))return FR_DISK_ERR;if(find(a)<0)return FR_NO_FILE;if(find(b)>=0)return FR_EXIST;unsigned n=strlen(a);for(int i=0;i<count;i++)if(!strncmp(nodes[i].path,a,n)&&(nodes[i].path[n]==0||nodes[i].path[n]=='/')){char tail[80];strcpy(tail,nodes[i].path+n);snprintf(nodes[i].path,80,"%s%s",b,tail);}return 0;}
static FRESULT f_opendir(DIR*d,const char*p){FRESULT r=fault();if(r)return r;if(find(p)<0)return FR_NO_PATH;strcpy(d->path,p);d->cursor=0;return 0;}
static FRESULT f_readdir(DIR*d,FILINFO*f){FRESULT r=fault();if(r)return r;memset(f,0,sizeof *f);unsigned n=strlen(d->path);while(d->cursor<(unsigned)count){const char*p=nodes[d->cursor++].path;if(!strncmp(p,d->path,n)&&p[n]=='/'){strcpy(f->fname,p+n+1);break;}}return 0;}
static FRESULT f_closedir(DIR*d){(void)d;return fault();}
static FRESULT f_unlink(const char*p){FRESULT r=fault();if(r)return r;int i=find(p);if(i<0)return FR_NO_FILE;nodes[i].path[0]=0;return 0;}
'''
# wd must precede f_open; filesystem functions need find/put.
stubs='static char wd[80]="/";\n'+stubs
fs=fs.replace('static char wd[80]="/";\n','')
extra=r'''
static void preset_saveDrumsetRam(int a,int b){(void)a;(void)b;}
static void preset_savePatternRAM(int a){(void)a;}
static uint8_t soundengine_backgroundAudioBegin(void){return 0;}
static void soundengine_backgroundAudioEnd(uint8_t b){(void)b;}
static FRESULT slotWrite(uint8_t i,char kind){char name[16];sprintf(name,"%u.%c",i,kind);FIL f;UINT n;FRESULT r=preset_openFile(&f,name,FA_CREATE_ALWAYS|FA_WRITE);if(r)return r;preset_writeFile(&f,&kind,1,&n);return preset_closeFile(&f);}
static FRESULT preset_saveDrumsetSD(uint8_t i,int x){(void)x;return slotWrite(i,'k');}
static FRESULT preset_savePatternSD(uint8_t i){return slotWrite(i,'p');}
static FRESULT preset_saveSongSD(uint8_t i){return slotWrite(i,'s');}
'''
storage=(root/'Core/Src/Preset/SafeStorage.c').read_text().replace('#include "Preset/SafeStorage.h"','typedef FRESULT (*StorageProjectWriter)(void);')
body=g['const']+''.join(fn(n) for n in ['preset_applyMasterComp','preset_writeGlobalData','preset_saveGlobals'])
writer='static uint8_t preset_projectSlot;\n'+''.join(fn(n) for n in ['preset_writeProjectBody','preset_writeProjectFiles','preset_saveProject'])
tests=r'''
static const uint8_t target[4]={48,19,30,34};
static void reset(void){count=0;operations=failAt=renames=failRename=failRollback=0;writes=shortWriteAt=closeError=0;preset_writeOpen=preset_writeSession=0;put("/proj01","",0);put("/proj01/glo.cfg","OLD",3);strcpy(wd,"/");preset_applyMasterComp(target);}
static int oldAt(const char*p){int i=find(p);return i>=0&&nodes[i].len==3&&!memcmp(nodes[i].data,"OLD",3);}
static int newAt(const char*p){int i=find(p);return i>=0&&nodes[i].len==38&&!memcmp(nodes[i].data+30,"MC\1\0",4)&&!memcmp(nodes[i].data+34,target,4);}
int main(void){
 reset();assert(preset_saveProject(1)==0);assert(newAt("/proj01/glo.cfg"));assert(find("/proj01n")<0&&find("/proj01o")<0);unsigned total=operations, totalWrites=writes;
 for(unsigned i=1;i<=total;i++){reset();failAt=i;FRESULT r=preset_saveProject(1);assert(oldAt("/proj01/glo.cfg")||oldAt("/proj01o/glo.cfg")||newAt("/proj01/glo.cfg"));if(!r)assert(newAt("/proj01/glo.cfg"));failAt=0;assert(preset_saveProject(1)==0);assert(newAt("/proj01/glo.cfg"));}
 for(unsigned i=1;i<=totalWrites;i++){reset();shortWriteAt=i;assert(preset_saveProject(1)!=0);assert(oldAt("/proj01/glo.cfg"));assert(find("/proj01n")>=0);shortWriteAt=0;writes=0;assert(preset_saveProject(1)==0);assert(newAt("/proj01/glo.cfg"));}
 reset();closeError=7;assert(preset_saveProject(1)!=0);assert(oldAt("/proj01/glo.cfg"));closeError=0;assert(preset_saveProject(1)==0);
 reset();failRename=2;assert(preset_saveProject(1)!=0);assert(oldAt("/proj01/glo.cfg")&&newAt("/proj01n/glo.cfg"));
 reset();failRollback=1;assert(preset_saveProject(1)!=0);assert(oldAt("/proj01o/glo.cfg")&&newAt("/proj01n/glo.cfg"));failRollback=0;assert(preset_saveProject(1)==0);assert(newAt("/proj01/glo.cfg"));
 printf("Combined real project writer/SafeStorage: %u directory faults, %u short writes, close/promotion/rollback failures passed\n",total,totalWrites);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src=Path(tmp)/'test.c'; exe=Path(tmp)/'test'
    src.write_text(pre+g['enum']+stubs+fs+storage+g['helpers']+'unsigned char preset_projectCleanupWarning;\nstatic uint8_t preset_projectWriteActive;\n'+body+extra+writer+tests)
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wno-deprecated-declarations','-fsanitize=address,undefined',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
