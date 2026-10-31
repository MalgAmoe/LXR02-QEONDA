/* SPDX-License-Identifier: GPL-3.0-only
 * Inspired by OpenElixir-02's post-save same-slot cleanup.
 * Never called until the replacement file has been successfully closed.
 */
#include "Preset/SafeStorage.h"
#include <string.h>
#include <stdio.h>
static int sameName(const char *a,const char *b)
{
    while(*a && *b) {
        char x=*a++,y=*b++;
        if(x>='A'&&x<='Z')x+='a'-'A';
        if(y>='A'&&y<='Z')y+='a'-'A';
        if(x!=y)return 0;
    }
    return *a==*b;
}
FRESULT storage_removeOtherSlotFiles(const char *folder,const char *keep)
{
    const char *extension=strrchr(keep,'.');
    if(strlen(keep)<5 || strlen(keep)>12 || keep[0]<'0'||keep[0]>'9'||keep[1]<'0'||keep[1]>'9'||keep[2]!='-'||!extension)
        return FR_INVALID_NAME;
    for(;;) {
        DIR dir;FILINFO info;char obsolete[13]={0};
        FRESULT res=f_opendir(&dir,folder);
        if(res!=FR_OK)return res;
        for(;;) {
            res=f_readdir(&dir,&info);
            if(res!=FR_OK||!info.fname[0])break;
            const char *ext=strrchr(info.fname,'.');
            if(!(info.fattrib&AM_DIR) && info.fname[0]==keep[0] && info.fname[1]==keep[1] && info.fname[2]=='-' && ext && sameName(ext,extension) && !sameName(info.fname,keep)) {
                if(strlen(info.fname)>=sizeof obsolete) {res=FR_INVALID_NAME;break;}
                strcpy(obsolete,info.fname);break;
            }
        }
        const FRESULT closed=f_closedir(&dir);
        if(res!=FR_OK)return res;
        if(closed!=FR_OK)return closed;
        if(!obsolete[0])return FR_OK;
        char path[64];
        int n=snprintf(path,sizeof path,"%s/%s",folder,obsolete);
        if(n<0 || (unsigned)n>=sizeof path)return FR_INVALID_NAME;
        res=f_unlink(path); /* parent DIR already closed: _FS_LOCK=1 */
        if(res!=FR_OK)return res;
    }
}
