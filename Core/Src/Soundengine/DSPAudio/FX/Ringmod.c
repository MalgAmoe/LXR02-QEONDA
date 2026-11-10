/*
 * Ringmod.c
 *
 *  Created on: 26.08.2020
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


#include "Soundengine/DSPAudio/FX/Ringmod.h"

void Ringmod_init(Ringmod *rm)
{
	rm->freq = 0.5f;


	rm->osc.freq = 100;
	rm->osc.modNodeValue = 1;
	rm->osc.waveform = REC; //for testing init to tri,saw,rec
	rm->osc.fmMod = 0;
	rm->osc.midiFreq = 70<<8 | 64;
	rm->osc.pitchMod = 1.0f;
	osc_setFreq(&rm->osc);
}
void Ringmod_process(Ringmod *rm, AudioSample*fxBuffer, AudioSample* outL, AudioSample* outR, uint16_t size,  uint8_t channels, float dryWet)
{
    AudioSample mod[size];
    calcNextOscSampleBlock(&rm->osc, mod, size, 1.f, 0.3f);
    for(unsigned i=0;i<size;++i) {
        float wet = fxBuffer[2*i]*mod[i]/65536.f;
        if(channels==1) wet = audio_mix_add(wet, outL[2*i]);
        outL[2*i] = audio_mix_add(outL[2*i], fxBuffer[2*i] + audio_mix_bound((wet-fxBuffer[2*i])*dryWet));
        if(channels==2) {
            wet = fxBuffer[2*i+1]*mod[i]/65536.f;
            outR[2*i] = audio_mix_add(outR[2*i], fxBuffer[2*i+1] + audio_mix_bound((wet-fxBuffer[2*i+1])*dryWet));
        }
    }
}
void Ringmod_setFreq(Ringmod *rm, float f)
{
	rm->osc.freq = f*880.f;
	osc_setFreq(&rm->osc);
}
void Ringmod_setWave(Ringmod *rm, uint8_t w)
{
	rm->osc.waveform = w;
}

void Ringmod_resetPhase(Ringmod* rm)
{
	if(rm->osc.waveform == SINE)
		rm->osc.phase = 1024 + ( (0x3ff<<20) - 1024);//voiceArray[voiceNr].osc.startPhase ;
	else //if(rm->osc.waveform > SINE && rm->osc.waveform <= REC)
		rm->osc.phase = (0xff<<22);

}

