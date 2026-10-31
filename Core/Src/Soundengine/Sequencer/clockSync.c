/*
 * clockSync.c
 *
 *  Created on: 03.02.2013
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */



#include "Soundengine/Sequencer/clockSync.h"
#include "Soundengine/TriggerOut.h"

/* Main and TIM2 share the parser and external sequencer work. Never wait in
 * an IRQ, and never keep PRIMASK set while parsing, stepping or loading kits. */
static volatile uint8_t sync_controlBusy;
static volatile uint8_t sync_delayedStepPending;
static uint32_t sync_delayedStepTimer;
static volatile uint8_t sync_transportPending, sync_transportReset, sync_transportRun;
static uint8_t sync_clockCnt;
static SyncPulseHistory sync_midiHistory;

uint8_t sync_tryControl(void)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    uint8_t acquired = !sync_controlBusy;
    if(acquired) sync_controlBusy = 1;
    __set_PRIMASK(mask);
    return acquired;
}

void sync_releaseControl(void)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    sync_controlBusy = 0;
    __set_PRIMASK(mask);
}

/* 4 kHz timestamps: subtract as integers BEFORE conversion to float.
 * Reject zero intervals and gaps over 60000 ticks (15 seconds).
 * This dropout threshold supports 2 BPM even at analogue 4 PPQ (30000 ticks).
 * A discontinuity starts a fresh window but preserves the last good BPM.
 * Each source owns its history; reset by source changes with IRQs masked. */
void sync_measurePulse(SyncPulseHistory *history, uint32_t now, uint8_t factor)
{
    uint32_t interval = now - history->last;
    history->last = now;
    if(!history->baseline) {
        history->baseline = 1;
        return;
    }
    if(interval == 0 || interval > 60000u) {
        history->count = history->pos = 0;
        return;
    }
    history->window[history->pos++] = (float)interval / factor;
    history->pos &= WINDOW_MASK;
    if(history->count < WINDOW_SIZE) history->count++;
    float sum = 0;
    for(uint8_t i = 0; i < history->count; i++) sum += history->window[i];
    float bpm = 10000.f / (sum / history->count);
    /* Bound the float-to-integer conversion even for malformed fast clocks. */
    if(bpm > 65535.f) bpm = 65535.f;
    if(bpm < 1.f) bpm = 1.f;
    seq_setBpm((uint16_t)bpm);
}

void sync_cancelPending(void)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    sync_delayedStepPending = 0;
    trigger_clockReceived = 0;
    __set_PRIMASK(mask);
}

void sync_sourceChanged(void)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    sync_cancelPending();
    sync_transportPending = sync_transportReset = 0;
    sync_clockCnt = 0;
    sync_midiHistory.baseline = sync_midiHistory.count = sync_midiHistory.pos = 0;
    trigger_ResetPosition();
    __set_PRIMASK(mask);
}

/* IRQ handoff, not an event queue: reset is sticky, last run level wins.
 * Thus a stop/start pair between ticks still resets before restarting. */
void sync_requestAnalogTransport(uint8_t run)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    sync_cancelPending();
    sync_transportPending = 1;
    sync_transportRun = run;
    if(!run) sync_transportReset = 1;
    __set_PRIMASK(mask);
}

void sync_processAnalogTransport(void)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    uint8_t pending = sync_transportPending;
    uint8_t reset = sync_transportReset;
    uint8_t run = sync_transportRun;
    sync_transportPending = sync_transportReset = 0;
    __set_PRIMASK(mask);
    if(!pending || seq_getExtSync() != 1) return;
    if(reset) {
        seq_setRunning(0);
        trigger_ResetPosition();
        seq_resetPosition();
        trigger_prescaleCounterClockInput = 0;
    }
    if(run) seq_setRunning(1);
}

uint8_t sync_canSchedule(void)
{
    return seq_isRunning() && seq_getExtSync() && !sync_transportPending;
}

/* Called with control ownership. IRQs can cancel but cannot step the seq. */
void sync_externalStep(void)
{
    uint32_t delay = (uint32_t)seq_getDeltaTShuffleDelay(seq_getBpm());
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    uint8_t ready = sync_canSchedule();
    uint8_t shuffled = seq_getMasterStepCnt() % 2 == 1;
    if(ready && shuffled) {
        sync_delayedStepTimer = systick_ticks + delay;
        sync_delayedStepPending = 1;
    }
    __set_PRIMASK(mask);
    if(ready && !shuffled && sync_canSchedule()) {
        seq_nextStep();
        seq_prescaleCounter = 0;
        seq_MidiSyncQueue(0);
    }
}

void sync_pollDelayedStep(void)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    uint8_t due = sync_delayedStepPending && sync_canSchedule() &&
        (uint32_t)(systick_ticks - sync_delayedStepTimer) < 0x80000000u;
    if(due) sync_delayedStepPending = 0;
    __set_PRIMASK(mask);
    if(due && sync_canSchedule()) {
        seq_nextStep();
        seq_prescaleCounter = 0;
        seq_MidiSyncQueue(0);
    }
}

void sync_tick(void)
{
    if(seq_getExtSync() != 2) return;
    sync_measurePulse(&sync_midiHistory, systick_ticks, 1);
    if(sync_canSchedule() && sync_clockCnt == 0) sync_externalStep();
    if(++sync_clockCnt >= 6) sync_clockCnt = 0;
}

void sync_midiResetPosition(void)
{
    sync_cancelPending();
    sync_clockCnt = 0;
    seq_resetPosition();
}

void sync_midiStartStop(uint8_t isStart)
{
    seq_setRunning(isStart);
    if(isStart) {
        sync_midiHistory.baseline = sync_midiHistory.count = sync_midiHistory.pos = 0;
    }
}

uint8_t sync_getClockCnt(void)
{
    return sync_clockCnt;
}
