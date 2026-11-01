/* Copyright (C) 2026 Erica Synths; SPDX-License-Identifier: GPL-3.0-only */
#include <assert.h>
#include <string.h>
#include "Soundengine/MIDI/MidiUsbTx.h"
static MidiUsbTx s;
static unsigned push(unsigned b, unsigned n, unsigned source, unsigned sysex)
{
    MidiEvent e = {b,n,{1,2},sysex};
    return midi_usb_tx_push(&s,&e,source);
}
int main(void)
{
    assert(push(0xc0,1,1,0)); assert(push(0xf1,1,1,0));
    assert(push(0xf2,2,1,0)); assert(push(0xf6,0,1,0));
    assert(midi_usb_tx_stage(&s)==16);
    assert(s.stage[0]==12 && s.stage[3]==0);
    assert(s.stage[4]==2 && s.stage[8]==3 && s.stage[12]==5);
    uint8_t saved[64]; memcpy(saved,s.stage,64);
    assert(push(0x90,2,2,0)); assert(midi_usb_tx_stage(&s)==16);
    assert(!memcmp(saved,s.stage,64)); midi_usb_tx_complete(&s);
    assert(midi_usb_tx_stage(&s)==4); midi_usb_tx_complete(&s);
    midi_usb_tx_reset(&s);
    assert(push(0xf0,0,1,0)); assert(!push(0x90,2,2,0));
    assert(push(1,0,1,1)); assert(push(0xf7,0,1,0));
    assert(midi_usb_tx_stage(&s)==4);
    assert(s.stage[0]==7 && s.stage[1]==0xf0 && s.stage[2]==1 && s.stage[3]==0xf7);
    midi_usb_tx_complete(&s);
    for(unsigned i=0;i<10000;i++) {
        assert(push(0xf0,0,1,0)); assert(push(0xf8,0,2,0));
        midi_usb_tx_abort(&s,1); assert(!s.owner);
        assert(midi_usb_tx_stage(&s)==8); assert(s.stage[4]==6);
        midi_usb_tx_complete(&s);
    }
    midi_usb_tx_reset(&s); assert(push(0xf0,0,1,0));
    while(push(1,0,1,1)) {}
    assert(s.aborted==1 && !s.owner && s.rejected);
    unsigned bytes=0;
    while(midi_usb_tx_stage(&s)) {bytes+=s.staged;midi_usb_tx_complete(&s);}
    assert(bytes==63*4);
    assert(!push(1,0,1,1));
    return 0;
}
