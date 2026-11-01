#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include "ff_gen_drv.h"
#include "sd_diskio.h"
SD_HandleTypeDef hsd1;
extern Disk_drvTypeDef disk;

static int present=1, initresult, ioresult, state=4, calls, initcalls, iocalls;
static int busy_left, guard_enabled;
static uint32_t timeout, tick, tickstep=100, query_ms;
static jmp_buf guard;
uint32_t HAL_GetTick(void){uint32_t t=tick;tick+=tickstep;return t;}
uint8_t BSP_PlatformIsDetected(void){return present;}
int HAL_SD_Init(SD_HandleTypeDef*h){initcalls++;return initresult;}
int HAL_SD_ReadBlocks(SD_HandleTypeDef*h,uint8_t*p,uint32_t a,uint32_t n,uint32_t t){iocalls++;timeout=t;return ioresult;}
int HAL_SD_WriteBlocks(SD_HandleTypeDef*h,uint8_t*p,uint32_t a,uint32_t n,uint32_t t){iocalls++;timeout=t;return ioresult;}
int HAL_SD_ReadBlocks_DMA(SD_HandleTypeDef*h,uint8_t*p,uint32_t a,uint32_t n){abort();}
int HAL_SD_WriteBlocks_DMA(SD_HandleTypeDef*h,uint8_t*p,uint32_t a,uint32_t n){abort();}
int HAL_SD_Erase(SD_HandleTypeDef*h,uint32_t a,uint32_t b){return 0;}
int HAL_SD_GetCardState(SD_HandleTypeDef*h){tick += query_ms;if(++calls==100000 && guard_enabled)longjmp(guard,1);if(busy_left>0){busy_left--;return HAL_SD_CARD_PROGRAMMING;}return state;}
int HAL_SD_GetCardInfo(SD_HandleTypeDef*h,HAL_SD_CardInfoTypeDef*i){i->LogBlockNbr=100;i->LogBlockSize=512;return 0;}
static BYTE buf[512];
static DRESULT transfer(int write){return write?disk_write(0,buf,0,1):disk_read(0,buf,0,1);}
static void io_tests(void){
 char path[4];assert(!FATFS_LinkDriver(&SD_Driver,path));
 for(int w=getenv("WRITE_ONLY")?1:0;w<2;w++){
  state=4;calls=0;iocalls=0;assert(transfer(w)==RES_OK);assert(calls==1 && iocalls==1);assert(timeout==SDMMC_DATATIMEOUT);
  busy_left=3;calls=0;assert(transfer(w)==RES_OK);assert(calls==4);
  ioresult=1;calls=0;iocalls=0;assert(transfer(w)==RES_ERROR);assert(calls==0 && iocalls==1);ioresult=0;
  int states[]={255,0,8,3};
  for(unsigned i=0;i<sizeof(states)/sizeof(states[0]);i++){
   if(getenv("STATUS_ONLY") && states[i]!=255)continue;
   state=states[i];calls=0;iocalls=0;tick=UINT32_MAX-200;guard_enabled=1;
   if(setjmp(guard)){fprintf(stderr,"FAIL: %s state %d still polling after 100000 calls\n",w?"write":"read",state);exit(2);}
   assert(transfer(w)==RES_ERROR);assert(iocalls==1);
   assert(calls==1);
   guard_enabled=0;
  }
 }
 assert(!FATFS_UnLinkDriver(path));
 puts("PASS read/write: ready, finite busy, HAL error, terminal status errors; no data retries; original SD timeout");
}
/* No production elapsed-time policy: slow READY and long finite BUSY succeed.
 * Only this test harness interrupts truly endless BUSY; not a driver timeout. */
static void query_budget_tests(void){
 char path[4];assert(!FATFS_LinkDriver(&SD_Driver,path));
 for(int w=0;w<2;w++){
  for(int wrap=0;wrap<2;wrap++){
   const uint32_t durations[]={4999,5000,5001,30001};
   for(unsigned i=0;i<4;i++){
    tick=wrap?UINT32_MAX-200:0;tickstep=0;query_ms=durations[i];
    state=HAL_SD_CARD_TRANSFER;busy_left=3;calls=0;iocalls=0;
    guard_enabled=1;
    if(setjmp(guard)){fprintf(stderr,"FAIL: finite busy did not finish\n");exit(2);}
    assert(transfer(w)==RES_OK);
    assert(calls==4 && iocalls==1 && timeout==SDMMC_DATATIMEOUT);
    guard_enabled=0;
    busy_left=0;calls=0;iocalls=0;
    assert(transfer(w)==RES_OK); /* Even a single slow READY is accepted. */
    assert(calls==1 && iocalls==1 && timeout==SDMMC_DATATIMEOUT);
   }
  }
  for(int busy=HAL_SD_CARD_SENDING;busy<=HAL_SD_CARD_PROGRAMMING;busy++){
   state=busy;calls=0;iocalls=0;guard_enabled=1;
   if(setjmp(guard)==0){
    (void)transfer(w);
    fprintf(stderr,"FAIL: persistent busy returned\n");exit(2);
   }
   assert(calls==100000 && iocalls==1);
   guard_enabled=0;
  }
 }
 query_ms=0;tickstep=100;
 assert(!FATFS_UnLinkDriver(path));
 puts("PASS read/write: long finite BUSY then READY, slow READY >5s/>30s, tick wrap; endless BUSY stopped only by test harness");
}
static void init_tests(void){
 char path[4];assert(!FATFS_LinkDriver(&SD_Driver,path));
 initresult=1;state=4;assert(disk_initialize(0)&STA_NOINIT);assert(initcalls==1);assert(!disk.is_initialized[0]);
 initresult=0;assert(disk_initialize(0)==0);assert(initcalls==2);assert(disk.is_initialized[0]);
 assert(disk_initialize(0)==0);assert(initcalls==2);
 state=255;initresult=1;assert(disk_initialize(0)&STA_NOINIT);assert(initcalls==3);assert(!disk.is_initialized[0]);
 state=4;initresult=0;assert(disk_initialize(0)==0);assert(initcalls==4);
 state=255;assert(disk_initialize(0)&STA_NOINIT);assert(initcalls==5);assert(!disk.is_initialized[0]);
 state=4;assert(disk_initialize(0)==0);assert(initcalls==6);
 assert(!FATFS_UnLinkDriver(path));assert(!FATFS_LinkDriver(&SD_Driver,path));assert(disk_initialize(0)==0);assert(initcalls==7);
 puts("PASS init: failure retry, ready cache, reinit after prior success/status NOINIT, post-init status failure retry, unlink/link");
}
int main(int argc,char**argv){if(argc>1 && !strcmp(argv[1],"init")){init_tests();}else{io_tests();query_budget_tests();init_tests();}return 0;}
