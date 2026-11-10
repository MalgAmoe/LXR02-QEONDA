/*
 * BufferTools.h
 *
 *  Created on: 04.01.2013
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include "Soundengine/AudioSample.h"


#ifndef BUFFERTOOLS_H_
#define BUFFERTOOLS_H_

#include "stm32f7xx_hal.h"
#include "dither.h"
#include "Soundengine/config.h"
#include <string.h>
//---------------------------------------------------
static inline void bufferTool_addBuffers(AudioSample* buf1, AudioSample* buf2, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		buf1[i] += buf2[i];
	}
}
//---------------------------------------------------
IN_ITCM_RAM static inline void bufferTool_addBuffersSaturating(AudioSample* buf1, AudioSample* buf2, const uint8_t size)
{
#if LXR_AUDIO_FLOAT32
    for(unsigned i=0;i<size;++i) buf1[i] = audio_mix_add(buf1[i], buf2[i]);
#elif 1
	int32_t* x = (int32_t*)buf1;
	int32_t* y = (int32_t*)buf2;

	for(uint8_t i=0;i<size/2;i++)
	{
		x[i] = (__QADD16(x[i],y[i]));
	}

#else
		uint8_t i;
		for(i=0;i<size;i++)

		for(uint8_t i=0;i<size;i++)
	 	{
			buf1[i] = (__QADD16(buf1[i],buf2[i]));
	 	}
#endif
}
//---------------------------------------------------
static inline void bufferTool_addBuffersSaturatingWithGain(AudioSample* buf1, AudioSample* buf2, const float gain, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		#if LXR_AUDIO_FLOAT32 && LXR_FLOAT_MIX_CLIP
        buf1[i] = audio_mix_add(buf1[i],buf2[i]) * gain;
#else
        buf1[i] = (__QADD16(buf1[i],buf2[i])) * gain;
#endif
	}
}
//---------------------------------------------------
static inline void bufferTool_subBuffersSaturating(AudioSample* buf1, AudioSample* buf2, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		#if LXR_AUDIO_FLOAT32 && LXR_FLOAT_MIX_CLIP
        buf1[i] = audio_mix_bound(buf1[i]-buf2[i]);
#else
        buf1[i] = (__QSUB16(buf1[i],buf2[i])) ;
#endif
	}
}
//---------------------------------------------------
static inline void bufferTool_copyWithGain(AudioSample* buf1, AudioSample* buf2, float gain, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		buf1[i] = buf2[i]*gain;
	}
}
//---------------------------------------------------
IN_ITCM_RAM static inline void bufferTool_clearBuffer(AudioSample* buf, const uint8_t size)
{
#if 0
	uint8_t i;
	for(i=0;i<size;i++)
	{
		buf[i] = 0;
	}
#else

	/*
	int32_t* buffer = (int32_t*)buf;
	for(uint8_t i=0;i<size/2;i++)
	{
		buffer[i] = 0;
	}
	*/
	#if LXR_AUDIO_FLOAT32
memset(buf, 0, size*sizeof(*buf));
#else
memset((int32_t*)buf, 0 ,size/2*sizeof(int32_t));
#endif

#endif
}
//---------------------------------------------------
static inline void bufferTool_addGain(AudioSample* buf, const float gain, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		buf[i] *= gain;
	}
}
//---------------------------------------------------
static inline void bufferTool_addGainDithered(Dither* dither, AudioSample* buf, const float gain, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
#if LXR_AUDIO_FLOAT32
buf[i] *= gain;
#else
		buf[i] = dither_process(dither,(buf[i]/32768.0f) * gain);
#endif
	}
}
//---------------------------------------------------
static inline void bufferTool_addGainInterpolated(AudioSample* buf, const float gain, const float lastGain, const uint8_t size)
{


#if 0
	//Size == 32 (DMA_BUFFER_SIZE)
#if (OUTPUT_DMA_SIZE != 32)
#error "WRONG DMA BUFFER SIZE. MUST BE 32 TO WORK WITH THIS ROUTINE"
#endif

	//Resolution OK?
	int16_t g = gain* 0x7fff;		//16 bit gain value
	int16_t lg = lastGain* 0x7fff;	//last gain as 16 bit

	uint32_t val1, val2;
	uint64_t val3 = 0;

	val1 = lg | (g<<16);

		for(uint8_t i=0;i<size;i++)
		{
			int16_t frac = i/(size-1.f)*0xff;//i<<3;							//8-bit interpolation index - ONLY WORKS WITH SIZE 32!!!
			val2 = (256-frac) | (frac<<16);
			uint64_t res = __SMLALD(val1, val2, val3);
			uint32_t cg = res>>8;//(lg*(256-frac) + g * frac) >> 8;
			buf[i] = ((int32_t)buf[i] * cg)>>16;
		}

#else

#if 0
	uint64_t g = gain* 0xffffffff;		//32 bit gain value
	uint64_t lg = lastGain* 0xffffffff;				//last gain as 32 bit

	for(uint8_t i=0;i<size;i++)
	{
		uint8_t frac = i/(size-1.f)*0xff;//i<<3;							//8-bit interpolation index -
		uint32_t cg = (lg*(256-frac) + g * frac) >> 8;
		buf[i] = ((int64_t)buf[i] * cg)>>32;
	}
#else
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const AudioReal frac = i/(size-1.f);
		const AudioReal currentGain = lastGain + frac*(gain - lastGain);
		buf[i] = buf[i] * currentGain;
	}
#endif
#endif
}
//---------------------------------------------------
static inline void bufferTool_addGainInterpolatedDouble(AudioSample* buf, const AudioReal gain, const AudioReal lastGain, const uint8_t size)
{

	uint8_t i;
	for(i=0;i<size;i++)
	{
		const AudioReal frac = i/(size-1.0);
		const AudioReal currentGain = lastGain + frac*(gain - lastGain);
		buf[i] = buf[i] * currentGain;
	}

}
//---------------------------------------------------
static inline void bufferTool_addGainInterpolatedDoubleDithered(Dither* dither, AudioSample* buf, const AudioReal gain, const AudioReal lastGain, const uint8_t size)
{

	uint8_t i;
	for(i=0;i<size;i++)
	{
		AudioReal in = (buf[i]/32768.0f);
		if(in>1.0)in=1.0;
		else if( in < -1.0)in=-1.0;
		const AudioReal frac = i/(size-1.0);
		const AudioReal currentGain = lastGain + frac*(gain - lastGain);
#if LXR_AUDIO_FLOAT32
buf[i] *= currentGain;
#else
		buf[i] = dither_process(dither,in* currentGain);
#endif
//		buf[i] = buf[i] * currentGain;
	}

}
//---------------------------------------------------
static inline void bufferTool_mulInt(AudioSample* buf, const int16_t gain, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		buf[i] *= gain;
	}
}
//---------------------------------------------------
static inline void bufferTool_multiplyWithFloatBuffer(AudioSample* buf, float* fltBuf, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		buf[i] *= fltBuf[i];
	}
}
//---------------------------------------------------
static inline void bufferTool_multiplyWithFloatBufferDithered(Dither* dither, AudioSample* buf, float* fltBuf, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
#if LXR_AUDIO_FLOAT32
buf[i] *= fltBuf[i];
#else
		buf[i] = dither_process(dither,(buf[i]/32768.0f) * fltBuf[i]);
#endif

	}
}
//---------------------------------------------------
static inline void bufferTool_moveBuffer(AudioSample* dst, AudioSample* src, const uint8_t size)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		dst[i] = src[i];
	}
}
//---------------------------------------------------
#endif /* BUFFERTOOLS_H_ */
