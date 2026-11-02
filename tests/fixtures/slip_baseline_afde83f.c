/* Frozen differential-test oracle, extracted verbatim from
 * Core/Src/Soundengine/Sequencer/sequencer.c at afde83f97efad30e07601361661ea907ebea4517
 * Functions: getShiftValue, flamIdxToPattern, seq_getShiftFlamPattern, seq_processFlam.
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 * See LICENSE and NOTICE.md in the repository root.
 * Intentionally retains historical behavior; do not update to match production.
 */
int8_t getShiftValue(uint8_t in)
{
	switch(in)
	{
	case 0:
		return -7;
		break;

	case 1:
		return -6;
		break;

	case 2:
		return -5;
		break;

	case 3:
		return -4;
		break;

	case 4:
		return -3;
		break;

	case 5:
		return -2;
		break;

	case 6:
		return -1;
		break;

	default:
	case 7:
		return 0;
		break;

	case 8:
		return 1;
		break;

	case 9:
		return 2;
		break;

	case 10:
		return 3;
		break;

	case 11:
		return 4;
		break;

	case 12:
		return 5;
		break;

	case 13:
		return 6;
		break;

	case 14:
		return 7;
		break;
	}
}
uint32_t flamIdxToPattern(uint8_t flamIdx)
{
	switch(flamIdx)
	{
	default:
	case 0: //off
		return 0b100000000000000000000000;
		break;

	case 1: //x2
		return 0b100000000000100000000000;
		break;

	case 2: //x3
		return 0b100000001000000010000000;
		break;

	case 3: //x4
		return 0b100000100000100000100000;
		break;

	case 4: //x6
		return 0b100010001000100010001000;
		break;

	case 5: //x8
		return 0b100100100100100100100100;
		break;
	}
}
//return pattern as 8 bit binary value (steps 0-7)
uint32_t seq_getShiftFlamPattern(const uint8_t track, uint8_t step, StepPosition stepPos)
{
#if 0
	const uint8_t length = seq_patternSet.length[seq_activePattern][track];
	const uint8_t nextStep = (step+1)%length;
	const uint8_t prevStep = step != 0 ? step - 1 : length-1;

	/* we have 3 possible step sources:
	 * - flammed AND positive shifted notes from the previous step
	 * - current step data
	 * - negative shifted data from the next step
	 */

	uint8_t prevStepActive = seq_intIsMainStepActive(track,prevStep,seq_activePattern);
	uint8_t currentStepActive = seq_intIsMainStepActive(track,step,seq_activePattern);
	uint8_t nextStepActive = seq_intIsMainStepActive(track,nextStep,seq_activePattern);


	const uint8_t flamCurrentStep = seq_patternSet.seq_stepTiming[seq_activePattern][track][step].flam;
	const uint8_t flamNextStep = seq_patternSet.seq_stepTiming[seq_activePattern][track][nextStep].flam;
	const uint8_t flamPrevStep = seq_patternSet.seq_stepTiming[seq_activePattern][track][prevStep].flam;
	const uint8_t shiftCurrentStep = seq_patternSet.seq_stepTiming[seq_activePattern][track][step].shift;
	const uint8_t shiftNextStep = seq_patternSet.seq_stepTiming[seq_activePattern][track][nextStep].shift;
	const uint8_t shiftPrevStep = seq_patternSet.seq_stepTiming[seq_activePattern][track][prevStep].shift;

	//calc flam step pattern
	StepPattern prev, current, next;

	//check probability
	if( (seq_rndValue[track].prev) > seq_patternSet.seq_subStepPattern[seq_activePattern][track][prevStep].prob ) prevStepActive = 0;
	if( (seq_rndValue[track].current) > seq_patternSet.seq_subStepPattern[seq_activePattern][track][step].prob ) currentStepActive = 0;
	if( (seq_rndValue[track].next) > seq_patternSet.seq_subStepPattern[seq_activePattern][track][nextStep].prob ) nextStepActive = 0;

	//add step pattern for active steps
	prev.StepData.prevStep = prevStepActive ? flamIdxToPattern(flamPrevStep) : 0;
	current.StepData.prevStep = currentStepActive ? flamIdxToPattern(flamCurrentStep) : 0;
	next.StepData.prevStep = nextStepActive ? flamIdxToPattern(flamNextStep) : 0;

	//add shift
	prev.completeData = shiftPrevStep >= 0 ? prev.completeData >> shiftPrevStep : prev.completeData << shiftPrevStep;
	current.completeData = shiftCurrentStep >= 0 ? current.completeData >> shiftCurrentStep : current.completeData << shiftCurrentStep;
	next.completeData = shiftNextStep >= 0 ? next.completeData >> shiftNextStep : next.completeData << shiftNextStep;

	//combine
	uint8_t pattern =  prev.StepData.currentStep | current.StepData.currentStep | next.StepData.currentStep;

	return pattern;
#else
		uint8_t currentStepActive = seq_intIsMainStepActive(track,step,seq_activePattern);
		if(!currentStepActive) return 0;


		const  uint8_t flamCurrentStep = seq_patternSet.seq_stepTiming[seq_activePattern][track][step].flam;
		int8_t shiftCurrentStep = getShiftValue(seq_patternSet.seq_stepTiming[seq_activePattern][track][step].shift);

		uint32_t stepPattern;

		//check probability
		switch(stepPos)
		{
		case STEP_PREV:
			if( (seq_rndValue[track].prev) > seq_patternSet.seq_subStepPattern[seq_activePattern][track][step].prob ) currentStepActive = 0;
			break;

		default:
		case STEP_CURRENT:
			if( (seq_rndValue[track].current) > seq_patternSet.seq_subStepPattern[seq_activePattern][track][step].prob ) currentStepActive = 0;
			break;

		case STEP_NEXT:
			if( (seq_rndValue[track].next) > seq_patternSet.seq_subStepPattern[seq_activePattern][track][step].prob ) currentStepActive = 0;
			break;
		}
		if(!currentStepActive) return 0;

		//add step pattern for active steps
		stepPattern = flamIdxToPattern(flamCurrentStep);

		//we have 24 pulses per step (96ppq) but only 8 possible shift values (0-7)
		shiftCurrentStep *= 3;

		//since we use this function to determine what to play at the current step, we have to look at different shifted sections depending of which step we calculate
		//i.e. we only play the data from the previous step, that was shifted into the current(next) step
		if(shiftCurrentStep == 0)
		{
			switch(stepPos)
			{
				case STEP_PREV:
					return 0;	//nothing from prev step is shifted forward to this one
					break;

				default:
				case STEP_CURRENT:
					return (stepPattern) & 0xFFFFFF;
					break;

				case STEP_NEXT:
					return 0;	//nothing from next step is shifted backwards to this one
					break;
			}
		}
		else if(shiftCurrentStep > 0)
		{
			switch(stepPos)
			{
				case STEP_PREV:
					//data from prev step is shifted forward to this one
					return (stepPattern << (24-shiftCurrentStep)) & 0xFFFFFF;
					break;

				default:
				case STEP_CURRENT:
					//data is shifted forward, but a rest remains in this step
					return (stepPattern >> shiftCurrentStep) & 0xFFFFFF;
					break;

				case STEP_NEXT:
					return 0;	//nothing from next step is shifted backwards to this one
					break;
			}
		}
		else
		{
			//make shift value positive
			shiftCurrentStep *= -1;
			switch(stepPos)
			{
				case STEP_PREV:
					//no data from prev step is shifted forward to this one
					return 0;
					break;

				default:
				case STEP_CURRENT:
					//data is shifted backwards, but a rest remains in this step
					return (stepPattern << shiftCurrentStep) & 0xFFFFFF;
					break;

				case STEP_NEXT:
					//data from next step is shifted backwards to this one
					return (stepPattern >> (24-shiftCurrentStep)) & 0xFFFFFF;
					break;
			}
		}
#endif
}

