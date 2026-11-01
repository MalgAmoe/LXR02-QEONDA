#include "Soundengine/DSPAudio/MainDjFilter.h"
#include <math.h>
#include "Soundengine/DSPAudio/MainCompressor.h"
#ifndef LXR_HOST_TEST
#include "stm32f7xx.h"
#endif

/* Only targets are shared; render owns both independent stereo stages. */
static volatile uint8_t targetHp, targetLp = 127, targetResonance;
typedef struct {
    float s1[2], s2[2];
    float g, goalG, dg, wet;
    unsigned ramp;
    uint8_t lastCutoff;
} FilterStage;
typedef struct {
    FilterStage hp, lp;
    float k, goalK, dk;
    unsigned rampK;
    uint8_t lastResonance, initialized;
} FilterState;
static FilterState state;
_Static_assert(sizeof(FilterState) + 3 <= 128, "DJ filter static budget");

static uint32_t lockTargets(void)
{
#ifdef LXR_HOST_TEST
    return 0; /* Single-threaded harness, not an atomicity simulation. */
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
void MainDjFilter_setTargets(uint8_t hp, uint8_t lp, uint8_t resonance)
{
    if (hp > 127) hp = 127;
    if (lp > 127) lp = 127;
    if (resonance > 127) resonance = 127;
    uint32_t saved = lockTargets();
    targetHp = hp;
    targetLp = lp;
    targetResonance = resonance;
    unlockTargets(saved);
}
void MainDjFilter_reset(void) { MainDjFilter_setTargets(0, 127, 0); }

static void setCutoff(FilterStage *s, uint8_t cutoff, unsigned highpass)
{
    if (state.initialized && cutoff == s->lastCutoff) return;
    /* Bypass uses its adjacent active frequency. No sample-loop transcendentals. */
    float position = highpass ? (cutoff ? cutoff-1 : 0)/126.f
                              : (cutoff < 127 ? cutoff : 126)/126.f;
    float fc = highpass ? 20.f * powf(400.f, position)
                        : 40.f * powf(450.f, position);
    s->goalG = tanf(3.14159265358979323846f * fc / 44140.f);
    if (!state.initialized) s->g = s->goalG;
    s->dg = (s->goalG-s->g)/256.f;
    s->ramp = 256;
    s->lastCutoff = cutoff;
}
static void advance(FilterStage *s, unsigned active)
{
    if (s->ramp) {
        s->g += s->dg;
        if (!--s->ramp) s->g = s->goalG;
    }
    if (active) {
        s->wet += 1.f/256.f;
        if (s->wet > 1.f) s->wet = 1.f;
    } else {
        s->wet -= 1.f/256.f;
        if (s->wet <= 0.f) {
            s->wet = 0.f;
            s->s1[0]=s->s1[1]=s->s2[0]=s->s2[1]=0.f;
        }
    }
}
static void processStage(FilterStage *s, float x[2], unsigned highpass)
{
    if (s->wet == 0.f) return; /* Exact bypass, including independent stages. */
    float a1=1.f/(1.f+s->g*(s->g+state.k));
    float a2=s->g*a1, a3=s->g*a2;
    for (unsigned c=0; c<2; ++c) {
        float v3=x[c]-s->s2[c];
        float v1=a1*s->s1[c]+a2*v3;
        float v2=s->s2[c]+a2*s->s1[c]+a3*v3;
        s->s1[c]=2.f*v1-s->s1[c];
        s->s2[c]=2.f*v2-s->s2[c];
        float filtered=highpass ? x[c]-state.k*v1-v2 : v2;
        x[c] += s->wet*(filtered-x[c]);
    }
}
void MainDjFilter_process(int16_t *buffer, unsigned frames)
{
    unsigned compress=MainCompressor_beginBlock();
    uint32_t saved = lockTargets();
    uint8_t hp=targetHp, lp=targetLp, resonance=targetResonance;
    unlockTargets(saved);
    setCutoff(&state.hp, hp, 1);
    setCutoff(&state.lp, lp, 0);
    if (!state.initialized || resonance != state.lastResonance) {
        float q=0.70710678f+(3.f-0.70710678f)*(resonance/127.f);
        state.goalK=1.f/q;
        if (!state.initialized) state.k=state.goalK;
        state.dk=(state.goalK-state.k)/256.f;
        state.rampK=256;
        state.lastResonance=resonance;
    }
    state.initialized=1;
    for (unsigned i=0; i<frames; ++i) {
        advance(&state.hp, hp != 0);
        advance(&state.lp, lp != 127);
        if (state.rampK) {
            state.k += state.dk;
            if (!--state.rampK) state.k=state.goalK;
        }
        if (state.hp.wet == 0.f && state.lp.wet == 0.f && !compress) continue;
        float x[2]={(float)buffer[2*i], (float)buffer[2*i+1]};
        processStage(&state.hp, x, 1);
        processStage(&state.lp, x, 0);
        if (compress) MainCompressor_processPair(x);
        for (unsigned c=0; c<2; ++c) {
            /* The sole conversion/clamp is after the float HP -> LP chain. */
            if (x[c]>32767.f) x[c]=32767.f;
            if (x[c]< -32768.f) x[c]= -32768.f;
            buffer[2*i+c]=(int16_t)x[c];
        }
    }
}
