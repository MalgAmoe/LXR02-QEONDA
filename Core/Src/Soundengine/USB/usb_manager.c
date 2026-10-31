/*
 * usb_manager.c
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 *
 *
 *  Created on: 26.10.2012
 *      Author: Julian Schmidt
 */
#include "Soundengine/MIDI/MidiUsbRx.h"
#include "Soundengine/MIDI/MidiUsbTx.h"
#include "Soundengine/MIDI/Uart.h"
#include "Soundengine/USB/usb_manager.h"
#include <string.h>
#include "usbd_cdc_if.h"


/* Only queue operations use PRIMASK. Submission excludes the USB IRQ alone;
 * the claim also prevents a higher-priority producer from submitting twice. */
static volatile uint8_t submitting, inFlight;

void usb_midiReset(void)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    midi_usb_tx_reset(&midiUsbTx);
    inFlight = 0;
    /* Do not touch the decoder: foreground may be inside midi_decode(). */
    midiUsbRx.read = midiUsbRx.write;
    midiUsbRx.lost = 1;
    __set_PRIMASK(mask);
}

void usb_midiTxComplete(void)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    if(inFlight) {
        midi_usb_tx_complete(&midiUsbTx);
        inFlight = 0;
    }
    __set_PRIMASK(mask);
}

void usb_tick(void) { usb_flushMidi(); }

void usb_flushMidi(void)
{
    uint32_t mask = __get_PRIMASK();
    /* Never invoke the USB stack under a caller's global interrupt lock. */
    if(mask) return;
    __disable_irq();
    if(submitting || inFlight) { __set_PRIMASK(mask); return; }
    submitting = 1;
    __set_PRIMASK(mask);

    uint32_t enabled = NVIC_GetEnableIRQ(OTG_FS_IRQn);
    NVIC_DisableIRQ(OTG_FS_IRQn);
    __DSB(); __ISB();
    mask = __get_PRIMASK();
    __disable_irq();
    uint16_t length = midi_usb_tx_stage(&midiUsbTx);
    if(length) inFlight = 1; /* Before submission: tolerate synchronous completion. */
    __set_PRIMASK(mask);
    uint8_t result = length ? CDC_Transmit_FS(midiUsbTx.stage, length) : USBD_OK;
    mask = __get_PRIMASK();
    __disable_irq();
    if(result != USBD_OK) inFlight = 0; /* BUSY retains the immutable stage. */
    __set_PRIMASK(mask);
    if(enabled) NVIC_EnableIRQ(OTG_FS_IRQn);
    mask = __get_PRIMASK();
    __disable_irq();
    submitting = 0;
    __set_PRIMASK(mask);
}

static void sendMidi(MidiMsg msg, uint8_t source)
{
    MidiEvent e = {msg.status, msg.bits.length, {msg.data1, msg.data2}, msg.bits.sysxbyte};
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    midi_usb_tx_push(&midiUsbTx, &e, source);
    __set_PRIMASK(mask);
}
void usb_sendMidi(MidiMsg msg)
{
    sendMidi(msg, msg.bits.source == midiSourceMIDI ? 1 : 2);
}
void usb_sendMidiOwn(MidiMsg msg)
{
    msg.bits.sysxbyte = 0;
    sendMidi(msg, 3);
}
void usb_abortMidiSource(uint8_t source)
{
    uint32_t mask = __get_PRIMASK();
    __disable_irq();
    midi_usb_tx_abort(&midiUsbTx, source);
    __set_PRIMASK(mask);
}
//-------------------------------------------------------------------------------
uint8_t usb_getMidi(MidiMsg* msg)
{
    for(;;) {
        uint8_t byte, lost, have;
        MidiEvent e;
        uint32_t mask = __get_PRIMASK();
        __disable_irq();
        have = midi_usb_rx_take(&midiUsbRx, &byte, &lost);
        __set_PRIMASK(mask);
        if(lost) {
            midi_decode_reset(&midiUsbRx.decoder);
            uart_abortMidiSource(2);
            usb_abortMidiSource(2);
        }
        if(!have) return 0;
        /* Abort at the status boundary, even if decoding emits no event
         * (undefined Common or an incomplete channel message). */
        if(midiUsbRx.decoder.sysex && byte >= 0x80 && byte < 0xf8 && byte != 0xf7) {
            uart_abortMidiSource(2);
            usb_abortMidiSource(2);
        }
        if(!midi_decode(&midiUsbRx.decoder, byte, &e)) continue;
        memset(msg, 0, sizeof(*msg));
        msg->status = e.status; msg->data1 = e.data[0]; msg->data2 = e.data[1];
        msg->bits.length = e.length; msg->bits.sysxbyte = e.sysex;
        msg->bits.source = midiSourceUSB;
        return 1;
    }
}

