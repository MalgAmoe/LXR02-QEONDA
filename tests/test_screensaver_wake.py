#!/usr/bin/env python3
"""Actual screensaver/LCD/menu bodies with deterministic host time and GPIO seams."""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def fun(source, name):
    # Strip comments before counting braces; do not copy production implementations.
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    match = re.search(r'^(?:uint8_t|void) ' + name + r'\([^;]*?\)\s*\{', source, re.M)
    assert match, name
    end = source.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]

lcd = (ROOT / 'Core/Src/lcd.c').read_text()
menu = (ROOT / 'Core/Src/menu/menu.c').read_text()
screen = (ROOT / 'Core/Src/menu/screensaver.c').read_text()
screen = re.sub(r'^#include.*$', '', screen, flags=re.M)

PRE = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdlib.h>
static uint64_t us; static unsigned audio,repaints; static uint64_t deadline;
typedef union { uint32_t itg; } Framebuffer;
typedef struct { uint32_t ODR,BSRR; } GPIO;
static GPIO pins;
#define LCD_RS_GPIO_Port (&pins)
#define LCD_E_GPIO_Port (&pins)
#define LCD_D4_GPIO_Port (&pins)
#define LCD_RS_Pin 1
#define LCD_E_Pin 2
#define LCD_D4_Pin 128
#define USE_BSRR 0
static uint8_t lcd_command_state,lcd_data_state,lcd_clear_state;
static uint8_t display_refresh_state,display_needs_refresh,display_needs_clear_all;
static char currentDisplayBuffer[2][16],editDisplayBuffer[2][17];
static uint8_t refresh_i,refresh_j,visibleCursor;
static uint8_t activeParameters[1];
#define PAR_SCREENSAVER_ON_OFF 0
static uint32_t HAL_GetTick(void){return (uint32_t)(us/1000);}
static void DWT_init_nonblock(uint32_t n){deadline=us+n;}
static uint8_t DWT_check_nonblock(void){return us>=deadline;}
static void soundengine_process(void){audio++;us+=9;assert(audio<1000000);}
uint8_t screensaver_process(void);
uint8_t sendDisplayBuffer(void);
void menu_repaintAll(void);
'''
UI = r'''
#define PATTERN_SAVE_PAGE_OK 91
#define KIT_SAVE_PAGE_OK 92
#define SELECT_MODE_VOICE 0
static int menu_activePage,systick_ticks,sucessTimer;
static void buttonHandler_setMode(int x){(void)x;}
static void led_clearAllBlinkLeds(void){}
static void led_setMode2(int x){(void)x;}
static int menu_getActiveVoice(void){return 0;}
static void menu_switchPage(int x){(void)x;}
static int menu_getSubPage(void){return 0;}
static void led_setActiveSelectButton(int x){(void)x;}
static void menu_resetActiveParameter(void){}
static void menu_repaint(void){repaints++;}
'''

# Use production LCD timing/command constants; GPIO addresses remain host substitutes.
header = (ROOT / 'Core/Inc/lcd.h').read_text()
names = ('ENABLE_US', 'WRITEDATA_US', 'COMMAND_US', 'CLEAR_DISPLAY_MS',
         'CLEAR_DISPLAY', 'SET_DDADR', 'DDADR_LINE1', 'DDADR_LINE2',
         'DDADR_LINE3', 'DDADR_LINE4', 'SET_DISPLAY', 'DISPLAY_ON',
         'CURSOR_ON', 'BLINKING_OFF')
constants = '\n'.join(re.search(r'^#define LCD_' + name + r'\s+[^\n]+',
                                 header, re.M).group() for name in names)
code = PRE + constants + '\n'
code += '\n'.join(fun(lcd, name) for name in (
    'lcd_data_nonBlock', 'lcd_command_nonblock', 'lcd_clear_nonblock',
    'lcd_setcursor_nonBlock', 'lcd_turnOn_nonblock'))
# Simulated elapsed time per sender poll also lets its existing busy flush progress.
code += fun(menu, 'sendDisplayBuffer').replace('{', '{ us++;', 1)
code += fun(menu, 'menu_repaintAll') + screen + UI + fun(menu, 'menu_uiTick')
code += (Path(__file__).with_suffix('.c')).read_text()
with tempfile.TemporaryDirectory(prefix='qeonda-wake-') as directory:
    source = Path(directory) / 'wake.c'
    binary = Path(directory) / 'wake'
    source.write_text(code)
    subprocess.run([os.environ.get('CC', 'clang'), '-std=c11', '-O0',
                    '-Wall', '-Wextra', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=20)
