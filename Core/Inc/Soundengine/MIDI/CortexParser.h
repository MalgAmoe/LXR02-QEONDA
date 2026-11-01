/*
 * frontPanelParser.h
 *
 *  Created on: 27.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#ifndef FRONTPANELPARSER_H_
#define FRONTPANELPARSER_H_

#include "Soundengine/MIDI/MidiMessages.h"
#include "Soundengine/DSPAudio/modulationNode.h"
#include "Soundengine/MIDI/valueShaper.h"

extern uint8_t frontParser_activeTrack;
extern uint8_t frontParser_shownPattern;
extern uint8_t frontParser_sysexActive;

extern uint8_t frontParser_activeFrontTrack;

void frontParser_parseUartData(unsigned char data);
/* Apply local sound edits without capturing automation or altering parser state. */
void frontParser_dispatchNonRecording(uint8_t status, uint8_t data1, uint8_t data2);

//void frontParser_updateTrackLeds(const uint8_t trackNr, uint8_t patternNr);

#endif /* FRONTPANELPARSER_H_ */
