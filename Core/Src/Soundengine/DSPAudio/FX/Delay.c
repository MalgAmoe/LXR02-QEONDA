/*
 * Delay.c
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

#include "Soundengine/AudioSample.h"

/* History retains old/32767 units; taps convert to normalized old/32768,
 * bounded feedback converts back. History itself must not be rescaled. */

#include "Soundengine/DSPAudio/FX/Delay.h"

void Delay_init(Delay* d)
{

	d->pendingDelayTime = 0.f;
	d->timePending = 0;
	d->oldRead = d->newRead = 0;
	d->fracReadNew = d->fracReadOld = 0;
	d->write = FX_BUFFER_SIZE/20-10;

	d->feedback = 0.7f;
	//lp.setFreq(1);
	//d->rateFilter.setFreq(CALC_FILTER_FREQ(5000));

	//lpShaper.setShape(0.9f);
	//hpShaper.setShape(-0.9f);
	d->interpStep = d->interpValue = 0;

	initOnePole(&d->tone);
	initOnePole(&d->tone2);
}

float interpolate_s16(float a, float b, float x)
{
	return a*(1-x) + b*x;
}

void Delay_calcBufferPingPong(Delay* d, uint8_t bufferIdx)
{
	const uint32_t halfsize = FX_BUFFER_SIZE>>1;

	if(bufferIdx==0)
	{
		//calc with read pointer 0
		uint32_t pos2 = d->oldRead+1;
		pos2 = pos2 & (halfsize);
		d->tmpBuffer[0] = interpolate_s16((float)FX_HISTORY(d->oldRead), (float)FX_HISTORY(pos2),d->fracReadOld)*(32767.f/32768.f) ;
		d->tmpBuffer2[0] = interpolate_s16((float)FX_HISTORY(halfsize + d->oldRead), (float)FX_HISTORY(halfsize + pos2),d->fracReadOld)*(32767.f/32768.f) ;
		d->oldRead++;
		d->oldRead = d->oldRead & (halfsize);
	} else
	{
		//calc with read pointetr 2
		uint32_t pos2 = d->newRead+1;
		pos2 = pos2 & (halfsize);
		d->tmpBuffer[1] = interpolate_s16((float)FX_HISTORY(d->newRead), (float)FX_HISTORY(pos2),d->fracReadNew)*(32767.f/32768.f);
		d->tmpBuffer2[1] = interpolate_s16((float)FX_HISTORY(halfsize + d->newRead), (float)FX_HISTORY(halfsize + pos2),d->fracReadNew)*(32767.f/32768.f);
		d->newRead++;
		d->newRead = d->newRead & (halfsize);
	}

}

void Delay_calcBuffer(Delay* d, uint8_t bufferIdx)
{
	if(bufferIdx==0)
	{
		//calc with read pointer 0
		uint32_t pos2 = d->oldRead+1;
		pos2 = pos2 & (FX_BUFFER_SIZE);
		d->tmpBuffer[0] = interpolate_s16((float)FX_HISTORY(d->oldRead), (float)FX_HISTORY(pos2),d->fracReadOld)*(32767.f/32768.f) ;
		d->oldRead++;
		d->oldRead = d->oldRead & (FX_BUFFER_SIZE);
	} else
	{
		//calc with read pointetr 2
		uint32_t pos2 = d->newRead+1;
		pos2 = pos2 & (FX_BUFFER_SIZE);
		d->tmpBuffer[1] = interpolate_s16((float)FX_HISTORY(d->newRead), (float)FX_HISTORY(pos2),d->fracReadNew)*(32767.f/32768.f) ;;
		d->newRead++;
		d->newRead = d->newRead & (FX_BUFFER_SIZE);
	}
}

