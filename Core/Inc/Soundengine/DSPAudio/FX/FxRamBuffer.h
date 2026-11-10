/*
 * FxRamBuffer.h
 *
 *  Created on: 30.08.2020
 *      Author: julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#ifndef INC_SOUNDENGINE_DSPAUDIO_FX_FXRAMBUFFER_H_
#define INC_SOUNDENGINE_DSPAUDIO_FX_FXRAMBUFFER_H_

#include "Soundengine/globals.h"
#include "Soundengine/config.h"

/* 32768 float history samples; capacity and delay-time laws are unchanged. */
#define FX_BUFFER_SIZE 0x7FFF // Power-of-two capacity minus one for masking.

/* The old history occupied 64 KiB DTCM. Float history uses 32 KiB DTCM
 * plus 96 KiB ordinary RAM, leaving both regions room for stack/heap.
 * Logical indices, capacity and delay-time laws are unchanged. */
#define FX_FLOAT_FAST_SAMPLES 8192u
extern INDTCMZ float fxHistoryFast[FX_FLOAT_FAST_SAMPLES];
extern float fxHistoryRam[FX_BUFFER_SIZE+1-FX_FLOAT_FAST_SAMPLES];
static inline float *fx_history_sample(unsigned index)
{
    return index < FX_FLOAT_FAST_SAMPLES ? &fxHistoryFast[index] :
        &fxHistoryRam[index-FX_FLOAT_FAST_SAMPLES];
}
#define FX_HISTORY(index) (*fx_history_sample(index))

//because we have 17 delay units using the memory in the reverb
//must be masking compatible pow2-1
#define MAX_ALLPASS_SIZE 0x800//(FX_BUFFER_SIZE/18)

#endif /* INC_SOUNDENGINE_DSPAUDIO_FX_FXRAMBUFFER_H_ */
