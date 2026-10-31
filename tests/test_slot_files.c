#include "Preset/SafeStorage.h"
#include <string.h>
#include <assert.h>
#include <stdio.h>
static const char *names[]={"03-OLD.SND","03-NEW.SND","03-ALT.SND","04-OTHER.SND","03-SAME.PAT","03-DIR.SND"};
static int present[6],opened,index_,failRead,failClose,failDelete;
FRESULT f_opendir(DIR*d,const TCHAR*p){(void)d;assert(!opened&&!strcmp(p,"/tmp"));opened=1;index_=0;return FR_OK;}
FRESULT f_readdir(DIR*d,FILINFO*f){(void)d;assert(opened);if(failRead)return FR_DISK_ERR;memset(f,0,sizeof *f);while(index_<6&&!present[index_])index_++;if(index_<6){strcpy(f->fname,names[index_]);if(index_==5)f->fattrib=AM_DIR;index_++;}return FR_OK;}
FRESULT f_closedir(DIR*d){(void)d;assert(opened);opened=0;return failClose?FR_DISK_ERR:FR_OK;}
FRESULT f_unlink(const TCHAR*p){assert(!opened);if(failDelete)return FR_DISK_ERR;assert(!strncmp(p,"/tmp/",5));for(int i=0;i<6;i++)if(!strcmp(p+5,names[i])){assert(i!=1&&i!=3&&i!=4&&i!=5);present[i]=0;return FR_OK;}return FR_NO_FILE;}
static void reset(void){for(int i=0;i<6;i++)present[i]=1;opened=failRead=failClose=failDelete=0;}
int main(void){
 reset();assert(storage_removeOtherSlotFiles("/tmp","03-new.snd")==FR_OK);assert(!present[0]&&present[1]&&!present[2]&&present[3]&&present[4]&&present[5]);
 reset();failRead=1;assert(storage_removeOtherSlotFiles("/tmp","03-NEW.SND")!=FR_OK);assert(present[0]&&present[1]);
 reset();failClose=1;assert(storage_removeOtherSlotFiles("/tmp","03-NEW.SND")!=FR_OK);assert(present[0]&&present[1]);
 reset();failDelete=1;assert(storage_removeOtherSlotFiles("/tmp","03-NEW.SND")!=FR_OK);assert(present[0]&&present[1]);
 reset();assert(storage_removeOtherSlotFiles("/tmp","../oops")==FR_INVALID_NAME);assert(!opened);
 puts("Slot cleanup: same-slot/type only; keep case-insensitive; directory exclusion; read/close/delete failures pass.");
}
