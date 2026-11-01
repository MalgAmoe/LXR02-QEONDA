#!/usr/bin/env python3
"""Compile actual UART ISR/queue adapters with fake registers, real framing and FIFO."""
from pathlib import Path
import re, subprocess, tempfile, os
root=Path(__file__).resolve().parents[1]
def extract(text,name):
    clean=re.sub(r'/\*.*?\*/|//[^\n]*',lambda m:' '*len(m[0]),text,flags=re.S)
    m=re.search(r'^(?:static )?(?:void|uint8_t) '+name+r'\([^;\n]*\)\s*\{',clean,re.M)
    assert m,name
    p=clean.index('{',m.start())+1; depth=1
    while depth:
        depth+=(clean[p]=='{')-(clean[p]=='}');p+=1
    return text[m.start():p]+'\n'
uart=(root/'Core/Src/Soundengine/MIDI/Uart.c').read_text()
c=r'''
#include <assert.h>
#include <string.h>
#include "Soundengine/MIDI/MidiStream.h"
#include "Soundengine/MIDI/MidiMessages.h"
#include "Soundengine/FIFO.h"
#define USART_ISR_RXNE 1
#define USART_ISR_TXE 2
#define USART_ISR_ORE 4
#define USART_ISR_FE 8
#define USART_ISR_NE 16
#define USART_ICR_FECF 8
#define USART_ICR_NCF 16
#define RESET 0
#define UART_IT_TXE 2
#define READ_REG(x) (x)
#define WRITE_REG(x,y) ((x)=(y))
#define __HAL_UART_CLEAR_OREFLAG(x) ((void)(x))
#define __HAL_UART_ENABLE_IT(x,y) ((void)(x),(void)(y))
#define __HAL_UART_DISABLE_IT(x,y) ((void)(x),(void)(y))
static struct {uint32_t ISR, RDR, TDR, ICR;} regs;
#define USART3 (&regs)
static struct {typeof(regs) *Instance;} huart3={&regs};
#undef __disable_irq
static unsigned mask,owned,resets,events;
static uint32_t __get_PRIMASK(void){return mask;}
static void __disable_irq(void){mask=1;}
static void __set_PRIMASK(uint32_t m){mask=m;}
static uint8_t sync_tryControl(void){if(owned)return 0;owned=1;return 1;}
static void sync_releaseControl(void){owned=0;}
static Fifo fifo_midiRx;
static MidiSerial midiTx;
static volatile uint8_t midiRxLost;
static uint32_t midiRxLossCount,midiRxResyncCount;
static MidiDecoder decoder;
void uart_abortMidiSource(uint8_t source);
static void midiParser_resetUart(void){assert(!mask);resets++;midi_decode_reset(&decoder);}
static void midiParser_parseUartData(uint8_t b){
 assert(!mask);MidiEvent e;
 if(midi_decode(&decoder,b,&e)){events++;assert(e.status==0x90||e.status==0xf8);}
}
'''
for name in ['USART3_IRQHandler','uart_processMidi','uart_abortMidiSource','sendMidi','uart_sendMidi','uart_sendMidiOwn']:
    c+=extract(uart,name)
c+=r'''
static void rx(uint8_t b,uint32_t errors){regs.ISR=USART_ISR_RXNE|errors;regs.RDR=b;USART3_IRQHandler();}
int main(void){
 fifo_init(&fifo_midiRx);
 /* Hold ownership during overflow: the ISR discards the old queue atomically. */
 owned=1;for(unsigned i=0;i<256;i++)rx(1,0);
 assert(midiRxLost&&midiRxLossCount==1&&fifo_midiRx.read==fifo_midiRx.write);
 uart_processMidi();assert(midiRxLost&&resets==0);
 rx(100,0);rx(0xf8,0);rx(0x90,0);rx(60,0);rx(100,0);
 owned=0;uart_processMidi();assert(resets==1&&events==2&&midiRxResyncCount==1);
 /* A UART error discards pending data, drops the corrupt byte, and resets before newer bytes. */
 rx(0x90,0);rx(60,0);uart_processMidi();
 rx(100,USART_ISR_FE);rx(61,0);rx(100,0);rx(0xf8,0);
 uart_processMidi();assert(events==3&&resets==2&&midiRxLossCount==2);
 /* A partial outgoing SysEx is closed at a receive loss boundary. */
 MidiMsg start={.status=0xf0};uart_sendMidi(start);assert(midiTx.owner==1);
 rx(1,USART_ISR_ORE);uart_processMidi();assert(!midiTx.owner&&midiTx.aborted==1);
 uint8_t b;assert(midi_serial_pop(&midiTx,&b)&&b==0xf0);
 assert(midi_serial_pop(&midiTx,&b)&&b==0xf7);
 /* Producers preserve an already-set PRIMASK. No callbacks in transactions. */
 MidiMsg note={.status=0x90,.data1=60,.data2=100,.bits={.length=2}};
 mask=1;uart_sendMidiOwn(note);assert(mask==1);uart_abortMidiSource(1);assert(mask==1);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);(p/'case.c').write_text(c)
    subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-DLXR_HOST_TEST','-Wall','-Werror','-fsanitize=address,undefined',
        '-I'+str(root/'tests/shim'),'-I'+str(root/'Core/Inc'),str(p/'case.c'),
        str(root/'Core/Src/Soundengine/MIDI/MidiStream.c'),str(root/'Core/Src/Soundengine/FIFO.c'),'-o',str(p/'case')],check=True)
    subprocess.run([str(p/'case')],check=True)
print('Actual UART ISR, loss boundary, ownership and saved PRIMASK PASS')