void Delay_processPingPong(Delay *d, AudioSample*fxBuffer,AudioSample* outL, AudioSample* outR, uint16_t size,  uint8_t channels, float dryWet)
{

    d->oldRead &= FX_BUFFER_SIZE >> 1;
    d->newRead &= FX_BUFFER_SIZE >> 1;
    d->write &= FX_BUFFER_SIZE >> 1;

	float x[2];
	AudioSample* stereoOut = outL;

	for(uint8_t i=0;i<size;i++)
	{

		const uint8_t idx1 = i*2;
		const uint8_t idx2 = i*2+1;

			float outL, outR;

			if(d->interpValue <= 0.f)
			{
				Delay_calcBufferPingPong(d, 0);
				outL = d->tmpBuffer[0];
				outR = d->tmpBuffer2[0];

				{

					if(	d->timePending )
					{
						d->timePending = 0;
						Delay_setDelayTime(d, d->pendingDelayTime);
					}
				}

			} else
			{
				Delay_calcBufferPingPong(d, 0);
				Delay_calcBufferPingPong(d, 1);

				outL = d->tmpBuffer[0] * d->interpValue + d->tmpBuffer[1] * (1.0f - d->interpValue);
				outR = d->tmpBuffer2[0] * d->interpValue + d->tmpBuffer2[1] * (1.0f - d->interpValue);

				d->interpValue -= d->interpStep;

				if (d->interpValue <= 0.0f)
				{
					d->oldRead = d->newRead;
					d->fracReadOld = d->fracReadNew;
				}
			}

			outL = calcOnePole(&d->tone, outL);
			outR = calcOnePole(&d->tone2, outR);

			float itg = (audio_sample_bound((fxBuffer[idx1]) + ((outL*d->feedback))));
			float val = itg*(32768.f/32767.f);
			if(val > 1.f) val = 1.f;
			else if(val < -1.f) val = -1.f;
			FX_HISTORY((FX_BUFFER_SIZE>>1) + d->write) = val;

			itg = (audio_sample_bound((fxBuffer[idx2]) + ((outR*d->feedback))));
			val = itg*(32768.f/32767.f);
			if(val > 1.f) val = 1.f;
			else if(val < -1.f) val = -1.f;
			FX_HISTORY(d->write++) = val;

			d->write &= FX_BUFFER_SIZE>>1;

			float wet =  outL;
			float wet2 =  outR;

			{ float pair[2] = {(fxBuffer[idx1] + (audio_mix_bound((wet - fxBuffer[idx1]) * dryWet))), (fxBuffer[idx2] + (audio_mix_bound((wet2 - fxBuffer[idx2]) * dryWet)))}; x[0]=audio_mix_bound(pair[0]); x[1]=audio_mix_bound(pair[1]); }

			if (channels == 2)
      {
        stereoOut[0] = audio_mix_add(stereoOut[0], x[0]); stereoOut[1] = audio_mix_add(stereoOut[1], x[1]);
        stereoOut += 2;
      }
      else
      {
        stereoOut[0] = audio_mix_add(stereoOut[0], x[0]);
        stereoOut += 2;
      }

	}
}

