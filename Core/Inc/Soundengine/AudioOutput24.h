#ifndef AUDIO_OUTPUT24_H
#define AUDIO_OUTPUT24_H
#include <stdint.h>
/* Input is normalized (original signed16 / 32768). Truncate toward zero, like the
 * original output conversion. Explicit signed24 bounds precede conversion.
 * Mix-site musical bounds are separate; main output DSP may exceed those
 * bounds before this final signed24 clamp. */
static inline void audio_output24_store(int16_t *dst, float sample)
{
    float scaled = sample * 8388608.f;
    if (scaled > 8388607.f) scaled = 8388607.f;
    if (scaled < -8388608.f) scaled = -8388608.f;
    uint32_t bits = (uint32_t)(int32_t)scaled;
    dst[0] = (int16_t)(bits >> 8);
    dst[1] = (int16_t)((bits & 255u) << 8);
}
#endif
