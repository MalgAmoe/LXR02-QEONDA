/* Actual wrapper + active main reinsertion sequence, real bundled FatFs. RAM only. */
#include "ff.h"
#include "diskio.h"
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define SECTORS 131072u
#define NUM_KIT_SLOTS 64
static BYTE *disk;
static int failSync, mountFail;
static unsigned closeCalls, names, errors;
static FRESULT lastError;
static FATFS SDFatFS;
static FIL SDFile;
static char SDPath[]="";
DSTATUS disk_initialize(BYTE p){(void)p;return mountFail?STA_NOINIT:0;}
DSTATUS disk_status(BYTE p){(void)p;return mountFail?STA_NOINIT:0;}
DRESULT disk_read(BYTE p,BYTE*b,DWORD s,UINT n){(void)p;assert(s<SECTORS&&n<=SECTORS-s);memcpy(b,disk+s*512u,n*512u);return RES_OK;}
DRESULT disk_write(BYTE p,const BYTE*b,DWORD s,UINT n){(void)p;if(failSync)return RES_ERROR;assert(s<SECTORS&&n<=SECTORS-s);memcpy(disk+s*512u,b,n*512u);return RES_OK;}
DRESULT disk_ioctl(BYTE p,BYTE cmd,void*b){(void)p;switch(cmd){case CTRL_SYNC:return failSync?RES_ERROR:RES_OK;case GET_SECTOR_COUNT:*(DWORD*)b=SECTORS;break;case GET_BLOCK_SIZE:*(DWORD*)b=1;break;case GET_SECTOR_SIZE:*(WORD*)b=512;break;default:return RES_PARERR;}return RES_OK;}
DWORD get_fattime(void){return (46u<<25)|(1u<<21)|(1u<<16);}
static FRESULT counted_close(FIL*f){closeCalls++;return f_close(f);}
#define f_close counted_close
/* HELPERS */
static uint8_t soundengine_backgroundAudioBegin(void){return 0;}
static void soundengine_backgroundAudioEnd(uint8_t bg){(void)bg;}
static void MX_FATFS_ReInit(void){}
static void menu_showSdError(FRESULT e){
 assert(e!=FR_OK);errors++;lastError=e;
 if(e==FR_DISK_ERR){
  UINT n=99;unsigned c=closeCalls;
  assert(!preset_writeOpen);
  assert(preset_writeFile(&SDFile,"never replay",12,&n)==FR_DISK_ERR&&n==0);
  assert(preset_closeFile(&SDFile)==FR_DISK_ERR&&closeCalls==c);
 }
}
static void preset_loadProjectNames(unsigned i){(void)i;names++;assert(preset_openFile(&SDFile,"old",FA_READ)==FR_OK);assert(preset_closeFile(&SDFile)==FR_OK);}
static void reinsert(void){FRESULT res;/* REMOUNT */}
static void pending(void){UINT n;assert(preset_openFile(&SDFile,"old",FA_CREATE_ALWAYS|FA_WRITE)==FR_OK);assert(preset_writeFile(&SDFile,"old",3,&n)==FR_OK);failSync=1;assert(preset_closeFile(&SDFile)==FR_DISK_ERR);assert(preset_writeOpen);}
int main(void){
 disk=calloc(SECTORS,512);assert(disk);BYTE work[4096];
 assert(f_mkfs("",FM_FAT32|FM_SFD,512,work,sizeof work)==FR_OK);
 assert(f_mount(&SDFatFS,"",1)==FR_OK);
 pending();unsigned c=closeCalls;
 assert(preset_openFile(&SDFile,"blocked",FA_WRITE|FA_CREATE_ALWAYS)==FR_DISK_ERR);
 assert(closeCalls==c+1&&preset_writeOpen); /* same mount retry retained */
 FIL stale=SDFile;WORD id=SDFatFS.id;
 failSync=0;c=closeCalls;reinsert();assert(closeCalls==c+64);
 assert(SDFatFS.id!=id);assert(f_close(&stale)==FR_INVALID_OBJECT);
 assert(names==64);assert(errors==1&&lastError==FR_DISK_ERR);
 UINT n;assert(preset_openFile(&SDFile,"new",FA_CREATE_ALWAYS|FA_WRITE)==FR_OK);
 assert(preset_writeFile(&SDFile,"new",3,&n)==FR_OK&&n==3);assert(preset_closeFile(&SDFile)==FR_OK);
 /* Shared read FIL is invalid too; next read and next write start fresh. */
 assert(preset_openFile(&SDFile,"new",FA_READ)==FR_OK);stale=SDFile;
 reinsert();assert(f_close(&stale)==FR_INVALID_OBJECT);
 pending();failSync=0;mountFail=1;reinsert();assert(!preset_writeOpen);
 mountFail=0;reinsert();assert(preset_openFile(&SDFile,"new",FA_READ)==FR_OK);assert(preset_closeFile(&SDFile)==FR_OK);
 assert(f_mount(NULL,"",0)==FR_OK);free(disk);puts("Actual wrappers/main remount and FatFs stale mount-ID regression pass.");
}
