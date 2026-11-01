#ifndef MAIN_DJ_FILTER_H
#define MAIN_DJ_FILTER_H
#include <stdint.h>
/* Session controls only. Reset smooths to HP bypass, LP bypass, minimum Q. */
void MainDjFilter_setTargets(uint8_t hp, uint8_t lp, uint8_t resonance);
void MainDjFilter_reset(void);
/* St1 master float chain: HP -> LP -> compressor -> sole int16 conversion. */
void MainDjFilter_process(int16_t *interleaved, unsigned frames);
#endif
