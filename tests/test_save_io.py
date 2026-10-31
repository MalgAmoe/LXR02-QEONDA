#!/usr/bin/env python3
"""Test actual preset write wrappers with short-write and close/open faults."""
from pathlib import Path
import tempfile, subprocess, os
root=Path(__file__).resolve().parents[1]
s=(root/'Core/Src/Preset/presetManager.c').read_text()
helpers=s[s.index('static FRESULT preset_writeResult'):s.index('unsigned char preset_projectCleanupWarning;')]
c=r'''
#include <assert.h>
#include <stdint.h>
typedef int FRESULT; typedef int FIL; typedef char TCHAR; typedef unsigned UINT;typedef unsigned char BYTE;
#define FR_OK 0
#define FR_DENIED 7
#define FR_INVALID_OBJECT 9
#define FA_WRITE 2
static int shortWrite,writeError,closeError,openError,writes,closes,opens;
static FRESULT f_open(FIL*f,const TCHAR*p,BYTE m){(void)f;(void)p;(void)m;opens++;return openError;}
static FRESULT f_write(FIL*f,const void*p,UINT n,UINT*w){(void)f;(void)p;writes++;*w=shortWrite?n-1:n;return writeError;}
static FRESULT f_close(FIL*f){(void)f;closes++;return closeError;}
'''+helpers+r'''
int main(void) {
 FIL file;UINT n;
 assert(preset_openFile(&file,"x",FA_WRITE)==0);
 assert(preset_writeFile(&file,"abc",3,&n)==0 && n==3);
 assert(preset_closeFile(&file)==0 && !preset_writeOpen);
 shortWrite=1;writes=0;
 assert(preset_openFile(&file,"x",FA_WRITE)==0);
 assert(preset_writeFile(&file,"abc",3,&n)==FR_DENIED);
 assert(!preset_writeOpen);
 assert(preset_writeFile(&file,"abc",3,&n)==FR_DENIED && writes==1);
 assert(preset_closeFile(&file)==FR_DENIED);
 shortWrite=0;writeError=3;closeError=4;
 preset_openFile(&file,"x",FA_WRITE);
 assert(preset_writeFile(&file,"abc",3,&n)==3 && preset_writeOpen);
 assert(preset_closeFile(&file)==3);
 unsigned prior=opens;
 assert(preset_openFile(&file,"next",FA_WRITE)==4 && opens==prior);
 closeError=0;writeError=0;
 assert(preset_openFile(&file,"next",FA_WRITE)==0);
 closeError=4;assert(preset_closeFile(&file)==4 && preset_writeOpen);
 closeError=0;assert(preset_openFile(&file,"read",0)==0);
 assert(preset_closeFile(&file)==0);
 openError=5;assert(preset_openFile(&file,"x",FA_WRITE)==5);
 assert(preset_writeFile(&file,"abc",3,&n)==5);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp)/'io.c';exe=Path(tmp)/'io';p.write_text(c)
 subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Werror','-fsanitize=address,undefined',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('Actual preset IO wrappers pass success, short-write, sticky error, close failure, retained handle and failed-open tests.')
