#ifndef MAIN_DJ_FILTER_H
#define MAIN_DJ_FILTER_H
#include <stdint.h>
/* Session controls only. reset requests a smoothed return; it never clears live DSP. */
void MainDjFilter_setTargets(uint8_t filter, uint8_t resonance);
void MainDjFilter_reset(void);
void MainDjFilter_process(int16_t *interleaved, unsigned frames);
#endif
