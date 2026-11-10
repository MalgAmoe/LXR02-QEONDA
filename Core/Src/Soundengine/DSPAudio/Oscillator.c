/*
 * Oscillator.c
 *
 *  Created on: 02.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include "Soundengine/AudioSample.h"


#include "Soundengine/DSPAudio/Oscillator.h"
#include "Soundengine/DSPAudio/random.h"
#include "Soundengine/DSPAudio/Samples.h"
#include "Soundengine/MIDI/MidiParser.h"
#include "Soundengine/MIDI/MidiNoteNumbers.h"
#include "Soundengine/Sequencer/sequencer.h"

static __inline uint32_t freq2PhaseIncr(const float f) //4096
{
	return (((TABLESIZE*f)/REAL_FS))*1048576 ; // 1048576 <-> (<<20)
}
//TODO die phaseInc berechnung kann man doch sicher per LUT machen!
//-----------------------------------------------------------
static __inline uint8_t fast_log2 (const uint32_t val)
{
	return 31-__CLZ(val);
}
//-----------------------------------------------------------
static __inline int freqToMidiNote(const float f)
{
	return (12*fast_log2((uint32_t)(f/440.f)))+70;
}
//-----------------------------------------------------------
static __inline uint8_t freqToTableIndex(const float f)
{
	return freqToMidiNote(f)/12;
}
//-----------------------------------------------------------

//-----------------------------------------------------------
static __inline uint32_t freq2PhaseIncr1024(const float f)
{
	return (((1024*f)/REAL_FS))*4194304 ; //(<<22)
}
//-----------------------------------------------------------
static __inline uint32_t freq2PhaseIncr32767(const float f)
{
	return (((1024*f)/REAL_FS))*131072 ; //(<<17)
}
//-----------------------------------------------------------
IN_ITCM_RAM void calcSineBlock(OscInfo* osc, AudioSample* buf, const uint8_t size ,const float gain)
{
	//tablesize 4096 => 0b111111111111 -> 12 bits
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		AudioSample oscOut;

		const uint32_t index =  oscPhase;
		uint32_t  itg	= index>>20; // 12 msb as itg index

		#if INTERPOLATE_OSC
			oscOut = (sine_table[itg++] * (1.f/32768.f));

			//const float frac = (index&0x7ffff)*0.0000019073486328125f;  // 1/0x7ffff = 0.0000019073486328125f
			//oscOut += frac*(sine_table[itg] - oscOut);
			//a + t * (b - a);
			uint32_t frac = index&0xFFFFF;
oscOut = oscOut + ((sine_table[itg] * (1.f/32768.f)) - oscOut) * ((float)frac / 1048576.f);
		#else
			oscOut = (sine_table[itg] * (1.f/32768.f));
		#endif

		osc->phase = oscPhase + osc->phaseInc;

		buf[i] = oscOut * gain;
	}
}
//-----------------------------------------------------------

//-----------------------------------------------------------
// These three FM blocks intentionally depend on the production ARM compiler
// emitting vcvt.u32.f32 (bounded negative products map to zero on target).
// Negative float-to-unsigned conversion is not portable C; verify ARM codegen.
// Restore the old modulation scale BEFORE multiply/uint32 quantization, not
// after conversion. Waveform reads (both endpoints) stay normalized.
IN_ITCM_RAM void calcFmSineBlock(OscInfo* osc, AudioSample* modBuffer, AudioSample* buf, uint8_t size,const float gain)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		AudioSample oscOut ;

		const uint32_t index =  oscPhase + (((uint32_t)((modBuffer[i]*32768.f)*osc->fmMod))<<17);
		uint32_t  itg	= index>>20;

	#if INTERPOLATE_FM_OSC
		oscOut = (sine_table[itg++] * (1.f/32768.f));
		//const float frac	= (index&0x7ffff)*0.0000019073486328125f;
		//oscOut += frac*(sine_table[itg] - oscOut);
		uint32_t frac = index&0xFFFFF;
oscOut = oscOut + ((sine_table[itg] * (1.f/32768.f)) - oscOut) * ((float)frac / 1048576.f);
	#else
		oscOut = (sine_table[itg] * (1.f/32768.f));
	#endif

		osc->phase = oscPhase + osc->phaseInc;
		buf[i] =  oscOut * gain;
	}
}
//-----------------------------------------------------------
//---------------------------------------------------------------
IN_ITCM_RAM void calcFmBlock(OscInfo* osc, const int16_t table[][1024], AudioSample* modBuffer, AudioSample* buf, uint8_t size ,const float gain)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		AudioSample oscOut ;
		const uint32_t index =  oscPhase + (((uint32_t)((modBuffer[i]*32768.f)*osc->fmMod))<<19);

		uint32_t  itg	= index>>22; //10 bit index, 22 bit fractional part

	#if INTERPOLATE_FM_OSC
		oscOut = (table[osc->tableOffset][itg++] * (1.f/32768.f));
		//const float frac	= (index&0x003FFFFF)*2.38418579101562e-07f;
		//oscOut += frac*(table[osc->tableOffset][itg] - oscOut);
		uint32_t frac = index & 0x3FFFFF;
oscOut = oscOut + ((table[osc->tableOffset][itg & 1023u] * (1.f/32768.f)) - oscOut) * ((float)frac / 4194304.f);

	#else
		oscOut = (table[overtoneIndex][itg] * (1.f/32768.f));
	#endif

		osc->phase = oscPhase + osc->phaseInc;
		osc->output = oscOut;
		buf[i] = oscOut * gain;
	}
}
//-----------------------------------------------------------
void calcPwmFmBlock(OscInfo* osc, AudioSample* modBuffer, AudioSample* buf, uint8_t size ,const float gain, const float pwm)
{
	// PWM is normalized to [0,1] by normal control paths. Convert only the
	// offset, then use unsigned addition for defined modulo-2^32 phase wrap.
	const uint32_t pwmOffset = (uint32_t)(pwm * (UINT32_MAX/2));
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		AudioSample oscOut ;
		const uint32_t index =  oscPhase + (((uint32_t)((modBuffer[i]*32768.f)*osc->fmMod))<<19);
		const uint32_t index2 = index + pwmOffset;

		 uint32_t  itg	 = index>>22;
		 uint32_t  itg2 = index2>>22;

	#if INTERPOLATE_FM_OSC
		oscOut = (sawTable[osc->tableOffset][itg++] * (1.f/32768.f));
		//const float frac	= (index&0x003FFFFF)*2.38418579101562e-07f;
		//oscOut += frac*(sawTable[osc->tableOffset][itg] - oscOut);
		uint32_t frac = index & 0x3FFFFF;
oscOut = oscOut + ((sawTable[osc->tableOffset][itg & 1023u] * (1.f/32768.f)) - oscOut) * ((float)frac / 4194304.f);

		AudioSample osc2Out = (sawTable[osc->tableOffset][itg2++] * (1.f/32768.f));// * -1;
		//const float frac	= (index&0x003FFFFF)*2.38418579101562e-07f;
		frac = index2 & 0x3FFFFF;
		//osc2Out += frac*(sawTable[osc->tableOffset][itg2] * -1 - osc2Out);
osc2Out = osc2Out + ((sawTable[osc->tableOffset][itg2 & 1023u] * (1.f/32768.f)) - osc2Out) * ((float)frac / 4194304.f);

        oscOut = audio_sample_bound(oscOut-osc2Out); /* PWM waveform saturation */


	#else
		oscOut = (sawTable[overtoneIndex][itg] * (1.f/32768.f));
	#endif

		osc->phase = oscPhase + osc->phaseInc;
		osc->output = oscOut;
		buf[i] = oscOut * gain;
	}
}
//-----------------------------------------------------------
//-----------------------------------------------------------
IN_ITCM_RAM void calcNextOscSampleFmBlock(OscInfo* osc, AudioSample* modBuffer, AudioSample* buf, uint8_t size ,const float gain, const float pwm)
{
	switch(osc->waveform)
		{
		case SINE:
			calcFmSineBlock(osc,modBuffer,buf,size,gain);
			break;

		case SAW:
			calcFmBlock(osc,sawTable,modBuffer,buf,size,gain);
			break;

		case TRI:
			calcFmBlock(osc, triTable, modBuffer,buf,size,gain);
			break;

		case REC:
			calcFmBlock(osc, recTable, modBuffer,buf,size,gain);
			break;

		case NOISE:
			//TODO FM noise - needed since its tuned digi noise!
			calcNoiseBlock(osc,buf,size,gain);
			break;

		case PWM:
			calcPwmFmBlock(osc,modBuffer,buf,size,gain, pwm);//calcSampleOscFmBlock(osc,modBuffer,buf,size,gain);
			break;

		default:
			calcUserSampleOscFmBlock(osc,modBuffer,buf,size,gain);
			break;

		}
}
//-----------------------------------------------------------

