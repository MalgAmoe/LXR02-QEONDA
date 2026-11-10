/*
 * presetManager.c
 *
 * Created: 09.05.2012 16:06:19
 *  Author: Julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */
//#include "../config.h"
#include <frontPanelParser_ui.h>
#include "Preset/PresetManager.h"
#include "Preset/SafeStorage.h"
#include "Preset/ProjectCodec.h"
#include "Soundengine/DSPAudio/MainCompressor.h"
//#include "../Hardware/SD/ff.h"
#include "ff.h"
#include <stdio.h>
#include "menu/CcNr2Text.h"
#include "menu/menu.h"
//#include <util/delay.h>
#include "lcd.h"
//#include <avr/pgmspace.h>
#include <stdlib.h>
//#include <util/atomic.h>
#include "IO/uart.h"
#include "IO/DIO.h"

#include "Soundengine/MIDI/MidiParser.h"
#include "Soundengine/Sequencer/sequencer.h"
#include "Soundengine/Sequencer/clockSync.h"
#include "Soundengine/Soundengine.h"


//#include "../Hardware/timebase.h"

//FATFS SDFatFS;		/* File system object for the logical drive */
//FIL SDFile;		/* place to hold 1 file*/
static uint8_t morph_state = 0; //flag for non blocking morph
static uint8_t morph_index = 0;
char savefileNames[NUM_KIT_SLOTS][NUM_SAVEFILE_NAMES][8];

char currentFolder[13];
// First error wins; no further writes after a failure. Keep a failed-close
// handle owned until it can be closed, rather than reusing its FIL object.
static FRESULT preset_writeResult = FR_OK;
static FIL *preset_writeFileHandle;
static uint8_t preset_writeOpen;
static uint8_t preset_writeSession;
// Foreground only, immediately after explicit unmount. Never close/replay an
// old FIL on replacement media. Return abandoned-write failure for the caller
// to acknowledge; sticky failure remains until the next explicit open.
FRESULT preset_invalidateUnmountedFiles(void)
{
    FRESULT abandoned = FR_OK;
    if(preset_writeOpen)
        abandoned = preset_writeResult != FR_OK ? preset_writeResult : FR_INVALID_OBJECT;
    preset_writeOpen = 0;
    preset_writeSession = 1;
    preset_writeFileHandle = (FIL*)&SDFile;
    preset_writeResult = abandoned != FR_OK ? abandoned : FR_INVALID_OBJECT;
    memset((FIL*)&SDFile, 0, sizeof(SDFile));
    return abandoned;
}
static FRESULT preset_closeFile(FIL *file)
{
    if(preset_writeSession && file == preset_writeFileHandle)
    {
        if(preset_writeOpen)
        {
            FRESULT res = f_close(file);
            if(res == FR_OK) preset_writeOpen = 0;
            if(preset_writeResult == FR_OK) preset_writeResult = res;
        }
        return preset_writeResult;
    }
    return f_close(file);
}
static FRESULT preset_openFile(FIL *file, const TCHAR *path, BYTE mode)
{
    if(preset_writeOpen)
    {
        FRESULT res = f_close(preset_writeFileHandle);
        if(res != FR_OK) return res;
        preset_writeOpen = 0;
    }
    preset_writeSession = (mode & FA_WRITE) != 0;
    preset_writeFileHandle = file;
    preset_writeResult = f_open(file, path, mode);
    preset_writeOpen = preset_writeSession && preset_writeResult == FR_OK;
    return preset_writeResult;
}
static FRESULT preset_writeFile(FIL *file, const void *data, UINT length, UINT *written)
{
    *written = 0;
    if(preset_writeResult != FR_OK) return preset_writeResult;
    if(!preset_writeOpen || file != preset_writeFileHandle) return FR_INVALID_OBJECT;
    preset_writeResult = f_write(file, data, length, written);
    if(preset_writeResult == FR_OK && *written != length) preset_writeResult = FR_DENIED;
    if(preset_writeResult != FR_OK) preset_closeFile(file);
    return preset_writeResult;
}
unsigned char preset_projectCleanupWarning;
unsigned char preset_fileCleanupWarning;
uint8_t preset_isNameEmpty(char* name)
{
	uint8_t isEmpty = 1;

	if( (name[0] != 'E') && (name[0] != 0) ) isEmpty = 0;
	if( (name[1] != 'm') && (name[1] != 0) ) isEmpty = 0;
	if( (name[2] != 'p') && (name[2] != 0) ) isEmpty = 0;
	if( (name[3] != 't') && (name[3] != 0) ) isEmpty = 0;
	if( (name[4] != 'y') && (name[4] != 0) ) isEmpty = 0;
	if( (name[5] != 0) ) isEmpty = 0;
	if( (name[6] != 0) ) isEmpty = 0;
	if( (name[7] != 0) ) isEmpty = 0;


	return isEmpty;
}
//----------------------------------------------------
//load init kit
void preset_init(uint8_t presetNr)
{

	//const uint8_t presetNr = menu_selectedPresetNr[SAVE_TYPE_KIT];

	//first the preset name
	memcpy(savefileNames[presetNr][KIT_NAMES],initKit,8*sizeof(uint8_t));


	if(preset_isNameEmpty(savefileNames[presetNr][KIT_NAMES]))
	{
		sprintf((void*)savefileNames[presetNr][KIT_NAMES], "Empty");
	}


	//then the data
	//read the file content

	int16_t i;
	uint8_t *para;


	para=mainParameters[presetNr];

	for(int i=8;i<END_OF_SOUND_PARAMETERS; i++)
	{
		para[i-8] = initKit[i];
	}

	//special case mod targets. normalize.
	const uint8_t nmt=getNumModTargets();
	for(i=0;i<6;i++) {
		// since I've changed the meaning of these, I'll ensure that it's valid for kits saved prior to the
		// change
		if(para[PAR_VEL_DEST_1+i] >= nmt )
			para[PAR_VEL_DEST_1+i] = 0;
		if(para[PAR_TARGET_LFO1+i] >= nmt )
			para[PAR_TARGET_LFO1+i] = 0;
	}

	//copy parameters to edit buffer
	memcpy(activeParameters, mainParameters[presetNr], sizeof(uint8_t) * END_OF_SOUND_PARAMETERS);
	preset_sendDrumsetParameters();
	//frontPanel_sendData(PRESET,PRESET_LOAD,presetNr);

}

