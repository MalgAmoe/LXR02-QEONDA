/*
 * 1PoleLp.h
 *
 *  Created on: 08.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include "Soundengine/AudioSample.h"


#ifndef ONE_POLELP_H_
#define ONE_POLELP_H_
//-------------------------------------------------------------
#include "stm32f7xx_hal.h"
//-------------------------------------------------------------
#define CALC_FILTER_FREQ(f) (1-expf(-2.f*M_PI*f/(float)REAL_FS))

typedef struct OnePoleStruct
{
	AudioReal r;
	AudioReal b;
} OnePoleFilter;
//-------------------------------------------------------------
void initOnePole(OnePoleFilter* filter);
float calcOnePole(OnePoleFilter* filter, AudioReal input);
float calcOnePoleAdaptiveVolume(OnePoleFilter* filter, AudioReal input);
void calcOnePoleBlock(OnePoleFilter* filter, AudioSample* buf, const uint8_t size);
void calcOnePoleBlockFixedInput(OnePoleFilter* filter, float input,float* output, const uint8_t size);
void setOnePoleCoef(OnePoleFilter* filter,AudioReal val);
void setOnePoleValue(OnePoleFilter* filter,AudioReal val);
void setOnePoleFreq(OnePoleFilter* filter,AudioReal f);

#endif /* ONE_POLELP_H_ */
