/* Real FatFs RAM-disk integration regression. No physical disk access. */
#include "Preset/SafeStorage.h"
#include "diskio.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define SECTORS 131072u
static BYTE *disk;
static unsigned reads,writes,syncs;
DSTATUS disk_initialize(BYTE p){(void)p;return 0;}
DSTATUS disk_status(BYTE p){(void)p;return 0;}
DRESULT disk_read(BYTE p,BYTE *b,DWORD s,UINT n){(void)p;assert(s<SECTORS&&n<=SECTORS-s);memcpy(b,disk+s*512u,n*512u);reads+=n;return RES_OK;}
DRESULT disk_write(BYTE p,const BYTE *b,DWORD s,UINT n){(void)p;assert(s<SECTORS&&n<=SECTORS-s);memcpy(disk+s*512u,b,n*512u);writes+=n;return RES_OK;}
DRESULT disk_ioctl(BYTE p,BYTE cmd,void *b){(void)p;switch(cmd){case CTRL_SYNC:syncs++;break;case GET_SECTOR_COUNT:*(DWORD*)b=SECTORS;break;case GET_BLOCK_SIZE:*(DWORD*)b=1;break;case GET_SECTOR_SIZE:*(WORD*)b=512;break;default:return RES_PARERR;}return RES_OK;}
DWORD get_fattime(void){return ((DWORD)(2026-1980)<<25)|(1u<<21)|(1u<<16);}
static void put(const char *p){FIL f;UINT n;assert(f_open(&f,p,FA_CREATE_ALWAYS|FA_WRITE)==FR_OK);assert(f_write(&f,"keep",4,&n)==FR_OK&&n==4);assert(f_close(&f)==FR_OK);}
static void empty(const char *p){DIR d;FILINFO f;assert(f_opendir(&d,p)==FR_OK);assert(f_readdir(&d,&f)==FR_OK&&!f.fname[0]);assert(f_closedir(&d)==FR_OK);}
int main(void){
 _Static_assert(sizeof(DWORD)==4,"FatFs requires 32-bit DWORD");
 disk=calloc(SECTORS,512);assert(disk);BYTE work[4096];FATFS fs;
 assert(f_mkfs("",FM_FAT32|FM_SFD,512,work,sizeof work)==FR_OK);
 assert(f_mount(&fs,"",1)==FR_OK&&fs.fs_type==FS_FAT32);
 assert(f_mkdir("/keep")==FR_OK);put("/keep/SAFE.SND");
 DWORD freeBefore,freeAfter;FATFS *mounted;assert(f_getfree("",&freeBefore,&mounted)==FR_OK);
 assert(f_mkdir("/old")==FR_OK);
 char path[64];for(unsigned i=0;i<194;i++){snprintf(path,sizeof path,"/old/%03u.SND",i);put(path);}
 /* Actual one-slot lock: a second non-root directory cannot be opened,
    but deleting a closed child while its parent stays open is permitted. */
 DIR d,other;FILINFO info;assert(f_opendir(&d,"/old")==FR_OK);
 assert(f_opendir(&other,"/keep")==FR_TOO_MANY_OPEN_FILES);
 assert(f_readdir(&d,&info)==FR_OK&&info.fname[0]);
 snprintf(path,sizeof path,"/old/%s",info.fname);assert(f_unlink(path)==FR_OK);
 assert(f_closedir(&d)==FR_OK);put(path);
 reads=writes=syncs=0;
 assert(storage_emptyDirectory("/old")==FR_OK);
 printf("194-file FAT32 cleanup: read sectors=%u write sectors=%u syncs=%u\n",reads,writes,syncs);
 assert(reads < 4000); /* Baseline restart-per-file cleanup reads 5424 sectors. */
 empty("/old");assert(f_stat("/keep/SAFE.SND",&info)==FR_OK&&info.fsize==4);
 /* Nested traversal, with files both before and after the child. */
 put("/old/FIRST.SND");assert(f_mkdir("/old/sub")==FR_OK);
 assert(f_mkdir("/old/sub/deeper")==FR_OK);put("/old/sub/deeper/X.SND");put("/old/LAST.SND");
 assert(storage_removeDirectory("/old")==FR_OK);assert(f_stat("/old",&info)==FR_NO_FILE);
 assert(f_stat("/keep/SAFE.SND",&info)==FR_OK);
 assert(f_mount(NULL,"",0)==FR_OK);assert(f_mount(&fs,"",1)==FR_OK);
 assert(f_stat("/keep/SAFE.SND",&info)==FR_OK&&info.fsize==4);
 assert(f_stat("/old",&info)==FR_NO_FILE);
 FIL survivor;char contents[4];UINT got;
 assert(f_open(&survivor,"/keep/SAFE.SND",FA_READ)==FR_OK);
 assert(f_read(&survivor,contents,4,&got)==FR_OK&&got==4&&!memcmp(contents,"keep",4));
 assert(f_close(&survivor)==FR_OK);
 assert(f_getfree("",&freeAfter,&mounted)==FR_OK&&freeBefore==freeAfter);
 assert(f_mount(NULL,"",0)==FR_OK);free(disk);puts("Real FatFs cleanup, nested directories, lock behavior and remount pass.");
}