//----------------------------------------------------
void preset_loadDrumsetRam(uint8_t presetNr, uint8_t isMorph, uint8_t sendImmediate)
{
	soundengine_process();
	if(isMorph)
	{
		morphParameters = mainParameters[presetNr];
	}
	else
	{
		//copy parameters to edit buffer
		memcpy(activeParameters, mainParameters[presetNr], sizeof(uint8_t) * END_OF_SOUND_PARAMETERS);
		//if(activeParameters[PAR_PATTERN_MODE] = 1)
		//load asociated morph kit as well

		// morphParameters = mainParameters[activeParameters[PAR_MORPH_KIT_DEST]];


	}
	soundengine_process();

	if(sendImmediate)
	{
		preset_sendDrumsetParametersImmediate();
	}
	else
	{
		//activePresetNr = menu_currentPresetNr[menu_saveOptions.category];
		preset_sendDrumsetParameters();
	}
}
//----------------------------------------------------
void preset_saveDrumsetRam(uint8_t presetNr, uint8_t isMorph)
{
	if(isMorph)
	{
		for(uint16_t i=0;i<END_OF_SOUND_PARAMETERS;i++)
		{
			uint8_t value;
			//Mod targets are not morphed!!!
			if( (i >= PAR_VEL_DEST_1) && (i <= PAR_VEL_DEST_6) )
			{
				value = activeParameters[i];
			} else if( (i >= PAR_TARGET_LFO1) && (i <= PAR_TARGET_LFO6) )
			{
				value = activeParameters[i];
			} else if( (i >= PAR_VOICE_LFO1) && (i <= PAR_VOICE_LFO6) )
			{
				value = activeParameters[i];
			}
			else
			{
				value = preset_getMorphValue(i,activeParameters[PAR_MORPH]);
			}
			//preset_writeFile((FIL*)&SDFile,&value,1,&bytesWritten);
			mainParameters[presetNr][i] = value;
		}
	}
	else
	{
		//copy edit buffer to parameter array
		memcpy(mainParameters[presetNr], activeParameters, sizeof(uint8_t) * END_OF_SOUND_PARAMETERS);
	}
}
//----------------------------------------------------
FRESULT preset_saveDrumsetSD(uint8_t presetNr, uint8_t isMorph)
{
    preset_fileCleanupWarning = 0;
    if(presetNr >= NUM_KIT_SLOTS) return FR_INVALID_NAME;
    preset_saveDrumsetRam(presetNr, isMorph);
    return FR_OK;
};

