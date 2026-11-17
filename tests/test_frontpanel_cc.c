/*
 * test_frontpanel_cc.c - MIDI CCs forwarded to the front-panel parser
 * (frontPanelParser.c), in particular bank select (CC 0) kit changes
 *
 * Copyright (C) 2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include "lxr_test.h"
#include "frontPanelParser_ui.h"
#include "menu/menu.h"
#include "Preset/PresetManager.h"
#include "buttonHandler.h"

// --- Stubs for what frontPanelParser.c calls ------------------------------

uint8_t activeParameters[NUM_PARAMS];
uint8_t menu_activePage;
uint8_t menu_playedPattern;
uint8_t menu_selectedPresetNr[NUM_PRESET_LOCATIONS];
uint8_t paramToModTarget[END_OF_SOUND_PARAMETERS];

static int loadCalls, loadedKit, kitLoadedCalls, kitLoadedNr, kitTimerTouched, repaints;
static int mode, shownPattern, patternPaints, seqPaints, ledWrites;

void preset_loadDrumsetRam(uint8_t presetNr, uint8_t isMorph, uint8_t sendImmediate)
{
	loadCalls++;
	loadedKit = presetNr;
	CHECK_EQ(isMorph, 0);
	CHECK_EQ(sendImmediate, 0);
	// The real function copies mainParameters[presetNr]: must be a valid slot.
	CHECK(presetNr < NUM_KIT_SLOTS);
}
void menu_kitLoaded(uint8_t kitNr)
{
	kitLoadedCalls++;
	kitLoadedNr = kitNr;
}

void menu_repaint() { repaints++; }

uint8_t buttonHandler_getMode() { return (uint8_t)mode; }
void buttonHandler_muteVoice(uint8_t voice, uint8_t isMuted) {}
void buttonHandler_setRunStopState(uint8_t running) {}
void frontParser_parseUartData(unsigned char data) {}
void led_clearAllBlinkLeds() {}
void led_clearSequencerLeds() {}
void led_initPatternSelectLeds() { patternPaints++; }
void led_pulseLed(uint8_t ledNr) {}
void led_setValue(uint8_t val, uint8_t ledNr) { ledWrites++; }
void led_updateSeqLeds() { seqPaints++; }
void menu_repaintAll() { repaints++; }
void menu_setNumSamples(uint8_t num) {}
void menu_setShownPattern(uint8_t patternNr) { shownPattern = patternNr; }

// --- Helpers -------------------------------------------------------------------

static void reset(void)
{
	loadCalls = loadedKit = kitLoadedCalls = kitLoadedNr = kitTimerTouched = repaints = 0;
	memset(activeParameters, 0, sizeof activeParameters);
	mode = shownPattern = patternPaints = seqPaints = ledWrites = 0;
}

// What MidiParser.c does with a received CC: forward its three bytes.
static void receiveCc(uint8_t channel, uint8_t cc, uint8_t value)
{
	frontPanel_parseData((uint8_t)(0xb0 | channel));
	frontPanel_parseData(cc);
	frontPanel_parseData(value);
}

// --- Tests -----------------------------------------------------------------------

static void test_bank_select_loads_the_kit_and_updates_the_menu(void)
{
	reset();
	receiveCc(0, 0, 5);
	CHECK_EQ(loadCalls, 1);
	CHECK_EQ(loadedKit, 5);
	CHECK_EQ(kitLoadedCalls, 1);
	CHECK_EQ(kitLoadedNr, 5);
	CHECK_EQ(kitTimerTouched, 0);
	CHECK(repaints > 0);
}

static void test_bank_select_accepts_every_kit_slot(void)
{
	for (int kit = 0; kit < NUM_KIT_SLOTS; kit++) {
		reset();
		receiveCc(3, 0, (uint8_t)kit);
		CHECK_EQ(loadCalls, 1);
		CHECK_EQ(loadedKit, kit);
		CHECK_EQ(kitLoadedNr, kit);
	}
}

// There are 64 kits but CC values go up to 127.
static void test_bank_select_ignores_values_past_the_last_kit(void)
{
	for (int value = NUM_KIT_SLOTS; value <= 127; value++) {
		reset();
		receiveCc(0, 0, (uint8_t)value);
		CHECK_EQ(loadCalls, 0);
		CHECK_EQ(kitLoadedCalls, 0);
		CHECK_EQ(kitTimerTouched, 0);
		CHECK_EQ(repaints, 0);
		for (int i = 0; i < NUM_PARAMS; i++)
			CHECK_EQ(activeParameters[i], 0);
	}
}

// Bank select must not be treated as a parameter.
static void test_bank_select_doesnt_change_parameters(void)
{
	reset();
	receiveCc(0, 0, 7);
	for (int i = 0; i < NUM_PARAMS; i++)
		CHECK_EQ(activeParameters[i], 0);
}

// Other CCs still set front-panel parameter CC-1 (CC 2 = parameter 1, ...).
static void test_other_ccs_set_parameters(void)
{
	reset();
	receiveCc(0, 2, 99);
	CHECK_EQ(activeParameters[1], 99);
	CHECK_EQ(loadCalls, 0);
	CHECK_EQ(kitLoadedCalls, 0);
}

static void test_live_pattern_ack_and_direct_step_led_ownership(void)
{
	for (int page = 0; page < NUM_PAGES; page++) {
		reset();
		mode = SELECT_MODE_PATTERN_LIVE;
		menu_activePage = (uint8_t)page;
		frontPanel_parseData(SEQ_CC);
		frontPanel_parseData(SEQ_CHANGE_PAT);
		frontPanel_parseData(37);
		CHECK_EQ(menu_playedPattern, 37);
		CHECK_EQ(shownPattern, 37);
		CHECK_EQ(patternPaints, 1);
		CHECK(repaints > 0);
		CHECK_EQ(menu_activePage, page);
		frontPanel_parseData(LED_CC);
		frontPanel_parseData(LED_SEQ_BUTTON);
		frontPanel_parseData(16);
		CHECK_EQ(ledWrites, 0);
	}
	reset();
	menu_activePage = VOICE1_PAGE;
	frontPanel_parseData(LED_CC);
	frontPanel_parseData(LED_SEQ_BUTTON);
	frontPanel_parseData(16);
	CHECK_EQ(ledWrites, 1); /* ordinary legacy step display remains enabled */
}

int main(void)
{
	RUN_TEST(test_live_pattern_ack_and_direct_step_led_ownership);
	RUN_TEST(test_bank_select_loads_the_kit_and_updates_the_menu);
	RUN_TEST(test_bank_select_accepts_every_kit_slot);
	RUN_TEST(test_bank_select_ignores_values_past_the_last_kit);
	RUN_TEST(test_bank_select_doesnt_change_parameters);
	RUN_TEST(test_other_ccs_set_parameters);
	return TEST_REPORT();
}
