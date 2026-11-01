"""Compile production adapter, CDC submission and DataIn against a fake USB core.
Links the actual portable TX queue, staging and ownership implementation.
"""
from pathlib import Path
import re, tempfile, subprocess, os
root = Path(__file__).resolve().parents[1]
def extract(path, name):
    s=(root/path).read_text()
    m=re.search(r'^(?:static )?(?:void|uint8_t)\s+'+name+r'\s*\([^;]*?\)\s*\{',s,re.M)
    assert m,name
    i=s.index('{',m.start())+1; depth=1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}'); i+=1
    return s[m.start():i]+'\n'
c=r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "Soundengine/MIDI/MidiUsbTx.h"
#define PCD_HandleTypeDef ShimPCD_HandleTypeDef
#include "Soundengine/MIDI/MidiMessages.h"
#undef PCD_HandleTypeDef
#undef __disable_irq
static unsigned mask, irq=1, calls;
static uint32_t __get_PRIMASK(void){return mask;}
static void __disable_irq(void){mask=1;}
static void __set_PRIMASK(uint32_t m){mask=m;}
#define OTG_FS_IRQn 1
static unsigned NVIC_GetEnableIRQ(int i){return irq;}
static void NVIC_DisableIRQ(int i){irq=0;}
static void NVIC_EnableIRQ(int i){irq=1;}
#define __DSB() ((void)0)
#define __ISB() ((void)0)
#define USBD_OK 0
#define USBD_BUSY 1
#define USBD_FAIL 2
#define USBD_STATE_CONFIGURED 3
#define CDC_IN_EP 0x81
#define CDC_DATA_FS_IN_PACKET_SIZE 64
static struct {unsigned read,write,lost;} midiUsbRx;
static volatile uint8_t submitting,inFlight;
typedef struct {unsigned TxState,TxLength;uint8_t *TxBuffer;} USBD_CDC_HandleTypeDef;
typedef struct {struct {unsigned maxpacket;} IN_ep[16];} PCD_HandleTypeDef;
typedef struct {void *pClassData,*pData;unsigned dev_state;struct {unsigned total_length;} ep_in[16];} USBD_HandleTypeDef;
static USBD_HandleTypeDef hUsbDeviceFS;
void usb_flushMidi(void);
void usb_midiTxComplete(void);
static unsigned llResult, synchronous, reenter, zlp;
static uint8_t USBD_LL_Transmit(USBD_HandleTypeDef *p,unsigned ep,uint8_t *b,unsigned len){
 assert(!mask);calls++; if(!len)zlp++;
 if(reenter){reenter=0;usb_flushMidi();}
 if(synchronous){synchronous=0;((USBD_CDC_HandleTypeDef*)p->pClassData)->TxState=0;usb_midiTxComplete();}
 return llResult;
}
static void USBD_CDC_SetTxBuffer(USBD_HandleTypeDef *p,uint8_t *b,unsigned n){assert(!mask);USBD_CDC_HandleTypeDef *h=p->pClassData;h->TxBuffer=b;h->TxLength=n;}
'''
driver=Path('Middlewares/JS/STM32_USB_Device_Library/Class/CDC/Src/usbd_cdc.c')
c+=extract(driver,'USBD_CDC_TransmitPacket')
c+=extract(Path('USB_DEVICE_MIDI/App/usbd_cdc_if.c'),'CDC_Transmit_FS')
manager=Path('Core/Src/Soundengine/USB/usb_manager.c')
for name in ['usb_midiReset','usb_midiTxComplete','usb_flushMidi','sendMidi','usb_sendMidi','usb_sendMidiOwn','usb_abortMidiSource']:
    c+=extract(manager,name)
c+=extract(driver,'USBD_CDC_DataIn')
c+=r'''
int main(void){
 USBD_CDC_HandleTypeDef h={0}; PCD_HandleTypeDef pc={0};pc.IN_ep[1].maxpacket=64;
 hUsbDeviceFS.pData=&pc;hUsbDeviceFS.dev_state=USBD_STATE_CONFIGURED;
 uint8_t b[64]={0};
 assert(CDC_Transmit_FS(b,4)==USBD_FAIL); /* disconnected: no NULL dereference */
 hUsbDeviceFS.pClassData=&h;
 assert(CDC_Transmit_FS(0,4)==USBD_FAIL);
 assert(CDC_Transmit_FS(b,65)==USBD_FAIL);
 hUsbDeviceFS.dev_state=0;assert(CDC_Transmit_FS(b,4)==USBD_FAIL);
 hUsbDeviceFS.dev_state=USBD_STATE_CONFIGURED;
 mask=1;usb_flushMidi();assert(mask&&!calls&&!submitting);mask=0;
 /* Fill via actual adapters, then stage through usb_flushMidi on BUSY. */
 MidiMsg note={0};note.status=0x90;note.data1=60;note.data2=100;note.bits.length=2;
 for(unsigned i=0;i<16;i++)usb_sendMidiOwn(note);
 h.TxState=1;h.TxBuffer=b;h.TxLength=7;
 usb_flushMidi();assert(!inFlight&&midiUsbTx.staged==64&&!calls&&h.TxBuffer==b&&h.TxLength==7);
 h.TxState=0;reenter=1;usb_flushMidi();assert(inFlight&&calls==1&&irq&&!mask);
 usb_flushMidi();assert(calls==1); /* no double submission */
 assert(USBD_CDC_DataIn(&hUsbDeviceFS,2)==USBD_FAIL&&inFlight);
 USBD_CDC_DataIn(&hUsbDeviceFS,1);assert(zlp==1&&inFlight&&h.TxState&&midiUsbTx.staged==64);
 for(unsigned i=0;i<16;i++){assert(midiUsbTx.stage[4*i]==9);assert(midiUsbTx.stage[4*i+1]==0x90);assert(midiUsbTx.stage[4*i+2]==60);assert(midiUsbTx.stage[4*i+3]==100);}
 /* Admission while in flight must not mutate stage, nor be lost on completion. */
 usb_sendMidiOwn(note);
 assert(midiUsbTx.stage[2]==60&&midiUsbTx.staged==64);
 USBD_CDC_DataIn(&hUsbDeviceFS,1);assert(!inFlight&&!h.TxState&&!midiUsbTx.staged);
 llResult=USBD_FAIL;usb_flushMidi();assert(!inFlight&&!h.TxState&&midiUsbTx.staged==4);
 llResult=0;synchronous=1;usb_flushMidi();assert(!inFlight&&!midiUsbTx.staged);
 usb_sendMidiOwn(note);irq=0;usb_flushMidi();assert(!irq&&inFlight);
 midiUsbRx.read=1;midiUsbRx.write=9;usb_midiReset();assert(!inFlight&&!midiUsbTx.staged&&midiUsbRx.read==9&&midiUsbRx.lost&&!midiUsbTx.owner);
 hUsbDeviceFS.pClassData=0;assert(USBD_CDC_DataIn(&hUsbDeviceFS,1)==USBD_FAIL);
 usb_sendMidiOwn(note);usb_flushMidi();assert(!inFlight&&midiUsbTx.staged==4);usb_midiReset();
 MidiMsg msg={0};msg.status=0xf0;usb_sendMidi(msg);assert(midiUsbTx.owner==1);
 usb_abortMidiSource(2);assert(midiUsbTx.owner==1);
 usb_abortMidiSource(1);assert(!midiUsbTx.owner&&midiUsbTx.aborted==1&&!mask);
 usb_midiReset();msg.bits.source=midiSourceUSB;usb_sendMidi(msg);assert(midiUsbTx.owner==2);
 usb_midiReset();usb_sendMidiOwn(note);assert(midi_usb_tx_stage(&midiUsbTx)==4&&midiUsbTx.stage[0]==9);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as td:
    src=Path(td)/'test.c'; src.write_text(c); exe=Path(td)/'test'
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-g','-fsanitize=address,undefined','-I'+str(root/'tests/shim'),'-I'+str(root/'Core/Inc'),str(src),str(root/'Core/Src/Soundengine/MIDI/MidiUsbTx.c'),str(root/'Core/Src/Soundengine/MIDI/MidiStream.c'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