//----------------------------------------------------
static const uint8_t preset_masterCompDefaults[4] = {36, 0, 17, 20};

static void preset_applyMasterComp(const uint8_t values[4])
{
    activeParameters[MASTER_COMP_THRESHOLD] = values[0];
    activeParameters[MASTER_COMP_RATIO] = values[1];
    activeParameters[MASTER_COMP_ATTACK] = values[2];
    activeParameters[MASTER_COMP_RELEASE] = values[3];
    // Publish before any subsequent per-field menu redispatch (same values).
    MainCompressor_setControls(values);
}


//----------------------------------------------------
FRESULT preset_saveGlobals()
{
    // Global controls already live in project RAM; only Project Save writes SD.
    return FR_OK;
}
//----------------------------------------------------
// returns 1 on success

//----------------------------------------------------
uint8_t preset_loadGlobals()
{
    // No independent global file or tmp overlay.
    menu_sendAllGlobals();
    return 1;
}

//----------------------------------------------------
void preset_loadDefaultGlobals()
{
    preset_applyMasterComp(preset_masterCompDefaults);
    menu_parseGlobalParam(MASTER_COMP_THRESHOLD, preset_masterCompDefaults[0]);
    menu_parseGlobalParam(MASTER_COMP_RATIO, preset_masterCompDefaults[1]);
    menu_parseGlobalParam(MASTER_COMP_ATTACK, preset_masterCompDefaults[2]);
    menu_parseGlobalParam(MASTER_COMP_RELEASE, preset_masterCompDefaults[3]);
	activeParameters[PAR_BPM] = 120;

	activeParameters[PAR_MIDI_CHAN_1] = 1;
	activeParameters[PAR_MIDI_CHAN_2] = 1;
	activeParameters[PAR_MIDI_CHAN_3] = 1;
	activeParameters[PAR_MIDI_CHAN_4] = 1;
	activeParameters[PAR_MIDI_CHAN_5] = 1;
	activeParameters[PAR_MIDI_CHAN_6] = 1;
	activeParameters[PAR_MIDI_CHAN_7] = 1;

	activeParameters[PAR_MIDI_NOTE1] = 48;
	activeParameters[PAR_MIDI_NOTE2] = 48;
	activeParameters[PAR_MIDI_NOTE3] = 48;
	activeParameters[PAR_MIDI_NOTE4] = 48;
	activeParameters[PAR_MIDI_NOTE5] = 48;
	activeParameters[PAR_MIDI_NOTE6] = 48;
	activeParameters[PAR_MIDI_NOTE7] = 48;


	activeParameters[PAR_FETCH] = 0;
	activeParameters[PAR_FOLLOW] = 0;

	activeParameters[PAR_QUANTISATION] = 0;

	activeParameters[PAR_SCREENSAVER_ON_OFF] = 1;

	activeParameters[PAR_MIDI_ROUTING] = 0;
	activeParameters[PAR_MIDI_FILT_TX] = 15;	//all
	activeParameters[PAR_MIDI_FILT_RX] = 15; //all

	activeParameters[PAR_PRESCALER_CLOCK_IN] = 0; //all
	activeParameters[PAR_PRESCALER_CLOCK_OUT1] = 0; //all
	activeParameters[PAR_PRESCALER_CLOCK_OUT2] = 0; //all
	activeParameters[PAR_TRIG_GATE_MODE] = 0; //all

	activeParameters[PAR_BAR_RESET_MODE] = 1; //all
	activeParameters[PAR_MIDI_CHAN_GLOBAL] = 0; //all

	activeParameters[PAR_PATTERN_MODE] = 1; //auto

}
//----------------------------------------------------
FRESULT preset_createGlobals()
{
	preset_loadDefaultGlobals();
	return preset_saveGlobals();
}
//----------------------------------------------------
FRESULT preset_loadLastUsedProjectNrFromSD(uint8_t* projNr)
{
    *projNr = 0;
    UINT done = 0;
    uint8_t candidate = 0;
    FRESULT res = preset_openFile((FIL*)&SDFile, "/proj.idx", FA_READ);
    if(res != FR_OK) return res;
    res = f_read((FIL*)&SDFile, &candidate, 1, &done);
    FRESULT closed = preset_closeFile((FIL*)&SDFile);
    if(res == FR_OK) res = closed;
    if(res == FR_OK && (done != 1 || candidate >= NUM_KIT_SLOTS)) res = FR_INVALID_PARAMETER;
    if(res == FR_OK) *projNr = candidate;
    return res;
}
//----------------------------------------------------
FRESULT preset_saveLastUsedProjectNrToSD(uint8_t projNr)
{
#if USE_SD_CARD
    FRESULT res;

	//open the file
	res = preset_openFile((FIL*)&SDFile,"/proj.idx",FA_CREATE_ALWAYS | FA_WRITE);
	if(res != FR_OK)
	{
		//close the file handle
		preset_closeFile((FIL*)&SDFile);
		return res;
	}

	unsigned int bytesWritten;
	res = preset_writeFile((FIL*)&SDFile,&projNr,1,&bytesWritten);
	if(res != FR_OK)
	{
		//close the file handle
		preset_closeFile((FIL*)&SDFile);
		return res;
	}

	//close the file
	res = preset_closeFile((FIL*)&SDFile);

	//f_unmount((TCHAR const*)SDPath);
	return res;
#else
#endif
}
//----------------------------------------------------
//val is interpolation value between 0 and 255
//uses bankers rounding
static uint8_t interpolate(uint8_t a, uint8_t b, uint8_t x)
{
	uint16_t fixedPointValue = (uint16_t)(((a*256) + (b-a)*x));
	uint8_t result = (uint8_t)(fixedPointValue/256);

	return (uint8_t)((fixedPointValue&0xff) < 0x7f ? result : result+1);
	//return ((a*255) + (b-a)*x)/255;
}

