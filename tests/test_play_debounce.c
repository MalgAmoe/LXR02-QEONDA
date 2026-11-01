#include "IO/DIO.h"
#include "buttonHandler.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
GPIO_TypeDef lxr_test_gpio_b;
static uint32_t now;
static uint8_t raw[NUM_INPUTS/8];
static unsigned pressed[NUM_INPUTS+1], released[NUM_INPUTS+1];
static SPI_HandleTypeDef spi;
extern uint8_t din_inputData_old[NUM_INPUTS/8];
uint32_t HAL_GetTick(void) { return now; }
HAL_StatusTypeDef HAL_SPI_Receive(SPI_HandleTypeDef *s,uint8_t *p,uint16_t n,uint32_t t)
{ (void)s;(void)t;memcpy(p,raw,n);return HAL_OK; }
HAL_StatusTypeDef HAL_SPI_Transmit(SPI_HandleTypeDef *s,uint8_t *p,uint16_t n,uint32_t t)
{ (void)s;(void)p;(void)n;(void)t;return HAL_OK; }
void buttonHandler_buttonPressed(uint8_t b) { pressed[b]++; }
void buttonHandler_buttonReleased(uint8_t b) { released[b]++; }
static uint8_t testedButton = BUT_START_STOP;
static void sample(uint32_t t,int play)
{
 now=t;
 if(testedButton==BUT_PAGE_DOWN) {
  if(play) SW_43_GPIO_Port->IDR |= SW_43_Pin;
  else SW_43_GPIO_Port->IDR &= ~SW_43_Pin;
 } else if(play) raw[testedButton/8] |= 1u << (testedButton%8);
 else raw[testedButton/8] &= ~(1u << (testedButton%8));
 dio_process();
}
static void reset(void)
{
 memset(raw,0,sizeof raw);memset(din_inputData_old,0,sizeof raw);
 memset(pressed,0,sizeof pressed);memset(released,0,sizeof released);
 now=0;SW_43_GPIO_Port->IDR=0;dio_init(&spi);
}
int main(void)
{
 const uint8_t buttons[] = { BUT_START_STOP, BUT_PAGE_UP, BUT_PAGE_DOWN };
 for(unsigned k=0;k<3;k++) {
 testedButton=buttons[k];
 reset();sample(0,1);assert(pressed[testedButton]==1); /* no first-press delay */
 sample(1,0);sample(2,1);sample(4,0);sample(8,1);
 assert(pressed[testedButton]==1 && released[testedButton]==0);
 sample(1000,1);assert(pressed[testedButton]==1); /* hold */
 sample(1001,0);sample(1020,0);assert(released[testedButton]==0);
 sample(1021,0);assert(released[testedButton]==1);
 sample(1022,1);assert(pressed[testedButton]==2); /* deliberate new press */
 /* Other buttons retain raw-edge semantics, including Shift. */
 raw[BUT_REC/8] |= 1u << (BUT_REC%8);sample(1023,1);
 raw[BUT_REC/8] &= ~(1u << (BUT_REC%8));sample(1024,1);
 raw[BUT_REC/8] |= 1u << (BUT_REC%8);sample(1025,1);
 assert(pressed[BUT_REC]==2 && released[BUT_REC]==1);
 reset();raw[BUT_SHIFT/8] |= 1u << (BUT_SHIFT%8);sample(0,1);
 assert(pressed[BUT_SHIFT]==1 && pressed[testedButton]==1);
 sample(1,0);sample(2,1);assert(pressed[testedButton]==1);
 reset();sample(UINT32_MAX-12,1);sample(UINT32_MAX-10,0);
 sample(8,0);assert(released[testedButton]==0);
 sample(9,0);assert(released[testedButton]==1);
 sample(10,1);assert(pressed[testedButton]==2);
 }
 /* A bouncing UP must not suppress a DOWN or Play press. */
 testedButton=BUT_PAGE_UP;reset();sample(0,1);sample(1,0);
 SW_43_GPIO_Port->IDR |= SW_43_Pin;
 raw[BUT_START_STOP/8] |= 1u << (BUT_START_STOP%8);
 sample(2,1);
 assert(pressed[BUT_PAGE_UP]==1 && pressed[BUT_PAGE_DOWN]==1 && pressed[BUT_START_STOP]==1);
 puts("Play debounce: immediate press, bounce, hold, release boundary, repeat, other buttons, Shift and tick wrap passed.");
}
