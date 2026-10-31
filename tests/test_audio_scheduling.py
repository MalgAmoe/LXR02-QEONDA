#!/usr/bin/env python3
"""Compile actual scheduling function bodies with a deterministic fake HAL.
Not a hardware/DMA timing simulation. Temporary generated C is never firmware.
"""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
def source(name):
    return (root / 'Core/Src' / name).read_text()
def function(text, name):
    start = text.index(name + '(')
    start = text.rfind('\n', 0, start) + 1
    opening = text.index('{', start)
    level = 1
    end = opening + 1
    while level:
        level += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'
codec = source('Soundengine/cs4344_cs5343.c')
engine = source('Soundengine/Soundengine.c')
fixture = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#define OUTPUT_DMA_SIZE 64
#define SAMPLE_VALID 0xff
#define USE_DAC2 1
#define CALC_SAMPLES_IN_INTERRUPT 1
#define USE_INTERRUPT_ONLY_DURING_SAVE_PROJ 1
#define IN_ITCM_RAM
#define TIM_IT_UPDATE 1
#define DMA_IT_FE 1
#define DMA1_Stream4_IRQn 4
#define DMA1_Stream5_IRQn 5
#define HAL_DMA_ERROR_NO_XFER 1
#define HAL_I2S_ERROR_TIMEOUT 2
#define SPI2 ((void*)2)
#define SPI3 ((void*)3)
typedef enum {HAL_OK, HAL_ERROR} HAL_StatusTypeDef;
typedef struct {unsigned ErrorCode;} DMA;
typedef struct {void *Instance; DMA *hdmatx; unsigned ErrorCode;} I2S_HandleTypeDef;
typedef struct {unsigned DIER;} Timer;
static Timer timer;
static struct {Timer *Instance;} htim2 = {&timer};
static DMA dma2, dma3;
static I2S_HandleTypeDef hi2s2 = {SPI2,&dma2,0}, hi2s3 = {SPI3,&dma3,0};
static int16_t dma_buffer[256], dma_buffer2[256];
static volatile uint8_t bCurrentSampleValid = SAMPLE_VALID;
static volatile uint32_t codec_requestGeneration;
static volatile uint8_t codec_recoveryPending;
static volatile uint32_t codec_recoveryFailures;
static volatile uint8_t codec_recoveryFault;
static uint8_t codec_recoveryAttempts;
static uint32_t codec_recoveryLastAttempt;
static uint32_t tick;
static uint32_t HAL_GetTick(void) {return tick;}
static int error, stopCalls, startCalls, failStart, failStop, renderingLate;
static int timerRunning, mask, noTransfer;
static unsigned lastHalf;
#define __HAL_DMA_DISABLE_IT(d,i) ((void)0)
#define __HAL_TIM_SetCounter(t,v) ((void)0)
#define __HAL_TIM_DISABLE_IT(t,i) ((t)->Instance->DIER &= ~(i))
#define __HAL_TIM_ENABLE_IT(t,i) ((t)->Instance->DIER |= (i))
#define HAL_NVIC_DisableIRQ(i) ((void)0)
#define HAL_NVIC_EnableIRQ(i) ((void)0)
#define HAL_NVIC_ClearPendingIRQ(i) ((void)0)
static unsigned __get_PRIMASK(void) {return mask;}
static void __disable_irq(void) {mask=1;}
static void __set_PRIMASK(unsigned m) {mask=m;}
static HAL_StatusTypeDef HAL_TIM_Base_Start_IT(void *t) {
    (void)t; if(timerRunning) return HAL_ERROR; timerRunning=1; return HAL_OK;
}
static HAL_StatusTypeDef HAL_TIM_Base_Stop_IT(void *t) {
    (void)t; timerRunning=0; return HAL_OK;
}
static HAL_StatusTypeDef HAL_I2S_DMAStop(I2S_HandleTypeDef *h) {
    ++stopCalls;
    if(failStop) {h->ErrorCode=HAL_I2S_ERROR_TIMEOUT;return HAL_ERROR;}
    if(noTransfer) {h->hdmatx->ErrorCode=HAL_DMA_ERROR_NO_XFER;return HAL_ERROR;}
    return HAL_OK;
}
static HAL_StatusTypeDef HAL_I2S_Transmit_DMA(I2S_HandleTypeDef *h,uint16_t *p,unsigned n) {
    ++startCalls;
    assert(n == 256);
    assert(p == (uint16_t*)(h->Instance == SPI2 ? dma_buffer2 : dma_buffer));
    return (failStart == 1 || (failStart == 2 && h->Instance == SPI2)) ? HAL_ERROR : HAL_OK;
}
void HAL_I2S_TxHalfCpltCallback(I2S_HandleTypeDef *h);
void HAL_I2S_TxCpltCallback(I2S_HandleTypeDef *h);
static void mixer_calcNextSampleBlock(int16_t *a,int16_t *b) {
    assert(a >= dma_buffer && a < dma_buffer+256);
    lastHalf=(a-dma_buffer)/128;
    assert(b == dma_buffer2+lastHalf*128);
    if(renderingLate) HAL_I2S_TxCpltCallback(&hi2s3);
}
'''
for name in ('codec_ignoreFifoErrors', 'codec_blockSent', 'HAL_I2S_TxHalfCpltCallback',
             'HAL_I2S_TxCpltCallback', 'HAL_I2S_ErrorCallback', 'codec_serviceDmaRecovery'):
    fixture += function(codec, name)
for name in ('soundengine_calcNextSampleBlock', 'soundengine_backgroundAudioBegin',
             'soundengine_backgroundAudioEnd'):
    fixture += function(engine, name)
fixture += r'''
int main(void) {
    HAL_I2S_TxHalfCpltCallback(&hi2s2);
    assert(bCurrentSampleValid == SAMPLE_VALID);
    HAL_I2S_TxHalfCpltCallback(&hi2s3);
    assert(bCurrentSampleValid == 0);
    assert(soundengine_calcNextSampleBlock() == 1 && lastHalf == 0);
    assert(bCurrentSampleValid == SAMPLE_VALID);
    HAL_I2S_TxCpltCallback(&hi2s3);
    assert(soundengine_calcNextSampleBlock() == 1 && lastHalf == 1);
    assert(soundengine_calcNextSampleBlock() == 0);
    HAL_I2S_TxHalfCpltCallback(&hi2s3);
    renderingLate=1;
    assert(soundengine_calcNextSampleBlock() == 1 && lastHalf == 0);
    assert(bCurrentSampleValid == 1); /* newer request was not erased */
    renderingLate=0;
    soundengine_calcNextSampleBlock();
    assert(bCurrentSampleValid == SAMPLE_VALID);
    unsigned outer=soundengine_backgroundAudioBegin();
    unsigned inner=soundengine_backgroundAudioBegin();
    assert(outer && !inner && timerRunning);
    soundengine_backgroundAudioEnd(inner); assert(timerRunning);
    soundengine_backgroundAudioEnd(outer); assert(!timerRunning);
    timer.DIER=1;
    HAL_I2S_ErrorCallback(&hi2s2);
    assert(codec_recoveryPending && !startCalls && !stopCalls);
    codec_serviceDmaRecovery();
    assert(stopCalls==2 && startCalls==2 && !codec_recoveryPending);
    assert(timer.DIER==1 && codec_recoveryFailures==0);
    failStart=2;
    HAL_I2S_ErrorCallback(&hi2s3); codec_serviceDmaRecovery();
    assert(codec_recoveryFailures==1 && stopCalls==6);
    tick += 100;
    failStop=1;
    HAL_I2S_ErrorCallback(&hi2s3); codec_serviceDmaRecovery();
    assert(codec_recoveryFailures==2 && startCalls==4);
    assert(mask==0);
    /* No new IRQ: a transient failure must retry from foreground alone. */
    failStop=failStart=0;
    noTransfer=1;
    hi2s2.ErrorCode=hi2s3.ErrorCode=0;
    tick += 100;
    codec_serviceDmaRecovery();
    assert(!codec_recoveryPending && !codec_recoveryFault && startCalls==6);
    noTransfer=0;
    failStart=1;
    HAL_I2S_ErrorCallback(&hi2s2);
    codec_serviceDmaRecovery();
    tick+=100; codec_serviceDmaRecovery();
    tick+=100; codec_serviceDmaRecovery();
    assert(codec_recoveryFault && !codec_recoveryPending);
    unsigned before=startCalls;
    tick+=100; codec_serviceDmaRecovery();
    assert(startCalls==before);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    c = Path(directory) / 'scheduling.c'
    exe = Path(directory) / 'scheduling'
    c.write_text(fixture)
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Werror',
                    '-fsanitize=address,undefined', '-g', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

# Source-order guards complement runtime function tests; they are not an SD simulation.
preset = source('Preset/presetManager.c')
save = preset[preset.index('FRESULT preset_saveProject('):]
cleanup = save.index('preset_clearTmpFolder();')
assert save.index('HAL_TIM_Base_Stop_IT', cleanup) < save.index('return FR_OK;', cleanup)
assert 'menu_repaint' not in function(source('menu/menu.c'), 'menu_tick')
assert 'menu_uiTick();' in source('main.c')
for spi in ('spi2', 'spi3'):
    assert f'hdma_{spi}_tx.Init.Mode = DMA_CIRCULAR;' in source('stm32f7xx_hal_msp.c')
print('Scheduling function tests and source-order guards passed (fake HAL; not hardware validation).')
