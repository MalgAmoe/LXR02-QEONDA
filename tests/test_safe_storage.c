/* SPDX-License-Identifier: GPL-3.0-only */
#include "Preset/SafeStorage.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>

/* Disposable in-memory filesystem. The production state machine and cleanup
 * code are compiled unchanged. FatFs persistence/power-cut behaviour is not simulated. */
static struct {int exists, contents;} nodes[3];
static const char *names[]={"/proj03","/proj03n","/proj03o"};
static unsigned calls,failAt,failRenames,writerFail;
static int cwd=-1;
static struct {DIR *dir;int node,read,child;} dirs[16];
static unsigned depth;
static unsigned renameCalls,failRenameFrom;
static int nested;
static FRESULT fault(void) {return ++calls==failAt ? FR_DISK_ERR : FR_OK;}
static int node(const char *p) {for(int i=2;i>=0;i--)if(!strncmp(p,names[i],strlen(names[i])) && (p[strlen(names[i])]==0 || p[strlen(names[i])]=='/'))return i;return -1;}
FRESULT f_stat(const TCHAR *p,FILINFO *info) {
 FRESULT r=fault();if(r)return r;int i=node(p);
 if(i<0||!nodes[i].exists)return FR_NO_FILE;
 memset(info,0,sizeof *info);info->fattrib=AM_DIR;return FR_OK;
}
FRESULT f_chdir(const TCHAR *p) {
 FRESULT r=fault();if(r)return r;
 if(!strcmp(p,"/")){cwd=-1;return FR_OK;}
 int i=node(p);if(i<0||!nodes[i].exists)return FR_NO_PATH;cwd=i;return FR_OK;
}
FRESULT f_mkdir(const TCHAR *p) {
 FRESULT r=fault();if(r)return r;int i=node(p);assert(i>=0);
 if(nodes[i].exists)return FR_EXIST;nodes[i].exists=1;nodes[i].contents=0;return FR_OK;
}
FRESULT f_rename(const TCHAR *a,const TCHAR *b) {
 FRESULT r=fault();if(r||failRenames||(++renameCalls >= failRenameFrom && failRenameFrom))return FR_DISK_ERR;
 int i=node(a),j=node(b);assert(i>=0&&j>=0);
 if(!nodes[i].exists)return FR_NO_FILE;if(nodes[j].exists)return FR_EXIST;
 nodes[j]=nodes[i];nodes[i].exists=nodes[i].contents=0;return FR_OK;
}
FRESULT f_opendir(DIR *d,const TCHAR *p) {
 FRESULT r=fault();if(r)return r;int i=node(p);
 if(i<0||!nodes[i].exists)return FR_NO_PATH;
 if(depth) return FR_TOO_MANY_OPEN_FILES;dirs[depth].dir=d;dirs[depth].node=i;dirs[depth].read=0;dirs[depth].child=strstr(p,"/sub")!=NULL;depth++;return FR_OK;
}
FRESULT f_readdir(DIR *d,FILINFO *info) {
 FRESULT r=fault();if(r)return r;assert(depth&&dirs[depth-1].dir==d);
 memset(info,0,sizeof *info);unsigned k=depth-1;
 if(!dirs[k].read++ && nodes[dirs[k].node].contents) {
  if(nested && !dirs[k].child) {strcpy(info->fname,"sub");info->fattrib=AM_DIR;}
  else if(!nested || nested==1) strcpy(info->fname,"00-LONGN.SND");
 }
 return FR_OK;
}
FRESULT f_closedir(DIR *d) {assert(depth&&dirs[depth-1].dir==d);depth--;return fault();}
FRESULT f_unlink(const TCHAR *p) {
 FRESULT r=fault();if(r)return r;int i=node(p);assert(i>=0);
 if(!nodes[i].exists)return FR_NO_FILE;
 if(strstr(p,"/sub/")) nested=2;
 else if(strstr(p,"/sub")) {nested=0;nodes[i].contents=0;}
 else if(p[strlen(names[i])]=='/')nodes[i].contents=0;
 else {if(nodes[i].contents)return FR_DENIED;nodes[i].exists=0;}
 return FR_OK;
}
static FRESULT writer(void) {assert(cwd==1);nodes[1].contents=writerFail?1:3;return writerFail?FR_DISK_ERR:FR_OK;}
static void reset(int existing) {memset(nodes,0,sizeof nodes);nodes[0].exists=existing;nodes[0].contents=existing?2:0;calls=failAt=failRenames=writerFail=depth=0;cwd=-1;nested=0;renameCalls=failRenameFrom=0;}
static int complete(void) {return (nodes[0].exists&&nodes[0].contents>=2)||(nodes[1].exists&&nodes[1].contents>=2)||(nodes[2].exists&&nodes[2].contents>=2);}
int main(void) {
 unsigned char warning;
 reset(1);assert(storage_saveProject(3,writer,&warning)==FR_OK);assert(!warning&&nodes[0].contents==3&&!nodes[1].exists&&!nodes[2].exists);unsigned operations=calls;
 for(unsigned i=1;i<=operations;i++) {
  reset(1);failAt=i;FRESULT r=storage_saveProject(3,writer,&warning);
  assert(complete());assert(depth==0);
  if(r==FR_OK)assert(nodes[0].exists&&nodes[0].contents==3);
  failAt=0;
  /* A retry must not discard the only complete copy after a failed operation. */
  assert(storage_saveProject(3,writer,&warning)==FR_OK);assert(nodes[0].contents==3);assert(depth==0);
 }
 reset(1);writerFail=1;assert(storage_saveProject(3,writer,&warning)!=FR_OK);assert(nodes[0].contents==2&&nodes[1].contents==1);
 reset(1);failRenameFrom=2;
 assert(storage_saveProject(3,writer,&warning)!=FR_OK);
 assert(!nodes[0].exists && nodes[1].contents==3 && nodes[2].contents==2);
 failRenameFrom=0;assert(storage_saveProject(3,writer,&warning)==FR_OK);assert(nodes[0].contents==3);
 reset(0);nodes[1].exists=nodes[2].exists=1;nodes[1].contents=nodes[2].contents=2;failRenames=1;
 assert(storage_saveProject(3,writer,&warning)!=FR_OK);assert(nodes[1].contents==2&&nodes[2].contents==2);
 failRenames=0;assert(storage_recoverProject(3)==FR_OK);assert(nodes[0].contents==2&&nodes[1].contents==2);
 reset(0);nodes[1].exists=1;nodes[1].contents=1;assert(storage_saveProject(3,writer,&warning)==FR_DENIED);assert(nodes[1].contents==1);
 reset(0);assert(storage_saveProject(3,writer,&warning)==FR_OK);assert(nodes[0].contents==3);
 reset(1);char original[13]="/proj03";assert(storage_emptyDirectory(original)==FR_OK);assert(!strcmp(original,"/proj03"));assert(!nodes[0].contents);
 reset(1);nested=1;assert(storage_emptyDirectory("/proj03")==FR_OK);assert(!nested&&!nodes[0].contents&&!depth);
 unsigned nestedOperations=calls;
 for(unsigned i=1;i<=nestedOperations;i++) {
  reset(1);nested=1;failAt=i;
  assert(storage_emptyDirectory("/proj03")!=FR_OK);assert(!depth);
  failAt=0;assert(storage_emptyDirectory("/proj03")==FR_OK);
  assert(!nested&&!nodes[0].contents&&!depth);
 }
 char longPath[80];memset(longPath,'x',79);longPath[79]=0;assert(storage_emptyDirectory(longPath)==FR_INVALID_NAME);
 assert(storage_saveProject(64,writer,&warning)==FR_INVALID_NAME);
 printf("Storage tests pass: %u injected operation failures plus retries, write failure, recovery preservation, first save and bounded cleanup.\n",operations);
}
