#ifndef AUDIO_OUTPUT24_H
#define AUDIO_OUTPUT24_H
#include <stdint.h>
/* Input units remain signed16 full scale. Truncate toward zero, like the
 * original output conversion. Explicit signed24 bounds precede conversion.
 * Caller retains the musical +32767/-32768 saturation before this encoder. */
static inline void audio_output24_store(int16_t *dst, float sample)
{
    float scaled = sample * 256.f;
    if (scaled > 8388607.f) scaled = 8388607.f;
    if (scaled < -8388608.f) scaled = -8388608.f;
    uint32_t bits = (uint32_t)(int32_t)scaled;
    dst[0] = (int16_t)(bits >> 8);
    dst[1] = (int16_t)((bits & 255u) << 8);
}
#endif