//----------------------------------------------------
IN_ITCM_RAM void preset_sendDrumsetParametersImmediate()
{
		//special case mod targets
		for(uint8_t i=0;i<6;i++)
		{
			//**VELO load drumkit. translate to param value before sending
			// parameter_values[PAR_VEL_DEST_1+i] is an index into modTargets, we need to send
			// a parameter number
			uint8_t value = (uint8_t)pgm_read_word(&modTargets[activeParameters[PAR_VEL_DEST_1+i]].param);
			uint8_t upper,lower;
			upper = (uint8_t)(((value&0x80)>>7) | (((i)&0x3f)<<1));
			lower = value&0x7f;
			frontPanel_sendData(CC_VELO_TARGET,upper,lower);

			// ensure target voice # is valid
			if(activeParameters[PAR_VOICE_LFO1+i] < 1 || activeParameters[PAR_VOICE_LFO1+i] > 6 )
				activeParameters[PAR_VOICE_LFO1+i]=1;

			// **LFO par_target_lfo will be an index into modTargets, but we need a parameter number to send
			value = (uint8_t)pgm_read_word(&modTargets[activeParameters[PAR_TARGET_LFO1+i]].param);

			upper = (uint8_t)(((value&0x80)>>7) | (((i)&0x3f)<<1));
			lower = value&0x7f;
			frontPanel_sendData(CC_LFO_TARGET,upper,lower);
		}

		static MidiMsg msg = {0};
		//pre-send fx type to prevent clicks
		/*
		msg.status = CC_2;
		msg.data1 = PAR_FX_TYPE-128; //stupid offset only in CC not CC2
		msg.data2 = activeParameters[PAR_FX_TYPE];

		//	msg.data1 += 1;
		msg.data1 &= 0x7f;
		midiParser_ccHandler(msg,1, 0, 0.f);
		*/

		//try to prevent click by sending BD params first

		//stuff from the morph function
		for(uint32_t i=0;i<END_OF_SOUND_PARAMETERS; i++)
		{

			uint8_t paramNumber = parameterOrder[i];

			//const uint8_t morph = activeParameters[PAR_MORPH];

			const uint8_t val = activeParameters[paramNumber];//interpolate(activeParameters[i],morphParameters[i],morph);

			if(paramNumber < 128)
			{
				/* comes from cortex midi handler
				 * stupid offset!
				 * TODO fix this stupid offset			 *
				 * 		frontParser_midiMsg.data1 += 1;

						//because hh slope on front is 127 and on cortex is 0 wrap data1 at 127
						frontParser_midiMsg.data1 &= 0x7f;
				 *
				 */
				msg.status = MIDI_CC;
				msg.data1 = paramNumber;
				msg.data2 = val;

				msg.data1 += 1;
				msg.data1 &= 0x7f;
				midiParser_ccHandler(msg,1, 0, 0.f);


			}
			else
			{
				msg.status = CC_2;
				msg.data1 = paramNumber-128; //stupid offset only in CC not CC2
				msg.data2 = val;

			//	msg.data1 += 1;
				msg.data1 &= 0x7f;
				midiParser_ccHandler(msg,1, 0, 0.f);

			}
			soundengine_process();
		}
}
//----------------------------------------------------
// send loaded parameters to back
void preset_sendDrumsetParameters()
{
	uint8_t i;
	//special case mod targets
	for(i=0;i<6;i++)
	{
		//**VELO load drumkit. translate to param value before sending
		// parameter_values[PAR_VEL_DEST_1+i] is an index into modTargets, we need to send
		// a parameter number
		uint8_t value = (uint8_t)pgm_read_word(&modTargets[activeParameters[PAR_VEL_DEST_1+i]].param);
		uint8_t upper,lower;
		upper = (uint8_t)(((value&0x80)>>7) | (((i)&0x3f)<<1));
		lower = value&0x7f;
		frontPanel_sendData(CC_VELO_TARGET,upper,lower);

		// ensure target voice # is valid
		if(activeParameters[PAR_VOICE_LFO1+i] < 1 || activeParameters[PAR_VOICE_LFO1+i] > 6 )
			activeParameters[PAR_VOICE_LFO1+i]=1;

		// **LFO par_target_lfo will be an index into modTargets, but we need a parameter number to send
		value = (uint8_t)pgm_read_word(&modTargets[activeParameters[PAR_TARGET_LFO1+i]].param);

		upper = (uint8_t)(((value&0x80)>>7) | (((i)&0x3f)<<1));
		lower = value&0x7f;
		frontPanel_sendData(CC_LFO_TARGET,upper,lower);
	}

	// todo will this morph (and fuck up) our modulation targets?
	// send parameters (possibly combined with morph parameters) to back
	preset_morph(activeParameters[PAR_MORPH]);


}
//----------------------------------------------------
/** request step data from the cortex via uart and save it in the provided step struct*/