//-----------------------------------------------------------
IN_ITCM_RAM void calcNoiseBlock(OscInfo* osc, AudioSample* buf, const uint8_t size ,const float gain)
{
	int i;
	for(i=0;i<size;i++)
	{
		const uint32_t lastPhase = osc->phase;
		osc->phase += osc->phaseInc;

		if(lastPhase > osc->phase)
		{
			//overflow happened -> phaseWrapped
			osc->output = (int16_t)GetRngValue() * (1.f/32768.f); //normal pitched white noise
		}

		buf[i] = osc->output * gain;
	}
}
//-----------------------------------------------------------
//-----------------------------------------------------------
IN_ITCM_RAM void calcNextOscSampleBlock(OscInfo* osc, AudioSample* buf, const uint8_t size, const float gain, const float pwm)
{
	switch(osc->waveform)
		{
		case SINE:
			calcSineBlock(osc,buf,size, gain);
			break;

		case SAW:
			calcWavetableOscBlock(osc,sawTable,buf,size, gain);
			break;

		case TRI:
			calcWavetableOscBlock(osc,triTable,buf,size, gain);
			break;

		case REC:
			calcWavetableOscBlock(osc,recTable,buf,size, gain);
			break;

		case NOISE:
			calcNoiseBlock(osc,buf,size, gain);
			break;

		case PWM:
			calcPwmBlock(osc,buf,size, gain, pwm);
			break;

		default://sample playback
		//	if( osc->waveform - OSC_SAMPLE_START > sampleMemory_getNumSamples() ) return; // return if out of range

		//	calcUserSampleOscBlock(osc,buf,size, gain);
			break;
		}
}
//-----------------------------------------------------------

