#ifndef LXR_AUDIO_SAMPLE_H
#define LXR_AUDIO_SAMPLE_H
#include <stdint.h>
/* Audio units remain signed16 full scale; only storage/arithmetic change.
 * Tables, phase words and parameter widths are deliberately not audio samples. */
typedef float AudioSample;
typedef float AudioReal;
static inline float audio_sample_bound(float x)
{
    return x > 32767.f ? 32767.f : x < -32768.f ? -32768.f : x;
}
/* Per-operation mixing saturation, without quantization.
 * Call only at baseline saturating operations; not wrapping assignments. */
static inline float audio_mix_bound(float x)
{
    return audio_sample_bound(x);
}
static inline float audio_mix_add(float a, float b)
{
    return audio_mix_bound(a + b);
}
#endif