//----------------------------------------------------
/*

*/
//----------------------------------------------------
/** send step data from SD card to the sequencer*/

//----------------------------------------------------
FRESULT preset_savePatternSD(uint8_t presetNr)
{
    preset_fileCleanupWarning = 0;
    if(presetNr >= NUM_KIT_SLOTS) return FR_INVALID_NAME;
    return preset_savePatternRAM(presetNr);
}

//----------------------------------------------------
// returns 1 on success

//----------------------------------------------------
FRESULT preset_savePatternRAM(uint8_t presetNr)
{

	//check if current slot or new slot
	if(presetNr == seq_activePattern)
	{
		//### Current Slot ###
		//Refresh the snapshot; pattern edits already remain in RAM.
		seq_copyPatternToBackupBuffer(presetNr);
	}
	else
	{
		//### NEW SLOT ###
		//- write current (changed) pattern to new slot
		seq_copyPattern(seq_activePattern, presetNr);
		//- activate the new slot, retaining the edited source in RAM
		seq_setNextPattern(presetNr);
	}

	return FR_OK;
}
//----------------------------------------------------
FRESULT preset_loadPatternRAM(uint8_t presetNr)
{

	//I'm unused since there is no Pattern Load page, it just uses the pattern change/select page instead
	return FR_OK;
}
//----------------------------------------------------
//called periodically to process non blocking morph
void preset_morph_tick()
{
	//morph_state = 0;
	//return;
	if(morph_state)
	{

		uint8_t morph;

		//Do not morph audio routing
		if((morph_index >= PAR_AUDIO_OUT1) && (morph_index <= PAR_AUDIO_OUT6)) //morph_index++;
		{
			//always use source kit (morph = 0) for audio routing
			morph = 0;
		}
		else
		{
			morph = activeParameters[PAR_MORPH];
		}

		static MidiMsg msg = {0};


		const uint8_t val = interpolate(activeParameters[morph_index],morphParameters[morph_index],morph);


		if(morph_index < 128)
		{
			/* comes from cortex midi handler
			 * stupid offset!
			 * TODO fix this stupid offset			 *
			 * 		frontParser_midiMsg.data1 += 1;

					//because hh slope on front is 127 and on cortex is 0 wrap data1 at 127
					frontParser_midiMsg.data1 &= 0x7f;
			 *
			 */
			msg.status = MIDI_CC;
			msg.data1 = morph_index;
			msg.data2 = val;

			msg.data1 += 1;
			msg.data1 &= 0x7f;
			midiParser_ccHandler(msg,1, 0, 0.f);


		}
		else
		{
			msg.status = CC_2;
			msg.data1 = morph_index-128; //stupid offset only in CC not CC2
			msg.data2 = val;

		//	msg.data1 += 1;
			msg.data1 &= 0x7f;
			midiParser_ccHandler(msg,1, 0, 0.f);

		}


		morph_index++;
		if(morph_index >= END_OF_SOUND_PARAMETERS)
		{
			//finished morphing
			morph_state = 0;
		}
	}
}
//----------------------------------------------------
// This will determine an interpolated value between parameters
// and morph parameters and send the data to the back
// if the morph value is 0 it will just send the parameter values
// to the back
void preset_morph(uint8_t morph)
{
#if 1
	//initialize new morph
	morph_state = 1; //start morph
	morph_index = 0; //reset index
#else
	int i;
	//TODO so far only sound parameters are interpolated, no LFOs etc

	for(i=0;i<END_OF_SOUND_PARAMETERS;i++)
	{


		uint8_t val;

		val = interpolate(mainParameters[i],morphParameters[i],morph);

		if(i<128) {
			frontPanel_sendData(MIDI_CC,(uint8_t)i,val);

		} else {
			frontPanel_sendData(CC_2,(uint8_t)(i-128),val);

		}


		//to omit front panel button/LED lag we have to process din dout and uart here
		//read next button

		//update LEDs
		dio_process();
		//read uart messages from sequencer
		uart_checkAndParse();
	}
#endif
}