//---------------------------------------------------------------
IN_ITCM_RAM void calcWavetableOscBlock(OscInfo* osc, const int16_t table[][1024], AudioSample* buf, const uint8_t size ,const float gain)
{
	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
			AudioSample oscOut ;
			uint32_t  itg	= oscPhase>>22;
		#if INTERPOLATE_OSC
			//todo use ldm instead of ldr to load multiple values from memory
			oscOut = (table[osc->tableOffset][itg++] * (1.f/32768.f));
			//const float frac = (itg&0x003FFFFF)*2.38418579101562e-07f; //2.38... => 1.f/0x3fffff
			//oscOut += frac*(table[osc->tableOffset][itg] - oscOut);
			uint32_t frac = oscPhase & 0x3FFFFF;
oscOut = oscOut + ((table[osc->tableOffset][itg & 1023u] * (1.f/32768.f)) - oscOut) * ((float)frac / 4194304.f);
		#else
			oscOut = (table[osc->tableOffset][itg] * (1.f/32768.f));
		#endif

			osc->phase = oscPhase + osc->phaseInc;
			buf[i] = oscOut * gain;
	}
}

//---------------------------------------------------------------

//------------------------------------------------------------------

//------------------------------------------------------------------

//------------------------------------------------------------------
void calcUserSampleOscFmBlock(OscInfo* osc,AudioSample* modBuffer, AudioSample* buf, uint8_t size ,const float gain)
{
}
//---------------------------------------------------------------
void calcUserSampleOscBlock(OscInfo* osc, AudioSample* buf, const uint8_t size ,const float gain)
{
}
//---------------------------------------------------------------

