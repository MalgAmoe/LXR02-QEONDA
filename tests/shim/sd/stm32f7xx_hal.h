#ifndef TEST_HAL
#define TEST_HAL
#include <stdint.h>
#undef __weak
#define __weak __attribute__((weak))
#define __IO volatile
#define SDMMC_DATATIMEOUT 0xFFFFFFFFU
typedef struct { int unused; } SD_HandleTypeDef;
typedef struct {uint32_t LogBlockNbr,LogBlockSize;} HAL_SD_CardInfoTypeDef;
typedef int HAL_StatusTypeDef;
#define HAL_OK 0
#define HAL_SD_CARD_TRANSFER 4
#define HAL_SD_CARD_SENDING 5
#define HAL_SD_CARD_RECEIVING 6
#define HAL_SD_CARD_PROGRAMMING 7
#define HAL_SD_CARD_ERROR 255
uint32_t HAL_GetTick(void);
int HAL_SD_Init(SD_HandleTypeDef*);
int HAL_SD_ReadBlocks(SD_HandleTypeDef*,uint8_t*,uint32_t,uint32_t,uint32_t);
int HAL_SD_WriteBlocks(SD_HandleTypeDef*,uint8_t*,uint32_t,uint32_t,uint32_t);
int HAL_SD_ReadBlocks_DMA(SD_HandleTypeDef*,uint8_t*,uint32_t,uint32_t);
int HAL_SD_WriteBlocks_DMA(SD_HandleTypeDef*,uint8_t*,uint32_t,uint32_t);
int HAL_SD_Erase(SD_HandleTypeDef*,uint32_t,uint32_t);
int HAL_SD_GetCardState(SD_HandleTypeDef*);
int HAL_SD_GetCardInfo(SD_HandleTypeDef*,HAL_SD_CardInfoTypeDef*);
#endif
