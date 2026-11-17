/*
 * Compressor.c
 *
 *  Created on: Aug 27, 2020
 *      Author: julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include "Soundengine/AudioSample.h"

#include "Soundengine/DSPAudio/FX/Compressor.h"
#include "math.h"
#include "main.h"

enum
{
	RATIO_1,
	RATIO_2,
	RATIO_3,
	RATIO_4,
	RATIO_6,
	RATIO_8
};

static const AudioReal DC_OFFSET = 1.0E-25;

void Compressor_init(Compressor *c)
{
	c->attack = 0.1;
	c->release = 300;

	//c->filter = 0.0;
	c->env = 0.0;
	c->tresh = 3;
	c->markupGain = 1.0f;

}

// linear -> dB conversion
static AudioReal lin2dB( AudioReal lin ) {
	static const AudioReal LOG_2_DB = 8.6858896380650365530225783783321;	// 20 / ln( 10 )
	return logf( lin ) * LOG_2_DB;
}

// dB -> linear conversion
static AudioReal dB2lin( AudioReal dB ) {
	static const AudioReal DB_2_LOG = 0.11512925464970228420089957273422;	// ln( 10 ) / 20
	return expf( dB * DB_2_LOG );
}

//att/release, time in ms to reach 63% of final value
void Compressor_setAttack(Compressor *c, float a)
{
	c->attack = 0.03f + a *100.f; //[ms]
	c->attack = exp( -1000.0 / ( c->attack * REAL_FS ) );
}
void Compressor_setTreshold(Compressor *c, float t)
{
	c->tresh = -96 + t*96; //[-96:0]dB
}

void Compressor_setGain(Compressor *c, float g)
{
	c->markupGain = 1.f + g*2;
}
void Compressor_setRelease(Compressor *c, float r)
{
	c->release = 25+r*175.f; //[ms]
	c->release = exp( -1000.0 / ( c->release * REAL_FS ) );
}

void Compressor_setRatio(Compressor *c, uint8_t r)
{
	switch(r)
	{
	default:
	case RATIO_1:
		c->ratio = 1.0f;
		break;

	case RATIO_2:
		c->ratio = 0.5f;
		break;
	case RATIO_3:
		c->ratio = 1.f/3.f;
		break;
	case RATIO_4:
		c->ratio = 0.25f;
		break;
	case RATIO_6:
		c->ratio = 1.f/6.f;
		break;
	case RATIO_8:
		c->ratio = 0.125f;
		break;
	}
}

void Compressor_process(Compressor *c, AudioSample*fxBuffer,AudioSample* outL, AudioSample* outR, uint16_t size,  uint8_t channels, float dryWet)
{

	float x[2];
	AudioSample* stereoOut = outL;

	float left[size];
	float right[size];

	if(channels==2)
	{

		for(uint8_t i=0; i<size;i++)
		{

			float in = 0.5f * (fxBuffer[i*2]) + 0.5f * (fxBuffer[i*2+1]);
			AudioReal peak = fabs(in);

			peak += DC_OFFSET;
			AudioReal peakdB = lin2dB(peak);
			AudioReal overdB = peakdB - c->tresh;
			if ( overdB < 0.0f )
				overdB = 0.0f;

			AudioReal  coeff = overdB > c->env ? c->attack : c->release;
			c->env = overdB + coeff * (c->env - overdB);

			AudioReal gr = c->env * (c->ratio - 1.0f);
			gr = dB2lin(gr);

			left[i]  = audio_sample_bound(fxBuffer[i*2] * gr * c->markupGain);
			right[i] = audio_sample_bound(fxBuffer[i*2+1] * gr * c->markupGain);

			const uint8_t idx1 = i*2;
			const uint8_t idx2 = i*2+1;

			{ float pair[2] = {fxBuffer[idx1] + (audio_mix_bound((left[i] - fxBuffer[idx1]) * dryWet)), fxBuffer[idx2] + (audio_mix_bound((right[i] - fxBuffer[idx2]) * dryWet))}; x[0]=pair[0]; x[1]=pair[1]; }

			stereoOut[0] = audio_mix_add(stereoOut[0], x[0]); stereoOut[1] = audio_mix_add(stereoOut[1], x[1]);
			stereoOut += 2;
		}
	}
	else
	{
		for(uint8_t i=0; i<size;i++)
		{
			const uint8_t idx1 = i*2;

			float in = fxBuffer[idx1];
			AudioReal peak = fabs(in);

			peak += DC_OFFSET;
			AudioReal peakdB = lin2dB(peak);
			AudioReal overdB = peakdB - c->tresh;
			if ( overdB < 0.0f )
				overdB = 0.0f;

			AudioReal  coeff = overdB > c->env ? c->attack : c->release;
			c->env = overdB + coeff * (c->env - overdB);

			AudioReal gr = c->env * (c->ratio - 1.0f);
			gr = dB2lin(gr);

			left[i]  = audio_sample_bound(fxBuffer[idx1] * gr * c->markupGain);

			const float dw = fxBuffer[idx1] + (audio_mix_bound((left[i] - fxBuffer[idx1]) * dryWet));
			*outL = audio_mix_add(*outL, dw);
			outL += 2;
		}
	}
}

