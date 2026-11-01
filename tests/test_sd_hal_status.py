"""Compile unchanged actual-source HAL status function with command stub only."""
from pathlib import Path
import os, shlex, subprocess, tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'Drivers/STM32F7xx_HAL_Driver/Src/stm32f7xx_hal_sd.c').read_text()
start=s.index('HAL_SD_CardStateTypeDef HAL_SD_GetCardState(')
end=s.index('\n}',start)+2
prefix='''#include <assert.h>
#include <stdint.h>
typedef struct {uint32_t ErrorCode;} SD_HandleTypeDef;
typedef uint32_t HAL_SD_CardStateTypeDef;
#define HAL_SD_ERROR_NONE 0
#define HAL_SD_CARD_ERROR 255
static uint32_t error, response;
static uint32_t SD_SendStatus(SD_HandleTypeDef*h,uint32_t*r){if(!error)*r=response;return error;}
'''
tail='''
int main(void){SD_HandleTypeDef h={0};
for(int state=0;state<16;state++){response=state<<9;assert(HAL_SD_GetCardState(&h)==state);}
error=8;assert(HAL_SD_GetCardState(&h)==255);assert(h.ErrorCode==8);
error=0;response=4<<9;assert(HAL_SD_GetCardState(&h)==4);assert(h.ErrorCode==8);
return 0;}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(prefix+s[start:end]+tail)
 subprocess.run([*shlex.split(os.environ.get('CC', 'cc')),'-O1','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS actual HAL_SD_GetCardState source: state decoding, CMD13 failure sentinel/ErrorCode, sticky old error does not poison success')
