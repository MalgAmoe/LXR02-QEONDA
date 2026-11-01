"""Production decoder, routing boundary, adapters and serializers end to end."""
from pathlib import Path
import re, tempfile, subprocess, os
root=Path(__file__).resolve().parents[1]
def extract(path,name):
 s=(root/path).read_text();m=re.search(r'^(?:static )?(?:void|uint8_t)\s+'+name+r'\s*\([^;]*?\)\s*\{',s,re.M);assert m,name
 i=s.index('{',m.start())+1;d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]+'\n'
parser=Path('Core/Src/Soundengine/MIDI/MidiParser.c')
manager=Path('Core/Src/Soundengine/USB/usb_manager.c')
uart=Path('Core/Src/Soundengine/MIDI/Uart.c')
c=r''' 
#include <assert.h>
#include <string.h>
#include "Soundengine/MIDI/MidiUsbRx.h"
#include "Soundengine/MIDI/MidiUsbTx.h"
#include "Soundengine/MIDI/MidiMessages.h"
#undef __disable_irq
static unsigned mask;
static uint32_t __get_PRIMASK(void){return mask;}
static void __disable_irq(void){mask=1;}
static void __set_PRIMASK(uint32_t m){mask=m;}
static MidiSerial midiTx;
static MidiDecoder dinDecoder;
static struct {unsigned CR1;} regs;
static struct {void *Instance;} huart3;
#define UART_IT_TXE 1
#define __HAL_UART_ENABLE_IT(a,b) ((void)0)
'''
s=(root/parser).read_text();c+=s[s.index('static union {'):s.index('} midiParser_routing = {0};')+len('} midiParser_routing = {0};')]
for path,names in [(uart,['sendMidi','uart_abortMidiSource','uart_sendMidi','uart_sendMidiOwn']), (manager,['sendMidi','usb_sendMidi','usb_sendMidiOwn','usb_abortMidiSource','usb_getMidi'])]:
 for name in names:c+=extract(path,name).replace(" sendMidi(", " dinSendMidi(" if path==uart else " usbSendMidi(")
f=extract(parser,'midiParser_parseMidiMessage');c+=f[:f.index('\n\tif(msg.bits.sysxbyte)')]+'\n}\n'
for name in ['midiParser_parseUartData','midiParser_setRouting']:c+=extract(parser,name)
c+=r'''
static void byte(unsigned b){uint8_t p[]={15,b,0,0};MidiMsg m;midi_usb_rx_receive(&midiUsbRx,p,4);if(usb_getMidi(&m)){assert(!mask);midiParser_parseMidiMessage(m);}}
static void reset(void){memset(&midiTx,0,sizeof midiTx);midi_usb_tx_reset(&midiUsbTx);memset(&midiUsbRx,0,sizeof midiUsbRx);memset(&dinDecoder,0,sizeof dinDecoder);midiParser_setRouting(0);}
static void own(void){MidiMsg m={0};m.status=0x90;m.data1=60;m.data2=100;m.bits.length=2;uart_sendMidiOwn(m);usb_sendMidiOwn(m);}
int main(void){
 for(unsigned status=0x80;status<0xf8;status++){if(status==0xf7||status==0xf0)continue;
  reset();midiParser_setRouting(1);byte(0xf0);byte(1);assert(midiTx.owner==2);
  /* USB has no U2U route, but the same source-abort contract must release
   * either serializer if that source owns it. Use the real adapter. */
  MidiMsg m={0};m.status=0xf0;m.bits.source=midiSourceUSB;usb_sendMidi(m);
  m.status=1;m.bits.sysxbyte=1;usb_sendMidi(m);
  byte(status);assert(!midiUsbTx.owner&&midiUsbTx.aborted==1);
  assert(midi_usb_tx_stage(&midiUsbTx)==4&&midiUsbTx.stage[0]==7&&midiUsbTx.stage[3]==0xf7);
  assert(!midiTx.owner&&midiTx.aborted==1);own();uint8_t b;unsigned eox=0;while(midi_serial_pop(&midiTx,&b))eox+=b==0xf7;assert(eox==1&&midiTx.rejected==0);
 }
 /* Realtime preserves ownership; a second F0 terminates then starts anew. */
 reset();midiParser_setRouting(1);byte(0xf0);byte(0xf8);assert(midiTx.owner==2&&!midiTx.aborted);
 byte(0xf0);assert(midiTx.owner==2&&midiTx.aborted==1);byte(0xf7);assert(!midiTx.owner);
 /* DIN interruption must also terminate both destinations before a message completes. */
 reset();midiParser_setRouting(5);midiParser_parseUartData(0xf0);midiParser_parseUartData(1);midiParser_parseUartData(0x90);
 assert(!midiTx.owner&&!midiUsbTx.owner&&midiTx.aborted==1&&midiUsbTx.aborted==1);own();assert(!midiTx.rejected&&!midiUsbTx.rejected);
 /* Every route transition: only removed destinations lose their owner. */
 unsigned routes[]={0,1,4,5,8,12};
 for(unsigned from=0;from<6;from++)for(unsigned to=0;to<6;to++)for(unsigned source=1;source<=2;source++){
  reset();midiParser_setRouting(from);
  if(source==1){midiParser_parseUartData(0xf0);midiParser_parseUartData(1);}else{byte(0xf0);byte(1);}
  unsigned din=source==1?4:1,usb=source==1?8:0;
  midiParser_setRouting(to);
  assert(midiTx.owner==((routes[from]&routes[to]&din)?source:0));
  assert(midiUsbTx.owner==((routes[from]&routes[to]&usb)?source:0));
  if(!midiTx.owner&&!midiUsbTx.owner){own();assert(!midiTx.rejected&&!midiUsbTx.rejected);}
  if((routes[from]&din)&&!(routes[to]&din)){uint8_t b;unsigned n=0;while(midi_serial_pop(&midiTx,&b))n+=b==0xf7;assert(n==1);}
  if((routes[from]&usb)&&!(routes[to]&usb)){assert(midi_usb_tx_stage(&midiUsbTx)>=4);assert(midiUsbTx.stage[0]==7&&midiUsbTx.stage[1]==0xf0&&midiUsbTx.stage[2]==1&&midiUsbTx.stage[3]==0xf7);}
 }
 reset();mask=1;midiParser_setRouting(5);assert(mask);mask=0;
 return 0;
}
'''
with tempfile.TemporaryDirectory() as td:
 src=Path(td)/'test.c';src.write_text(c);exe=Path(td)/'test'
 subprocess.run([os.environ.get('CC','cc'),'-std=c11','-g','-fsanitize=address,undefined','-I'+str(root/'tests/shim'),'-I'+str(root/'Core/Inc'),str(src),*[str(root/'Core/Src/Soundengine/MIDI'/n) for n in ['MidiStream.c','MidiUsbRx.c','MidiUsbTx.c']],'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