//----------------------------------------------------
uint8_t preset_getMorphValue(uint16_t index, uint8_t morph)
{
	return interpolate(activeParameters[index],morphParameters[index],morph);
};
//----------------------------------------------------

FRESULT preset_createProject(uint8_t presetNr)
{
    if(presetNr >= NUM_KIT_SLOTS) return FR_INVALID_NAME;
    memset(&activeParameters[PAR_BEGINNING_OF_GLOBALS], 0, PROJECT_CODEC_GLOBAL_BYTES);
    preset_loadDefaultGlobals();
    seq_activeSong = seq_songData[0];
    memset(seq_songData, SONG_END, sizeof seq_songData);
    seq_songData[0][0] = 0;
    for(uint8_t i=0;i<NUM_PATTERN;i++) {
        seq_clearPattern(i);
        seq_patternSet.kitNr[i] = 0;
        seq_patternSet.shuffle[i] = 0;
        memset(mainParameters[i], 0, END_OF_SOUND_PARAMETERS);
        preset_init(i);
        memset(savefileNames[i][PATTERN_NAMES], 0, 8);
        memcpy(savefileNames[i][PATTERN_NAMES], "Empty", 5);
        memset(savefileNames[i][SONG_NAMES], 0, 8);
        memcpy(savefileNames[i][SONG_NAMES], "Empty", 5);
    }
    memset(savefileNames[presetNr][PROJECT_NAMES], 0, 8);
    memcpy(savefileNames[presetNr][PROJECT_NAMES], "Init", 4);
    morphParameters = mainParameters[0];
    preset_loadDrumsetRam(0, 0, 1);
    menu_selectedPresetNr[SAVE_TYPE_KIT] = menu_loadedPresetNr[CURRENT_KIT] = 0;
    seq_copyPatternToBackupBuffer(seq_activePattern);
    menu_sendAllGlobals();
    return FR_OK;
}

