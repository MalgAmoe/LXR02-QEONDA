#ifndef LXR_AUDIO_SAMPLE_H
#define LXR_AUDIO_SAMPLE_H
#include <stdint.h>
/* Audio units remain signed16 full scale; only storage/arithmetic change.
 * Tables, phase words and parameter widths are deliberately not audio samples. */
#if LXR_AUDIO_FLOAT32
typedef float AudioSample;
typedef float AudioReal;
static inline float audio_sample_bound(float x)
{
    return x > 32767.f ? 32767.f : x < -32768.f ? -32768.f : x;
}
/* Comparison only: equivalent to signed16 saturation, without quantization.
 * Call only at baseline saturating operations; not wrapping assignments. */
static inline float audio_mix_bound(float x)
{
#if LXR_FLOAT_MIX_CLIP
    return audio_sample_bound(x);
#else
    return x;
#endif
}
static inline float audio_mix_add(float a, float b)
{
    return audio_mix_bound(a + b);
}
#else
typedef int16_t AudioSample;
typedef double AudioReal;
#endif
#endif