void seq_processFlam(uint8_t idx)
{
	if(!seq_running)
		return;

	if(idx==0)
	{
		chokeCurrent=0;
		chokeNext=0;
	}

	for(uint8_t track=0;track<NUM_TRACKS;track++)
	{
		if(seq_stepIndex[track] < 0) continue;
		//if track is not muted
		if(!(seq_mutedTracks & (1<<track) ) )
		{
			//pattern takes main step active and probability into account
#if 1
			const uint8_t length = seq_patternSet.length[seq_activePattern][track];
			const uint8_t currentStep = seq_stepIndex[track];
			const uint8_t nextStep = (seq_stepIndex[track]+1)%length;
			const uint8_t prevStep = seq_stepIndex[track] != 0 ? seq_stepIndex[track] - 1 : length-1;

			/* we have 3 possible step sources:
			 * - flammed AND positive shifted notes from the previous step
			 * - current step data
			 * - negative shifted data from the next step
			 */
			uint32_t currentStepPattern = seq_getShiftFlamPattern(track, currentStep, STEP_CURRENT);
			uint32_t nextStepPattern 	= seq_getShiftFlamPattern(track, nextStep, STEP_NEXT);
			uint32_t prevStepPattern 	= seq_getShiftFlamPattern(track, prevStep, STEP_PREV);

			//calc priotity (next > current > prev)
			uint8_t prevActive 		= (prevStepPattern 		& (1UL<<(23-idx)) ) != 0;
			uint8_t currentActive 	= (currentStepPattern 	& (1UL<<(23-idx)) ) != 0;
			uint8_t nextActive 		= (nextStepPattern 		& (1UL<<(23-idx)) ) != 0;

			if(nextActive && !seq_performanceBreak)
			{
				lastWasNoteOn[track] = 1;
				chokeNext = 1;
				const uint8_t vol = seq_patternSet.seq_subStepPattern[seq_activePattern][track][nextStep].volume&STEP_VOLUME_MASK;
				const uint8_t note = seq_patternSet.seq_subStepPattern[seq_activePattern][track][nextStep].note;
				seq_triggerVoice(track,vol,note);
			}
			else if((currentActive) && (chokeNext == 0) && !seq_performanceBreak)
			{
				lastWasNoteOn[track] = 1;
				chokeCurrent = 1;
				const uint8_t vol = seq_patternSet.seq_subStepPattern[seq_activePattern][track][currentStep].volume&STEP_VOLUME_MASK;
				const uint8_t note = seq_patternSet.seq_subStepPattern[seq_activePattern][track][currentStep].note;
				seq_triggerVoice(track,vol,note);
			}
			else if((prevActive) && (chokeNext == 0) && (chokeCurrent == 0) && !seq_performanceBreak)
			{
				lastWasNoteOn[track] = 1;
				const uint8_t vol = seq_patternSet.seq_subStepPattern[seq_activePattern][track][prevStep].volume&STEP_VOLUME_MASK;
				const uint8_t note = seq_patternSet.seq_subStepPattern[seq_activePattern][track][prevStep].note;
				seq_triggerVoice(track,vol,note);
			}
			else if (lastWasNoteOn[track])
			{
				lastWasNoteOn[track] = 0;
				voiceControl_noteOff(track);
			}
#else

			//if main step is active
			if(seq_intIsMainStepActive(track,seq_stepIndex[track],seq_activePattern))
			{


				if( (seq_rndValue[track]) <= seq_patternSet.seq_subStepPattern[seq_activePattern][track][seq_stepIndex[track]].prob )
				{
					/* to be able to process flam and shift simultaneously
					   we have to look at the current and the next step
					   as a negative shifted step will be played at the previous step
					   (including a wrap around at the track length end)
					   */



					uint8_t flamCurrentStep = seq_patternSet.seq_stepTiming[seq_activePattern][track][seq_stepIndex[track]]+1;
					uint8_t length = patternSet->length[seq_activePattern][track];
					uint8_t flamNextStep = seq_patternSet.seq_stepTiming[seq_activePattern][track][(seq_stepIndex[track]+1)%length]+1;
					uint8_t shift = 0;
					switch(flamCurrentStep)
					{
					default:
						break;

					case 5:
						flamCurrentStep = 6;
						break;

					case 6:
						flamCurrentStep=8;
						break;

					case 7:
					case 8:
					case 9:
					case 10:
					case 11:
					case 12:
					case 13:
					case 14:
						shift = flamCurrentStep - 6;
						break;
					}
					if(flamCurrentStep<=1) continue;


					if(shift != 0)
					{
						// ######## SHIFT #######
						if(idx == shift*3)
						{
							const uint8_t vol = seq_patternSet.seq_subStepPattern[seq_activePattern][i][seq_stepIndex[i]].volume&STEP_VOLUME_MASK;
							const uint8_t note = seq_patternSet.seq_subStepPattern[seq_activePattern][track][seq_stepIndex[track]].note;
							seq_triggerVoice(track,vol,note);
						}

					}
					else
					{
						// ######## FLAM ########
						// idx value 0 to 24
						// 24 /3 = 8
						uint8_t div = 24/flam;
						//if(idx%(8/flamCurrentStep)==0)
						if(idx%(div)==0)
						{
							const uint8_t vol = seq_patternSet.seq_subStepPattern[seq_activePattern][i][seq_stepIndex[i]].volume&STEP_VOLUME_MASK;
							const uint8_t note = seq_patternSet.seq_subStepPattern[seq_activePattern][i][seq_stepIndex[i]].note;
							seq_triggerVoice(i,vol,note);
						}
					}
				}
			}
#endif
		}
	}
}
