/* Copyright (C) 2026 Erica Synths; SPDX-License-Identifier: GPL-3.0-only */
#ifndef MIDI_USB_TX_H
#define MIDI_USB_TX_H
#include "Soundengine/MIDI/MidiStream.h"
typedef struct {
    uint8_t packets[64][4], read, write, owner, partial[3], used;
    uint8_t stage[64];
    uint16_t staged;
    uint32_t rejected, aborted;
} MidiUsbTx;
extern MidiUsbTx midiUsbTx;
void midi_usb_tx_reset(MidiUsbTx *s);
uint8_t midi_usb_tx_push(MidiUsbTx *s, const MidiEvent *e, uint8_t source);
void midi_usb_tx_abort(MidiUsbTx *s, uint8_t source);
uint16_t midi_usb_tx_stage(MidiUsbTx *s);
void midi_usb_tx_complete(MidiUsbTx *s);
#endif
