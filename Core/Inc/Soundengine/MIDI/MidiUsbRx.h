/* USB cable zero RX. Producer: USB IRQ. Consumer takes under saved PRIMASK.
 * Loss discards pending bytes; decoder reset/abort is done in foreground. */
#ifndef MIDI_USB_RX_H
#define MIDI_USB_RX_H
#include "Soundengine/MIDI/MidiStream.h"
typedef struct {
    uint8_t bytes[256], read, write, lost;
    uint32_t invalid, overflow, losses;
    MidiDecoder decoder;
} MidiUsbRx;
extern MidiUsbRx midiUsbRx;
void midi_usb_rx_receive(MidiUsbRx *r, const uint8_t *data, uint32_t length);
uint8_t midi_usb_rx_take(MidiUsbRx *r, uint8_t *byte, uint8_t *lost);
#endif
