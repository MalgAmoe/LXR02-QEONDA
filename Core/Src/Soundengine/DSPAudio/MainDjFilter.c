#include "Soundengine/DSPAudio/MainDjFilter.h"
#include <math.h>
#ifndef LXR_HOST_TEST
#include "stm32f7xx.h"
#endif

/* Only targets are shared. All remaining state belongs exclusively to render. */
static volatile uint8_t targetFilter = 63, targetResonance;
typedef struct {
    float s1[2], s2[2];
    float g, k, dg, dk, goalG, goalK, wet;
    unsigned ramp;
    uint8_t mode, lastFilter, lastResonance, initialized;
} FilterState;
static FilterState state;
_Static_assert(sizeof(FilterState) + 2 <= 128, "DJ filter static budget");

static uint32_t lockTargets(void)
{
#ifdef LXR_HOST_TEST
    return 0; /* Single-threaded host harness; not an atomicity simulation. */
#else
    uint32_t saved = __get_PRIMASK();
    __disable_irq();
    return saved;
#endif
}
static void unlockTargets(uint32_t saved)
{
#ifdef LXR_HOST_TEST
    (void)saved;
#else
    __set_PRIMASK(saved);
#endif
}
void MainDjFilter_setTargets(uint8_t filter, uint8_t resonance)
{
    if (filter > 126) filter = 126;
    if (resonance > 127) resonance = 127;
    uint32_t saved = lockTargets();
    targetFilter = filter;
    targetResonance = resonance;
    unlockTargets(saved);
}
void MainDjFilter_reset(void) { MainDjFilter_setTargets(63, 0); }

void MainDjFilter_process(int16_t *buffer, unsigned frames)
{
    uint32_t saved = lockTargets();
    uint8_t filter = targetFilter, resonance = targetResonance;
    unlockTargets(saved);
    uint8_t wanted = filter < 63 ? 1 : filter > 63 ? 2 : 0;
    if (!state.initialized || filter != state.lastFilter || resonance != state.lastResonance) {
        /* Log-frequency mapping only on target changes, never in the sample loop. */
        float distance = filter < 63 ? (63-filter)/63.f : (filter-63)/63.f;
        float fc = wanted == 1 ? 18000.f * powf(40.f/18000.f, distance)
                               : 20.f * powf(8000.f/20.f, distance);
        state.goalG = tanf(3.14159265358979323846f * fc / 44140.f);
        state.goalK = 1.41421356237f + (0.5f-1.41421356237f)*(resonance/127.f);
        state.dg = (state.goalG-state.g)/256.f;
        state.dk = (state.goalK-state.k)/256.f;
        state.ramp = 256;
        state.lastFilter = filter;
        state.lastResonance = resonance;
        state.initialized = 1;
    }
    for (unsigned i=0; i<frames; ++i) {
        /* Never change response while audible. A reversal cancels the fade-out. */
        if (state.wet == 0.f && state.mode != wanted) {
            state.mode = wanted;
            state.g = state.goalG;
            state.k = state.goalK;
            state.ramp = 0;
            for (unsigned c=0; c<2; ++c) {
                state.s1[c] = 0.f;
                state.s2[c] = (float)buffer[2*i+c];
            }
        }
        if (!wanted && state.wet == 0.f) continue; /* exact int16 bypass */
        if (state.ramp) {
            state.g += state.dg;
            state.k += state.dk;
            if (!--state.ramp) { state.g=state.goalG; state.k=state.goalK; }
        }
        if (wanted == state.mode && wanted) {
            state.wet += 1.f/256.f;
            if (state.wet > 1.f) state.wet = 1.f;
        } else {
            state.wet -= 1.f/256.f;
            if (state.wet <= 0.f) {
                state.wet = 0.f;
                state.s1[0]=state.s1[1]=state.s2[0]=state.s2[1]=0.f;
                continue;
            }
        }
        float a1=1.f/(1.f+state.g*(state.g+state.k));
        float a2=state.g*a1, a3=state.g*a2;
        for (unsigned c=0; c<2; ++c) {
            float x=(float)buffer[2*i+c];
            float v3=x-state.s2[c];
            float v1=a1*state.s1[c]+a2*v3;
            float v2=state.s2[c]+a2*state.s1[c]+a3*v3;
            state.s1[c]=2.f*v1-state.s1[c];
            state.s2[c]=2.f*v2-state.s2[c];
            float filtered=state.mode==1 ? v2 : x-state.k*v1-v2;
            float y=x+state.wet*(filtered-x);
            if (y>32767.f) y=32767.f;
            if (y< -32768.f) y= -32768.f;
            buffer[2*i+c]=(int16_t)y;
        }
    }
}
