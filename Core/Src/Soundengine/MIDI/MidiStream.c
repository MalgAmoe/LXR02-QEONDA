/*
 * Copyright (C) 2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 * See LICENSE and NOTICE.md for terms.
 */
#include "Soundengine/MIDI/MidiStream.h"
#include <string.h>
uint8_t midi_data_length(uint8_t s)
{
    if(s < 0x80) return 0;
    if(s < 0xf0) return (s >> 4 == 0xc || s >> 4 == 0xd) ? 1 : 2;
    return s == 0xf2 ? 2 : (s == 0xf1 || s == 0xf3 ? 1 : 0);
}
void midi_decode_reset(MidiDecoder *d) { memset(d, 0, sizeof(*d)); }
uint8_t midi_decode(MidiDecoder *d, uint8_t b, MidiEvent *e)
{
    memset(e, 0, sizeof(*e));
    if(b >= 0xf8) { e->status = b; return 1; }
    if(b & 0x80) {
        uint8_t was_sysex = d->sysex;
        d->used = 0; d->sysex = 0;
        d->running = b < 0xf0 ? b : 0;
        d->status = b; d->length = midi_data_length(b);
        if(b == 0xf0) { d->sysex = 1; e->status = b; return 1; }
        if(b == 0xf7) { e->status = b; return was_sysex; }
        if(b == 0xf6) { e->status = b; return 1; }
        /* Undefined Common cancels running status, but is not dispatched. */
        return 0;
    }
    if(d->sysex) { e->status = b; e->sysex = 1; return 1; }
    if(!d->length) return 0;
    d->data[d->used++] = b;
    if(d->used < d->length) return 0;
    e->status = d->status; e->length = d->length;
    e->data[0] = d->data[0]; e->data[1] = d->length == 2 ? d->data[1] : 0;
    d->used = 0;
    d->status = d->running; d->length = midi_data_length(d->running);
    return 1;
}
static void put(MidiSerial *s, uint8_t b) { s->bytes[s->write++] = b; }
void midi_serial_abort(MidiSerial *s, uint8_t source)
{
    if(s->owner == source) {
        put(s, 0xf7); /* Reserved slot, even when ordinary admission is full. */
        s->owner = 0; s->running = 0; s->aborted++;
    }
}
uint8_t midi_serial_push(MidiSerial *s, const MidiEvent *e, uint8_t source)
{
    uint8_t b = e->status, realtime = b >= 0xf8;
    uint8_t free = (uint8_t)(s->read - s->write - 1);
    uint8_t omit = b < 0xf0 && b >= 0x80 && b == s->running;
    uint8_t n = 1 + e->length - omit;
    if(!source || e->length > 2) goto reject;
    if(e->sysex) {
        if(b >= 0x80 || e->length) goto reject;
    } else {
        if(b < 0x80 || e->length != midi_data_length(b)) goto reject;
        if(b == 0xf4 || b == 0xf5) goto reject;
        if((e->length && e->data[0] >= 0x80) ||
           (e->length == 2 && e->data[1] >= 0x80)) goto reject;
    }
    if(!realtime && s->owner && (s->owner != source || (!e->sysex && b != 0xf7))) {
        /* A new status from the owner explicitly ends its damaged SysEx. */
        if(s->owner == source && b >= 0x80) midi_serial_abort(s, source);
        else goto reject;
        free = (uint8_t)(s->read - s->write - 1);
    }
    if(e->sysex && s->owner != source) goto reject;
    if(b == 0xf7 && s->owner != source) goto reject;
    if(b < 0x80 && !e->sysex) goto reject;
    /* Always reserve EOX while a stream is open or being started. */
    if(free < n + ((s->owner || b == 0xf0) && b != 0xf7 ? 1 : 0)) {
        if(e->sysex || b == 0xf7) midi_serial_abort(s, source);
        goto reject;
    }
    if(!omit) put(s, b);
    if(e->length) put(s, e->data[0]);
    if(e->length > 1) put(s, e->data[1]);
    if(!realtime) {
        if(b == 0xf0) s->owner = source;
        if(b == 0xf7) s->owner = 0;
        s->running = b >= 0x80 && b < 0xf0 ? b : 0;
    }
    return 1;
reject:
    s->rejected++; return 0;
}
uint8_t midi_serial_pop(MidiSerial *s, uint8_t *b)
{
    if(s->read == s->write) return 0;
    *b = s->bytes[s->read++]; return 1;
}