FRESULT preset_bootProject(uint8_t *project)
{
    FRESULT res = preset_loadLastUsedProjectNrFromSD(project);
    if(res == FR_NO_FILE || res == FR_NO_PATH) res = FR_OK;
    if(res == FR_OK) res = preset_loadProject(*project, 0);
    if(res == FR_NO_FILE || res == FR_NO_PATH) res = preset_createProject(*project);
    return res;
}
//----------------------------------------------------
// **SAVEALL
// save all settings (global, pattern, kit)
// or save performance settings (pattern, kit)

// Normalize decoded kit caches once at storage ingress, not in the audio loop.
static void preset_normalizeKit(uint8_t *kit)
{
    if(kit[PAR_FX_DRY_WET] > 100) kit[PAR_FX_DRY_WET] = 100;
    const uint8_t nmt = getNumModTargets();
    for(uint8_t i=0;i<6;i++) {
        if(kit[PAR_VEL_DEST_1+i] >= nmt) kit[PAR_VEL_DEST_1+i] = 0;
        if(kit[PAR_TARGET_LFO1+i] >= nmt) kit[PAR_TARGET_LFO1+i] = 0;
    }
}

static uint8_t preset_projectSlot;
static ProjectStream preset_projectStream;
static uint8_t preset_projectCompressor[4];
static ProjectCodecData preset_projectData(uint8_t slot)
{
    ProjectCodecData data = {mainParameters, &seq_patternSet, seq_songData,
        savefileNames, savefileNames[slot][PROJECT_NAMES],
        &activeParameters[PAR_BEGINNING_OF_GLOBALS], preset_projectCompressor};
    return data;
}
static FRESULT preset_writeProjectFiles(void)
{
    ProjectCodecData data = preset_projectData(preset_projectSlot);
    preset_projectCompressor[0] = activeParameters[MASTER_COMP_THRESHOLD];
    preset_projectCompressor[1] = activeParameters[MASTER_COMP_RATIO];
    preset_projectCompressor[2] = activeParameters[MASTER_COMP_ATTACK];
    preset_projectCompressor[3] = activeParameters[MASTER_COMP_RELEASE];
    FRESULT res = preset_openFile((FIL*)&SDFile, "project.qpr", FA_CREATE_ALWAYS | FA_WRITE);
    if(res != FR_OK) return res;
    ProjectStream_InitWrite(&preset_projectStream, (FIL*)&SDFile);
    res = ProjectCodec_Write(&preset_projectStream, &data);
    // Stream writes bypass preset_writeFile; retain its first-error/close ownership.
    if(preset_writeResult == FR_OK) preset_writeResult = res;
    res = preset_closeFile((FIL*)&SDFile);
    return res;
}
FRESULT preset_saveProject(uint8_t presetNr)
{
    preset_projectCleanupWarning = 0;
    if(presetNr >= NUM_KIT_SLOTS || menu_loadedPresetNr[CURRENT_KIT] >= NUM_KIT_SLOTS)
        return FR_INVALID_NAME;
    preset_saveDrumsetRam(menu_loadedPresetNr[CURRENT_KIT], 0);
    // Shuffle edits are live globals until pad-save; capture only the playing
    // pattern, not the viewed/selected destination on the pattern-save page.
    seq_patternSet.shuffle[seq_activePattern] = activeParameters[PAR_SHUFFLE];
    preset_savePatternRAM(seq_activePattern);
    const uint8_t bg = soundengine_backgroundAudioBegin();
    lcd_process_display_interrupt = 0;
    while(sendDisplayBuffer() != 0);
    lcd_clear(); lcd_home(); lcd_string(PSTR("Saving Project"));
    preset_projectSlot = presetNr;
    // Release a retained write lock before recovery or staging cleanup can
    // open directories/unlink files (_FS_LOCK=1). Keep ownership if close fails.
    FRESULT res = FR_OK;
    if(preset_writeOpen)
    {
        res = f_close(preset_writeFileHandle);
        if(res == FR_OK) preset_writeOpen = 0;
    }
    if(res == FR_OK)
        res = storage_saveProject(presetNr, preset_writeProjectFiles, &preset_projectCleanupWarning);
    if(res == FR_OK && preset_saveLastUsedProjectNrToSD(presetNr) != FR_OK)
        preset_projectCleanupWarning = 1; // project committed, selection metadata failed
    lcd_process_display_interrupt = 1;
    soundengine_backgroundAudioEnd(bg);
    return res;
}
// Load follows below.

