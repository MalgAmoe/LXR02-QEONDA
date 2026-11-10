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
transport = (root / 'Core/Inc/Soundengine/cs4344_cs5343.h').read_text()
transport = transport[transport.index('/* HAL Size'):transport.index('/* Mask for')]
fixture = r'''
#include <assert.h>
#include <stdint.h>
typedef float AudioSample;
#include "Soundengine/AudioOutput24.h"
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
#define INDTCMZ
''' + transport + r'''
int16_t dma_buffer[AUDIO_DMA_HALFWORDS], dma_buffer2[AUDIO_DMA_HALFWORDS];
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
static int packingSeam;
void HAL_I2S_TxCpltCallback(I2S_HandleTypeDef *h);
static unsigned __get_PRIMASK(void) {
    if(packingSeam && dma_buffer[0]==-64 && dma_buffer2[0]==64 &&
       dma_buffer[255]==0 && dma_buffer2[255]==0) {
        packingSeam=0;
        HAL_I2S_TxCpltCallback(&hi2s3);
    }
    return mask;
}
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
    for(unsigned i=0;i<AUDIO_DMA_HALFWORDS;++i)
        assert(dma_buffer[i]==0 && dma_buffer2[i]==0);
    assert(p == (uint16_t*)(h->Instance == SPI2 ? dma_buffer2 : dma_buffer));
    return (failStart == 1 || (failStart == 2 && h->Instance == SPI2)) ? HAL_ERROR : HAL_OK;
}
void HAL_I2S_TxHalfCpltCallback(I2S_HandleTypeDef *h);
void HAL_I2S_TxCpltCallback(I2S_HandleTypeDef *h);
static void mixer_calcNextSampleBlock(AudioSample *a,AudioSample *b) {
    static unsigned renderCount;
    lastHalf = renderCount++ == 1 ? 1 : 0;
    for(unsigned i=0;i<128;++i) {a[i]=(int16_t)(i-64)/32768.f; b[i]=(int16_t)(64-i)/32768.f;}
    if(renderingLate) HAL_I2S_TxCpltCallback(&hi2s3);
}
'''
for name in ('codec_ignoreFifoErrors', 'codec_blockSent', 'HAL_I2S_TxHalfCpltCallback',
             'HAL_I2S_TxCpltCallback', 'HAL_I2S_ErrorCallback', 'codec_serviceDmaRecovery'):
    fixture += function(codec, name)
fixture += r'''
static unsigned mainCalls;
static void MainDjFilter_process24(const AudioSample *src,int16_t *dst,unsigned frames) {
    assert(frames==OUTPUT_DMA_SIZE); ++mainCalls;
    for(unsigned i=0;i<frames*2;++i) audio_output24_store(dst+2*i,src[i]);
}
'''
for name in ('soundengine_calcNextSampleBlock', 'soundengine_backgroundAudioBegin',
             'soundengine_backgroundAudioEnd'):
    fixture += function(engine, name)
fixture += r'''
int main(void) {
    int16_t src[128], guarded[514];
    for(unsigned i=0;i<128;++i) src[i]=(int16_t)(i%4==0 ? -32768 : i%4==1 ? 32767 : i%4==2 ? -1 : 0);
    for(unsigned half=0;half<2;++half) {
        for(unsigned i=0;i<514;++i) guarded[i]=1234;
        for(unsigned i=0;i<128;++i) audio_output24_store(guarded+1+half*256+2*i,src[i]/32768.f);
        for(unsigned i=0;i<128;++i) {
            assert(guarded[1+half*256+2*i]==src[i]);
            assert(guarded[2+half*256+2*i]==0);
        }
        assert(guarded[half*256]==1234 && guarded[257+half*256]==1234);
    }
    HAL_I2S_TxHalfCpltCallback(&hi2s2);
    assert(bCurrentSampleValid == SAMPLE_VALID);
    HAL_I2S_TxHalfCpltCallback(&hi2s3);
    assert(bCurrentSampleValid == 0);
    assert(soundengine_calcNextSampleBlock() == 1 && lastHalf == 0);
    assert(bCurrentSampleValid == SAMPLE_VALID);
    assert(mainCalls==1);
    for(unsigned i=0;i<128;++i) {
        assert(dma_buffer[2*i]==(int16_t)(i-64) && dma_buffer[2*i+1]==0);
        assert(dma_buffer2[2*i]==(int16_t)(64-i) && dma_buffer2[2*i+1]==0);
    }
    HAL_I2S_TxCpltCallback(&hi2s3);
    assert(soundengine_calcNextSampleBlock() == 1 && lastHalf == 1);
    for(unsigned i=0;i<128;++i) {
        assert(dma_buffer[256+2*i]==(int16_t)(i-64) && dma_buffer[257+2*i]==0);
        assert(dma_buffer2[256+2*i]==(int16_t)(64-i) && dma_buffer2[257+2*i]==0);
    }
    assert(soundengine_calcNextSampleBlock() == 0);
    HAL_I2S_TxHalfCpltCallback(&hi2s3);
    packingSeam=1;
    dma_buffer[0]=dma_buffer2[0]=999;
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
    for(unsigned i=0;i<AUDIO_DMA_HALFWORDS;++i) dma_buffer[i]=dma_buffer2[i]=123;
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
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-I'+str(root/'Core/Inc'), '-Wall', '-Werror',
                    '-fsanitize=address,undefined', '-g', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

# Source-order guards complement runtime function tests; they are not an SD simulation.
preset = source('Preset/presetManager.c')
save = preset[preset.index('FRESULT preset_saveProject(uint8_t presetNr)\n{'):]
cleanup = save.index('preset_saveLastUsedProjectNrToSD(presetNr)')
assert save.index('soundengine_backgroundAudioEnd(bg);', cleanup) < save.index('return res;', cleanup)
assert 'menu_repaint' not in function(source('menu/menu.c'), 'menu_tick')
assert 'menu_uiTick();' in source('main.c')
for spi in ('spi2', 'spi3'):
    assert f'hdma_{spi}_tx.Init.Mode = DMA_CIRCULAR;' in source('stm32f7xx_hal_msp.c')
print('Scheduling function tests and source-order guards passed (fake HAL; not hardware validation).')

manager = source('Soundengine/AudioCodecManager.c')
assert 'codec_initCsCodec((uint32_t)dma_buffer2, AUDIO_HAL_CHANNEL_SAMPLES,(uint32_t)dma_buffer, AUDIO_HAL_CHANNEL_SAMPLES)' in manager
for spi in ('spi2', 'spi3'):
    for kind in ('Periph', 'Mem'):
        assert f'hdma_{spi}_tx.Init.{kind}DataAlignment = DMA_{"P" if kind == "Periph" else "M"}DATAALIGN_HALFWORD;' in source('stm32f7xx_hal_msp.c')
hal = (root / 'Drivers/STM32F7xx_HAL_Driver/Src/stm32f7xx_hal_i2s.c').read_text()
assert 'hi2s->TxXferSize = (Size << 1U);' in function(hal, 'HAL_I2S_Transmit_DMA')