//-----------------------------------------------------------
IN_ITCM_RAM void calcPwmBlock(OscInfo* osc, AudioSample* buf, uint8_t size ,const float gain, const float pwm)
{
	// PWM is normalized to [0,1] by normal control paths. Convert only the
	// offset, then use unsigned addition for defined modulo-2^32 phase wrap.
	const uint32_t pwmOffset = (uint32_t)(pwm * (UINT32_MAX/2));



	uint8_t i;
	for(i=0;i<size;i++)
	{
		const uint32_t oscPhase = osc->phase;
		const uint32_t oscPhase2 = oscPhase + pwmOffset;
		AudioSample oscOut ;
		uint32_t  itg	= oscPhase>>22;
		uint32_t  itg2	= oscPhase2>>22;


		#if INTERPOLATE_FM_OSC
			oscOut = (sawTable[osc->tableOffset][itg++] * (1.f/32768.f));
			//const float frac	= (oscPhase&0x003FFFFF)*2.38418579101562e-07f;
			//const float frac = (itg&0x003FFFFF)*2.38418579101562e-07f;
			//oscOut += frac*(sawTable[osc->tableOffset][itg] - oscOut);
			uint32_t frac = oscPhase & 0x3FFFFF;
oscOut = oscOut + ((sawTable[osc->tableOffset][itg & 1023u] * (1.f/32768.f)) - oscOut) * ((float)frac / 4194304.f);

			AudioSample osc2Out = (sawTable[osc->tableOffset][itg2++] * (1.f/32768.f)) ;//* -1;
			//const float frac	= (index&0x003FFFFF)*2.38418579101562e-07f;
			//osc2Out += frac*(sawTable[osc->tableOffset][itg2] * -1 - osc2Out);
			frac = oscPhase2 & 0x3FFFFF;
osc2Out = osc2Out + ((sawTable[osc->tableOffset][itg2 & 1023u] * (1.f/32768.f)) - osc2Out) * ((float)frac / 4194304.f);

        oscOut = audio_sample_bound(oscOut-osc2Out); /* PWM waveform saturation */

		#else
			oscOut = (sawTable[overtoneIndex][itg] * (1.f/32768.f));
		#endif

			osc->phase = oscPhase + osc->phaseInc;
			osc->output = oscOut;
			buf[i] = oscOut * gain;
	}
}
//---------------------------------------------------------------

 //-----------------------------------------------------------
void osc_calcSineFreq(OscInfo* osc)
{
	osc->phaseInc = freq2PhaseIncr(osc->freq* osc->pitchMod*osc->modNodeValue);
}
//-----------------------------------------------------------
void osc_calcNoiseFreq(OscInfo* osc)
{
	osc_calcSineFreq(osc);
}
//-----------------------------------------------------------
void osc_calcWavetableFreq(OscInfo* osc)
{
	const float currentFreq = osc->freq*osc->pitchMod*osc->modNodeValue;
	osc->phaseInc = freq2PhaseIncr1024(currentFreq);

	const uint8_t overtoneIndex = freqToTableIndex(currentFreq);
	osc->tableOffset = overtoneIndex>10?10:overtoneIndex;
}
//-----------------------------------------------------------
void osc_calcSampleFreq(OscInfo* osc)
{
	const float currentFreq = osc->freq*osc->pitchMod*osc->modNodeValue;
	osc->phaseInc = freq2PhaseIncr32767(currentFreq);
}
//-----------------------------------------------------------
void osc_calcUserSampleFreq(OscInfo* osc)
{
	const float currentFreq = osc->freq*osc->pitchMod*osc->modNodeValue;
	osc->phaseInc = freq2PhaseIncr32767(currentFreq);
}
//-----------------------------------------------------------
 void osc_setFreq(OscInfo* osc)
 {
		switch(osc->waveform)
		{
		case SINE:
			osc_calcSineFreq(osc);
			break;

		case SAW:
			osc_calcWavetableFreq(osc);
			break;

		case TRI:
			osc_calcWavetableFreq(osc);
			break;

		case REC:
			osc_calcWavetableFreq(osc);
			break;

		case NOISE:
			osc_calcNoiseFreq(osc);
			break;


		case PWM:
			osc_calcWavetableFreq(osc);
			break;

		//samples
		default:
			osc_calcUserSampleFreq(osc);
			break;

		}
 }
 //-----------------------------------------------------------
 void osc_setBaseNote(OscInfo* osc, uint8_t baseNote)
 {

	 //get fine tune
	 const float cent = midiParser_calcDetune(osc->midiFreq&0xff);
	 //calc coarse tune
	 int16_t note =  (osc->midiFreq>>8) + (baseNote-SEQ_DEFAULT_NOTE);
	 if(note>127)note=127;
	 if(note<0)note=0;

	 osc->freq = MidiNoteFrequencies[note]*cent;
	 osc->baseNote = baseNote;
 };

 //-----------------------------------------------------------
 IN_ITCM_RAM void osc_recalcFreq(OscInfo* osc)
 {
	 //get fine tune
	 const float cent = midiParser_calcDetune(osc->midiFreq&0xff);
	 //calc coarse tune
	 int16_t note =  (osc->midiFreq>>8) + (osc->baseNote-SEQ_DEFAULT_NOTE);

	 if(note>127)note=127;
 	 if(note<0)note=0;

	 osc->freq = MidiNoteFrequencies[note]*cent;
 }
 //-----------------------------------------------------------
