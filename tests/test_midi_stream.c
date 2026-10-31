/* Actual portable production source; no duplicate parser or serializer. */
#include "Soundengine/MIDI/MidiStream.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static MidiDecoder d;
static MidiSerial tx;
static MidiEvent e;
static unsigned feed(const uint8_t *p, unsigned n, MidiEvent *out)
{
    unsigned count=0;
    for(unsigned i=0;i<n;i++) if(midi_decode(&d,p[i],&e)) out[count++]=e;
    return count;
}
static void framing(void)
{
    MidiEvent out[32];
    const uint8_t bytes[]={0x90,60,100,0xf1,3,61,100,0xf3,4,62,100,0xf6,63,100};
    assert(feed(bytes,sizeof bytes,out)==4);
    assert(out[1].status==0xf1 && out[1].length==1 && out[1].data[0]==3);
    assert(out[2].status==0xf3 && out[2].length==1 && out[2].data[0]==4);
    assert(out[3].status==0xf6 && out[3].length==0);
    for(unsigned common=0xf0;common<=0xf7;common++) {
        midi_decode_reset(&d);
        uint8_t b[]={0x90,1,2,common,3,4,5,6};
        unsigned count=feed(b,sizeof b,out);
        for(unsigned i=1;i<count;i++) assert(out[i].status!=0x90);
    }
    midi_decode_reset(&d);
    const uint8_t rt[]={0x90,60,0xf8,100,61,0xff,101};
    assert(feed(rt,sizeof rt,out)==4);
    assert(out[0].status==0xf8 && out[1].status==0x90 && out[1].data[1]==100);
    assert(out[2].status==0xff && out[3].data[0]==61);
    midi_decode_reset(&d); midi_decode(&d,0x90,&e); midi_decode(&d,60,&e);
    midi_decode_reset(&d); assert(!midi_decode(&d,100,&e));
    assert(midi_decode(&d,0xf8,&e)); assert(!midi_decode(&d,61,&e));
    MidiDecoder other={0}; assert(!midi_decode(&other,100,&e));
}
static unsigned drain(uint8_t *p)
{
    unsigned n=0; while(midi_serial_pop(&tx,p+n)) n++; return n;
}
static MidiEvent note={0x90,2,{60,100},0};
static void serialization(void)
{
    uint8_t out[256]; memset(&tx,0,sizeof tx);
    assert(midi_serial_push(&tx,&note,1)); assert(midi_serial_push(&tx,&note,2));
    assert(drain(out)==5); assert(out[0]==0x90 && out[3]==60);
    MidiEvent other=note; other.status=0x91;
    assert(midi_serial_push(&tx,&other,3)); assert(midi_serial_push(&tx,&note,1));
    assert(drain(out)==6 && out[0]==0x91 && out[3]==0x90);
    /* Fill to every boundary, including wrap, never admit a short prefix. */
    for(unsigned fill=0;fill<256;fill++) {
        memset(&tx,0,sizeof tx); tx.read=tx.write=251;
        MidiEvent rt={0xf8,0,{0,0},0};
        for(unsigned i=0;i<fill;i++) assert(midi_serial_push(&tx,&rt,3));
        unsigned before=tx.write;
        unsigned accepted=midi_serial_push(&tx,&note,1);
        assert(accepted==(fill<=252));
        if(!accepted) assert(tx.write==before && tx.running==0);
        assert(drain(out)==fill+(accepted?3:0));
    }
}
static void sysex(void)
{
    uint8_t out[256]; memset(&tx,0,sizeof tx);
    MidiEvent start={0xf0,0,{0,0},0}, data={1,0,{0,0},1};
    MidiEvent end={0xf7,0,{0,0},0}, rt={0xf8,0,{0,0},0};
    assert(midi_serial_push(&tx,&start,1));
    assert(!midi_serial_push(&tx,&note,3));
    assert(!midi_serial_push(&tx,&data,2));
    assert(midi_serial_push(&tx,&rt,3));
    for(unsigned i=0;i<252;i++) assert(midi_serial_push(&tx,&data,1));
    assert(!midi_serial_push(&tx,&data,1));
    assert(tx.aborted==1 && tx.owner==0);
    assert(drain(out)==255 && out[0]==0xf0 && out[1]==0xf8 && out[254]==0xf7);
    assert(!midi_serial_push(&tx,&data,1)); assert(!midi_serial_push(&tx,&end,1));
    assert(midi_serial_push(&tx,&note,3)); drain(out);
    assert(midi_serial_push(&tx,&start,2));
    midi_serial_abort(&tx,1); assert(tx.owner==2);
    midi_serial_abort(&tx,2); assert(!tx.owner && tx.aborted==2);
    assert(drain(out)==2 && out[1]==0xf7);
    /* Long streams bounded by the ring, not a short wall-clock timeout. */
    assert(midi_serial_push(&tx,&start,1)); drain(out);
    for(unsigned i=0;i<10000;i++) { assert(midi_serial_push(&tx,&data,1)); assert(drain(out)==1); }
    assert(midi_serial_push(&tx,&end,1)); assert(drain(out)==1 && out[0]==0xf7);
}
int main(void) { framing(); serialization(); sysex(); puts("MIDI framing/atomic TX/SysEx PASS"); }
