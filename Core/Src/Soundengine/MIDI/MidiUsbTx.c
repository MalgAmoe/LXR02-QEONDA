/* Copyright (C) 2026 Erica Synths; SPDX-License-Identifier: GPL-3.0-only */
#include "Soundengine/MIDI/MidiUsbTx.h"
#include <string.h>
MidiUsbTx midiUsbTx;
static unsigned space(MidiUsbTx *s) { return (s->read - s->write - 1) & 63; }
static void packet(MidiUsbTx *s, uint8_t cin, const uint8_t *p, unsigned n)
{
    uint8_t *out = s->packets[s->write];
    memset(out, 0, 4); out[0] = cin; memcpy(out + 1, p, n);
    s->write = (s->write + 1) & 63;
}
void midi_usb_tx_reset(MidiUsbTx *s) { memset(s, 0, sizeof(*s)); }
void midi_usb_tx_abort(MidiUsbTx *s, uint8_t source)
{
    if(s->owner != source || !source) return;
    s->partial[s->used++] = 0xf7;
    packet(s, 4 + s->used, s->partial, s->used);
    s->used = s->owner = 0; s->aborted++;
}
uint8_t midi_usb_tx_push(MidiUsbTx *s, const MidiEvent *e, uint8_t source)
{
    uint8_t b = e->status, rt = b >= 0xf8;
    if(!source || e->length > 2) goto reject;
    if(e->sysex) {
        if(b >= 0x80 || e->length || s->owner != source) goto reject;
    } else {
        if(b < 0x80 || e->length != midi_data_length(b) || b == 0xf4 || b == 0xf5) goto reject;
        if((e->length && e->data[0] >= 0x80) || (e->length == 2 && e->data[1] >= 0x80)) goto reject;
    }
    if(!rt && s->owner && (s->owner != source || (!e->sysex && b != 0xf7))) {
        if(s->owner != source) goto reject;
        midi_usb_tx_abort(s, source);
    }
    if(b == 0xf7 && s->owner != source) goto reject;
    /* One complete packet remains reserved to terminate an owned stream. */
    if(space(s) < (unsigned)((s->owner || b == 0xf0) && b != 0xf7 ? 2 : 1)) {
        if(e->sysex || b == 0xf7) midi_usb_tx_abort(s, source);
        goto reject;
    }
    if(e->sysex || b == 0xf0 || b == 0xf7) {
        if(b == 0xf0) s->owner = source;
        s->partial[s->used++] = b;
        if(b == 0xf7 || s->used == 3) {
            packet(s, b == 0xf7 ? 4 + s->used : 4, s->partial, s->used);
            s->used = 0;
        }
        if(b == 0xf7) s->owner = 0;
    } else {
        uint8_t p[3] = {b, e->data[0], e->data[1]};
        uint8_t cin = b < 0xf0 ? b >> 4 : rt ? 15 : b == 0xf6 ? 5 : b == 0xf2 ? 3 : 2;
        packet(s, cin, p, 1 + e->length);
    }
    return 1;
reject:
    s->rejected++; return 0;
}
uint16_t midi_usb_tx_stage(MidiUsbTx *s)
{
    if(s->staged) return s->staged;
    while(s->read != s->write && s->staged < sizeof(s->stage)) {
        memcpy(s->stage + s->staged, s->packets[s->read], 4);
        s->staged += 4; s->read = (s->read + 1) & 63;
    }
    return s->staged;
}
void midi_usb_tx_complete(MidiUsbTx *s) { s->staged = 0; }