void Delay_process(Delay *d, AudioSample*fxBuffer,AudioSample* outL, AudioSample* outR, uint16_t size,  uint8_t channels, float dryWet)
{

	float x[2];
	AudioSample* stereoOut = outL;

	for(uint8_t i=0;i<size;i++)
	{

		const uint8_t idx1 = i*2;
		const uint8_t idx2 = i*2+1;

    float out;

    if(d->interpValue <= 0.f)
    {
      Delay_calcBuffer(d, 0);
      out = d->tmpBuffer[0];

      {

        if(	d->timePending )
        {
          d->timePending = 0;
          Delay_setDelayTime(d, d->pendingDelayTime);
        }
      }

    } else
    {
      Delay_calcBuffer(d, 0);
      Delay_calcBuffer(d, 1);

      out = d->tmpBuffer[0] * d->interpValue + d->tmpBuffer[1] * (1.0f - d->interpValue);

      d->interpValue -= d->interpStep;

      if (d->interpValue <= 0.0f)
      {
        d->oldRead = d->newRead;
        d->fracReadOld = d->fracReadNew;
      }
    }

    out = calcOnePole(&d->tone, out);

    float itg = (audio_sample_bound((audio_sample_bound((fxBuffer[idx1]) + (fxBuffer[idx2]))) + ((out*d->feedback))));
    float val = itg*(32768.f/32767.f);
    if(val > 1.f) val = 1.f;
    else if(val < -1.f) val = -1.f;
    FX_HISTORY(d->write++) = val;

    d->write &= FX_BUFFER_SIZE;

    float wet =  out;
    float wet2 =  out;

    { float pair[2] = {(fxBuffer[idx1] + (audio_mix_bound((wet - fxBuffer[idx1]) * dryWet))), (fxBuffer[idx2] + (audio_mix_bound((wet2 - fxBuffer[idx2]) * dryWet)))}; x[0]=audio_mix_bound(pair[0]); x[1]=audio_mix_bound(pair[1]); }

    if (channels == 2)
    {
      stereoOut[0] = audio_mix_add(stereoOut[0], x[0]); stereoOut[1] = audio_mix_add(stereoOut[1], x[1]);
      stereoOut += 2;
    }
    else
    {
      stereoOut[0] = audio_mix_add(stereoOut[0], x[0]);
      stereoOut += 2;
    }

	}
}

float interpolate(float a, float b, float x)
{
	return a*(1-x) + b*x;
}
float calcDelayTime(Delay* d, float timeCv)
{
	if(d->delayType == DELAY_NORMAL)
	{
		const float min = interpolate(LOW_MIN,HI_MIN,d->range);
		const float max = interpolate(LOW_MAX,HI_MAX,d->range);
		return interpolate(min,max,timeCv);
	}
	else
	{
		const float min = interpolate(LOW_MIN,HI_MIN,d->range);
		const float max = interpolate(LOW_MAX,HI_MAX*0.48f,d->range);
		return interpolate(min,max,timeCv);
	}

}

void Delay_setDelayTime(Delay* d, float t)
{

#if 1
	if(d->interpValue <=0)
	{
		d->delayTime = t;//rateFilter.process(t);

		//uint32_t offset = medianFilter(delayTime*SRAM_SIZE*range);
		float offset =  /*medianFilter*/(calcDelayTime(d, d->delayTime * d->range));
		//timeBuffer.write(offset);
		//offset = timeBuffer.getAverage();

		uint32_t offItg = (uint32_t)offset;
		d->fracReadNew = offset-offItg;

		//MainApplication::setLedTempo(offset/(float)(SAMPLE_RATE)*500.f);

		//newRead = medianFilter((uint32_t)(write-1-delayTime*SRAM_SIZE*range));
		d->newRead = (d->write-1-  offItg);

		//read = (uint32_t)(write-t*44100);
		if(d->delayType == DELAY_NORMAL)
		{
			d->newRead = d->newRead & (FX_BUFFER_SIZE);
		}
		else
		{
			d->newRead = d->newRead & (FX_BUFFER_SIZE>>1);
		}

		d->interpValue = 1.f;
		const float fadeSeconds = 0.01f;//100 ms
		const float fadeInSamps = REAL_FS * fadeSeconds;
		d->interpStep = 1.0f / fadeInSamps;
	}
	else
	{
		d->pendingDelayTime = t;
		d->timePending = 1;
	}
#else
	d->delayTime = t;

	d->oldRead = (uint32_t)(d->write - 1 -  (d->delayTime*d->bufferSize));
	d->oldRead = d->oldRead & (d->bufferSize);

#endif

}

void Delay_setFeedback(Delay* d, float fb)
{
	d->feedback = fb;
}
void Delay_setRange(Delay* d, float r)
{
	d->range = r;
	Delay_setDelayTime(d, d->delayTime);

}
void Delay_setFilter(Delay* d, float f)
{
	setOnePoleCoef(&d->tone, f*f);
	setOnePoleCoef(&d->tone2, f*f);
}