//----------------------------------------------------
FRESULT preset_saveSongSD(uint8_t songNr)
{
    preset_fileCleanupWarning = 0;
    return songNr < NUM_KIT_SLOTS ? FR_OK : FR_INVALID_NAME;
}


//----------------------------------------------------
void preset_loadProjectNames(uint8_t projectNr)
{
    if(projectNr >= NUM_KIT_SLOTS) return;
    char path[32];
    uint8_t header[PROJECT_CODEC_HEADER_BYTES];
    char name[8];
    UINT done;
    FRESULT res = storage_recoverProject(projectNr);
    sprintf(path, "/proj%02u/project.qpr", (unsigned)projectNr);
    if(res == FR_OK) res = preset_openFile((FIL*)&SDFile, path, FA_READ);
    if(res == FR_OK) {
        res = f_read((FIL*)&SDFile, header, sizeof header, &done);
        if(res == FR_OK && (done != sizeof header || memcmp(header, "QEONDAPR", 8) ||
            header[8] != 1 || header[9] != 0 || f_size((FIL*)&SDFile) != PROJECT_CODEC_FILE_BYTES))
            res = FR_INVALID_PARAMETER;
        if(res == FR_OK) {
            res = f_read((FIL*)&SDFile, name, sizeof name, &done);
            if(res == FR_OK && done != sizeof name) res = FR_DISK_ERR;
        }
        FRESULT closed = preset_closeFile((FIL*)&SDFile);
        if(res == FR_OK) res = closed;
    }
    memset(savefileNames[projectNr][PROJECT_NAMES], 0, 8);
    if(res == FR_OK) memcpy(savefileNames[projectNr][PROJECT_NAMES], name, 8);
    else memcpy(savefileNames[projectNr][PROJECT_NAMES], "Empty", 5);
}
//----------------------------------------------------
FRESULT preset_loadProject(uint8_t presetNr, uint8_t clearTmp)
{
    (void)clearTmp; // retained API argument; tmp restoration no longer exists
    if(presetNr >= NUM_KIT_SLOTS) return FR_INVALID_NAME;
    seq_slipClear();
    seq_setPerformanceBreak(0);
    sync_cancelPending();
    const uint8_t bg = soundengine_backgroundAudioBegin();
    FRESULT res = storage_recoverProject(presetNr);
    lcd_process_display_interrupt = 0;
    while(sendDisplayBuffer() != 0);
    lcd_clear(); lcd_home(); lcd_string(PSTR("Loading Project"));
    char path[32];
    sprintf(path, "/proj%02u/project.qpr", (unsigned)presetNr);
    if(res == FR_OK) res = preset_openFile((FIL*)&SDFile, path, FA_READ);
    if(res == FR_OK) {
        ProjectCodecData data = preset_projectData(presetNr);
        ProjectStream_InitRead(&preset_projectStream, (FIL*)&SDFile);
        res = ProjectCodec_Read(&preset_projectStream, &data, f_size((FIL*)&SDFile));
        FRESULT closed = preset_closeFile((FIL*)&SDFile);
        if(res == FR_OK) res = closed;
    }
    if(res == FR_OK) {
        for(uint8_t i=0;i<NUM_KIT_SLOTS;i++) preset_normalizeKit(mainParameters[i]);
        preset_applyMasterComp(preset_projectCompressor);
        menu_sendAllGlobals();
        morphParameters = mainParameters[0];
        uint8_t kit = 0;
        if(activeParameters[PAR_PATTERN_MODE] >= 1) {
            activeParameters[PAR_PATTERN_MODE] = 1;
            kit = seq_patternSet.kitNr[seq_activePattern];
            if(kit >= NUM_KIT_SLOTS) kit = 0;
        }
        preset_loadDrumsetRam(kit, 0, 1);
        menu_selectedPresetNr[SAVE_TYPE_KIT] = menu_loadedPresetNr[CURRENT_KIT] = kit;
        seq_copyPatternToBackupBuffer(seq_activePattern);
        seq_setNextPattern(0);
    }
    lcd_process_display_interrupt = 1;
    soundengine_backgroundAudioEnd(bg);
    return res;
}
//----------------------------------------------------
