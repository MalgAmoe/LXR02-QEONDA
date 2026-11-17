#ifndef MAIN_DJ_FILTER_H
#define MAIN_DJ_FILTER_H
#include <stdint.h>
/* Session controls only. Reset smooths to HP bypass, LP bypass, minimum Q. */

#include "Soundengine/AudioSample.h"
void MainDjFilter_setTargets(uint8_t hp, uint8_t lp, uint8_t resonance);
void MainDjFilter_reset(void);
/* St1 master float chain: HP -> LP -> compressor -> 24-bit output encoding. */
/* Float32 samples in; MS halfword first, no intermediate quantization. */
void MainDjFilter_process24(const AudioSample *interleaved, int16_t *packed, unsigned frames);
#endif
