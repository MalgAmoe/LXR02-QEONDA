"""Actual production USB RX module and owned adapter functions, with fake IRQ/USB."""
from pathlib import Path
import re, tempfile, subprocess, os
root=Path(__file__).resolve().parents[1]
def extract(path,name):
 s=(root/path).read_text();m=re.search(r'^(?:static )?uint8_t\s+'+name+r'\s*\([^;]*?\)\s*\{',s,re.M);assert m,name
 i=s.index('{',m.start())+1;d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]+'\n'
c=r'''
#include <assert.h>
#include <string.h>
#include "Soundengine/MIDI/MidiUsbRx.h"
#include "Soundengine/MIDI/MidiMessages.h"
#undef __disable_irq
static unsigned mask,aborts,received;
static uint32_t __get_PRIMASK(void){return mask;}
static void __disable_irq(void){mask=1;}
static void __set_PRIMASK(uint32_t m){mask=m;}
static void uart_abortMidiSource(unsigned s){assert(!mask && s==2);aborts++;}
static void usb_abortMidiSource(uint8_t s){assert(!mask && s==2);}
typedef struct {uint8_t *RxBuffer; uint32_t RxLength;} USBD_CDC_HandleTypeDef;
typedef struct {int (*Receive)(uint8_t *,uint32_t *);} USBD_CDC_ItfTypeDef;
typedef struct {void *pClassData,*pUserData;} USBD_HandleTypeDef;
#define USBD_FAIL 1
#define USBD_OK 0
static unsigned length;
static uint32_t USBD_LL_GetRxDataSize(USBD_HandleTypeDef *p,uint8_t ep){return length;}
static int receive(uint8_t *p,uint32_t *n){assert(!mask);received++;memset(p,0,*n);return 0;}
'''
c+=extract(Path('Core/Src/Soundengine/USB/usb_manager.c'),'usb_getMidi')
c+=extract(Path('Middlewares/JS/STM32_USB_Device_Library/Class/CDC/Src/usbd_cdc.c'),'USBD_CDC_DataOut')
c+=r'''
static void packet(unsigned cin,unsigned a,unsigned b,unsigned c){uint8_t p[]={cin,a,b,c};midi_usb_rx_receive(&midiUsbRx,p,4);}
static MidiMsg next(unsigned status,unsigned sysex){MidiMsg m;assert(usb_getMidi(&m));assert(m.status==status&&m.bits.source==midiSourceUSB&&m.bits.sysxbyte==sysex);return m;}
int main(void){
 MidiMsg m;
 /* Driver copies before the Receive callback rearms/overwrites the buffer. */
 uint8_t p[]={9,0x90,60,100};USBD_CDC_HandleTypeDef h={p,0};USBD_CDC_ItfTypeDef f={receive};USBD_HandleTypeDef dev={&h,&f};length=4;
 assert(USBD_CDC_DataOut(&dev,1)==0&&received==1);m=next(0x90,0);assert(m.data1==60&&m.data2==100&&m.bits.length==2);
 dev.pClassData=0;assert(USBD_CDC_DataOut(&dev,1)==1);
 /* Every channel CIN, both Common lengths and arbitrary CIN F bytes. */
 for(unsigned cin=8;cin<=14;cin++){packet(cin,cin<<4,1,2);m=next(cin<<4,0);assert(m.bits.length==((cin==12||cin==13)?1:2));}
 packet(2,0xf1,7,255);next(0xf1,0);packet(2,0xf3,8,255);next(0xf3,0);
 packet(3,0xf2,1,2);next(0xf2,0);packet(5,0xf6,255,255);next(0xf6,0);
 packet(15,0x90,0,0);packet(15,60,0,0);packet(15,0xf8,0,0);next(0xf8,0);packet(15,100,0,0);next(0x90,0);
 packet(4,0xf0,1,2);next(0xf0,0);next(1,1);next(2,1);
 packet(4,3,4,5);next(3,1);next(4,1);next(5,1);
 packet(7,6,7,0xf7);next(6,1);next(7,1);next(0xf7,0);
 packet(6,0xf0,0xf7,0);next(0xf0,0);next(0xf7,0);
 /* Other cables do not reset cable zero's partial message. */
 packet(15,0x90,0,0);packet(0x19,0x90,1,2);packet(15,60,0,0);packet(15,100,0,0);next(0x90,0);
 /* Invalid/reserved packet does not terminate scanning; loss resets before newer data. */
 uint8_t mixed[]={0,0,0,0,9,0x90,3,4};midi_usb_rx_receive(&midiUsbRx,mixed,8);next(0x90,0);assert(aborts==1);
 packet(9,0x80,1,2);assert(!usb_getMidi(&m));assert(aborts==2);
 uint8_t shortp[3]={9,0x90,1};midi_usb_rx_receive(&midiUsbRx,shortp,3);assert(!usb_getMidi(&m));
 midi_usb_rx_receive(&midiUsbRx,shortp,65);assert(!usb_getMidi(&m));
 /* Full raw ring discards old data and requires a new status, preserving realtime. */
 for(unsigned i=0;i<256;i++)packet(15,1,0,0);
 assert(midiUsbRx.overflow);packet(15,0xf8,0,0);packet(9,0x90,9,10);next(0xf8,0);next(0x90,0);assert(!usb_getMidi(&m));
 /* Saved PRIMASK is restored; no-event path is safe when already masked. */
 mask=1;assert(!usb_getMidi(&m));assert(mask==1);mask=0;
 for(unsigned i=0;i<1000;i++){packet(9,0x90,1,2);next(0x90,0);} /* wrap */
 return 0;
}
'''
with tempfile.TemporaryDirectory() as td:
 src=Path(td)/'test.c';src.write_text(c);exe=Path(td)/'test'
 subprocess.run([os.environ.get('CC','cc'),'-std=c11','-g','-fsanitize=address,undefined','-I'+str(root/'tests/shim'),'-I'+str(root/'Core/Inc'),str(src),str(root/'Core/Src/Soundengine/MIDI/MidiUsbRx.c'),str(root/'Core/Src/Soundengine/MIDI/MidiStream.c'),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
