/*
 * Copyright (C) 2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 * See LICENSE and NOTICE.md for terms.
 */
#ifndef MIDI_STREAM_H
#define MIDI_STREAM_H
#include <stdint.h>
/* Portable framing. One instance per input; no dispatch/callback under a lock. */
typedef struct {
    uint8_t running, status, length, used, data[2], sysex;
} MidiDecoder;
typedef struct { uint8_t status, length, data[2], sysex; } MidiEvent;
uint8_t midi_decode(MidiDecoder *d, uint8_t byte, MidiEvent *e);
void midi_decode_reset(MidiDecoder *d);
uint8_t midi_data_length(uint8_t status);
/* Caller serializes push/pop/abort. Capacity 255, one byte reserved for EOX. */
typedef struct {
    uint8_t bytes[256], read, write, running, owner;
    uint32_t rejected, aborted;
} MidiSerial;
uint8_t midi_serial_push(MidiSerial *s, const MidiEvent *e, uint8_t source);
uint8_t midi_serial_pop(MidiSerial *s, uint8_t *byte);
void midi_serial_abort(MidiSerial *s, uint8_t source);
#endif
