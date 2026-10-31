#include "Soundengine/MIDI/MidiUsbRx.h"
MidiUsbRx midiUsbRx;
static void loss(MidiUsbRx *r)
{
    r->read = r->write; r->lost = 1; r->losses++;
}
/* Validate only meaningful bytes; padding is not MIDI. CIN F is an arbitrary
 * single byte and must pass through the source's stream decoder. */
static uint8_t packet(const uint8_t *p)
{
    uint8_t cin = p[0] & 15, b = p[1], n = 0;
    if(cin >= 8 && cin <= 14) {
        if((b >> 4) != cin) return 0;
        n = (cin == 12 || cin == 13) ? 2 : 3;
    } else switch(cin) {
    case 2: if(b != 0xf1 && b != 0xf3) return 0; n = 2; break;
    case 3: if(b != 0xf2) return 0; n = 3; break;
    case 4:
        if((b >= 0x80 && b != 0xf0) || p[2] >= 0x80 || p[3] >= 0x80) return 0;
        return 3;
    case 5: return b == 0xf6 || b == 0xf7 ? 1 : 0;
    case 6: case 7:
        n = cin - 4;
        if(p[n] != 0xf7 || (b >= 0x80 && b != 0xf0)) return 0;
        if(n == 3 && p[2] >= 0x80) return 0;
        return n;
    case 15: return 1;
    default: return 0;
    }
    for(uint8_t i = 2; i <= n; ++i) if(p[i] >= 0x80) return 0;
    return n;
}
void midi_usb_rx_receive(MidiUsbRx *r, const uint8_t *data, uint32_t length)
{
    /* FS endpoint maximum: bound IRQ work even if the driver reports bad length. */
    if(length > 64 || (length & 3) || (!data && length)) {
        r->invalid++; loss(r); return;
    }
    for(uint32_t i = 0; i < length; i += 4) {
        const uint8_t *p = data + i;
        if(p[0] >> 4) continue; /* Unsupported cable cannot damage cable zero. */
        uint8_t n = packet(p);
        if(!n) { r->invalid++; loss(r); continue; }
        if((uint8_t)(r->read - r->write - 1) < n) {
            r->overflow++; loss(r); continue;
        }
        for(uint8_t j = 1; j <= n; ++j) r->bytes[r->write++] = p[j];
    }
}
uint8_t midi_usb_rx_take(MidiUsbRx *r, uint8_t *byte, uint8_t *lost)
{
    *lost = r->lost; r->lost = 0;
    if(r->read == r->write) return 0;
    *byte = r->bytes[r->read++]; return 1;
}
